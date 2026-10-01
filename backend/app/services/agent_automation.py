"""Scheduling, guarded agent runs, and retention for shared agent automation."""

from __future__ import annotations

import asyncio
import json
import re
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.assistant.sanitize import diagnostic_projection, safe_text, sanitize
from app.core.audit import AuditEvent, record_audit
from app.core.config import Settings
from app.core.rbac import Permission, has_permission
from app.kubernetes.resource_management import RESOURCE_KINDS, ResourceManagementError, management_client
from app.models.entities import (
    AIAgent,
    AIAgentAutomationTrigger,
    AIAgentNotificationDestination,
    AIAgentRun,
    AIModelConfig,
    ApplicationSetting,
    ClusterConnection,
    Event,
    UserAccount,
)
from app.services.ai_runtime import AIRuntimeError, open_chat_stream, resolve_runtime_model
from app.services.agents import fail, get_agent


RETENTION_SETTING_KEY = "assistant.agent_run_retention_days"
DEFAULT_RETENTION_DAYS = 30
MIN_RETENTION_DAYS = 1
MAX_RETENTION_DAYS = 365
MAX_LOG_OUTPUT = 32_000
MAX_SNAPSHOT_OUTPUT = 48_000
CRON_FIELD_RANGES = ((0, 59), (0, 23), (1, 31), (1, 12), (0, 7))


class AgentAutomationError(RuntimeError):
    status_code = 422
    code = "agent_automation_error"

    def __init__(self, message: str, *, status_code: int | None = None, code: str | None = None):
        super().__init__(message)
        if status_code is not None:
            self.status_code = status_code
        if code is not None:
            self.code = code


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _clean_log(value: str) -> str:
    return safe_text(value, MAX_LOG_OUTPUT)


def _parse_cron_field(value: str, minimum: int, maximum: int, *, day_of_week: bool = False) -> tuple[set[int], bool]:
    if not value:
        raise AgentAutomationError("Cron fields must not be empty", code="invalid_cron")
    values: set[int] = set()
    unrestricted = value == "*"
    for token in value.split(","):
        if not token:
            raise AgentAutomationError("Cron fields contain an empty item", code="invalid_cron")
        base, separator, raw_step = token.partition("/")
        if separator:
            if not raw_step.isdigit() or int(raw_step) < 1:
                raise AgentAutomationError("Cron steps must be positive integers", code="invalid_cron")
            step = int(raw_step)
        else:
            step = 1
        if base == "*":
            start, end = minimum, maximum
        elif "-" in base:
            pieces = base.split("-")
            if len(pieces) != 2 or not all(piece.isdigit() for piece in pieces):
                raise AgentAutomationError("Cron ranges are invalid", code="invalid_cron")
            start, end = (int(piece) for piece in pieces)
        elif base.isdigit() and not separator:
            start = end = int(base)
        else:
            raise AgentAutomationError("Cron supports numbers, ranges, lists, and steps only", code="invalid_cron")
        if start < minimum or end > maximum or start > end:
            raise AgentAutomationError("Cron values are outside their allowed range", code="invalid_cron")
        values.update(range(start, end + 1, step))
    if day_of_week and 7 in values:
        values.add(0)
        values.discard(7)
    return values, unrestricted


def parse_cron(expression: str) -> tuple[tuple[set[int], bool], ...]:
    fields = expression.strip().split()
    if len(fields) != 5:
        raise AgentAutomationError("Use a simple five-field cron expression: minute hour day-of-month month day-of-week", code="invalid_cron")
    return tuple(
        _parse_cron_field(value, *bounds, day_of_week=index == 4)
        for index, (value, bounds) in enumerate(zip(fields, CRON_FIELD_RANGES))
    )


def validate_schedule(cron_expression: str | None, timezone_name: str) -> None:
    if not cron_expression:
        raise AgentAutomationError("A cron expression is required for scheduled triggers", code="invalid_cron")
    parse_cron(cron_expression)
    try:
        ZoneInfo(timezone_name)
    except (ZoneInfoNotFoundError, ValueError):
        raise AgentAutomationError("Choose a valid IANA timezone", code="invalid_timezone") from None


def cron_matches(moment: datetime, expression: str) -> bool:
    (minute, _), (hour, _), (day, day_unrestricted), (month, _), (weekday, weekday_unrestricted) = parse_cron(expression)
    if moment.minute not in minute or moment.hour not in hour or moment.month not in month:
        return False
    day_matches = moment.day in day
    cron_weekday = (moment.weekday() + 1) % 7
    weekday_matches = cron_weekday in weekday
    if not day_unrestricted and not weekday_unrestricted:
        return day_matches or weekday_matches
    return day_matches and weekday_matches


