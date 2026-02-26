from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Literal
from urllib.parse import urljoin, urlparse

from fastapi import FastAPI, Query, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from .downloader import DownloadWorker
from .media_routing import (
    classify_media_title,
    requires_classification_confirmation,
    resolve_destination_subpath,
)
from .models import Category, LanguageScope, SortMode
from .sdilej_client import BASE_URL, SdilejClient, SdilejClientError
from .storage import Storage

BASE_DIR = Path(__file__).resolve().parent
_FILE_ID_RE = re.compile(r"^/(\d+)/")

app = FastAPI(title="Sdilej Search Proxy", version="0.1.0")
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

client = SdilejClient()
storage = Storage()
worker = DownloadWorker(storage=storage)

DEFAULT_CATEGORY: Category = "all"
DEFAULT_SORT: SortMode = "relevance"
DEFAULT_LANGUAGE_SCOPE: LanguageScope = "any"

CATEGORY_OPTIONS: list[tuple[str, Category]] = [
    ("All", "all"),
    ("Video", "video"),
    ("Audio", "audio"),
    ("Archive", "archive"),
    ("Image", "image"),
]

SORT_OPTIONS: list[tuple[str, SortMode]] = [
    ("Relevance", "relevance"),
    ("Most downloaded", "downloads"),
    ("Newest", "newest"),
    ("Largest", "size_desc"),
    ("Smallest", "size_asc"),
]

LANGUAGE_SCOPE_OPTIONS: list[tuple[str, LanguageScope]] = [
    ("Any language hint", "any"),
    ("Audio / dubbing focus", "audio"),
    ("Subtitles only", "subtitles"),
]


class SaveCandidatePayload(BaseModel):
    file_id: int | None = None
    title: str | None = None
    detail_url: str
    download_url: str | None = None
    size: str | None = None
    duration: str | None = None
    extension: str | None = None
    primary_year: int | None = Field(default=None, ge=1900, le=2099)
    detected_languages: list[str] = Field(default_factory=list)
    has_dub_hint: bool = False
    has_subtitle_hint: bool = False
    media_kind: Literal["movie", "tv", "unknown"] | None = None
    is_kids: bool | None = None
    series_name: str | None = None
    season_number: int | None = Field(default=None, ge=1, le=99)
    episode_number: int | None = Field(default=None, ge=1, le=999)
    notes: str | None = None


class AccountPayload(BaseModel):
    login: str
    password: str
    verify: bool = True


class EnqueueDownloadPayload(BaseModel):
    detail_url: str
    file_id: int | None = None
    title: str | None = None
    preferred_mode: Literal["auto", "premium", "free"] = "auto"
    output_dir: str | None = None
    priority: int = Field(default=0, ge=-100, le=100)
    chunk_count: int | None = Field(default=None, ge=1, le=8)
    media_kind: Literal["movie", "tv"] | None = None
    is_kids: bool | None = None
    series_name: str | None = None
    season_number: int | None = Field(default=None, ge=1, le=99)
    episode_number: int | None = Field(default=None, ge=1, le=999)
    source_saved_file_id: int | None = Field(default=None, ge=1)
    delete_saved_on_complete: bool = False


class UpdatePriorityPayload(BaseModel):
    priority: int = Field(default=0, ge=-1000, le=1000)


class ClearDownloadsPayload(BaseModel):
    statuses: list[Literal["done", "failed", "canceled"]] = Field(default_factory=lambda: ["done", "failed", "canceled"])


class DownloadSettingsPayload(BaseModel):
    max_concurrent_jobs: int = Field(default=1, ge=1, le=8)
    default_chunk_count: int = Field(default=1, ge=1, le=8)
    bandwidth_limit_kbps: int = Field(default=0, ge=0, le=2_000_000)


class LibraryPathsPayload(BaseModel):
    movies_dir: str = Field(default="/movies", min_length=1, max_length=200)
    tv_dir: str = Field(default="/tv", min_length=1, max_length=200)
    kids_movies_dir: str = Field(default="/kids/movies", min_length=1, max_length=200)
    kids_tv_dir: str = Field(default="/kids/tv", min_length=1, max_length=200)
    unsorted_dir: str = Field(default="/unsorted", min_length=1, max_length=200)
    confirm_on_uncertain: bool = True


