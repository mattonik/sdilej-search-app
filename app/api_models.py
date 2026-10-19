from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from .models import Category, LanguageScope


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
    media_kind: Literal["movie", "tv", "music", "unknown"] | None = None
    is_kids: bool | None = None
    series_name: str | None = None
    season_number: int | None = Field(default=None, ge=1, le=99)
    episode_number: int | None = Field(default=None, ge=1, le=999)
    notes: str | None = None


class AccountPayload(BaseModel):
    login: str
    password: str
    verify: bool = True


class YoutubeAuthPayload(BaseModel):
    mode: Literal["none", "cookies_file", "cookies_from_browser"] = "none"
    cookies_path: str | None = Field(default=None, max_length=1000)
    cookies_text: str | None = Field(default=None, max_length=2_000_000)
    cookies_from_browser: str | None = Field(default=None, max_length=200)


class YoutubeAuthTestPayload(BaseModel):
    detail_url: str = Field(min_length=1, max_length=500)


DestinationPreset = Literal["auto", "movies", "tv", "kids_movies", "kids_tv", "music", "unsorted"]


class EnqueueDownloadPayload(BaseModel):
    detail_url: str
    file_id: int | None = None
    title: str | None = None
    source_type: Literal["sdilej", "youtube"] = "sdilej"
    source_metadata: dict | None = None
    preferred_mode: Literal["auto", "premium", "free"] = "auto"
    priority: int = Field(default=0, ge=-100, le=100)
    chunk_count: int | None = Field(default=None, ge=1, le=8)
    destination_preset: DestinationPreset = "auto"
    media_kind: Literal["movie", "tv", "music"] | None = None
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
    music_dir: str = Field(default="/music", min_length=1, max_length=200)
    unsorted_dir: str = Field(default="/unsorted", min_length=1, max_length=200)
    confirm_on_uncertain: bool = True


class MediaClassificationPayload(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    destination_preset: DestinationPreset = "auto"
    media_kind: Literal["movie", "tv", "music"] | None = None
    is_kids: bool | None = None
    series_name: str | None = None
    season_number: int | None = Field(default=None, ge=1, le=99)
    episode_number: int | None = Field(default=None, ge=1, le=999)


class UpdateDownloadClassificationPayload(BaseModel):
    destination_preset: DestinationPreset = "auto"
    media_kind: Literal["movie", "tv", "music"] | None = None
    is_kids: bool | None = None
    series_name: str | None = None
    season_number: int | None = Field(default=None, ge=1, le=99)
    episode_number: int | None = Field(default=None, ge=1, le=999)


class TvLookupPayload(BaseModel):
    show_name: str = Field(min_length=1, max_length=200)
    show_id: int | None = Field(default=None, ge=1)


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
