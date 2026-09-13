"""Fixed-path reuse of existing FastAPI routes, including their auth/validation/audit.

ASGI transport stays inside this process; no URL or headers are supplied by the model.
"""
from urllib.parse import quote

import httpx

from app.assistant.observations import active_cluster
from app.assistant.sanitize import sanitize
from app.assistant.schemas import ReadTool
from app.kubernetes.resource_management import ResourceManagementError


def segment(value: str | None) -> str:
    if not value or value in {".", ".."} or "/" in value or "\\" in value:
        raise ResourceManagementError(422, "invalid_tool_input", "A valid resource identifier is required")
    return quote(value, safe="")


async def call_api(request, path, *, method="GET", params=None, body=None):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=request.app), base_url="http://kubepilot.internal") as client:
        response = await client.request(method, "/api/v1" + path, params=params, json=body, headers={"cookie": request.headers.get("cookie", "")})
    if not response.is_success:
        error = response.json()
        if isinstance(error.get("detail"), dict):
            error = error["detail"]
        raise ResourceManagementError(response.status_code, str(error.get("code", "api_error")), str(sanitize(error.get("message", "KubePilot could not complete this operation"))))
    return response.json() if response.content else {"status": "success"}


async def read_tool(request, database, body: ReadTool):
    active_cluster(database, body.cluster)
    scope = {"cluster": body.cluster}
    if body.namespace:
        scope["namespace"] = body.namespace
    if body.tool == "listClusters":
        result = await call_api(request, "/clusters")
        result = {"items": [{k: item.get(k) for k in ("name", "status")} for item in result["items"]]}
    elif body.tool == "listNamespaces":
        result = await call_api(request, "/cluster/namespaces", params={"cluster": body.cluster})
    elif body.tool == "getResourceUsage":
        path = f"/cluster/metrics/namespaces/{segment(body.namespace)}" if body.namespace else "/cluster/metrics/nodes"
        result = await call_api(request, path, params={"cluster": body.cluster})
    elif body.tool == "listHelmReleases":
        result = await call_api(request, "/cluster/helm/releases", params={"cluster": body.cluster})
        if body.namespace:
            result["items"] = [item for item in result["items"] if item.get("namespace") == body.namespace]
    elif body.tool == "getHelmHistory":
        result = await call_api(request, f"/cluster/helm/releases/{segment(body.name)}/history", params=scope)
    elif body.tool == "listRepositories":
        result = await call_api(request, "/helm/repositories")
    elif body.tool == "searchPackages":
        result = await call_api(request, "/marketplace/packages", params={"ts_query_web": body.query or "", "limit": 10})
    elif body.tool == "getPackage":
        result = await call_api(request, f"/marketplace/packages/{segment(body.repository_name)}/{segment(body.package_name)}/versions")
    else:
        result = await call_api(request, f"/marketplace/installations/{segment(body.name)}")
        if result.get("cluster") != body.cluster:
            raise ResourceManagementError(404, "job_not_found", "Job not found in the selected cluster")
    return {"cluster": body.cluster, "namespace": body.namespace, "result": sanitize(result)}
