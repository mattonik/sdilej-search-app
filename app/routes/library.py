from __future__ import annotations

from collections import defaultdict
from pathlib import Path
import re

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


class TvFolderDeepScanPayload(BaseModel):
    folder_name: str = Field(min_length=1, max_length=200)
    is_kids: bool = False


class MusicFolderDeepScanPayload(BaseModel):
    artist_name: str = Field(min_length=1, max_length=200)
    album_name: str | None = Field(default=None, max_length=200)


_TV_SCAN_MEDIA_EXTENSIONS = {".mkv", ".mp4", ".avi", ".mov", ".m4v", ".wmv", ".ts", ".m2ts", ".webm"}
_TV_SCAN_IGNORED_MARKERS = (".part", ".partial", ".tmp", ".crdownload", ".download")
_TV_EPISODE_TOKEN_RE = re.compile(r"(?<![A-Za-z0-9])S(?P<season>\d{1,2})E(?P<episode>\d{1,3})(?!\d)", re.IGNORECASE)
_MUSIC_AUDIO_EXTENSIONS = {".mp3", ".flac", ".m4a", ".aac", ".ogg", ".opus", ".wav", ".wma"}


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


def _tv_library_root(request: Request, *, is_kids: bool) -> Path:
    library_paths = _get_services(request).storage.get_library_paths()
    root_key = "kids_tv_dir" if is_kids else "tv_dir"
    return _resolve_library_root(str(library_paths.get(root_key) or ("kids/tv" if is_kids else "tv")))


def _music_library_root(request: Request) -> Path:
    library_paths = _get_services(request).storage.get_library_paths()
    return _resolve_library_root(str(library_paths.get("music_dir") or "music"))


def _list_tv_folders(root: Path) -> list[dict]:
    if not root.exists() or not root.is_dir():
        return []
    folders: list[dict] = []
    for child in sorted(root.iterdir(), key=lambda path: path.name.lower()):
        if not child.is_dir() or not child.name.strip():
            continue
        season_count = sum(1 for item in child.iterdir() if item.is_dir() and re.fullmatch(r"S\d{1,3}", item.name, re.IGNORECASE))
        folders.append({"folder_name": child.name, "season_count": season_count})
    return folders


def _safe_tv_folder(root: Path, folder_name: str) -> Path:
    clean_name = folder_name.strip()
    if not clean_name or Path(clean_name).name != clean_name or clean_name in {".", ".."}:
        raise ValueError("Select a top-level TV folder.")
    candidate = (root / clean_name).resolve()
    root_resolved = root.resolve()
    try:
        candidate.relative_to(root_resolved)
    except ValueError as exc:
        raise ValueError("Folder is outside the configured TV library root.") from exc
    if candidate == root_resolved or not candidate.is_dir():
        raise ValueError("TV folder was not found.")
    return candidate


def _deep_scan_tv_folder(folder: Path) -> dict:
    episodes: dict[tuple[int, int], dict] = {}
    media_files: list[dict] = []
    for path in sorted(folder.rglob("*"), key=lambda item: str(item).lower()):
        if not path.is_file() or path.suffix.lower() not in _TV_SCAN_MEDIA_EXTENSIONS:
            continue
        name_lower = path.name.lower()
        if any(marker in name_lower for marker in _TV_SCAN_IGNORED_MARKERS):
            continue
        relative_name = str(path.relative_to(folder))
        tokens = list(_TV_EPISODE_TOKEN_RE.finditer(path.name))
        codes = [f"S{int(match.group('season')):02d}E{int(match.group('episode')):02d}" for match in tokens]
        media_files.append({"name": relative_name, "episode_codes": codes})
        for match, code in zip(tokens, codes):
            key = (int(match.group("season")), int(match.group("episode")))
            episodes.setdefault(key, {"season_number": key[0], "episode_number": key[1], "episode_code": code, "files": []})
            episodes[key]["files"].append(relative_name)
    return {
        "folder_name": folder.name,
        "media_file_count": len(media_files),
        "episode_count": len(episodes),
        "episodes": [episodes[key] for key in sorted(episodes)],
        "files": media_files[:500],
        "files_truncated": len(media_files) > 500,
    }


def _list_music_folders(root: Path) -> list[dict]:
    if not root.exists() or not root.is_dir():
        return []
    artists: list[dict] = []
    for artist in sorted(root.iterdir(), key=lambda path: path.name.lower()):
        if not artist.is_dir() or not artist.name.strip():
            continue
        albums = []
        for album in sorted(artist.iterdir(), key=lambda path: path.name.lower()):
            if not album.is_dir() or not album.name.strip():
                continue
            audio_count = sum(1 for item in album.rglob("*") if item.is_file() and item.suffix.lower() in _MUSIC_AUDIO_EXTENSIONS)
            albums.append({"album_name": album.name, "audio_file_count": audio_count})
        direct_audio_count = sum(1 for item in artist.iterdir() if item.is_file() and item.suffix.lower() in _MUSIC_AUDIO_EXTENSIONS)
        artists.append({"artist_name": artist.name, "album_count": len(albums), "direct_audio_file_count": direct_audio_count, "albums": albums})
    return artists


