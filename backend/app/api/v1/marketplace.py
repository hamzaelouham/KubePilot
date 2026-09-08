from typing import Annotated, Any
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.dependencies import AuthenticatedActor, get_current_actor

from .marketplace_schemas import (
    MarketplacePackageRepository,
    MarketplacePackageSummary,
    MarketplaceSearchResponse,
)

router = APIRouter()

ARTIFACT_HUB_SEARCH_URL = "https://artifacthub.io/api/v1/packages/search"
REQUEST_TIMEOUT_SECONDS = 15.0
DEFAULT_LIMIT = 24
MAX_LIMIT = 60


def _repository_summary(repository: Any) -> MarketplacePackageRepository | None:
    if not isinstance(repository, dict):
        return None
    return MarketplacePackageRepository(
        name=str(repository.get("name") or ""),
        display_name=repository.get("display_name"),
        organization_name=repository.get("organization_name"),
        organization_display_name=repository.get("organization_display_name"),
        url=repository.get("url"),
        kind=repository.get("kind"),
    )


def _package_summary(raw: dict[str, Any]) -> MarketplacePackageSummary:
    return MarketplacePackageSummary(
        package_id=str(raw.get("package_id") or ""),
        name=str(raw.get("name") or ""),
        normalized_name=raw.get("normalized_name"),
        description=raw.get("description"),
        version=raw.get("version"),
        app_version=raw.get("app_version"),
        logo_image_id=raw.get("logo_image_id"),
        stars=raw.get("stars"),
        deprecated=bool(raw.get("deprecated", False)),
        official=bool(raw.get("official", False)),
        signed=bool(raw.get("signed", False)),
        license=raw.get("license"),
        repository=_repository_summary(raw.get("repository")),
    )


def _read_limit(value: str | None) -> int:
    if value is None or value == "":
        return DEFAULT_LIMIT
    try:
        limit = int(value)
    except ValueError:
        limit = -1
    if not 1 <= limit <= MAX_LIMIT:
        raise HTTPException(
            status_code=400,
            detail={"code": "invalid_pagination", "message": "limit must be an integer between 1 and 60"},
        )
    return limit


def _read_offset(value: str | None) -> int:
    if value is None or value == "":
        return 0
    try:
        offset = int(value)
    except ValueError:
        offset = -1
    if offset < 0:
        raise HTTPException(
            status_code=400,
            detail={"code": "invalid_pagination", "message": "offset must be a non-negative integer"},
        )
    return offset


def _upstream_error(message: str) -> HTTPException:
    return HTTPException(
        status_code=502,
        detail={"code": "marketplace_upstream_error", "message": message},
    )


async def _fetch_artifact_hub_search(url: str) -> httpx.Response:
    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as client:
        return await client.get(url)


@router.get("/marketplace/packages", response_model=MarketplaceSearchResponse)
async def list_marketplace_packages(
    _actor: Annotated[AuthenticatedActor, Depends(get_current_actor)],
    limit: Annotated[str | None, Query()] = None,
    offset: Annotated[str | None, Query()] = None,
    ts_query_web: Annotated[str | None, Query()] = None,
    sort: Annotated[str | None, Query()] = None,
) -> MarketplaceSearchResponse:
    page_size = _read_limit(limit)
    page_offset = _read_offset(offset)

    params: dict[str, Any] = {
        "kind": 0,
        "deprecated": "false",
        "limit": page_size,
        "offset": page_offset,
    }
    if ts_query_web is not None:
        params["ts_query_web"] = ts_query_web
    if sort is not None:
        params["sort"] = sort
    search_url = f"{ARTIFACT_HUB_SEARCH_URL}?{urlencode(params)}"

    try:
        upstream = await _fetch_artifact_hub_search(search_url)
    except httpx.HTTPError:
        raise _upstream_error("Artifact Hub is unavailable")

    if upstream.status_code != 200:
        raise _upstream_error(f"Artifact Hub returned status {upstream.status_code}")

    try:
        payload = upstream.json()
    except ValueError:
        raise _upstream_error("Artifact Hub returned invalid package data")

    raw_packages = payload.get("packages") if isinstance(payload, dict) else None
    if not isinstance(raw_packages, list):
        raise _upstream_error("Artifact Hub returned unexpected package data")

    total = len(raw_packages)
    total_header = upstream.headers.get("Pagination-Total-Count")
    if total_header is not None:
        try:
            total = max(total, int(total_header))
        except ValueError:
            pass

    packages = [_package_summary(item) for item in raw_packages if isinstance(item, dict)]
    return MarketplaceSearchResponse(packages=packages, total=total)