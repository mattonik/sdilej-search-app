from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from ..diagnostics import error_response
from ..main import (
    TvEpisodeSearchPayload,
    TvLookupPayload,
    TvSeasonSearchPayload,
    _annotate_downloaded_tv_search_items,
    _build_tv_lookup_payload,
    _coerce_title_metadata_payload,
    _get_services,
    _resolve_tv_search_alias_context,
    _resolve_tv_search_alias_sets,
    _resolve_tv_show_local_context,
    _resolve_tv_show_summary,
    _search_single_tv_episode,
    _selected_tv_search_items,
)
from ..sdilej_client import SdilejClientError
from ..tvmaze_client import TvMazeClientError

router = APIRouter()


def _tv_error(
    request: Request,
    *,
    status_code: int,
    error: str,
    error_code: str,
    hint: str | None = None,
    retryable: bool | None = None,
    details: str | None = None,
) -> JSONResponse:
    return error_response(
        request,
        status_code=status_code,
        error=error,
        error_code=error_code,
        hint=hint,
        retryable=retryable,
        details=details,
    )


@router.post("/api/tv/lookup")
def api_tv_lookup(request: Request, payload: TvLookupPayload):
    try:
        show, seasons, title_metadata = _build_tv_lookup_payload(payload.show_name, services=_get_services(request))
        aliases, search_aliases = _resolve_tv_search_alias_context(
            show_name=str(show.get("name") or payload.show_name),
            title_metadata=title_metadata,
        )
        return JSONResponse(
            {
                "show": show,
                "title_metadata": title_metadata,
                "aliases": aliases,
                "all_search_aliases": search_aliases,
                "search_aliases": search_aliases,
                "seasons": seasons,
                "season_count": len(seasons),
                "episode_count": sum(item["episode_count"] for item in seasons),
            }
        )
    except TvMazeClientError as exc:
        return _tv_error(
            request,
            status_code=404,
            error=str(exc),
            error_code="tv_lookup_not_found",
            hint="Check the show name or try a different title.",
            retryable=False,
        )
    except Exception as exc:  # noqa: BLE001
        return _tv_error(
            request,
            status_code=500,
            error="TV lookup failed.",
            error_code="tv_lookup_failed",
            hint="Retry the lookup or check the TV worker and metadata services.",
            retryable=True,
            details=str(exc),
        )


@router.post("/api/tv/search")
def api_tv_search(request: Request, payload: TvSeasonSearchPayload):
    try:
        services = _get_services(request)
        episodes = services.tv_client.get_episodes(payload.show_id)
        selected_seasons, _selected_episode_map, selected_items = _selected_tv_search_items(payload, episodes)
        show_summary = _resolve_tv_show_summary(payload.show_name, show_id=payload.show_id, services=services)
        title_metadata = payload.title_metadata or services.metadata_resolver.resolve_tv(
            payload.show_name,
            show=show_summary,
        ).to_dict()
        local_context = _resolve_tv_show_local_context(payload.show_name, title_metadata=title_metadata, services=services)
        aliases, all_search_aliases, search_aliases = _resolve_tv_search_alias_sets(
            show_name=payload.show_name,
            title_metadata=title_metadata,
            category=payload.category,
            search_client=services.client,
        )
        grouped_seasons: list[dict] = []
        for season_number in selected_seasons:
            season_items = [item for item in selected_items if int(item["season_number"]) == season_number]
            grouped_episodes: list[dict] = []

            for episode in season_items:
                grouped_episodes.append(
                    _search_single_tv_episode(
                        show_name=payload.show_name,
                        title_metadata=title_metadata,
                        aliases=aliases,
                        all_search_aliases=all_search_aliases,
                        search_aliases=search_aliases,
                        season_number=int(episode["season_number"]),
                        episode_number=int(episode["episode_number"]),
                        episode_name=episode["episode_name"],
                        airdate=episode["airdate"],
                        category=payload.category,
                        language=payload.language,
                        language_scope=payload.language_scope,
                        strict_dubbing=payload.strict_dubbing,
                        max_results_per_variant=payload.max_results_per_variant,
                        alias_mode="optimized",
                        local_context=local_context,
                        services=services,
                    )
                )

            grouped_seasons.append(
                {
                    "season_number": season_number,
                    "episode_count": len(season_items),
                    "completed_episodes": len(season_items),
                    "episodes": grouped_episodes,
                    "result_count": sum(item["result_count"] for item in grouped_episodes),
                }
            )

        return JSONResponse(
            {
                "show": show_summary.to_dict(),
                "title_metadata": title_metadata,
                "aliases": aliases,
                "all_search_aliases": all_search_aliases,
                "search_aliases": search_aliases,
                "selected_seasons": selected_seasons,
                "language": services.client.normalize_language(payload.language),
                "language_scope": payload.language_scope,
                "strict_dubbing": payload.strict_dubbing,
                "max_results_per_variant": payload.max_results_per_variant,
                "category": payload.category,
                "status": "done",
                "total_episodes": len(selected_items),
                "completed_episodes": len(selected_items),
                "result_count": sum(item["result_count"] for item in grouped_seasons),
                "seasons": grouped_seasons,
            }
        )
    except SdilejClientError as exc:
        return _tv_error(
            request,
            status_code=400,
            error=str(exc),
            error_code="tv_search_invalid_request",
            hint="Check the selected seasons, episode selection, and filters.",
            retryable=False,
        )
    except TvMazeClientError as exc:
        return _tv_error(
            request,
            status_code=404,
            error=str(exc),
            error_code="tv_show_not_found",
            hint="Verify the show name or try an alternate title.",
            retryable=False,
        )
    except Exception as exc:  # noqa: BLE001
        return _tv_error(
            request,
            status_code=500,
            error="TV search failed.",
            error_code="tv_search_failed",
            hint="Retry the search or check the TV worker health.",
            retryable=True,
            details=str(exc),
        )


