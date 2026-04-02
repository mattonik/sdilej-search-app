from __future__ import annotations

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse

from ..main import (
    CATEGORY_OPTIONS,
    DEFAULT_CATEGORY,
    DEFAULT_LANGUAGE_SCOPE,
    DEFAULT_SORT,
    LANGUAGE_SCOPE_OPTIONS,
    ServiceContainer,
    SORT_OPTIONS,
    MovieInfoLinkPayload,
    MovieLookupPayload,
    SaveCandidatePayload,
    _build_media_plan,
    _extract_file_id,
    _get_services,
    _normalize_detail_url,
    _parse_optional_year,
    _resolve_movie_info_link,
    _search_files,
)
from ..sdilej_client import SdilejClientError

router = APIRouter()


@router.get("/")
def index(
    request: Request,
    query: str = Query(default="", max_length=200),
    category: str = Query(default=DEFAULT_CATEGORY),
    sort: str = Query(default=DEFAULT_SORT),
    language: str = Query(default="", max_length=32),
    language_scope: str = Query(default=DEFAULT_LANGUAGE_SCOPE),
    strict_dubbing: bool = Query(default=False),
    release_year: str = Query(default="", max_length=8),
    max_results: int = Query(default=120, ge=1, le=500),
):
    error: str | None = None
    search_response = None
    services = _get_services(request)

    if query.strip() or language.strip() or release_year.strip() or strict_dubbing:
        try:
            parsed_release_year = _parse_optional_year(release_year)
            search_response = _search_files(
                query=query,
                category=category,
                sort=sort,
                language=language,
                language_scope=language_scope,
                strict_dubbing=strict_dubbing,
                release_year=parsed_release_year,
                max_results=max_results,
                services=services,
            )
            services.storage.record_search(search_response)
        except SdilejClientError as exc:
            error = str(exc)
        except Exception as exc:  # noqa: BLE001
            error = f"Unexpected search failure: {exc}"

    return request.app.state.templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "query": query,
            "category": category,
            "sort": sort,
            "language": language,
            "language_scope": language_scope,
            "strict_dubbing": strict_dubbing,
            "release_year": release_year,
            "max_results": max_results,
            "error": error,
            "search": search_response,
            "category_options": CATEGORY_OPTIONS,
            "sort_options": SORT_OPTIONS,
            "language_scope_options": LANGUAGE_SCOPE_OPTIONS,
        },
    )


@router.get("/saved")
def saved_page(
    request: Request,
    limit: int = Query(default=500, ge=1, le=5000),
):
    items = _get_services(request).storage.list_saved_candidates(limit=limit)
    return request.app.state.templates.TemplateResponse(
        request=request,
        name="saved.html",
        context={
            "items": items,
            "limit": limit,
        },
    )


@router.get("/api/search")
def api_search(
    request: Request,
    query: str = Query(default="", max_length=200),
    category: str = Query(default=DEFAULT_CATEGORY),
    sort: str = Query(default=DEFAULT_SORT),
    language: str = Query(default="", max_length=32),
    language_scope: str = Query(default=DEFAULT_LANGUAGE_SCOPE),
    strict_dubbing: bool = Query(default=False),
    release_year: str = Query(default="", max_length=8),
    max_results: int = Query(default=120, ge=1, le=500),
):
    try:
        services = _get_services(request)
        parsed_release_year = _parse_optional_year(release_year)
        result = _search_files(
            query=query,
            category=category,
            sort=sort,
            language=language,
            language_scope=language_scope,
            strict_dubbing=strict_dubbing,
            release_year=parsed_release_year,
            max_results=max_results,
            services=services,
        )
        services.storage.record_search(result)
        return JSONResponse(result.to_dict())
    except SdilejClientError as exc:
        return JSONResponse(status_code=400, content={"error": str(exc)})
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(status_code=500, content={"error": str(exc)})


@router.get("/api/detail")
def api_detail(
    request: Request,
    detail_url: str = Query(..., min_length=1, max_length=500),
    preflight: bool = Query(default=True),
):
    try:
        result = _get_services(request).client.probe_detail(detail_url=detail_url, run_preflight=preflight)
        return JSONResponse(result.to_dict())
    except SdilejClientError as exc:
        return JSONResponse(status_code=400, content={"error": str(exc)})
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(status_code=500, content={"error": str(exc)})


