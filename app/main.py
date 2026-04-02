from __future__ import annotations

from collections import defaultdict
import os
import re
from pathlib import Path
from typing import Literal
from urllib.parse import urljoin, urlparse

from fastapi import APIRouter, FastAPI, Query, Request
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
from .models import Category, LanguageScope, SearchResponse, SortMode, TitleMetadata
from .sdilej_client import BASE_URL, SdilejClient, SdilejClientError
from .search_utils import (
    aggregate_query_results,
    build_episode_query_variants,
    build_tv_episode_result_scorer,
    build_tv_search_aliases,
    search_tv_episode_results,
    select_effective_tv_search_aliases,
    strip_internal_result_fields,
)
from .storage import Storage
from .title_metadata import TitleMetadataResolver, normalize_alias_key, parse_year
from .tv_search_worker import TvSearchWorker
from .tvmaze_client import TvEpisode, TvMazeClient, TvMazeClientError, TvShowSummary

BASE_DIR = Path(__file__).resolve().parent
_FILE_ID_RE = re.compile(r"^/(\d+)/")
_MOVIE_INFO_FILE_EXT_RE = re.compile(r"\.[A-Za-z0-9]{2,5}$")
_MOVIE_INFO_SEPARATOR_RE = re.compile(r"[._]+")
_MOVIE_INFO_BRACKET_RE = re.compile(r"[\[\](){}]+")
_TV_EPISODE_TOKEN_TEMPLATE = "s{season:02d}e{episode:02d}"
_TV_MEDIA_EXTENSIONS = {
    ".mkv",
    ".mp4",
    ".avi",
    ".mov",
    ".m4v",
    ".wmv",
    ".ts",
    ".m2ts",
    ".webm",
}
_TV_IGNORED_EXTENSIONS = {
    ".srt",
    ".sub",
    ".ass",
    ".ssa",
    ".txt",
    ".nfo",
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".webp",
}
_TV_TEMP_NAME_MARKERS = (".part", ".partial", ".tmp", ".crdownload", ".download")
_MOVIE_INFO_NOISE_TOKENS = {
    "1080p",
    "2160p",
    "480p",
    "4k",
    "720p",
    "aac",
    "ac3",
    "atmos",
    "bluray",
    "brrip",
    "cam",
    "csfd",
    "cz",
    "dab",
    "dabing",
    "dl",
    "dts",
    "dub",
    "dubbing",
    "dv",
    "dvdrip",
    "hdr",
    "hdrip",
    "hevc",
    "hvec",
    "imax",
    "mkv",
    "multi",
    "proper",
    "repack",
    "remux",
    "sk",
    "sub",
    "subs",
    "subtitle",
    "subtitles",
    "tit",
    "titulky",
    "uhd",
    "webrip",
    "webdl",
    "x264",
    "x265",
}

templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
router = APIRouter()

client = SdilejClient()
tv_client = TvMazeClient()
storage = Storage()
worker = DownloadWorker(storage=storage)
metadata_resolver = TitleMetadataResolver(storage=storage, tv_client=tv_client)
tv_search_worker = TvSearchWorker(storage=storage)

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


class TvLookupPayload(BaseModel):
    show_name: str = Field(min_length=1, max_length=200)


