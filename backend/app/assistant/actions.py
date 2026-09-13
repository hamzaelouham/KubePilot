from datetime import datetime, timedelta, timezone

from sqlalchemy import update
from starlette.concurrency import run_in_threadpool

from app.assistant.api_adapter import call_api, segment
from app.assistant.observations import active_cluster
from app.assistant.sanitize import sanitize
from app.assistant.schemas import Decision, Proposal
from app.core.audit import record_audit
from app.core.rbac import Permission, has_permission
from app.kubernetes.resource_management import ResourceManagementError, ensure_unprotected, management_client, resource_kind
from app.models.entities import AssistantProposal

PERMISSIONS = {"scale": Permission.RESOURCES_UPDATE, "restart": Permission.RESOURCES_UPDATE, "delete": Permission.RESOURCES_DELETE, "install": Permission.MARKETPLACE_INSTALL, "upgrade": Permission.MARKETPLACE_RELEASE, "rollback": Permission.MARKETPLACE_RELEASE, "uninstall": Permission.MARKETPLACE_RELEASE}


def authorize(actor, body):
    if actor.restricted or not has_permission(actor.role, PERMISSIONS[body.action]):
        raise ResourceManagementError(403, "insufficient_permissions", "Your current role cannot perform this action")


def object_precondition(cluster, body):
    with management_client(cluster) as client:
        item = client.read(resource_kind(body.resource_type), body.namespace, body.name)
        return {"uid": item.metadata.uid, "resource_version": item.metadata.resource_version}


async def snapshot(request, cluster, body):
    if body.action in {"scale", "restart", "delete"}:
        return await run_in_threadpool(object_precondition, cluster, body)
    if body.action in {"upgrade", "rollback", "uninstall"}:
        history = await call_api(request, f"/cluster/helm/releases/{segment(body.name)}/history", params={"cluster": body.cluster, "namespace": body.namespace})
        return {"revision": max((item["revision"] for item in history["revisions"]), default=0)}
    return {}


def summary(proposal):
    expiry = proposal.expires_at
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)
    return {"proposal_id": str(proposal.id), "arguments": proposal.arguments, "status": proposal.status, "expires_at": expiry.isoformat(), "precondition": proposal.precondition, "result": proposal.result}


async def propose(request, database, settings, actor, body: Proposal):
    authorize(actor, body)
    cluster = active_cluster(database, body.cluster)
    ensure_unprotected(resource_kind("deployments"), body.namespace, body.name, settings.host_namespace, deleting=True)
    precondition = await snapshot(request, cluster, body)
    proposal = AssistantProposal(actor_id=actor.user_id, session_id=actor.session_id, cluster_id=cluster.id, arguments=body.model_dump(exclude_none=True), precondition=precondition, status="pending", expires_at=datetime.now(timezone.utc) + timedelta(minutes=10))
    database.add(proposal)
    database.flush()
    record_audit(database, "assistant.proposed", actor.user_id, "assistant_proposal", str(proposal.id), result="pending", context={"action": body.action, "cluster": body.cluster, "namespace": body.namespace, "name": body.name})
    database.commit()
    return summary(proposal)


def deployment_change(cluster, body, expected):
    with management_client(cluster) as client:
        # Kubernetes checks resourceVersion atomically when applying the merge patch.
        patch = {"metadata": {"uid": expected["uid"], "resourceVersion": expected["resource_version"]}}
        patch["spec"] = {"replicas": body.replicas} if body.action == "scale" else {"template": {"metadata": {"annotations": {"kubectl.kubernetes.io/restartedAt": datetime.now(timezone.utc).isoformat()}}}}
        client.patch_deployment(body.namespace, body.name, patch)
    return {"status": "requested", "action": body.action, "name": body.name, "namespace": body.namespace, "cluster": body.cluster}


async def execute(request, cluster, body, expected):
    scope = {"cluster": body.cluster, "namespace": body.namespace}
    if body.action in {"scale", "restart"}:
        return await run_in_threadpool(deployment_change, cluster, body, expected)
    if body.action == "delete":
        return await call_api(request, f"/cluster/manage-resources/{body.resource_type}/{segment(body.name)}", method="DELETE", params=scope, body={"uid": expected["uid"], "confirm_name": body.name})
    if body.action == "install":
        return await call_api(request, "/marketplace/install", method="POST", body={"cluster": body.cluster, "namespace": body.namespace, "release_name": body.name, **{key: getattr(body, key) for key in ("package_id", "package_name", "repository_name", "version")}})
    payload = {"confirm_name": body.name}
    if body.action == "upgrade":
        payload.update({key: getattr(body, key) for key in ("repository_id", "chart_name", "version")})
    return await call_api(request, f"/cluster/helm/releases/{segment(body.name)}/{body.action}", method="POST", params=scope, body=payload)


async def decide(request, database, settings, actor, proposal_id, decision: Decision):
    proposal = database.get(AssistantProposal, proposal_id)
    if proposal is None or proposal.actor_id != actor.user_id or proposal.session_id != actor.session_id:
        raise ResourceManagementError(404, "proposal_not_found", "Proposal not found for this session")
    body = Proposal.model_validate(proposal.arguments)
    authorize(actor, body)
    if decision.cluster != body.cluster or decision.confirm_name != body.name:
        raise ResourceManagementError(409, "confirmation_mismatch", "Review and confirm the exact target in the original cluster")
    cluster = active_cluster(database, body.cluster)
    if cluster.id != proposal.cluster_id:
        raise ResourceManagementError(409, "cluster_replaced", "The cluster registration changed; request a new proposal")
    ensure_unprotected(resource_kind("deployments"), body.namespace, body.name, settings.host_namespace, deleting=True)
    now = datetime.now(timezone.utc)
    target_status = "executing" if decision.approved else "denied"
    claimed = database.execute(update(AssistantProposal).where(AssistantProposal.id == proposal_id, AssistantProposal.status == "pending", AssistantProposal.expires_at > now).values(status=target_status).execution_options(synchronize_session=False)).rowcount
    if claimed != 1:
        database.rollback()
        raise ResourceManagementError(409, "proposal_consumed_or_expired", "This proposal expired or was already decided. Do not retry an operation with an unknown result.")
    record_audit(database, "assistant.decision", actor.user_id, "assistant_proposal", str(proposal_id), result=target_status)
    database.commit()  # Durable claim BEFORE external effects; failure here sends no mutation.
    if not decision.approved:
        database.refresh(proposal)
        return summary(proposal)
    try:
        if await snapshot(request, cluster, body) != proposal.precondition:
            raise ResourceManagementError(409, "stale_target", "The resource or Helm revision changed. Inspect it and request a new proposal.")
        result = sanitize(await execute(request, cluster, body, proposal.precondition))
        # Dispatch/queue acknowledgement is not proof that a workload converged.
        proposal.status = "submitted"
        proposal.result = result
    except ResourceManagementError as error:
        proposal.status = "unknown" if error.code == "operation_outcome_unknown" or error.status >= 500 else "failed"
        proposal.result = sanitize({"code": error.code, "message": error.message})
    except Exception:
        proposal.status = "unknown"
        proposal.result = {"code": "operation_outcome_unknown", "message": "The result could not be confirmed. Inspect the target and job history before proposing another action."}
    record_audit(database, "assistant.result", actor.user_id, "assistant_proposal", str(proposal_id), result=proposal.status)
    database.commit()
    return summary(proposal)