@router.post("/api/tv/search-episode")
def api_tv_search_episode(request: Request, payload: TvEpisodeSearchPayload):
    try:
        services = _get_services(request)
        show_summary = _resolve_tv_show_summary(payload.show_name, show_id=payload.show_id, services=services)
        title_metadata_obj = _coerce_title_metadata_payload(payload.title_metadata)
        if title_metadata_obj is None:
            title_metadata_obj = services.metadata_resolver.resolve_tv(
                payload.show_name,
                show=show_summary,
            )
        title_metadata = title_metadata_obj.to_dict()
        local_context = _resolve_tv_show_local_context(payload.show_name, title_metadata=title_metadata, services=services)
        aliases, all_search_aliases, search_aliases = _resolve_tv_search_alias_sets(
            show_name=payload.show_name,
            title_metadata=title_metadata,
            category=payload.category,
            search_client=None if payload.alias_mode == "all" else services.client,
        )
        episode = _search_single_tv_episode(
            show_name=payload.show_name,
            title_metadata=title_metadata,
            aliases=aliases,
            all_search_aliases=all_search_aliases,
            search_aliases=search_aliases,
            season_number=payload.season_number,
            episode_number=payload.episode_number,
            episode_name=payload.episode_name,
            airdate=payload.airdate,
            category=payload.category,
            language=payload.language,
            language_scope=payload.language_scope,
            strict_dubbing=payload.strict_dubbing,
            max_results_per_variant=payload.max_results_per_variant,
            alias_mode=payload.alias_mode,
            force_search=payload.force_search,
            local_context=local_context,
            services=services,
        )
        return JSONResponse(
            {
                "show": show_summary.to_dict(),
                "title_metadata": title_metadata,
                "aliases": aliases,
                "all_search_aliases": all_search_aliases,
                "search_aliases": search_aliases,
                "max_results_per_variant": payload.max_results_per_variant,
                "episode": episode,
            }
        )
    except SdilejClientError as exc:
        return _tv_error(
            request,
            status_code=400,
            error=str(exc),
            error_code="tv_episode_search_invalid_request",
            hint="Check the season, episode, and filter inputs.",
            retryable=False,
        )
    except TvMazeClientError as exc:
        return _tv_error(
            request,
            status_code=404,
            error=str(exc),
            error_code="tv_show_not_found",
            hint="Verify the show name or try an alternate title.",
            retryable=False,
        )
    except Exception as exc:  # noqa: BLE001
        return _tv_error(
            request,
            status_code=500,
            error="Episode search failed.",
            error_code="tv_episode_search_failed",
            hint="Retry the episode search or inspect the TV worker health.",
            retryable=True,
            details=str(exc),
        )


