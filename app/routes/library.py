from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from ..diagnostics import error_response
from ..main import (
    _build_tv_lookup_payload,
    _get_services,
    _list_downloaded_tv_episode_files,
    _resolve_library_root,
    _resolve_tv_show_local_context,
)
from ..tvmaze_client import TvMazeClientError

router = APIRouter()


class TvMissingPayload(BaseModel):
    show_name: str = Field(min_length=1, max_length=200)


def _list_tv_show_dirs(root: Path, *, q: str, limit: int) -> list[str]:
    if not root.exists() or not root.is_dir():
        return []
    query = q.strip().lower()
    items: list[str] = []
    for child in sorted(root.iterdir(), key=lambda path: path.name.lower()):
        if not child.is_dir():
            continue
        name = child.name.strip()
        if not name:
            continue
        if query and query not in name.lower():
            continue
        items.append(name)
        if len(items) >= limit:
            break
    return items


def _library_error(
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


@router.get("/api/library/tv/shows")
def api_library_tv_shows(
    request: Request,
    q: str = Query(default="", max_length=200),
    is_kids: bool = Query(default=False),
    limit: int = Query(default=12, ge=1, le=100),
):
    try:
        library_paths = _get_services(request).storage.get_library_paths()
        root_key = "kids_tv_dir" if is_kids else "tv_dir"
        root = _resolve_library_root(str(library_paths.get(root_key) or ("kids/tv" if is_kids else "tv")))
        return JSONResponse({"items": _list_tv_show_dirs(root, q=q, limit=limit)})
    except Exception as exc:  # noqa: BLE001
        return _library_error(
            request,
            status_code=500,
            error="Failed to list local TV shows.",
            error_code="library_tv_shows_failed",
            hint="Retry the request or check the configured TV library folders.",
            retryable=True,
            details=str(exc),
        )


@router.post("/api/library/tv/missing")
def api_library_tv_missing(request: Request, payload: TvMissingPayload):
    try:
        services = _get_services(request)
        show, seasons, title_metadata = _build_tv_lookup_payload(payload.show_name, services=services)
        local_context = _resolve_tv_show_local_context(
            str(show.get("name") or payload.show_name),
            title_metadata=title_metadata,
            services=services,
        )

        season_rows: dict[int, list[dict]] = defaultdict(list)
        total_episodes = 0
        downloaded_episodes = 0
        for season in seasons:
            for episode in season.get("episodes") or []:
                season_number = int(episode["season"])
                episode_number = int(episode["number"])
                downloaded_files = _list_downloaded_tv_episode_files(
                    local_context,
                    season_number=season_number,
                    episode_number=episode_number,
                )
                downloaded = bool(downloaded_files)
                total_episodes += 1
                if downloaded:
                    downloaded_episodes += 1
                season_rows[season_number].append(
                    {
                        "episode_code": episode["episode_code"],
                        "season_number": season_number,
                        "episode_number": episode_number,
                        "episode_name": episode.get("name"),
                        "airdate": episode.get("airdate"),
                        "status": "downloaded" if downloaded else "missing",
                        "downloaded_files": downloaded_files,
                    }
                )

        grouped_seasons = []
        for season_number in sorted(season_rows):
            episodes = season_rows[season_number]
            downloaded_count = sum(1 for item in episodes if item["status"] == "downloaded")
            grouped_seasons.append(
                {
                    "season_number": season_number,
                    "episode_count": len(episodes),
                    "downloaded_episodes": downloaded_count,
                    "missing_episodes": len(episodes) - downloaded_count,
                    "episodes": episodes,
                }
            )

        return JSONResponse(
            {
                "show": show,
                "title_metadata": title_metadata,
                "local_context": {
                    "series_name": local_context.get("series_name"),
                    "is_kids": bool(local_context.get("is_kids")),
                    "series_dir": str(local_context.get("series_dir") or ""),
                },
                "summary": {
                    "total_episodes": total_episodes,
                    "downloaded_episodes": downloaded_episodes,
                    "missing_episodes": total_episodes - downloaded_episodes,
                },
                "seasons": grouped_seasons,
            }
        )
    except TvMazeClientError as exc:
        return _library_error(
            request,
            status_code=404,
            error=str(exc),
            error_code="library_tv_show_not_found",
            hint="Check the show name or try an alternate title.",
            retryable=False,
        )
    except Exception as exc:  # noqa: BLE001
        return _library_error(
            request,
            status_code=500,
            error="TV library scan failed.",
            error_code="library_tv_scan_failed",
            hint="Retry the scan or check the configured media folders.",
            retryable=True,
            details=str(exc),
        )