def _trigger_summary(row: AIAgentAutomationTrigger) -> dict[str, Any]:
    return {
        "id": row.id,
        "trigger_type": row.trigger_type,
        "cluster_id": row.cluster_id,
        "namespace": row.namespace,
        "cron_expression": row.cron_expression,
        "timezone": row.timezone,
        "event_kind": row.event_kind,
        "event_name": row.event_name,
        "event_type": row.event_type,
        "event_reason": row.event_reason,
        "owner_id": row.owner_id,
        "notification_destination_ids": row.notification_destination_ids or [],
        "enabled": row.enabled,
        "last_evaluated_at": row.last_evaluated_at,
        "created_by_id": row.created_by_id,
        "updated_by_id": row.updated_by_id,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


def _run_summary(row: AIAgentRun) -> dict[str, Any]:
    return {field: getattr(row, field) for field in (
        "id", "trigger_id", "agent_id", "owner_id", "cluster_id", "namespace", "trigger_type",
        "scheduled_for", "event_id", "status", "attempt_count", "result_code", "error_message",
        "created_at", "started_at", "completed_at",
    )}


def _get_trigger(database: Session, agent_id: UUID, trigger_id: UUID) -> AIAgentAutomationTrigger:
    row = database.get(AIAgentAutomationTrigger, trigger_id)
    if row is None or row.agent_id != agent_id:
        fail(404, "agent_automation_not_found", "This automation trigger no longer exists.")
    return row


def _validate_owner(database: Session, owner_id: UUID) -> UserAccount:
    owner = database.get(UserAccount, owner_id)
    if owner is None:
        raise AgentAutomationError("Choose an existing designated owner", code="owner_not_found", status_code=422)
    if not owner.is_active:
        raise AgentAutomationError("The designated owner must be active", code="owner_inactive", status_code=422)
    if not has_permission(owner.role, Permission.RESOURCES_READ):
        raise AgentAutomationError("The designated owner needs resource read permission", code="owner_permission_denied", status_code=422)
    return owner


def _validate_trigger(database: Session, agent_id: UUID, body) -> tuple[AIAgent, ClusterConnection, UserAccount, list[AIAgentNotificationDestination]]:
    agent = get_agent(database, agent_id)
    cluster = database.get(ClusterConnection, body.cluster_id)
    if cluster is None or cluster.status == "inactive":
        raise AgentAutomationError("Choose an active cluster", code="cluster_not_found", status_code=404)
    owner = _validate_owner(database, body.owner_id)
    if body.trigger_type == "schedule":
        validate_schedule(body.cron_expression, body.timezone)
    elif body.trigger_type != "kubernetes_event":
        raise AgentAutomationError("Unsupported automation trigger", code="invalid_trigger_type")
    if body.namespace and not re.fullmatch(r"[a-z0-9]([-a-z0-9]*[a-z0-9])?", body.namespace):
        raise AgentAutomationError("Choose a valid Kubernetes namespace", code="invalid_namespace")
    destination_ids = list(body.notification_destination_ids)
    destinations = []
    if destination_ids:
        destinations = list(database.scalars(
            select(AIAgentNotificationDestination).where(
                AIAgentNotificationDestination.agent_id == agent_id,
                AIAgentNotificationDestination.id.in_(destination_ids),
            )
        ))
        if len(destinations) != len(destination_ids):
            raise AgentAutomationError("Select notification destinations configured for this agent", code="destination_not_found")
        if body.enabled and any(not destination.enabled for destination in destinations):
            raise AgentAutomationError("Enable every notification destination before enabling this trigger", code="destination_disabled", status_code=409)
    if body.enabled and not agent.enabled:
        raise AgentAutomationError("Enable the agent before enabling an automation trigger", code="agent_disabled", status_code=409)
    if body.enabled and not destinations:
        raise AgentAutomationError("Select at least one notification destination before enabling this trigger", code="destination_required")
    return agent, cluster, owner, destinations


def list_triggers(database: Session, agent_id: UUID) -> list[dict[str, Any]]:
    get_agent(database, agent_id)
    rows = database.scalars(
        select(AIAgentAutomationTrigger)
        .where(AIAgentAutomationTrigger.agent_id == agent_id)
        .order_by(AIAgentAutomationTrigger.created_at.desc(), AIAgentAutomationTrigger.id.desc())
    ).all()
    return [_trigger_summary(row) for row in rows]


def save_trigger(database: Session, actor_id: UUID, agent_id: UUID, body, trigger_id: UUID | None = None) -> dict[str, Any]:
    _, _, _, _ = _validate_trigger(database, agent_id, body)
    row = _get_trigger(database, agent_id, trigger_id) if trigger_id else None
    if row is None:
        row = AIAgentAutomationTrigger(agent_id=agent_id, created_by_id=actor_id)
        database.add(row)
        action = AuditEvent.AGENT_AUTOMATION_CREATED
    else:
        action = AuditEvent.AGENT_AUTOMATION_UPDATED
    row.trigger_type = body.trigger_type
    row.cluster_id = body.cluster_id
    row.namespace = body.namespace
    row.cron_expression = body.cron_expression if body.trigger_type == "schedule" else None
    row.timezone = body.timezone if body.trigger_type == "schedule" else "UTC"
    row.event_kind = body.event_kind if body.trigger_type == "kubernetes_event" else None
    row.event_name = body.event_name if body.trigger_type == "kubernetes_event" else None
    row.event_type = body.event_type if body.trigger_type == "kubernetes_event" else None
    row.event_reason = body.event_reason if body.trigger_type == "kubernetes_event" else None
    row.owner_id = body.owner_id
    row.enabled = body.enabled
    row.notification_destination_ids = [str(identity) for identity in body.notification_destination_ids]
    row.updated_by_id = actor_id
    row.updated_at = _utc_now()
    try:
        database.flush()
        record_audit(database, action, actor_id, "ai_agent_automation_trigger", str(row.id), result="succeeded", context={"agent_id": str(agent_id), "trigger_type": row.trigger_type, "enabled": row.enabled})
        database.commit()
        database.refresh(row)
    except IntegrityError:
        database.rollback()
        raise AgentAutomationError("This automation trigger could not be saved", code="automation_conflict", status_code=409) from None
    return _trigger_summary(row)


def delete_trigger(database: Session, actor_id: UUID, agent_id: UUID, trigger_id: UUID) -> dict[str, UUID]:
    row = _get_trigger(database, agent_id, trigger_id)
    database.delete(row)
    record_audit(database, AuditEvent.AGENT_AUTOMATION_DELETED, actor_id, "ai_agent_automation_trigger", str(trigger_id), result="succeeded", context={"agent_id": str(agent_id)})
    database.commit()
    return {"id": trigger_id}


def retention_days(database: Session) -> int:
    setting = database.scalar(select(ApplicationSetting).where(ApplicationSetting.key == RETENTION_SETTING_KEY))
    value = setting.value_json if setting is not None else DEFAULT_RETENTION_DAYS
    if isinstance(value, int) and not isinstance(value, bool) and MIN_RETENTION_DAYS <= value <= MAX_RETENTION_DAYS:
        return value
    return DEFAULT_RETENTION_DAYS


def save_retention(database: Session, actor_id: UUID, value: int) -> dict[str, int]:
    if isinstance(value, bool) or not isinstance(value, int) or not MIN_RETENTION_DAYS <= value <= MAX_RETENTION_DAYS:
        raise AgentAutomationError("Retention must be between 1 and 365 days", code="invalid_retention", status_code=422)
    row = database.scalar(select(ApplicationSetting).where(ApplicationSetting.key == RETENTION_SETTING_KEY))
    if row is None:
        row = ApplicationSetting(key=RETENTION_SETTING_KEY, value_json=value, created_by_id=actor_id, updated_by_id=actor_id)
        database.add(row)
    else:
        row.value_json = value
        row.updated_by_id = actor_id
        row.updated_at = _utc_now()
    record_audit(database, AuditEvent.AGENT_AUTOMATION_RETENTION_UPDATED, actor_id, "application_setting", RETENTION_SETTING_KEY, result="succeeded", context={"retention_days": value})
    database.commit()
    return {"retention_days": value}


def list_runs(database: Session, agent_id: UUID, *, limit: int = 100, offset: int = 0) -> tuple[list[dict[str, Any]], int]:
    get_agent(database, agent_id)
    count = database.scalar(select(func.count()).select_from(AIAgentRun).where(AIAgentRun.agent_id == agent_id)) or 0
    rows = database.scalars(
        select(AIAgentRun).where(AIAgentRun.agent_id == agent_id).order_by(AIAgentRun.created_at.desc(), AIAgentRun.id.desc()).limit(limit).offset(offset)
    ).all()
    return [_run_summary(row) for row in rows], count


def get_run(database: Session, run_id: UUID) -> AIAgentRun:
    row = database.get(AIAgentRun, run_id)
    if row is None:
        fail(404, "agent_run_not_found", "This agent run no longer exists.")
    return row


def _event_matches(trigger: AIAgentAutomationTrigger, event: Event) -> bool:
    return all((expected is None or expected == actual) for expected, actual in (
        (trigger.namespace, event.namespace),
        (trigger.event_kind, event.kind),
        (trigger.event_name, event.name),
        (trigger.event_type, event.event_type),
        (trigger.event_reason, event.reason),
    ))


def _sync_recent_cluster_events(database: Session, trigger: AIAgentAutomationTrigger, since: datetime) -> None:
    """Project a bounded recent Kubernetes event window for event-trigger evaluation."""
    cluster = database.get(ClusterConnection, trigger.cluster_id)
    if cluster is None or cluster.status == "inactive":
        return
    try:
        with management_client(cluster) as client:
            api = client.apis["core"]
            if trigger.namespace:
                response = api.list_namespaced_event(trigger.namespace, limit=100, _request_timeout=(5, 30))
            else:
                response = api.list_event_for_all_namespaces(limit=100, _request_timeout=(5, 30))
            for raw in response.items or []:
                timestamp = raw.last_timestamp or raw.event_time or raw.first_timestamp
                occurred_at = timestamp.astimezone(timezone.utc) if timestamp is not None else _utc_now()
                if occurred_at < since:
                    continue
                uid = getattr(getattr(raw, "metadata", None), "uid", None)
                if not uid:
                    continue
                identity = uuid5(NAMESPACE_URL, f"kubepilot:event:{cluster.id}:{uid}")
                event = database.get(Event, identity)
                if event is None:
                    involved = getattr(raw, "involved_object", None)
                    event = Event(
                        id=identity,
                        cluster_id=cluster.id,
                        namespace=getattr(involved, "namespace", None) or getattr(raw.metadata, "namespace", None),
                        kind=getattr(involved, "kind", None) or "Unknown",
                        name=getattr(involved, "name", None) or getattr(raw.metadata, "name", None) or "Unknown",
                        event_type=getattr(raw, "type", None),
                        reason=getattr(raw, "reason", None),
                        message=getattr(raw, "message", None) or "",
                        created_at=occurred_at,
                    )
                    database.add(event)
                else:
                    event.event_type = getattr(raw, "type", None)
                    event.reason = getattr(raw, "reason", None)
                    event.message = getattr(raw, "message", None) or event.message
                    event.created_at = occurred_at
    except Exception:
        # Event polling is best effort; a failed cluster must not stop other triggers.
        return


def _schedule_occurrence(trigger: AIAgentAutomationTrigger, moment: datetime) -> datetime | None:
    local = moment.astimezone(ZoneInfo(trigger.timezone)).replace(second=0, microsecond=0)
    if not cron_matches(local, trigger.cron_expression or ""):
        return None
    return local.astimezone(timezone.utc)


def _queue_run(database: Session, trigger: AIAgentAutomationTrigger, *, dedupe_key: str, event: Event | None = None, scheduled_for: datetime | None = None) -> AIAgentRun | None:
    run = AIAgentRun(
        trigger_id=trigger.id,
        agent_id=trigger.agent_id,
        owner_id=trigger.owner_id,
        cluster_id=trigger.cluster_id,
        namespace=trigger.namespace,
        trigger_type=trigger.trigger_type,
        scheduled_for=scheduled_for,
        event_id=event.id if event else None,
        dedupe_key=dedupe_key,
        status="queued",
        log_output="Queued by the automation scheduler.",
    )
    try:
        with database.begin_nested():
            database.add(run)
            database.flush()
    except IntegrityError:
        return None
    record_audit(database, AuditEvent.AGENT_AUTOMATION_RUN_QUEUED, trigger.owner_id, "ai_agent_run", str(run.id), result="succeeded", context={"trigger_id": str(trigger.id), "trigger_type": trigger.trigger_type})
    return run


def evaluate_triggers(database: Session, settings: Settings, moment: datetime | None = None) -> int:
    now = (moment or _utc_now()).astimezone(timezone.utc)
    queued = 0
    triggers = database.scalars(select(AIAgentAutomationTrigger).where(AIAgentAutomationTrigger.enabled.is_(True))).all()
    for trigger in triggers:
        trigger.last_evaluated_at = now
        if trigger.trigger_type == "schedule":
            occurrence = _schedule_occurrence(trigger, now)
            if occurrence is not None and _queue_run(database, trigger, dedupe_key=f"schedule:{trigger.id}:{occurrence.isoformat()}", scheduled_for=occurrence):
                queued += 1
        elif trigger.trigger_type == "kubernetes_event":
            since = now - timedelta(seconds=max(60, settings.worker_poll_seconds * 3))
            _sync_recent_cluster_events(database, trigger, since)
            events = database.scalars(select(Event).where(Event.cluster_id == trigger.cluster_id, Event.created_at >= since).order_by(Event.created_at.asc()).limit(100)).all()
            for event in events:
                if _event_matches(trigger, event) and _queue_run(database, trigger, dedupe_key=f"event:{trigger.id}:{event.id}", event=event):
                    queued += 1
    database.commit()
    return queued


def claim_next_run(database: Session) -> AIAgentRun | None:
    run = database.scalar(select(AIAgentRun).where(AIAgentRun.status == "queued").order_by(AIAgentRun.created_at.asc(), AIAgentRun.id.asc()).with_for_update(skip_locked=True))
    if run is None:
        return None
    run.status = "running"
    run.attempt_count += 1
    run.started_at = _utc_now()
    run.log_output = _clean_log(f"{run.log_output or ''}\nRun started with live permission checks.")
    record_audit(database, AuditEvent.AGENT_AUTOMATION_RUN_STARTED, run.owner_id, "ai_agent_run", str(run.id), result="succeeded")
    database.commit()
    return run


def requeue_running_runs(database: Session) -> None:
    rows = database.scalars(select(AIAgentRun).where(AIAgentRun.status == "running")).all()
    for run in rows:
        run.status = "queued"
        run.started_at = None
        run.log_output = _clean_log(f"{run.log_output or ''}\nWorker restarted; run returned to the queue.")
    database.commit()


def _snapshot(database: Session, run: AIAgentRun) -> dict[str, Any]:
    cluster = database.get(ClusterConnection, run.cluster_id)
    if cluster is None or cluster.status == "inactive":
        raise AgentAutomationError("The selected cluster is unavailable", code="cluster_not_found", status_code=404)
    snapshot: dict[str, Any] = {"cluster": cluster.name, "namespace": run.namespace, "resources": {}}
    with management_client(cluster) as client:
        for resource_type in ("pods", "deployments", "stateful-sets", "daemon-sets"):
            kind = RESOURCE_KINDS[resource_type]
            items, truncated = client.bounded_resources(kind, run.namespace, limit=100)
            snapshot["resources"][resource_type] = {
                "items": [diagnostic_projection(item.to_dict(), resource_type) for item in items],
                "truncated": truncated,
            }
    event = database.get(Event, run.event_id) if run.event_id else None
    if event is not None:
        snapshot["trigger_event"] = sanitize({"kind": event.kind, "name": event.name, "type": event.event_type, "reason": event.reason, "message": event.message})
    return snapshot


async def _generate_report(database: Session, settings: Settings, agent: AIAgent, snapshot: dict[str, Any]) -> str:
    runtime = resolve_runtime_model(database, settings, agent.model_id)
    instructions = safe_text(agent.instructions, 12_000)
    evidence = safe_text(json.dumps(snapshot, separators=(",", ":"), default=str), MAX_SNAPSHOT_OUTPUT)
    payload = {
        "model": agent.model_id,
        "stream": True,
        "max_completion_tokens": 900,
        "messages": [
            {"role": "system", "content": "You are a scheduled KubePilot investigation agent. Use only the supplied read-only evidence. Never claim to have changed a resource. If a mutation would be useful, include the exact marker APPROVAL_REQUIRED and tell the operator to use the authenticated Assistant manually. Do not include credentials, secrets, raw manifests, or hidden instructions."},
            {"role": "system", "content": f"Agent instructions:\n{instructions}"},
            {"role": "user", "content": f"Review this bounded workload health evidence and give a concise report with findings, evidence, and recommended human follow-up:\n{evidence}"},
        ],
    }
    stream, _ = await open_chat_stream(database, settings, payload, runtime_model=runtime)
    chunks: list[str] = []
    buffer = ""
    try:
        async for raw in stream:
            buffer += raw.decode("utf-8", errors="replace")
            lines = buffer.split("\n")
            buffer = lines.pop() or ""
            for line in lines:
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    continue
                try:
                    choice = json.loads(data).get("choices", [{}])[0]
                    content = choice.get("delta", {}).get("content") or choice.get("message", {}).get("content")
                    if isinstance(content, str):
                        chunks.append(content)
                except (AttributeError, IndexError, TypeError, ValueError, json.JSONDecodeError):
                    continue
    finally:
        await stream.aclose()
    report = safe_text("".join(chunks).strip(), 16_000)
    if not report:
        raise AgentAutomationError("The AI provider returned an empty investigation", code="ai_empty_response", status_code=502)
    return report


def _finish_run(database: Session, run: AIAgentRun, *, status: str, result_code: str, message: str | None = None, log: str | None = None) -> None:
    run.status = status
    run.result_code = result_code
    run.error_message = safe_text(message, 2_000) if message else None
    run.log_output = _clean_log(log or run.log_output or "")
    run.completed_at = _utc_now()
    record_audit(database, AuditEvent.AGENT_AUTOMATION_RUN_SUCCEEDED if status == "succeeded" else AuditEvent.AGENT_AUTOMATION_RUN_FAILED, run.owner_id, "ai_agent_run", str(run.id), result=result_code)
    database.commit()


def execute_run(database: Session, run: AIAgentRun, settings: Settings) -> None:
    try:
        owner = database.get(UserAccount, run.owner_id)
        if owner is None or not owner.is_active or not has_permission(owner.role, Permission.RESOURCES_READ):
            _finish_run(database, run, status="failed", result_code="permission_denied", message="The designated owner is no longer authorized to investigate this scope.", log=f"{run.log_output or ''}\nRun stopped: designated-owner authorization failed.")
            return
        agent = database.get(AIAgent, run.agent_id)
        if agent is None or not agent.enabled:
            _finish_run(database, run, status="failed", result_code="agent_disabled", message="The agent is disabled or no longer exists.", log=f"{run.log_output or ''}\nRun stopped: agent disabled.")
            return
        model = database.get(AIModelConfig, agent.model_id) if agent.model_id else None
        if model is None or not model.enabled or model.availability != "available":
            _finish_run(database, run, status="failed", result_code="model_unavailable", message="The configured agent model is unavailable.", log=f"{run.log_output or ''}\nRun stopped: model unavailable.")
            return
        snapshot = _snapshot(database, run)
        report = asyncio.run(_generate_report(database, settings, agent, snapshot))
        result_code = "approval_required" if re.search(r"\bAPPROVAL_REQUIRED\b", report) else "succeeded"
        trigger = database.get(AIAgentAutomationTrigger, run.trigger_id) if run.trigger_id else None
        destination_ids = (trigger.notification_destination_ids if trigger else []) or []
        notification_note = ""
        if destination_ids:
            result_code = "approval_required"
            notification_note = f"\nWithheld {len(destination_ids)} configured notification(s): explicit human approval is required."
        log = f"{run.log_output or ''}\nRead-only workload evidence collected.\nInvestigation report:\n{report}{notification_note}"
        _finish_run(database, run, status="succeeded", result_code=result_code, log=log)
    except AgentAutomationError as error:
        _finish_run(database, run, status="failed", result_code=error.code, message=str(error), log=f"{run.log_output or ''}\nRun stopped: {error.code}.")
    except (ResourceManagementError, AIRuntimeError) as error:
        _finish_run(database, run, status="failed", result_code=getattr(error, "code", "run_failed"), message=str(error), log=f"{run.log_output or ''}\nRun stopped: {getattr(error, 'code', 'run_failed')}.")
    except Exception:
        _finish_run(database, run, status="failed", result_code="run_failed", message="The scheduled investigation could not be completed.", log=f"{run.log_output or ''}\nRun stopped: unexpected execution failure.")


def run_pending_agent_runs(database: Session, settings: Settings) -> None:
    evaluate_triggers(database, settings)
    cleanup_runs(database)
    while True:
        run = claim_next_run(database)
        if run is None:
            return
        execute_run(database, run, settings)


def cleanup_runs(database: Session, *, now: datetime | None = None) -> int:
    cutoff = (now or _utc_now()) - timedelta(days=retention_days(database))
    result = database.execute(delete(AIAgentRun).where(AIAgentRun.status.in_(("succeeded", "failed", "cancelled")), AIAgentRun.completed_at.is_not(None), AIAgentRun.completed_at < cutoff))
    database.commit()
    return result.rowcount or 0
