from __future__ import annotations

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse

from ..main import (
    AccountPayload,
    ClearDownloadsPayload,
    DownloadSettingsPayload,
    EnqueueDownloadPayload,
    LibraryPathsPayload,
    MediaClassificationPayload,
    UpdateDownloadClassificationPayload,
    UpdatePriorityPayload,
    _build_media_plan,
    _extract_file_id,
    _get_services,
    _normalize_detail_url,
)
from ..sdilej_client import SdilejClient, SdilejClientError

router = APIRouter()


@router.get("/api/account")
def api_account_get(request: Request):
    credentials = _get_services(request).storage.get_account_credentials()
    if not credentials:
        return JSONResponse({"configured": False, "login": None})
    return JSONResponse({"configured": True, "login": credentials[0]})


@router.post("/api/account")
def api_account_set(request: Request, payload: AccountPayload):
    try:
        services = _get_services(request)
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

        services.storage.set_account_credentials(login_value, payload.password)
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


@router.delete("/api/account")
def api_account_delete(request: Request):
    _get_services(request).storage.clear_account_credentials()
    return JSONResponse({"cleared": True})


@router.get("/api/downloads")
def api_downloads_list(
    request: Request,
    limit: int = Query(default=200, ge=1, le=1000),
    status: str | None = Query(default=None),
):
    try:
        services = _get_services(request)
        jobs = services.storage.list_download_jobs(limit=limit, status=status)
        return JSONResponse({"items": jobs, "summary": services.storage.get_download_summary(), "worker_alive": services.worker.is_alive()})
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(status_code=500, content={"error": str(exc)})


@router.get("/api/downloads/settings")
def api_download_settings_get(request: Request):
    try:
        settings = _get_services(request).storage.get_download_settings()
        return JSONResponse(settings)
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(status_code=500, content={"error": str(exc)})


@router.post("/api/downloads/settings")
def api_download_settings_set(request: Request, payload: DownloadSettingsPayload):
    try:
        services = _get_services(request)
        settings = services.storage.set_download_settings(
            max_concurrent_jobs=payload.max_concurrent_jobs,
            default_chunk_count=payload.default_chunk_count,
            bandwidth_limit_kbps=payload.bandwidth_limit_kbps,
        )
        services.worker.configure(
            max_concurrent_jobs=settings["max_concurrent_jobs"],
            default_chunk_count=settings["default_chunk_count"],
            bandwidth_limit_kbps=settings["bandwidth_limit_kbps"],
        )
        return JSONResponse(settings)
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(status_code=500, content={"error": str(exc)})


@router.get("/api/downloads/library-paths")
def api_library_paths_get(request: Request):
    try:
        return JSONResponse(_get_services(request).storage.get_library_paths())
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(status_code=500, content={"error": str(exc)})