class MovieLookupPayload(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    year: int | None = Field(default=None, ge=1900, le=2099)


class MovieInfoLinkPayload(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    primary_year: int | None = Field(default=None, ge=1900, le=2099)
    search_query: str | None = Field(default=None, max_length=200)
    search_title: str | None = Field(default=None, max_length=200)


class TvSeasonSearchPayload(BaseModel):
    show_id: int = Field(ge=1)
    show_name: str = Field(min_length=1, max_length=200)
    seasons: list[int] = Field(default_factory=list)
    episodes_by_season: dict[str, list[int]] = Field(default_factory=dict)
    aliases: list[str] = Field(default_factory=list)
    title_metadata: dict | None = None
    category: Category = "video"
    language: str | None = Field(default=None, max_length=32)
    language_scope: LanguageScope = "any"
    strict_dubbing: bool = False
    max_results_per_variant: int = Field(default=120, ge=1, le=500)


class TvEpisodeSearchPayload(BaseModel):
    show_id: int = Field(ge=1)
    show_name: str = Field(min_length=1, max_length=200)
    season_number: int = Field(ge=1, le=99)
    episode_number: int = Field(ge=1, le=999)
    episode_name: str | None = Field(default=None, max_length=200)
    airdate: str | None = Field(default=None, max_length=32)
    aliases: list[str] = Field(default_factory=list)
    title_metadata: dict | None = None
    category: Category = "video"
    language: str | None = Field(default=None, max_length=32)
    language_scope: LanguageScope = "any"
    strict_dubbing: bool = False
    max_results_per_variant: int = Field(default=120, ge=1, le=500)
    alias_mode: Literal["optimized", "all"] = "all"
    force_search: bool = False


def _set_services(
    *,
    client_instance: SdilejClient,
    tv_client_instance: TvMazeClient,
    storage_instance: Storage,
    worker_instance: DownloadWorker,
    metadata_resolver_instance: TitleMetadataResolver,
    tv_search_worker_instance: TvSearchWorker,
) -> None:
    global client, tv_client, storage, worker, metadata_resolver, tv_search_worker
    client = client_instance
    tv_client = tv_client_instance
    storage = storage_instance
    worker = worker_instance
    metadata_resolver = metadata_resolver_instance
    tv_search_worker = tv_search_worker_instance


def create_app(
    *,
    client_instance: SdilejClient | None = None,
    tv_client_instance: TvMazeClient | None = None,
    storage_instance: Storage | None = None,
    worker_instance: DownloadWorker | None = None,
    metadata_resolver_instance: TitleMetadataResolver | None = None,
    tv_search_worker_instance: TvSearchWorker | None = None,
    start_workers: bool = True,
) -> FastAPI:
    resolved_storage = storage_instance or Storage()
    resolved_client = client_instance or SdilejClient()
    resolved_tv_client = tv_client_instance or TvMazeClient()
    resolved_worker = worker_instance or DownloadWorker(storage=resolved_storage)
    resolved_metadata_resolver = metadata_resolver_instance or TitleMetadataResolver(
        storage=resolved_storage,
        tv_client=resolved_tv_client,
    )
    resolved_tv_search_worker = tv_search_worker_instance or TvSearchWorker(storage=resolved_storage)

    _set_services(
        client_instance=resolved_client,
        tv_client_instance=resolved_tv_client,
        storage_instance=resolved_storage,
        worker_instance=resolved_worker,
        metadata_resolver_instance=resolved_metadata_resolver,
        tv_search_worker_instance=resolved_tv_search_worker,
    )

    app = FastAPI(title="Sdilej Search Proxy", version="0.1.0")
    app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
    app.include_router(router)

    def on_startup() -> None:
        resolved_storage.init_db()
        resolved_storage.recover_download_queue_after_restart()
        resolved_storage.recover_tv_search_queue_after_restart()
        settings = resolved_storage.get_download_settings()
        resolved_worker.configure(
            max_concurrent_jobs=settings["max_concurrent_jobs"],
            default_chunk_count=settings["default_chunk_count"],
            bandwidth_limit_kbps=settings["bandwidth_limit_kbps"],
        )
        if start_workers:
            resolved_worker.start()
            resolved_tv_search_worker.start()

    def on_shutdown() -> None:
        if start_workers:
            resolved_worker.stop()
            resolved_tv_search_worker.stop()

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)
    return app


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


def _compact_lookup_token(value: str) -> str:
    return normalize_alias_key(value).replace(" ", "")


def _is_movie_info_noise_token(value: str) -> bool:
    if not value:
        return False
    if value in _MOVIE_INFO_NOISE_TOKENS:
        return True
    if re.fullmatch(r"(?:19\d{2}|20\d{2})", value):
        return False
    if re.fullmatch(r"\d{3,4}p", value):
        return True
    if re.fullmatch(r"h?26[45]", value):
        return True
    if re.fullmatch(r"ddp?\d(?:\d)?", value):
        return True
    return False


def _extract_movie_info_lookup(
    *,
    title: str,
    primary_year: int | None,
    search_query: str | None,
    search_title: str | None,
) -> dict[str, str | int | None]:
    raw_title = title.strip()
    if not raw_title:
        return {"query": None, "year": primary_year, "error": "Movie title is required."}

    classification = classify_media_title(raw_title)
    if classification.media_kind == "tv":
        return {
            "query": None,
            "year": primary_year,
            "error": "This result looks like a TV episode, not a movie.",
        }

    stem = _MOVIE_INFO_FILE_EXT_RE.sub("", raw_title)
    normalized = _MOVIE_INFO_SEPARATOR_RE.sub(" ", stem)
    normalized = _MOVIE_INFO_BRACKET_RE.sub(" ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip(" -._")

    fallback_year = primary_year or parse_year(normalized)
    tokens = normalized.split()
    kept_tokens: list[str] = []
    detected_year = fallback_year

    for token in tokens:
        compact = _compact_lookup_token(token)
        if not compact:
            continue
        token_year = parse_year(token)
        if token_year is not None and compact == str(token_year):
            detected_year = detected_year or token_year
            break
        if _is_movie_info_noise_token(compact):
            if kept_tokens:
                break
            continue
        kept_tokens.append(token)

    query = " ".join(kept_tokens).strip(" -._")
    if not query:
        fallback_query = _normalize_optional_text(search_title) or _normalize_optional_text(search_query)
        if fallback_query and classify_media_title(fallback_query).media_kind != "tv":
            query = fallback_query

    if not query:
        return {
            "query": None,
            "year": detected_year,
            "error": "Could not derive a clean movie title from this result.",
        }
    return {"query": query, "year": detected_year, "error": None}


def _resolve_movie_info_link(payload: MovieInfoLinkPayload) -> dict[str, str | int | bool | None]:
    lookup = _extract_movie_info_lookup(
        title=payload.title,
        primary_year=payload.primary_year,
        search_query=payload.search_query,
        search_title=payload.search_title,
    )
    query = lookup.get("query")
    year = lookup.get("year")
    error = lookup.get("error")

    if not query:
        return {
            "found": False,
            "preferred_url": None,
            "csfd_url": None,
            "imdb_url": None,
            "resolved_title": None,
            "original_title": None,
            "year": year,
            "source": "fallback",
            "error": error or "No movie info link found for this result.",
        }

    lookup_candidates: list[str] = []
    seen_candidates: set[str] = set()

    def add_candidate(value: str | None) -> None:
        text = _normalize_optional_text(value)
        if not text:
            return
        key = normalize_alias_key(text)
        if not key or key in seen_candidates:
            return
        seen_candidates.add(key)
        lookup_candidates.append(text)

    add_candidate(str(query))
    add_candidate(payload.search_title)
    add_candidate(payload.search_query)

    year_candidates: list[int | None] = []
    if isinstance(year, int):
        year_candidates.extend([year, None])
    else:
        year_candidates.append(None)

    for candidate in lookup_candidates:
        for year_candidate in year_candidates:
            info = metadata_resolver.resolve_movie_info_links(candidate, year_candidate)
            if info.get("found"):
                info["error"] = None
                return info

    return {
        "found": False,
        "preferred_url": None,
        "csfd_url": None,
        "imdb_url": None,
        "resolved_title": None,
        "original_title": None,
        "year": year,
        "source": "fallback",
        "error": "No external movie info link was found for this result.",
    }


def _resolve_download_root() -> Path:
    configured_root = os.getenv("DOWNLOAD_DIR", "./downloads")
    return Path(configured_root).expanduser().resolve()


def _resolve_library_root(subpath: str | None) -> Path:
    safe_subpath = (subpath or "").strip().lstrip("/")
    return _resolve_download_root() / Path(safe_subpath)


def _resolve_video_metadata(query: str, release_year: int | None):
    movie_metadata = metadata_resolver.resolve_movie(query, release_year)
    tv_metadata = metadata_resolver.resolve_tv(query, year=release_year)

    movie_score = len(movie_metadata.aliases)
    tv_score = len(tv_metadata.aliases)
    if release_year is not None and movie_metadata.year == release_year:
        movie_score += 2
    if movie_metadata.canonical_title.strip().lower() == query.strip().lower():
        movie_score += 1
    if tv_metadata.canonical_title.strip().lower() == query.strip().lower():
        tv_score += 1

    return tv_metadata if tv_score > movie_score else movie_metadata


def _resolve_classification_metadata(
    *,
    title: str,
    media_kind: Literal["movie", "tv"] | None,
    series_name: str | None,
    season_number: int | None,
    episode_number: int | None,
) -> TitleMetadata | None:
    initial = classify_media_title(
        title=title,
        media_kind_override=media_kind,
        series_name_override=_normalize_optional_text(series_name),
        season_number_override=season_number,
        episode_number_override=episode_number,
    )

    try:
        if initial.media_kind == "tv":
            lookup_name = (
                _normalize_optional_text(series_name)
                or _normalize_optional_text(initial.series_name)
                or _normalize_optional_text(title)
            )
            if lookup_name:
                return metadata_resolver.resolve_tv(lookup_name, year=parse_year(title))

        if initial.media_kind == "movie":
            lookup = _extract_movie_info_lookup(
                title=title,
                primary_year=parse_year(title),
                search_query=None,
                search_title=None,
            )
            lookup_query = lookup.get("query") if isinstance(lookup.get("query"), str) else None
            lookup_year = lookup.get("year") if isinstance(lookup.get("year"), int) else None
            if lookup_query:
                return metadata_resolver.resolve_movie(lookup_query, lookup_year)
    except Exception:
        return None

    return None


def _search_files(
    *,
    query: str,
    category: Category,
    sort: SortMode,
    language: str,
    language_scope: LanguageScope,
    strict_dubbing: bool,
    release_year: int | None,
    max_results: int,
) -> SearchResponse:
    normalized_query = query.strip()
    if category != "video" or not normalized_query:
        return client.search(
            query=query,
            category=category,
            sort=sort,
            language=language,
            language_scope=language_scope,
            strict_dubbing=strict_dubbing,
            release_year=release_year,
            max_results=max_results,
        )

    title_metadata = _resolve_video_metadata(normalized_query, release_year)
    aggregated = aggregate_query_results(
        client=client,
        queries=title_metadata.aliases or [normalized_query],
        category=category,
        sort=sort,
        language=language,
        language_scope=language_scope,
        strict_dubbing=strict_dubbing,
        release_year=release_year,
        max_results_per_query=max_results,
        max_results_total=max_results,
    )
    return SearchResponse(
        query=normalized_query,
        effective_query=aggregated["effective_query"] or normalized_query,
        slug=aggregated["slug"],
        category=category,
        sort=sort,
        language=client.normalize_language(language),
        language_scope=language_scope,
        strict_dubbing=strict_dubbing,
        release_year=release_year,
        search_url=aggregated["search_url"],
        unfiltered_result_count=aggregated["unfiltered_result_count"],
        result_count=len(aggregated["items"]),
        results=[strip_internal_result_fields(item) for item in aggregated["items"]],
        expanded_queries=aggregated["expanded_queries"],
        title_metadata=title_metadata,
    )


def _existing_tv_series_folder_name(series_name: str, *, is_kids: bool, aliases: list[str]) -> str | None:
    library_paths = storage.get_library_paths()
    tv_root_key = "kids_tv_dir" if is_kids else "tv_dir"
    series_root = _resolve_library_root(str(library_paths.get(tv_root_key) or "tv"))
    if not series_root.exists() or not series_root.is_dir():
        return None

    alias_keys = {normalize_alias_key(value) for value in [series_name, *aliases] if normalize_alias_key(value)}
    if not alias_keys:
        return None

    for child in sorted(series_root.iterdir(), key=lambda path: path.name.lower()):
        if not child.is_dir():
            continue
        if normalize_alias_key(child.name) in alias_keys:
            return child.name
    return None


def _coerce_title_metadata_payload(title_metadata: dict | TitleMetadata | None) -> TitleMetadata | None:
    if isinstance(title_metadata, TitleMetadata):
        return title_metadata
    if not isinstance(title_metadata, dict):
        return None
    try:
        return TitleMetadata(**title_metadata)
    except TypeError:
        return None


def _resolve_tv_show_summary(show_name: str, *, show_id: int | None = None) -> TvShowSummary:
    try:
        show = tv_client.lookup_show(show_name)
        if show_id is not None and int(show.id) != int(show_id):
            return TvShowSummary(
                id=int(show_id),
                name=show.name or show_name,
                premiered=show.premiered,
                language=show.language,
                image_url=show.image_url,
                type=show.type,
                genres=list(show.genres),
                summary=show.summary,
            )
        return show
    except Exception:
        return TvShowSummary(
            id=int(show_id or 0),
            name=show_name,
            premiered=None,
            language=None,
        )


def _resolve_tv_show_local_context(show_name: str, *, title_metadata: dict | None) -> dict:
    metadata_obj = _coerce_title_metadata_payload(title_metadata)
    if metadata_obj is None:
        metadata_obj = metadata_resolver.resolve_tv(show_name)
    media = classify_media_title(
        title=show_name,
        media_kind_override="tv",
        metadata=metadata_obj,
        series_name_override=_normalize_optional_text(show_name),
        season_number_override=1,
    )
    if media.series_name:
        existing_series_name = _existing_tv_series_folder_name(
            media.series_name,
            is_kids=media.is_kids,
            aliases=metadata_obj.aliases,
        )
        if existing_series_name:
            media.series_name = existing_series_name

    library_paths = storage.get_library_paths()
    destination_subpath = resolve_destination_subpath(media, library_paths=library_paths)
    season_dir = _resolve_download_root() / Path(destination_subpath)
    return {
        "series_name": media.series_name or show_name,
        "is_kids": media.is_kids,
        "series_dir": season_dir.parent,
        "title_metadata": metadata_obj.to_dict(),
    }


def _list_downloaded_tv_episode_files(local_context: dict | None, *, season_number: int, episode_number: int) -> list[str]:
    if not local_context:
        return []
    series_dir = local_context.get("series_dir")
    if not isinstance(series_dir, Path):
        return []
    season_dir = series_dir / f"S{season_number:02d}"
    if not season_dir.exists() or not season_dir.is_dir():
        return []

    token = _TV_EPISODE_TOKEN_TEMPLATE.format(season=season_number, episode=episode_number)
    matches: list[str] = []
    for child in sorted(season_dir.iterdir(), key=lambda path: path.name.lower()):
        if not child.is_file():
            continue
        name_lower = child.name.lower()
        if token not in name_lower:
            continue
        if any(marker in name_lower for marker in _TV_TEMP_NAME_MARKERS):
            continue
        suffix = child.suffix.lower()
        if suffix in _TV_IGNORED_EXTENSIONS:
            continue
        if suffix not in _TV_MEDIA_EXTENSIONS:
            continue
        matches.append(child.name)
    return matches


def _build_downloaded_tv_episode_payload(
    *,
    all_search_aliases: list[str],
    search_aliases_used: list[str],
    season_number: int,
    episode_number: int,
    episode_name: str | None,
    airdate: str | None,
    alias_mode: Literal["optimized", "all"],
    downloaded_files: list[str],
) -> dict:
    return {
        "episode_code": f"S{season_number:02d}E{episode_number:02d}",
        "season_number": season_number,
        "episode_number": episode_number,
        "episode_name": episode_name,
        "airdate": airdate,
        "status": "downloaded",
        "alias_mode": alias_mode,
        "search_aliases": list(search_aliases_used),
        "all_search_aliases": list(all_search_aliases),
        "query_variants": [],
        "query_errors": [],
        "result_count": 0,
        "results": [],
        "downloaded_files": list(downloaded_files),
    }


def _build_tv_lookup_payload(show_name: str) -> tuple[dict, list[dict], dict]:
    show = tv_client.lookup_show(show_name)
    episodes = tv_client.get_episodes(show.id)
    seasons = _serialize_tv_seasons(episodes)
    if not seasons:
        raise TvMazeClientError(f"No episode data found for '{show.name}'.")

    title_metadata = metadata_resolver.resolve_tv(
        show_name,
        show=show,
        year=parse_year(show.premiered),
    )
    return show.to_dict(), seasons, title_metadata.to_dict()


def _resolve_tv_search_alias_context(
    *,
    show_name: str,
    title_metadata: dict | None,
) -> tuple[list[str], list[str]]:
    raw_aliases = list((title_metadata or {}).get("aliases") or [])
    if not raw_aliases:
        raw_aliases = [show_name]
    search_aliases = build_tv_search_aliases(
        show_name=show_name,
        request_query=raw_aliases[0] if raw_aliases else show_name,
        title_metadata=title_metadata,
    )
    if not search_aliases:
        search_aliases = [show_name]
    return raw_aliases, search_aliases


def _resolve_tv_search_alias_sets(
    *,
    show_name: str,
    title_metadata: dict | None,
    category: Category,
    search_client: SdilejClient | None,
) -> tuple[list[str], list[str], list[str]]:
    aliases, all_search_aliases = _resolve_tv_search_alias_context(
        show_name=show_name,
        title_metadata=title_metadata,
    )
    effective_search_aliases = list(all_search_aliases)
    if search_client is not None:
        effective_search_aliases = select_effective_tv_search_aliases(
            client=search_client,
            show_name=show_name,
            search_aliases=effective_search_aliases,
            category=category,
        )
    return aliases, all_search_aliases, effective_search_aliases


def _search_single_tv_episode(
    *,
    show_name: str,
    title_metadata: dict | None,
    aliases: list[str],
    all_search_aliases: list[str],
    search_aliases: list[str],
    season_number: int,
    episode_number: int,
    episode_name: str | None,
    airdate: str | None,
    category: Category,
    language: str | None,
    language_scope: LanguageScope,
    strict_dubbing: bool,
    max_results_per_variant: int,
    alias_mode: Literal["optimized", "all"] = "optimized",
    force_search: bool = False,
    local_context: dict | None = None,
) -> dict:
    search_aliases_used = list(all_search_aliases if alias_mode == "all" else search_aliases)
    downloaded_files = [] if force_search else _list_downloaded_tv_episode_files(
        local_context,
        season_number=season_number,
        episode_number=episode_number,
    )
    if downloaded_files:
        return _build_downloaded_tv_episode_payload(
            all_search_aliases=all_search_aliases,
            search_aliases_used=search_aliases_used,
            season_number=season_number,
            episode_number=episode_number,
            episode_name=episode_name,
            airdate=airdate,
            alias_mode=alias_mode,
            downloaded_files=downloaded_files,
        )
    result_scorer = build_tv_episode_result_scorer(
        show_aliases=search_aliases_used,
        season=season_number,
        episode=episode_number,
        episode_name=episode_name,
    )
    aggregated = search_tv_episode_results(
        client=client,
        show_aliases=search_aliases_used,
        season=season_number,
        episode=episode_number,
        category=category,
        sort="relevance",
        language=language,
        language_scope=language_scope,
        strict_dubbing=strict_dubbing,
        release_year=None,
        max_results_per_query=max_results_per_variant,
        result_scorer=result_scorer,
    )
    return {
        "episode_code": f"S{season_number:02d}E{episode_number:02d}",
        "season_number": season_number,
        "episode_number": episode_number,
        "episode_name": episode_name,
        "airdate": airdate,
        "status": "done",
        "alias_mode": alias_mode,
        "search_aliases": search_aliases_used,
        "all_search_aliases": all_search_aliases,
        "query_variants": aggregated["expanded_queries"],
        "query_errors": aggregated["query_errors"],
        "result_count": len(aggregated["items"]),
        "results": aggregated["items"],
        "downloaded_files": [],
    }


def _annotate_downloaded_tv_search_items(
    selected_items: list[dict],
    *,
    local_context: dict | None,
) -> list[dict]:
    annotated: list[dict] = []
    for item in selected_items:
        downloaded_files = _list_downloaded_tv_episode_files(
            local_context,
            season_number=int(item["season_number"]),
            episode_number=int(item["episode_number"]),
        )
        next_item = dict(item)
        if downloaded_files:
            next_item["status"] = "downloaded"
            next_item["downloaded_files"] = downloaded_files
        annotated.append(next_item)
    return annotated


def _selected_tv_search_items(payload: TvSeasonSearchPayload, episodes: list[TvEpisode]) -> tuple[list[int], dict[int, set[int]], list[dict]]:
    if not payload.seasons:
        raise SdilejClientError("Select at least one season.")

    season_map: dict[int, list[TvEpisode]] = defaultdict(list)
    for episode in episodes:
        season_map[episode.season].append(episode)

    selected_seasons = sorted({season for season in payload.seasons if season >= 1})
    if not selected_seasons:
        raise SdilejClientError("Select at least one valid season.")

    selected_episode_map: dict[int, set[int]] = {}
    for raw_season, raw_numbers in (payload.episodes_by_season or {}).items():
        try:
            season_number = int(raw_season)
        except (TypeError, ValueError):
            continue
        if season_number < 1:
            continue
        cleaned_numbers: set[int] = set()
        for raw_number in raw_numbers or []:
            try:
                episode_number = int(raw_number)
            except (TypeError, ValueError):
                continue
            if episode_number >= 1:
                cleaned_numbers.add(episode_number)
        selected_episode_map[season_number] = cleaned_numbers

    for season_number in selected_seasons:
        if season_number in selected_episode_map and not selected_episode_map[season_number]:
            raise SdilejClientError(f"Select at least one episode for season {season_number}.")

    selected_items: list[dict] = []
    for season_number in selected_seasons:
        season_episodes = sorted(season_map.get(season_number, []), key=lambda ep: ep.number)
        selected_numbers = selected_episode_map.get(season_number)
        if selected_numbers is not None:
            season_episodes = [episode for episode in season_episodes if episode.number in selected_numbers]
        for episode in season_episodes:
            selected_items.append(
                {
                    "season_number": episode.season,
                    "episode_number": episode.number,
                    "episode_name": episode.name,
                    "airdate": episode.airdate,
                    "episode_code": f"S{episode.season:02d}E{episode.number:02d}",
                }
            )

    if not selected_items:
        raise SdilejClientError("No matching episodes were found for the selected seasons.")

    return selected_seasons, selected_episode_map, selected_items


def _serialize_tv_seasons(episodes: list[TvEpisode]) -> list[dict]:
    seasons: dict[int, list[dict]] = defaultdict(list)
    for episode in episodes:
        seasons[episode.season].append(
            {
                "id": episode.id,
                "season": episode.season,
                "number": episode.number,
                "name": episode.name,
                "airdate": episode.airdate,
                "episode_code": f"S{episode.season:02d}E{episode.number:02d}",
            }
        )

    ordered: list[dict] = []
    for season_number in sorted(seasons):
        season_episodes = sorted(seasons[season_number], key=lambda x: x["number"])
        ordered.append(
            {
                "season_number": season_number,
                "episode_count": len(season_episodes),
                "episodes": season_episodes,
            }
        )
    return ordered


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
    metadata = _resolve_classification_metadata(
        title=title,
        media_kind=media_kind,
        series_name=series_name,
        season_number=season_number,
        episode_number=episode_number,
    )
    media = classify_media_title(
        title=title,
        media_kind_override=media_kind,
        is_kids_override=is_kids,
        metadata=metadata,
        series_name_override=_normalize_optional_text(series_name),
        season_number_override=season_number,
        episode_number_override=episode_number,
    )
    if media.media_kind == "tv" and media.series_name:
        try:
            if metadata is None or metadata.kind != "tv":
                metadata = metadata_resolver.resolve_tv(media.series_name)
            existing_series_name = _existing_tv_series_folder_name(
                media.series_name,
                is_kids=media.is_kids,
                aliases=metadata.aliases,
            )
            if existing_series_name:
                media.series_name = existing_series_name
        except Exception:
            pass
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


@router.get("/")
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
            search_response = _search_files(
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


@router.get("/saved")
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


@router.get("/api/search")
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
        result = _search_files(
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


@router.get("/api/detail")
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


@router.get("/api/history")
def api_history(limit: int = Query(default=50, ge=1, le=500)):
    try:
        return JSONResponse({"items": storage.list_search_history(limit=limit)})
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(status_code=500, content={"error": str(exc)})


@router.get("/api/saved")
def api_saved_list(limit: int = Query(default=200, ge=1, le=1000)):
    try:
        return JSONResponse({"items": storage.list_saved_candidates(limit=limit)})
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(status_code=500, content={"error": str(exc)})


@router.post("/api/saved")
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
        media = _build_media_plan(
            title=title,
            media_kind=payload.media_kind,
            is_kids=payload.is_kids,
            series_name=payload.series_name,
            season_number=payload.season_number,
            episode_number=payload.episode_number,
        )["classification"]

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


@router.delete("/api/saved/{file_id}")
def api_saved_delete(file_id: int):
    try:
        deleted = storage.delete_saved_candidate(file_id=file_id)
        if not deleted:
            return JSONResponse(status_code=404, content={"error": "Saved candidate not found."})
        return JSONResponse({"deleted": True, "file_id": file_id})
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(status_code=500, content={"error": str(exc)})


@router.get("/api/account")
def api_account_get():
    credentials = storage.get_account_credentials()
    if not credentials:
        return JSONResponse({"configured": False, "login": None})
    return JSONResponse({"configured": True, "login": credentials[0]})


@router.post("/api/account")
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


@router.delete("/api/account")
def api_account_delete():
    storage.clear_account_credentials()
    return JSONResponse({"cleared": True})


@router.get("/api/downloads")
def api_downloads_list(
    limit: int = Query(default=200, ge=1, le=1000),
    status: str | None = Query(default=None),
):
    try:
        jobs = storage.list_download_jobs(limit=limit, status=status)
        return JSONResponse({"items": jobs, "summary": storage.get_download_summary(), "worker_alive": worker.is_alive()})
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(status_code=500, content={"error": str(exc)})


@router.get("/api/downloads/settings")
def api_download_settings_get():
    try:
        settings = storage.get_download_settings()
        return JSONResponse(settings)
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(status_code=500, content={"error": str(exc)})


@router.post("/api/downloads/settings")
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


@router.get("/api/downloads/library-paths")
def api_library_paths_get():
    try:
        return JSONResponse(storage.get_library_paths())
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(status_code=500, content={"error": str(exc)})


@router.post("/api/downloads/library-paths")
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


@router.post("/api/media/classify")
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


@router.post("/api/movie/lookup")
def api_movie_lookup(payload: MovieLookupPayload):
    try:
        metadata = metadata_resolver.resolve_movie(payload.title, payload.year)
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
def api_movie_info_link(payload: MovieInfoLinkPayload):
    try:
        return JSONResponse(_resolve_movie_info_link(payload))
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


@router.post("/api/tv/lookup")
def api_tv_lookup(payload: TvLookupPayload):
    try:
        show, seasons, title_metadata = _build_tv_lookup_payload(payload.show_name)
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
        return JSONResponse(status_code=404, content={"error": str(exc)})
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(status_code=500, content={"error": str(exc)})


@router.post("/api/tv/search")
def api_tv_search(payload: TvSeasonSearchPayload):
    try:
        episodes = tv_client.get_episodes(payload.show_id)
        selected_seasons, _selected_episode_map, selected_items = _selected_tv_search_items(payload, episodes)
        show_summary = _resolve_tv_show_summary(payload.show_name, show_id=payload.show_id)
        title_metadata = payload.title_metadata or metadata_resolver.resolve_tv(
            payload.show_name,
            show=show_summary,
        ).to_dict()
        local_context = _resolve_tv_show_local_context(payload.show_name, title_metadata=title_metadata)
        aliases, all_search_aliases, search_aliases = _resolve_tv_search_alias_sets(
            show_name=payload.show_name,
            title_metadata=title_metadata,
            category=payload.category,
            search_client=client,
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
                "language": client.normalize_language(payload.language),
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
        return JSONResponse(status_code=400, content={"error": str(exc)})
    except TvMazeClientError as exc:
        return JSONResponse(status_code=404, content={"error": str(exc)})
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(status_code=500, content={"error": str(exc)})


@router.post("/api/tv/search-episode")
def api_tv_search_episode(payload: TvEpisodeSearchPayload):
    try:
        show_summary = _resolve_tv_show_summary(payload.show_name, show_id=payload.show_id)
        title_metadata = payload.title_metadata or metadata_resolver.resolve_tv(
            payload.show_name,
            show=show_summary,
        ).to_dict()
        local_context = _resolve_tv_show_local_context(payload.show_name, title_metadata=title_metadata)
        aliases, all_search_aliases, search_aliases = _resolve_tv_search_alias_sets(
            show_name=payload.show_name,
            title_metadata=title_metadata,
            category=payload.category,
            search_client=None if payload.alias_mode == "all" else client,
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
        return JSONResponse(status_code=400, content={"error": str(exc)})
    except TvMazeClientError as exc:
        return JSONResponse(status_code=404, content={"error": str(exc)})
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(status_code=500, content={"error": str(exc)})


@router.post("/api/tv/search-jobs")
def api_tv_search_jobs_create(payload: TvSeasonSearchPayload):
    try:
        episodes = tv_client.get_episodes(payload.show_id)
        selected_seasons, _selected_episode_map, selected_items = _selected_tv_search_items(payload, episodes)
        show_summary = _resolve_tv_show_summary(payload.show_name, show_id=payload.show_id)
        title_metadata = payload.title_metadata or metadata_resolver.resolve_tv(
            payload.show_name,
            show=show_summary,
        ).to_dict()
        local_context = _resolve_tv_show_local_context(payload.show_name, title_metadata=title_metadata)
        annotated_items = _annotate_downloaded_tv_search_items(selected_items, local_context=local_context)
        aliases, all_search_aliases, search_aliases = _resolve_tv_search_alias_sets(
            show_name=payload.show_name,
            title_metadata=title_metadata,
            category=payload.category,
            search_client=client,
        )
        job = storage.enqueue_tv_search_job(
            show=show_summary.to_dict(),
            title_metadata=title_metadata,
            aliases=aliases,
            search_aliases=search_aliases,
            selected_seasons=selected_seasons,
            episodes_by_season=payload.episodes_by_season,
            category=payload.category,
            language=client.normalize_language(payload.language),
            language_scope=payload.language_scope,
            strict_dubbing=payload.strict_dubbing,
            max_results_per_variant=payload.max_results_per_variant,
            episodes=annotated_items,
        )
        response_payload = dict(job)
        response_payload["all_search_aliases"] = all_search_aliases
        return JSONResponse(response_payload)
    except SdilejClientError as exc:
        return JSONResponse(status_code=400, content={"error": str(exc)})
    except TvMazeClientError as exc:
        return JSONResponse(status_code=404, content={"error": str(exc)})
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(status_code=500, content={"error": str(exc)})


@router.get("/api/tv/search-jobs")
def api_tv_search_jobs_list(
    limit: int = Query(default=50, ge=1, le=200),
    status: str | None = Query(default=None),
):
    try:
        return JSONResponse({"items": storage.list_tv_search_jobs(limit=limit, status=status)})
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(status_code=500, content={"error": str(exc)})


@router.get("/api/tv/search-jobs/{job_id}")
def api_tv_search_jobs_get(job_id: int):
    try:
        job = storage.get_tv_search_job(job_id)
        if job is None:
            return JSONResponse(status_code=404, content={"error": "TV search job not found."})
        _aliases, all_search_aliases = _resolve_tv_search_alias_context(
            show_name=str((job.get("show") or {}).get("name") or job.get("show_name") or ""),
            title_metadata=job.get("title_metadata"),
        )
        job["all_search_aliases"] = all_search_aliases
        return JSONResponse(job)
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(status_code=500, content={"error": str(exc)})


@router.post("/api/tv/search-jobs/{job_id}/cancel")
def api_tv_search_jobs_cancel(job_id: int):
    try:
        changed = storage.cancel_tv_search_job(job_id)
        if not changed:
            return JSONResponse(status_code=404, content={"error": "TV search job not found or not cancelable."})
        return JSONResponse({"canceled": True, "job_id": job_id})
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(status_code=500, content={"error": str(exc)})


@router.post("/api/downloads")
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


@router.post("/api/downloads/{job_id}/classification")
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


@router.post("/api/downloads/{job_id}/cancel")
def api_downloads_cancel(job_id: int):
    try:
        changed = storage.cancel_download_job(job_id, complete=False)
        if not changed:
            return JSONResponse(status_code=404, content={"error": "Job not found or not cancelable."})
        return JSONResponse({"canceled": True, "job_id": job_id})
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(status_code=500, content={"error": str(exc)})


@router.post("/api/downloads/{job_id}/cancel-complete")
def api_downloads_cancel_complete(job_id: int):
    try:
        changed = storage.cancel_download_job(job_id, complete=True)
        if not changed:
            return JSONResponse(status_code=404, content={"error": "Job not found or not cancelable."})
        return JSONResponse({"canceled": True, "complete": True, "job_id": job_id})
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(status_code=500, content={"error": str(exc)})


@router.post("/api/downloads/{job_id}/retry")
def api_downloads_retry(job_id: int):
    try:
        changed = storage.retry_download_job(job_id)
        if not changed:
            return JSONResponse(status_code=404, content={"error": "Job not found or not retryable."})
        return JSONResponse({"retried": True, "job_id": job_id})
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(status_code=500, content={"error": str(exc)})


@router.delete("/api/downloads/{job_id}")
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


@router.post("/api/downloads/{job_id}/priority")
def api_downloads_priority(job_id: int, payload: UpdatePriorityPayload):
    try:
        changed = storage.set_download_priority(job_id, payload.priority)
        if not changed:
            return JSONResponse(status_code=404, content={"error": "Job not found or priority cannot be changed."})
        return JSONResponse({"updated": True, "job_id": job_id, "priority": payload.priority})
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(status_code=500, content={"error": str(exc)})


@router.post("/api/downloads/{job_id}/top")
def api_downloads_move_top(job_id: int):
    try:
        changed = storage.move_download_job_to_top(job_id)
        if not changed:
            return JSONResponse(status_code=404, content={"error": "Job not found or not queued."})
        return JSONResponse({"moved_to_top": True, "job_id": job_id})
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(status_code=500, content={"error": str(exc)})


@router.post("/api/downloads/clear")
def api_downloads_clear(payload: ClearDownloadsPayload):
    try:
        deleted = storage.delete_download_jobs(statuses=payload.statuses)
        return JSONResponse({"deleted": deleted, "statuses": payload.statuses})
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(status_code=500, content={"error": str(exc)})


@router.get("/api/autocomplete")
def api_autocomplete(
    q: str = Query(..., min_length=1, max_length=200),
    limit: int = Query(default=10, ge=1, le=30),
):
    try:
        suggestions = client.autocomplete(term=q, limit=limit)
        return JSONResponse({"q": q, "suggestions": suggestions})
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(status_code=500, content={"error": str(exc)})


@router.get("/healthz")
def healthcheck():
    return {
        "status": "ok",
        "worker_alive": worker.is_alive(),
        "tv_search_worker_alive": tv_search_worker.is_alive(),
    }


app = create_app()