def _safe_music_folder(root: Path, artist_name: str, album_name: str | None = None) -> Path:
    names = [artist_name.strip()]
    if album_name:
        names.append(album_name.strip())
    if any(not name or Path(name).name != name or name in {".", ".."} for name in names):
        raise ValueError("Select an artist or album from the configured music library list.")
    candidate = root.joinpath(*names).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError("Folder is outside the configured music library root.") from exc
    if candidate == root.resolve() or not candidate.is_dir():
        raise ValueError("Music folder was not found.")
    return candidate


def _deep_scan_music_folder(folder: Path, *, artist_name: str, album_name: str | None) -> dict:
    files = []
    total_bytes = 0
    for path in sorted(folder.rglob("*"), key=lambda item: str(item).lower()):
        if not path.is_file() or path.suffix.lower() not in _MUSIC_AUDIO_EXTENSIONS:
            continue
        size = path.stat().st_size
        total_bytes += size
        files.append({"name": str(path.relative_to(folder)), "size_bytes": size, "extension": path.suffix.lower()})
    query = " ".join(item for item in [artist_name.strip(), album_name.strip() if album_name else ""] if item)
    return {
        "artist_name": artist_name,
        "album_name": album_name,
        "search_query": query,
        "audio_file_count": len(files),
        "total_size_bytes": total_bytes,
        "files": files[:500],
        "files_truncated": len(files) > 500,
    }


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
        root = _tv_library_root(request, is_kids=is_kids)
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


@router.get("/api/library/tv/folders")
def api_library_tv_folders(request: Request, is_kids: bool = Query(default=False)):
    try:
        root = _tv_library_root(request, is_kids=is_kids)
        return JSONResponse({"is_kids": is_kids, "items": _list_tv_folders(root)})
    except Exception as exc:  # noqa: BLE001
        return _library_error(
            request,
            status_code=500,
            error="Failed to scan local TV folders.",
            error_code="library_tv_folders_failed",
            hint="Retry the scan or check the configured TV library folders.",
            retryable=True,
            details=str(exc),
        )


@router.post("/api/library/tv/folders/deep-scan")
def api_library_tv_folder_deep_scan(request: Request, payload: TvFolderDeepScanPayload):
    try:
        root = _tv_library_root(request, is_kids=payload.is_kids)
        folder = _safe_tv_folder(root, payload.folder_name)
        report = _deep_scan_tv_folder(folder)
        report["is_kids"] = payload.is_kids
        return JSONResponse(report)
    except ValueError as exc:
        return _library_error(
            request,
            status_code=400,
            error=str(exc),
            error_code="library_tv_folder_invalid",
            hint="Select a folder from the configured TV library list.",
            retryable=False,
        )
    except Exception as exc:  # noqa: BLE001
        return _library_error(
            request,
            status_code=500,
            error="TV folder deep scan failed.",
            error_code="library_tv_folder_deep_scan_failed",
            hint="Retry the scan or check folder permissions.",
            retryable=True,
            details=str(exc),
        )


@router.get("/api/library/music/folders")
def api_library_music_folders(request: Request):
    try:
        root = _music_library_root(request)
        return JSONResponse({"items": _list_music_folders(root)})
    except Exception as exc:  # noqa: BLE001
        return _library_error(
            request,
            status_code=500,
            error="Failed to scan local music folders.",
            error_code="library_music_folders_failed",
            hint="Retry the scan or check the configured music library folder.",
            retryable=True,
            details=str(exc),
        )


@router.post("/api/library/music/folders/deep-scan")
def api_library_music_folder_deep_scan(request: Request, payload: MusicFolderDeepScanPayload):
    try:
        root = _music_library_root(request)
        folder = _safe_music_folder(root, payload.artist_name, payload.album_name)
        return JSONResponse(_deep_scan_music_folder(folder, artist_name=payload.artist_name, album_name=payload.album_name))
    except ValueError as exc:
        return _library_error(
            request,
            status_code=400,
            error=str(exc),
            error_code="library_music_folder_invalid",
            hint="Select an artist or album from the configured music library list.",
            retryable=False,
        )
    except Exception as exc:  # noqa: BLE001
        return _library_error(
            request,
            status_code=500,
            error="Music folder deep scan failed.",
            error_code="library_music_folder_deep_scan_failed",
            hint="Retry the scan or check folder permissions.",
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
