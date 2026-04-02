from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import os
import re
from pathlib import Path
from typing import Literal
from urllib.parse import urljoin, urlparse

from fastapi import FastAPI, Request
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


@dataclass
class ServiceContainer:
    client: SdilejClient
    tv_client: TvMazeClient
    storage: Storage
    worker: DownloadWorker
    metadata_resolver: TitleMetadataResolver
    tv_search_worker: TvSearchWorker


def _get_services(request: Request) -> ServiceContainer:
    return request.app.state.services


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
    services = ServiceContainer(
        client=resolved_client,
        tv_client=resolved_tv_client,
        storage=resolved_storage,
        worker=resolved_worker,
        metadata_resolver=resolved_metadata_resolver,
        tv_search_worker=resolved_tv_search_worker,
    )

    app = FastAPI(title="Sdilej Search Proxy", version="0.1.0")
    app.state.services = services
    app.state.templates = templates
    app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
    from .routes.downloads import router as downloads_router
    from .routes.health import router as health_router
    from .routes.search import router as search_router
    from .routes.tv import router as tv_router

    app.include_router(search_router)
    app.include_router(tv_router)
    app.include_router(downloads_router)
    app.include_router(health_router)

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


def _resolve_movie_info_link(
    payload: MovieInfoLinkPayload,
    *,
    services: ServiceContainer,
) -> dict[str, str | int | bool | None]:
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
            info = services.metadata_resolver.resolve_movie_info_links(candidate, year_candidate)
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


def _resolve_video_metadata(
    query: str,
    release_year: int | None,
    *,
    services: ServiceContainer,
):
    movie_metadata = services.metadata_resolver.resolve_movie(query, release_year)
    tv_metadata = services.metadata_resolver.resolve_tv(query, year=release_year)

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
    services: ServiceContainer,
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
                return services.metadata_resolver.resolve_tv(lookup_name, year=parse_year(title))

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
                return services.metadata_resolver.resolve_movie(lookup_query, lookup_year)
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
    services: ServiceContainer,
) -> SearchResponse:
    normalized_query = query.strip()
    if category != "video" or not normalized_query:
        return services.client.search(
            query=query,
            category=category,
            sort=sort,
            language=language,
            language_scope=language_scope,
            strict_dubbing=strict_dubbing,
            release_year=release_year,
            max_results=max_results,
        )

    title_metadata = _resolve_video_metadata(normalized_query, release_year, services=services)
    aggregated = aggregate_query_results(
        client=services.client,
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
        language=services.client.normalize_language(language),
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


def _existing_tv_series_folder_name(
    series_name: str,
    *,
    is_kids: bool,
    aliases: list[str],
    services: ServiceContainer,
) -> str | None:
    library_paths = services.storage.get_library_paths()
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


def _resolve_tv_show_summary(
    show_name: str,
    *,
    show_id: int | None = None,
    services: ServiceContainer,
) -> TvShowSummary:
    try:
        show = services.tv_client.lookup_show(show_name)
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


def _resolve_tv_show_local_context(
    show_name: str,
    *,
    title_metadata: dict | None,
    services: ServiceContainer,
) -> dict:
    metadata_obj = _coerce_title_metadata_payload(title_metadata)
    if metadata_obj is None:
        metadata_obj = services.metadata_resolver.resolve_tv(show_name)
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
            services=services,
        )
        if existing_series_name:
            media.series_name = existing_series_name

    library_paths = services.storage.get_library_paths()
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


def _build_tv_lookup_payload(
    show_name: str,
    *,
    services: ServiceContainer,
) -> tuple[dict, list[dict], dict]:
    show = services.tv_client.lookup_show(show_name)
    episodes = services.tv_client.get_episodes(show.id)
    seasons = _serialize_tv_seasons(episodes)
    if not seasons:
        raise TvMazeClientError(f"No episode data found for '{show.name}'.")

    title_metadata = services.metadata_resolver.resolve_tv(
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
    services: ServiceContainer,
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
        client=services.client,
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
    services: ServiceContainer,
) -> dict:
    library_paths = services.storage.get_library_paths()
    metadata = _resolve_classification_metadata(
        title=title,
        media_kind=media_kind,
        series_name=series_name,
        season_number=season_number,
        episode_number=episode_number,
        services=services,
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
                metadata = services.metadata_resolver.resolve_tv(media.series_name)
            existing_series_name = _existing_tv_series_folder_name(
                media.series_name,
                is_kids=media.is_kids,
                aliases=metadata.aliases,
                services=services,
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


app = create_app()