class MediaClassificationPayload(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    media_kind: Literal["movie", "tv"] | None = None
    is_kids: bool | None = None
    series_name: str | None = None
    season_number: int | None = Field(default=None, ge=1, le=99)
    episode_number: int | None = Field(default=None, ge=1, le=999)


class UpdateDownloadClassificationPayload(BaseModel):
    media_kind: Literal["movie", "tv"] | None = None
    is_kids: bool | None = None
    series_name: str | None = None
    season_number: int | None = Field(default=None, ge=1, le=99)
    episode_number: int | None = Field(default=None, ge=1, le=999)


@app.on_event("startup")
def on_startup() -> None:
    storage.init_db()
    storage.recover_download_queue_after_restart()
    settings = storage.get_download_settings()
    worker.configure(
        max_concurrent_jobs=settings["max_concurrent_jobs"],
        default_chunk_count=settings["default_chunk_count"],
        bandwidth_limit_kbps=settings["bandwidth_limit_kbps"],
    )
    worker.start()


@app.on_event("shutdown")
def on_shutdown() -> None:
    worker.stop()


def _parse_optional_year(raw_value: str | None) -> int | None:
    if raw_value is None:
        return None

    text = raw_value.strip()
    if not text:
        return None

    if not text.isdigit():
        raise SdilejClientError("release_year must be an integer between 1900 and 2099.")

    year = int(text)
    if year < 1900 or year > 2099:
        raise SdilejClientError("release_year must be an integer between 1900 and 2099.")

    return year


def _normalize_detail_url(detail_url: str) -> str:
    raw = detail_url.strip()
    if raw.startswith("http://") or raw.startswith("https://"):
        return raw
    if raw.startswith("/"):
        return urljoin(BASE_URL, raw)
    raise SdilejClientError("detail_url must be absolute or start with '/'.")


def _extract_file_id(detail_url: str) -> int | None:
    path = urlparse(detail_url).path
    match = _FILE_ID_RE.match(path)
    if not match:
        return None
    return int(match.group(1))


def _normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    text = value.strip()
    return text or None


def _resolve_download_root() -> Path:
    configured_root = os.getenv("DOWNLOAD_DIR", "./downloads")
    return Path(configured_root).expanduser().resolve()


def _build_media_plan(
    *,
    title: str,
    media_kind: Literal["movie", "tv"] | None,
    is_kids: bool | None,
    series_name: str | None,
    season_number: int | None,
    episode_number: int | None,
) -> dict:
    library_paths = storage.get_library_paths()
    media = classify_media_title(
        title=title,
        media_kind_override=media_kind,
        is_kids_override=is_kids,
        series_name_override=_normalize_optional_text(series_name),
        season_number_override=season_number,
        episode_number_override=episode_number,
    )
    destination_subpath = resolve_destination_subpath(media, library_paths=library_paths)
    resolved_output_dir = str(_resolve_download_root() / Path(destination_subpath))
    requires_confirmation = bool(
        library_paths.get("confirm_on_uncertain", True) and requires_classification_confirmation(media)
    )
    return {
        "classification": media,
        "destination_subpath": destination_subpath,
        "resolved_output_dir": resolved_output_dir,
        "requires_confirmation": requires_confirmation,
        "confirm_on_uncertain": bool(library_paths.get("confirm_on_uncertain", True)),
    }


@app.get("/")
def index(
    request: Request,
    query: str = Query(default="", max_length=200),
    category: Category = Query(default=DEFAULT_CATEGORY),
    sort: SortMode = Query(default=DEFAULT_SORT),
    language: str = Query(default="", max_length=32),
    language_scope: LanguageScope = Query(default=DEFAULT_LANGUAGE_SCOPE),
    strict_dubbing: bool = Query(default=False),
    release_year: str = Query(default="", max_length=8),
    max_results: int = Query(default=120, ge=1, le=500),
):
    error: str | None = None
    search_response = None

    if query.strip() or language.strip() or release_year.strip() or strict_dubbing:
        try:
            parsed_release_year = _parse_optional_year(release_year)
            search_response = client.search(
                query=query,
                category=category,
                sort=sort,
                language=language,
                language_scope=language_scope,
                strict_dubbing=strict_dubbing,
                release_year=parsed_release_year,
                max_results=max_results,
            )
            storage.record_search(search_response)
        except SdilejClientError as exc:
            error = str(exc)
        except Exception as exc:  # noqa: BLE001
            error = f"Unexpected search failure: {exc}"

    return templates.TemplateResponse(
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


@app.get("/saved")
def saved_page(
    request: Request,
    limit: int = Query(default=500, ge=1, le=5000),
):
    items = storage.list_saved_candidates(limit=limit)
    return templates.TemplateResponse(
        request=request,
        name="saved.html",
        context={
            "items": items,
            "limit": limit,
        },
    )


@app.get("/api/search")
def api_search(
    query: str = Query(default="", max_length=200),
    category: Category = Query(default=DEFAULT_CATEGORY),
    sort: SortMode = Query(default=DEFAULT_SORT),
    language: str = Query(default="", max_length=32),
    language_scope: LanguageScope = Query(default=DEFAULT_LANGUAGE_SCOPE),
    strict_dubbing: bool = Query(default=False),
    release_year: str = Query(default="", max_length=8),
    max_results: int = Query(default=120, ge=1, le=500),
):
    try:
        parsed_release_year = _parse_optional_year(release_year)
        result = client.search(
            query=query,
            category=category,
            sort=sort,
            language=language,
            language_scope=language_scope,
            strict_dubbing=strict_dubbing,
            release_year=parsed_release_year,
            max_results=max_results,
        )
        storage.record_search(result)
        return JSONResponse(result.to_dict())
    except SdilejClientError as exc:
        return JSONResponse(status_code=400, content={"error": str(exc)})
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(status_code=500, content={"error": str(exc)})


@app.get("/api/detail")
def api_detail(
    detail_url: str = Query(..., min_length=1, max_length=500),
    preflight: bool = Query(default=True),
):
    try:
        result = client.probe_detail(detail_url=detail_url, run_preflight=preflight)
        return JSONResponse(result.to_dict())
    except SdilejClientError as exc:
        return JSONResponse(status_code=400, content={"error": str(exc)})
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(status_code=500, content={"error": str(exc)})


@app.get("/api/history")
def api_history(limit: int = Query(default=50, ge=1, le=500)):
    try:
        return JSONResponse({"items": storage.list_search_history(limit=limit)})
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(status_code=500, content={"error": str(exc)})


@app.get("/api/saved")
def api_saved_list(limit: int = Query(default=200, ge=1, le=1000)):
    try:
        return JSONResponse({"items": storage.list_saved_candidates(limit=limit)})
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(status_code=500, content={"error": str(exc)})


@app.post("/api/saved")
def api_saved_upsert(payload: SaveCandidatePayload):
    try:
        detail_url = _normalize_detail_url(payload.detail_url)
        file_id = payload.file_id if payload.file_id is not None else _extract_file_id(detail_url)
        if file_id is None:
            return JSONResponse(
                status_code=400,
                content={"error": "file_id is missing and could not be extracted from detail_url."},
            )

        title = payload.title.strip() if payload.title else detail_url.rsplit("/", 1)[-1]
        media = classify_media_title(
            title=title,
            media_kind_override=payload.media_kind,
            is_kids_override=payload.is_kids,
            series_name_override=payload.series_name,
            season_number_override=payload.season_number,
            episode_number_override=payload.episode_number,
        )

        saved = storage.upsert_saved_candidate(
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


@app.delete("/api/saved/{file_id}")
def api_saved_delete(file_id: int):
    try:
        deleted = storage.delete_saved_candidate(file_id=file_id)
        if not deleted:
            return JSONResponse(status_code=404, content={"error": "Saved candidate not found."})
        return JSONResponse({"deleted": True, "file_id": file_id})
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(status_code=500, content={"error": str(exc)})


@app.get("/api/account")
def api_account_get():
    credentials = storage.get_account_credentials()
    if not credentials:
        return JSONResponse({"configured": False, "login": None})
    return JSONResponse({"configured": True, "login": credentials[0]})


@app.post("/api/account")
def api_account_set(payload: AccountPayload):
    try:
        login_value = payload.login.strip()
        if not login_value or not payload.password:
            return JSONResponse(status_code=400, content={"error": "login and password are required."})

        verified = None
        message = None
        if payload.verify:
            probe_client = SdilejClient(timeout_seconds=45)
            ok, msg = probe_client.login(login_value, payload.password)
            verified = ok
            message = msg
            if not ok:
                return JSONResponse(status_code=400, content={"error": f"Credential verification failed: {msg}"})

        storage.set_account_credentials(login_value, payload.password)
        return JSONResponse(
            {
                "saved": True,
                "configured": True,
                "login": login_value,
                "verified": verified,
                "message": message,
            }
        )
    except SdilejClientError as exc:
        return JSONResponse(status_code=400, content={"error": str(exc)})
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(status_code=500, content={"error": str(exc)})


@app.delete("/api/account")
def api_account_delete():
    storage.clear_account_credentials()
    return JSONResponse({"cleared": True})


@app.get("/api/downloads")
def api_downloads_list(
    limit: int = Query(default=200, ge=1, le=1000),
    status: str | None = Query(default=None),
):
    try:
        jobs = storage.list_download_jobs(limit=limit, status=status)
        return JSONResponse({"items": jobs, "summary": storage.get_download_summary(), "worker_alive": worker.is_alive()})
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(status_code=500, content={"error": str(exc)})


@app.get("/api/downloads/settings")
def api_download_settings_get():
    try:
        settings = storage.get_download_settings()
        return JSONResponse(settings)
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(status_code=500, content={"error": str(exc)})


@app.post("/api/downloads/settings")
def api_download_settings_set(payload: DownloadSettingsPayload):
    try:
        settings = storage.set_download_settings(
            max_concurrent_jobs=payload.max_concurrent_jobs,
            default_chunk_count=payload.default_chunk_count,
            bandwidth_limit_kbps=payload.bandwidth_limit_kbps,
        )
        worker.configure(
            max_concurrent_jobs=settings["max_concurrent_jobs"],
            default_chunk_count=settings["default_chunk_count"],
            bandwidth_limit_kbps=settings["bandwidth_limit_kbps"],
        )
        return JSONResponse(settings)
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(status_code=500, content={"error": str(exc)})


@app.get("/api/downloads/library-paths")
def api_library_paths_get():
    try:
        return JSONResponse(storage.get_library_paths())
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(status_code=500, content={"error": str(exc)})


@app.post("/api/downloads/library-paths")
def api_library_paths_set(payload: LibraryPathsPayload):
    try:
        paths = storage.set_library_paths(
            movies_dir=payload.movies_dir,
            tv_dir=payload.tv_dir,
            kids_movies_dir=payload.kids_movies_dir,
            kids_tv_dir=payload.kids_tv_dir,
            unsorted_dir=payload.unsorted_dir,
            confirm_on_uncertain=payload.confirm_on_uncertain,
        )
        return JSONResponse(paths)
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(status_code=500, content={"error": str(exc)})


@app.post("/api/media/classify")
def api_media_classify(payload: MediaClassificationPayload):
    try:
        plan = _build_media_plan(
            title=payload.title,
            media_kind=payload.media_kind,
            is_kids=payload.is_kids,
            series_name=payload.series_name,
            season_number=payload.season_number,
            episode_number=payload.episode_number,
        )
        return JSONResponse(
            {
                "classification": plan["classification"].to_dict(),
                "destination_subpath": plan["destination_subpath"],
                "resolved_output_dir": plan["resolved_output_dir"],
                "requires_confirmation": plan["requires_confirmation"],
                "confirm_on_uncertain": plan["confirm_on_uncertain"],
            }
        )
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(status_code=500, content={"error": str(exc)})


@app.post("/api/downloads")
def api_downloads_enqueue(payload: EnqueueDownloadPayload):
    try:
        detail_url = _normalize_detail_url(payload.detail_url)
        file_id = payload.file_id if payload.file_id is not None else _extract_file_id(detail_url)
        title = payload.title.strip() if payload.title else None

        if file_id is None or title is None:
            probe = client.probe_detail(detail_url=detail_url, run_preflight=False)
            file_id = file_id if file_id is not None else probe.file_id
            title = title or probe.title

        saved_candidate = None
        if payload.source_saved_file_id is not None:
            saved_candidate = storage.get_saved_candidate(payload.source_saved_file_id)

        requested_media_kind = payload.media_kind or (saved_candidate.get("media_kind") if saved_candidate else None)
        if requested_media_kind == "movie":
            fallback_series_name = None
            fallback_season_number = None
            fallback_episode_number = None
        else:
            fallback_series_name = saved_candidate.get("series_name") if saved_candidate else None
            fallback_season_number = saved_candidate.get("season_number") if saved_candidate else None
            fallback_episode_number = saved_candidate.get("episode_number") if saved_candidate else None

        media_plan = _build_media_plan(
            title=title or detail_url.rsplit("/", 1)[-1],
            media_kind=requested_media_kind,
            is_kids=(
                payload.is_kids if payload.is_kids is not None else (saved_candidate.get("is_kids") if saved_candidate else None)
            ),
            series_name=payload.series_name if payload.series_name is not None else fallback_series_name,
            season_number=payload.season_number if payload.season_number is not None else fallback_season_number,
            episode_number=payload.episode_number if payload.episode_number is not None else fallback_episode_number,
        )
        media = media_plan["classification"]

        if media_plan["requires_confirmation"]:
            return JSONResponse(
                status_code=409,
                content={
                    "error": "Destination is uncertain. Confirm media classification first.",
                    "requires_confirmation": True,
                    "classification": media.to_dict(),
                    "destination_subpath": media_plan["destination_subpath"],
                },
            )

        duplicate = storage.find_duplicate_download(detail_url=detail_url, file_id=file_id)
        if duplicate:
            status = duplicate.get("status")
            if status in {"queued", "running"}:
                return JSONResponse(
                    status_code=409,
                    content={
                        "error": f"A matching job is already {status}.",
                        "duplicate_job": duplicate,
                    },
                )
            if status == "done":
                return JSONResponse(
                    status_code=409,
                    content={
                        "error": "This file appears to be already downloaded.",
                        "duplicate_job": duplicate,
                    },
                )

        settings = storage.get_download_settings()
        effective_chunk_count = payload.chunk_count or settings["default_chunk_count"]
        destination_subpath = media_plan["destination_subpath"]
        resolved_output_dir = media_plan["resolved_output_dir"]

        job = storage.enqueue_download_job(
            detail_url=detail_url,
            file_id=file_id,
            title=title,
            preferred_mode=payload.preferred_mode,
            output_dir=resolved_output_dir,
            priority=payload.priority,
            chunk_count=effective_chunk_count,
            media_kind=media.media_kind,
            is_kids=media.is_kids,
            series_name=media.series_name,
            season_number=media.season_number,
            episode_number=media.episode_number,
            destination_subpath=destination_subpath,
            source_saved_file_id=payload.source_saved_file_id,
            delete_saved_on_complete=payload.delete_saved_on_complete,
        )
        return JSONResponse(job)
    except SdilejClientError as exc:
        return JSONResponse(status_code=400, content={"error": str(exc)})
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(status_code=500, content={"error": str(exc)})


@app.post("/api/downloads/{job_id}/classification")
def api_downloads_update_classification(job_id: int, payload: UpdateDownloadClassificationPayload):
    try:
        job = storage.get_download_job(job_id)
        if job is None:
            return JSONResponse(status_code=404, content={"error": "Job not found."})
        if job.get("status") != "queued":
            return JSONResponse(status_code=409, content={"error": "Only queued jobs can be recategorized."})

        title = (job.get("title") or "").strip() or str(job.get("detail_url", "")).rsplit("/", 1)[-1]
        next_media_kind = payload.media_kind or job.get("media_kind")
        if next_media_kind == "movie":
            next_series_name = None
            next_season_number = None
            next_episode_number = None
        else:
            next_series_name = payload.series_name if payload.series_name is not None else job.get("series_name")
            next_season_number = payload.season_number if payload.season_number is not None else job.get("season_number")
            next_episode_number = payload.episode_number if payload.episode_number is not None else job.get("episode_number")

        plan = _build_media_plan(
            title=title,
            media_kind=next_media_kind,
            is_kids=payload.is_kids if payload.is_kids is not None else job.get("is_kids"),
            series_name=next_series_name,
            season_number=next_season_number,
            episode_number=next_episode_number,
        )
        if plan["requires_confirmation"]:
            return JSONResponse(
                status_code=409,
                content={
                    "error": "Destination is uncertain. Confirm media classification first.",
                    "requires_confirmation": True,
                    "classification": plan["classification"].to_dict(),
                    "destination_subpath": plan["destination_subpath"],
                },
            )

        changed = storage.update_download_job_classification(
            job_id,
            media_kind=plan["classification"].media_kind,
            is_kids=plan["classification"].is_kids,
            series_name=plan["classification"].series_name,
            season_number=plan["classification"].season_number,
            episode_number=plan["classification"].episode_number,
            output_dir=plan["resolved_output_dir"],
            destination_subpath=plan["destination_subpath"],
        )
        if not changed:
            return JSONResponse(status_code=409, content={"error": "Job could not be updated."})
        updated = storage.get_download_job(job_id)
        return JSONResponse(updated or {"updated": True, "job_id": job_id})
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(status_code=500, content={"error": str(exc)})


@app.post("/api/downloads/{job_id}/cancel")
def api_downloads_cancel(job_id: int):
    try:
        changed = storage.cancel_download_job(job_id, complete=False)
        if not changed:
            return JSONResponse(status_code=404, content={"error": "Job not found or not cancelable."})
        return JSONResponse({"canceled": True, "job_id": job_id})
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(status_code=500, content={"error": str(exc)})


@app.post("/api/downloads/{job_id}/cancel-complete")
def api_downloads_cancel_complete(job_id: int):
    try:
        changed = storage.cancel_download_job(job_id, complete=True)
        if not changed:
            return JSONResponse(status_code=404, content={"error": "Job not found or not cancelable."})
        return JSONResponse({"canceled": True, "complete": True, "job_id": job_id})
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(status_code=500, content={"error": str(exc)})


@app.post("/api/downloads/{job_id}/retry")
def api_downloads_retry(job_id: int):
    try:
        changed = storage.retry_download_job(job_id)
        if not changed:
            return JSONResponse(status_code=404, content={"error": "Job not found or not retryable."})
        return JSONResponse({"retried": True, "job_id": job_id})
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(status_code=500, content={"error": str(exc)})


@app.delete("/api/downloads/{job_id}")
def api_downloads_delete(job_id: int, with_data: bool = Query(default=False)):
    try:
        result = storage.delete_download_job(job_id, with_data=with_data)
        if result is None:
            return JSONResponse(status_code=404, content={"error": "Job not found."})
        return JSONResponse(result)
    except ValueError as exc:
        return JSONResponse(status_code=409, content={"error": str(exc)})
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(status_code=500, content={"error": str(exc)})


@app.post("/api/downloads/{job_id}/priority")
def api_downloads_priority(job_id: int, payload: UpdatePriorityPayload):
    try:
        changed = storage.set_download_priority(job_id, payload.priority)
        if not changed:
            return JSONResponse(status_code=404, content={"error": "Job not found or priority cannot be changed."})
        return JSONResponse({"updated": True, "job_id": job_id, "priority": payload.priority})
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(status_code=500, content={"error": str(exc)})


@app.post("/api/downloads/{job_id}/top")
def api_downloads_move_top(job_id: int):
    try:
        changed = storage.move_download_job_to_top(job_id)
        if not changed:
            return JSONResponse(status_code=404, content={"error": "Job not found or not queued."})
        return JSONResponse({"moved_to_top": True, "job_id": job_id})
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(status_code=500, content={"error": str(exc)})


@app.post("/api/downloads/clear")
def api_downloads_clear(payload: ClearDownloadsPayload):
    try:
        deleted = storage.delete_download_jobs(statuses=payload.statuses)
        return JSONResponse({"deleted": deleted, "statuses": payload.statuses})
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(status_code=500, content={"error": str(exc)})


@app.get("/api/autocomplete")
def api_autocomplete(
    q: str = Query(..., min_length=1, max_length=200),
    limit: int = Query(default=10, ge=1, le=30),
):
    try:
        suggestions = client.autocomplete(term=q, limit=limit)
        return JSONResponse({"q": q, "suggestions": suggestions})
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(status_code=500, content={"error": str(exc)})


@app.get("/healthz")
def healthcheck():
    return {"status": "ok", "worker_alive": worker.is_alive()}