@router.get("/api/history")
def api_history(request: Request, limit: int = Query(default=50, ge=1, le=500)):
    try:
        return JSONResponse({"items": _get_services(request).storage.list_search_history(limit=limit)})
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(status_code=500, content={"error": str(exc)})


@router.get("/api/saved")
def api_saved_list(request: Request, limit: int = Query(default=200, ge=1, le=1000)):
    try:
        return JSONResponse({"items": _get_services(request).storage.list_saved_candidates(limit=limit)})
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(status_code=500, content={"error": str(exc)})


@router.post("/api/saved")
def api_saved_upsert(request: Request, payload: SaveCandidatePayload):
    try:
        services: ServiceContainer = _get_services(request)
        detail_url = _normalize_detail_url(payload.detail_url)
        file_id = payload.file_id if payload.file_id is not None else _extract_file_id(detail_url)
        if file_id is None:
            return JSONResponse(
                status_code=400,
                content={"error": "file_id is missing and could not be extracted from detail_url."},
            )

        title = payload.title.strip() if payload.title else detail_url.rsplit("/", 1)[-1]
        media = _build_media_plan(
            title=title,
            media_kind=payload.media_kind,
            is_kids=payload.is_kids,
            series_name=payload.series_name,
            season_number=payload.season_number,
            episode_number=payload.episode_number,
            services=services,
        )["classification"]

        saved = services.storage.upsert_saved_candidate(
            file_id=file_id,
            title=title,
            detail_url=detail_url,
            download_url=payload.download_url,
            size=payload.size,
            duration=payload.duration,
            extension=payload.extension,
            primary_year=payload.primary_year,
            detected_languages=payload.detected_languages,
            has_dub_hint=payload.has_dub_hint,
            has_subtitle_hint=payload.has_subtitle_hint,
            media_kind=media.media_kind,
            is_kids=media.is_kids,
            series_name=media.series_name,
            season_number=media.season_number,
            episode_number=media.episode_number,
            classification_confidence=media.confidence,
            notes=payload.notes,
        )
        return JSONResponse(saved)
    except SdilejClientError as exc:
        return JSONResponse(status_code=400, content={"error": str(exc)})
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(status_code=500, content={"error": str(exc)})


@router.delete("/api/saved/{file_id}")
def api_saved_delete(request: Request, file_id: int):
    try:
        deleted = _get_services(request).storage.delete_saved_candidate(file_id=file_id)
        if not deleted:
            return JSONResponse(status_code=404, content={"error": "Saved candidate not found."})
        return JSONResponse({"deleted": True, "file_id": file_id})
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(status_code=500, content={"error": str(exc)})


@router.post("/api/movie/lookup")
def api_movie_lookup(request: Request, payload: MovieLookupPayload):
    try:
        metadata = _get_services(request).metadata_resolver.resolve_movie(payload.title, payload.year)
        return JSONResponse(
            {
                "query": payload.title.strip(),
                "title_metadata": metadata.to_dict(),
                "aliases": metadata.aliases,
            }
        )
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(status_code=500, content={"error": str(exc)})


@router.post("/api/movie/info-link")
def api_movie_info_link(request: Request, payload: MovieInfoLinkPayload):
    try:
        return JSONResponse(_resolve_movie_info_link(payload, services=_get_services(request)))
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(
            status_code=500,
            content={
                "found": False,
                "preferred_url": None,
                "csfd_url": None,
                "imdb_url": None,
                "resolved_title": None,
                "original_title": None,
                "year": payload.primary_year,
                "source": "fallback",
                "error": str(exc),
            },
        )


@router.get("/api/autocomplete")
def api_autocomplete(
    request: Request,
    q: str = Query(..., min_length=1, max_length=200),
    limit: int = Query(default=10, ge=1, le=30),
):
    try:
        suggestions = _get_services(request).client.autocomplete(term=q, limit=limit)
        return JSONResponse({"q": q, "suggestions": suggestions})
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(status_code=500, content={"error": str(exc)})