@router.post("/api/tv/search-jobs")
def api_tv_search_jobs_create(request: Request, payload: TvSeasonSearchPayload):
    try:
        services = _get_services(request)
        episodes = services.tv_client.get_episodes(payload.show_id)
        selected_seasons, _selected_episode_map, selected_items = _selected_tv_search_items(payload, episodes)
        show_summary = _resolve_tv_show_summary(payload.show_name, show_id=payload.show_id, services=services)
        title_metadata_obj = _coerce_title_metadata_payload(payload.title_metadata)
        if title_metadata_obj is None:
            title_metadata_obj = services.metadata_resolver.resolve_tv(
                payload.show_name,
                show=show_summary,
            )
        title_metadata = title_metadata_obj.to_dict()
        local_context = _resolve_tv_show_local_context(payload.show_name, title_metadata=title_metadata, services=services)
        annotated_items = _annotate_downloaded_tv_search_items(selected_items, local_context=local_context)
        aliases, all_search_aliases, search_aliases = _resolve_tv_search_alias_sets(
            show_name=payload.show_name,
            title_metadata=title_metadata,
            category=payload.category,
            search_client=services.client,
        )
        job = services.storage.enqueue_tv_search_job(
            show=show_summary.to_dict(),
            title_metadata=title_metadata,
            aliases=aliases,
            search_aliases=search_aliases,
            selected_seasons=selected_seasons,
            episodes_by_season=payload.episodes_by_season,
            category=payload.category,
            language=services.client.normalize_language(payload.language),
            language_scope=payload.language_scope,
            strict_dubbing=payload.strict_dubbing,
            max_results_per_variant=payload.max_results_per_variant,
            episodes=annotated_items,
        )
        response_payload = dict(job)
        response_payload["all_search_aliases"] = all_search_aliases
        return JSONResponse(response_payload)
    except SdilejClientError as exc:
        return _tv_error(
            request,
            status_code=400,
            error=str(exc),
            error_code="tv_search_invalid_request",
            hint="Check the selected seasons, episode selection, and filters.",
            retryable=False,
        )
    except TvMazeClientError as exc:
        return _tv_error(
            request,
            status_code=404,
            error=str(exc),
            error_code="tv_show_not_found",
            hint="Verify the show name or try an alternate title.",
            retryable=False,
        )
    except Exception as exc:  # noqa: BLE001
        return _tv_error(
            request,
            status_code=500,
            error="TV search job creation failed.",
            error_code="tv_search_job_create_failed",
            hint="Retry the search or check the TV worker health.",
            retryable=True,
            details=str(exc),
        )


@router.get("/api/tv/search-jobs")
def api_tv_search_jobs_list(
    request: Request,
    limit: int = 50,
    status: str | None = None,
):
    try:
        return JSONResponse({"items": _get_services(request).storage.list_tv_search_jobs(limit=limit, status=status)})
    except Exception as exc:  # noqa: BLE001
        return _tv_error(
            request,
            status_code=500,
            error="TV search jobs listing failed.",
            error_code="tv_search_jobs_list_failed",
            hint="Retry the request or check the storage layer.",
            retryable=True,
            details=str(exc),
        )


@router.get("/api/tv/search-jobs/{job_id}")
def api_tv_search_jobs_get(request: Request, job_id: int):
    try:
        job = _get_services(request).storage.get_tv_search_job(job_id)
        if job is None:
            return _tv_error(
                request,
                status_code=404,
                error="TV search job not found.",
                error_code="tv_search_job_not_found",
                hint="Refresh the queue or re-run the TV search.",
                retryable=False,
            )
        _aliases, all_search_aliases = _resolve_tv_search_alias_context(
            show_name=str((job.get("show") or {}).get("name") or job.get("show_name") or ""),
            title_metadata=job.get("title_metadata"),
        )
        job["all_search_aliases"] = all_search_aliases
        return JSONResponse(job)
    except Exception as exc:  # noqa: BLE001
        return _tv_error(
            request,
            status_code=500,
            error="TV search job refresh failed.",
            error_code="tv_search_job_refresh_failed",
            hint="Retry the refresh or check the TV worker health.",
            retryable=True,
            details=str(exc),
        )


@router.post("/api/tv/search-jobs/{job_id}/cancel")
def api_tv_search_jobs_cancel(request: Request, job_id: int):
    try:
        changed = _get_services(request).storage.cancel_tv_search_job(job_id)
        if not changed:
            return _tv_error(
                request,
                status_code=404,
                error="TV search job not found or not cancelable.",
                error_code="tv_search_job_not_cancelable",
                hint="Refresh the queue and try again.",
                retryable=False,
            )
        return JSONResponse({"canceled": True, "job_id": job_id})
    except Exception as exc:  # noqa: BLE001
        return _tv_error(
            request,
            status_code=500,
            error="TV search job cancellation failed.",
            error_code="tv_search_job_cancel_failed",
            hint="Retry the action or check the storage layer.",
            retryable=True,
            details=str(exc),
        )
