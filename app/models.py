from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Literal

Category = Literal["all", "video", "audio", "archive", "image"]
SortMode = Literal["relevance", "downloads", "newest", "size_desc", "size_asc"]
LanguageScope = Literal["any", "audio", "subtitles"]
AudioPreference = Literal["any", "original_or_english", "local_dub"]


@dataclass(slots=True)
class TitleMetadata:
    kind: Literal["movie", "tv", "unknown"]
    canonical_title: str
    original_title: str | None = None
    local_titles: list[str] = field(default_factory=list)
    aliases: list[str] = field(default_factory=list)
    genres: list[str] = field(default_factory=list)
    summary: str | None = None
    content_type: str | None = None
    year: int | None = None
    source: str = "fallback"
    source_ids: dict[str, str | int | None] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(slots=True)
class SearchResult:
    file_id: int | None
    title: str
    detail_url: str
    thumbnail_url: str | None
    size: str | None
    duration: str | None
    is_playable: bool
    extension: str | None
    detected_years: list[int]
    primary_year: int | None
    detected_languages: list[str]
    has_dub_hint: bool
    has_subtitle_hint: bool
    query_hits: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(slots=True)
class SearchResponse:
    query: str
    effective_query: str
    slug: str
    category: Category
    sort: SortMode
    language: str | None
    language_scope: LanguageScope
    strict_dubbing: bool
    release_year: int | None
    search_url: str
    unfiltered_result_count: int
    result_count: int
    results: list[SearchResult]
    expanded_queries: list[str] = field(default_factory=list)
    query_errors: list[str] = field(default_factory=list)
    title_metadata: TitleMetadata | None = None
    audio_preference: AudioPreference = "any"

    def to_dict(self) -> dict:
        data = asdict(self)
        data["results"] = [item.to_dict() for item in self.results]
        return data


def audio_preference_priority(result: SearchResult, preference: AudioPreference) -> int:
    if preference == "any":
        return 0

    languages = {value.upper() for value in result.detected_languages}
    has_local_audio = bool(languages & {"CZ", "SK"})
    has_english_audio = "EN" in languages

    if preference == "original_or_english":
        if has_english_audio:
            return 40
        if not has_local_audio and not result.has_dub_hint:
            return 15
        return 0

    if has_local_audio and result.has_dub_hint:
        return 40
    if has_local_audio:
        return 30
    if not result.has_dub_hint:
        return 10
    return 0


@dataclass(slots=True)
class DetailProbeResponse:
    file_id: int | None
    detail_url: str
    title: str | None
    size: str | None
    duration: str | None
    resolution: str | None
    download_fast_url: str | None
    download_slow_url: str | None
    selected_download_url: str | None
    preflight_status_code: int | None
    preflight_location: str | None
    preflight_content_type: str | None
    preflight_content_length: int | None
    preflight_accept_ranges: str | None

    def to_dict(self) -> dict:
        return asdict(self)