@router.post("/api/downloads/library-paths")
def api_library_paths_set(request: Request, payload: LibraryPathsPayload):
    try:
        paths = _get_services(request).storage.set_library_paths(
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


@router.post("/api/media/classify")
def api_media_classify(request: Request, payload: MediaClassificationPayload):
    try:
        plan = _build_media_plan(
            title=payload.title,
            media_kind=payload.media_kind,
            is_kids=payload.is_kids,
            series_name=payload.series_name,
            season_number=payload.season_number,
            episode_number=payload.episode_number,
            services=_get_services(request),
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


@router.post("/api/downloads")
def api_downloads_enqueue(request: Request, payload: EnqueueDownloadPayload):
    try:
        services = _get_services(request)
        detail_url = _normalize_detail_url(payload.detail_url)
        file_id = payload.file_id if payload.file_id is not None else _extract_file_id(detail_url)
        title = payload.title.strip() if payload.title else None

        if file_id is None or title is None:
            probe = services.client.probe_detail(detail_url=detail_url, run_preflight=False)
            file_id = file_id if file_id is not None else probe.file_id
            title = title or probe.title

        saved_candidate = None
        if payload.source_saved_file_id is not None:
            saved_candidate = services.storage.get_saved_candidate(payload.source_saved_file_id)

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
            services=services,
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

        duplicate = services.storage.find_duplicate_download(detail_url=detail_url, file_id=file_id)
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

        settings = services.storage.get_download_settings()
        effective_chunk_count = payload.chunk_count or settings["default_chunk_count"]
        destination_subpath = media_plan["destination_subpath"]
        resolved_output_dir = media_plan["resolved_output_dir"]

        job = services.storage.enqueue_download_job(
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


@router.post("/api/downloads/{job_id}/classification")
def api_downloads_update_classification(request: Request, job_id: int, payload: UpdateDownloadClassificationPayload):
    try:
        services = _get_services(request)
        job = services.storage.get_download_job(job_id)
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
            services=services,
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

        changed = services.storage.update_download_job_classification(
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
        updated = services.storage.get_download_job(job_id)
        return JSONResponse(updated or {"updated": True, "job_id": job_id})
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(status_code=500, content={"error": str(exc)})


@router.post("/api/downloads/{job_id}/cancel")
def api_downloads_cancel(request: Request, job_id: int):
    try:
        changed = _get_services(request).storage.cancel_download_job(job_id, complete=False)
        if not changed:
            return JSONResponse(status_code=404, content={"error": "Job not found or not cancelable."})
        return JSONResponse({"canceled": True, "job_id": job_id})
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(status_code=500, content={"error": str(exc)})


@router.post("/api/downloads/{job_id}/cancel-complete")
def api_downloads_cancel_complete(request: Request, job_id: int):
    try:
        changed = _get_services(request).storage.cancel_download_job(job_id, complete=True)
        if not changed:
            return JSONResponse(status_code=404, content={"error": "Job not found or not cancelable."})
        return JSONResponse({"canceled": True, "complete": True, "job_id": job_id})
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(status_code=500, content={"error": str(exc)})


@router.post("/api/downloads/{job_id}/retry")
def api_downloads_retry(request: Request, job_id: int):
    try:
        changed = _get_services(request).storage.retry_download_job(job_id)
        if not changed:
            return JSONResponse(status_code=404, content={"error": "Job not found or not retryable."})
        return JSONResponse({"retried": True, "job_id": job_id})
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(status_code=500, content={"error": str(exc)})


@router.delete("/api/downloads/{job_id}")
def api_downloads_delete(request: Request, job_id: int, with_data: bool = Query(default=False)):
    try:
        result = _get_services(request).storage.delete_download_job(job_id, with_data=with_data)
        if result is None:
            return JSONResponse(status_code=404, content={"error": "Job not found."})
        return JSONResponse(result)
    except ValueError as exc:
        return JSONResponse(status_code=409, content={"error": str(exc)})
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(status_code=500, content={"error": str(exc)})


@router.post("/api/downloads/{job_id}/priority")
def api_downloads_priority(request: Request, job_id: int, payload: UpdatePriorityPayload):
    try:
        changed = _get_services(request).storage.set_download_priority(job_id, payload.priority)
        if not changed:
            return JSONResponse(status_code=404, content={"error": "Job not found or priority cannot be changed."})
        return JSONResponse({"updated": True, "job_id": job_id, "priority": payload.priority})
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(status_code=500, content={"error": str(exc)})


@router.post("/api/downloads/{job_id}/top")
def api_downloads_move_top(request: Request, job_id: int):
    try:
        changed = _get_services(request).storage.move_download_job_to_top(job_id)
        if not changed:
            return JSONResponse(status_code=404, content={"error": "Job not found or not queued."})
        return JSONResponse({"moved_to_top": True, "job_id": job_id})
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(status_code=500, content={"error": str(exc)})


@router.post("/api/downloads/clear")
def api_downloads_clear(request: Request, payload: ClearDownloadsPayload):
    try:
        deleted = _get_services(request).storage.delete_download_jobs(statuses=payload.statuses)
        return JSONResponse({"deleted": deleted, "statuses": payload.statuses})
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(status_code=500, content={"error": str(exc)})
