from __future__ import annotations

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


class UpdatePriorityPayload(BaseModel):
    priority: int = Field(default=0, ge=-1000, le=1000)


class ClearDownloadsPayload(BaseModel):
    statuses: list[Literal["done", "failed", "canceled"]] = Field(default_factory=lambda: ["done", "failed", "canceled"])


@app.on_event("startup")
def on_startup() -> None:
    storage.init_db()
    storage.recover_download_queue_after_restart()
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

        job = storage.enqueue_download_job(
            detail_url=detail_url,
            file_id=file_id,
            title=title,
            preferred_mode=payload.preferred_mode,
            output_dir=payload.output_dir,
            priority=payload.priority,
        )
        return JSONResponse(job)
    except SdilejClientError as exc:
        return JSONResponse(status_code=400, content={"error": str(exc)})
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
