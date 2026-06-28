from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from ..diagnostics import error_response
from ..kids_catalog import KidsCatalogError, VeseleRozpravkyClient

router = APIRouter()


class KidsCatalogResolvePayload(BaseModel):
    episode_url: str = Field(min_length=1, max_length=1000)


def _catalog_error(request: Request, *, status_code: int, error: str, error_code: str, details: str | None = None):
    return error_response(
        request,
        status_code=status_code,
        error=error,
        error_code=error_code,
        hint="Retry the catalog request or open the source page directly.",
        retryable=True,
        details=details,
    )


@router.get("/api/kids-catalog/shows")
def api_kids_catalog_shows(request: Request):
    try:
        return JSONResponse({"items": VeseleRozpravkyClient().list_shows()})
    except KidsCatalogError as exc:
        return _catalog_error(request, status_code=502, error=str(exc), error_code="kids_catalog_load_failed")


@router.get("/api/kids-catalog/shows/{slug}")
def api_kids_catalog_show(request: Request, slug: str):
    try:
        return JSONResponse(VeseleRozpravkyClient().get_show(slug))
    except KidsCatalogError as exc:
        return _catalog_error(request, status_code=502, error=str(exc), error_code="kids_catalog_show_load_failed")


@router.post("/api/kids-catalog/resolve")
def api_kids_catalog_resolve(request: Request, payload: KidsCatalogResolvePayload):
    try:
        return JSONResponse(VeseleRozpravkyClient().resolve_episode(payload.episode_url))
    except KidsCatalogError as exc:
        return _catalog_error(request, status_code=502, error=str(exc), error_code="kids_catalog_resolve_failed")
