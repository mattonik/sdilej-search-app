from dataclasses import asdict, dataclass
from typing import Literal

Category = Literal["all", "video", "audio", "archive", "image"]
SortMode = Literal["relevance", "downloads", "newest", "size_desc", "size_asc"]
LanguageScope = Literal["any", "audio", "subtitles"]


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

    def to_dict(self) -> dict:
        data = asdict(self)
        data["results"] = [item.to_dict() for item in self.results]
        return data


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
