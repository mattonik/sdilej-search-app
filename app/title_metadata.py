from __future__ import annotations

from datetime import datetime, timedelta
import os
import re
import unicodedata
from typing import Any

import requests

from .models import TitleMetadata
from .storage import Storage
from .tvmaze_client import TvMazeClient, TvShowSummary

CZDB_SEARCH_URL = "https://api.czdb.cz/search"
CZDB_DETAIL_URL = CZDB_SEARCH_URL
MAX_ALIAS_COUNT = 12
DEFAULT_TITLE_METADATA_CACHE_TTL_HOURS = 168
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_SUMMARY_SPACE_RE = re.compile(r"\s+")


def normalize_alias_key(value: str | None) -> str:
    if value is None:
        return ""
    normalized = (
        unicodedata.normalize("NFKD", value)
        .encode("ascii", "ignore")
        .decode("ascii")
        .lower()
    )
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
    return normalized.strip()


def parse_year(value: Any) -> int | None:
    if value is None:
        return None
    text = str(value).strip()
    match = re.search(r"\b(19\d{2}|20\d{2})\b", text)
    if not match:
        return None
    return int(match.group(1))


def build_ordered_aliases(
    *,
    user_query: str,
    canonical_title: str,
    original_title: str | None,
    local_titles: list[str],
    aliases: list[str],
    max_aliases: int = MAX_ALIAS_COUNT,
) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()

    def add(value: str | None) -> None:
        if not value:
            return
        text = value.strip()
        if not text:
            return
        key = normalize_alias_key(text)
        if not key or key in seen:
            return
        seen.add(key)
        ordered.append(text)

    add(user_query)
    add(canonical_title)
    add(original_title)
    for value in local_titles:
        add(value)
    for value in aliases:
        add(value)
    return ordered[:max_aliases]


class TitleMetadataResolver:
    def __init__(
        self,
        *,
        storage: Storage,
        tv_client: TvMazeClient,
        timeout_seconds: int = 20,
        max_alias_count: int = MAX_ALIAS_COUNT,
        cache_ttl_hours: int | None = None,
    ) -> None:
        self.storage = storage
        self.tv_client = tv_client
        self.timeout_seconds = timeout_seconds
        self.max_alias_count = max_alias_count
        self.cache_ttl = timedelta(hours=_resolve_cache_ttl_hours(cache_ttl_hours))
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "sdilej-search-app/1.0"})

    def resolve_movie(self, title: str, year: int | None = None) -> TitleMetadata:
        query = title.strip()
        if not query:
            raise ValueError("title is required")

        cache_key = normalize_alias_key(query)
        cached_entry = self.storage.get_title_metadata_cache_entry("movie", cache_key, year)
        if cached_entry:
            cached_metadata = self._metadata_from_dict(cached_entry["payload"])
            if self._cache_entry_is_fresh(cached_entry):
                return cached_metadata
            refreshed = self._resolve_from_czdb(kind="movie", query=query, year=year)
            if refreshed is not None:
                self.storage.set_title_metadata_cache("movie", cache_key, year, refreshed.to_dict(), refreshed.source)
                return refreshed
            return cached_metadata

        metadata = self._resolve_from_czdb(kind="movie", query=query, year=year)
        if metadata is None:
            metadata = TitleMetadata(
                kind="movie",
                canonical_title=query,
                original_title=None,
                local_titles=[query],
                aliases=[query],
                genres=[],
                summary=None,
                content_type=None,
                year=year,
                source="fallback",
                source_ids={},
            )

        self.storage.set_title_metadata_cache("movie", cache_key, year, metadata.to_dict(), metadata.source)
        return metadata

    def resolve_tv(
        self,
        title: str,
        *,
        show: TvShowSummary | None = None,
        year: int | None = None,
    ) -> TitleMetadata:
        query = title.strip()
        if not query:
            raise ValueError("title is required")

        effective_year = year or parse_year(show.premiered if show else None)
        cache_key = normalize_alias_key(query)
        cached_entry = self.storage.get_title_metadata_cache_entry("tv", cache_key, effective_year)
        if cached_entry:
            cached_metadata = self._metadata_from_dict(cached_entry["payload"])
            if not self._cache_entry_is_fresh(cached_entry):
                refreshed = self._resolve_from_czdb(kind="tv", query=query, year=effective_year)
                if refreshed is not None:
                    cached_metadata = refreshed
                    self.storage.set_title_metadata_cache(
                        "tv",
                        cache_key,
                        effective_year,
                        cached_metadata.to_dict(),
                        cached_metadata.source,
                    )
            if show is None:
                return cached_metadata
            # Refresh TVMaze aliases when we have a concrete show id.
            tvmaze_aliases = self._load_tvmaze_aliases(show)
            merged_aliases = build_ordered_aliases(
                user_query=query,
                canonical_title=cached_metadata.canonical_title or show.name,
                original_title=cached_metadata.original_title or show.name,
                local_titles=cached_metadata.local_titles,
                aliases=[*cached_metadata.aliases, *tvmaze_aliases],
                max_aliases=self.max_alias_count,
            )
            cached_metadata.aliases = merged_aliases
            cached_metadata.genres = self._merge_genres(cached_metadata.genres, list(show.genres))
            cached_metadata.summary = self._clean_summary_text(cached_metadata.summary or show.summary)
            cached_metadata.content_type = self._clean_optional_text(cached_metadata.content_type or show.type)
            if show.id and "tvmaze" not in cached_metadata.source_ids:
                cached_metadata.source_ids["tvmaze"] = show.id
            return cached_metadata

        tvmaze_aliases = self._load_tvmaze_aliases(show) if show else []
        metadata = self._resolve_from_czdb(kind="tv", query=query, year=effective_year)

        canonical_title = metadata.canonical_title if metadata else (show.name if show else query)
        original_title = metadata.original_title if metadata and metadata.original_title else (show.name if show else None)
        local_titles = list(metadata.local_titles) if metadata else []
        aliases = list(metadata.aliases) if metadata else []
        source = metadata.source if metadata else ("tvmaze" if show is not None else "fallback")
        source_ids = dict(metadata.source_ids) if metadata else {}

        if show is not None:
            source_ids["tvmaze"] = show.id
            if not local_titles:
                local_titles.append(show.name)
            aliases.extend(tvmaze_aliases)
            if metadata is None:
                aliases.append(show.name)
        elif metadata is None:
            local_titles.append(query)
            aliases.append(query)

        merged = TitleMetadata(
            kind="tv",
            canonical_title=canonical_title,
            original_title=original_title,
            local_titles=self._dedupe_texts(local_titles),
            aliases=build_ordered_aliases(
                user_query=query,
                canonical_title=canonical_title,
                original_title=original_title,
                local_titles=self._dedupe_texts(local_titles),
                aliases=aliases,
                max_aliases=self.max_alias_count,
            ),
            genres=self._merge_genres(
                metadata.genres if metadata else [],
                list(show.genres) if show else [],
            ),
            summary=self._clean_summary_text(
                (metadata.summary if metadata else None) or (show.summary if show else None)
            ),
            content_type=self._clean_optional_text(
                (metadata.content_type if metadata else None) or (show.type if show else None)
            ),
            year=effective_year,
            source=source,
            source_ids=source_ids,
        )

        self.storage.set_title_metadata_cache("tv", cache_key, effective_year, merged.to_dict(), merged.source)
        return merged

    def resolve_movie_info_links(self, title: str, year: int | None = None) -> dict[str, Any]:
        metadata = self.resolve_movie(title, year)
        detail = self._fetch_czdb_detail(metadata.source_ids.get("csfd") or metadata.source_ids.get("czdb"))

        resolved_title = metadata.canonical_title or title.strip()
        original_title = metadata.original_title
        resolved_year = metadata.year or year
        csfd_url = self._clean_optional_text(metadata.source_ids.get("csfd_url")) or self._build_csfd_url(
            metadata.source_ids.get("csfd")
        )
        imdb_url = None

        if detail:
            resolved_title = self._clean_optional_text(detail.get("nazev")) or resolved_title
            original_title = self._clean_optional_text(detail.get("original")) or original_title
            resolved_year = parse_year(detail.get("rok")) or resolved_year
            csfd_url = self._clean_optional_text(detail.get("csfd_url")) or csfd_url or self._build_csfd_url(
                detail.get("csfd_id")
            )
            imdb_url = self._build_imdb_title_url(detail.get("imdb_id"))

        preferred_url = csfd_url or imdb_url
        return {
            "found": bool(preferred_url),
            "preferred_url": preferred_url,
            "csfd_url": csfd_url,
            "imdb_url": imdb_url,
            "resolved_title": resolved_title,
            "original_title": original_title,
            "year": resolved_year,
            "source": metadata.source,
        }

    def _resolve_from_czdb(
        self,
        *,
        kind: str,
        query: str,
        year: int | None,
    ) -> TitleMetadata | None:
        try:
            response = self.session.get(
                CZDB_SEARCH_URL,
                params={k: v for k, v in {"q": query, "y": year}.items() if v is not None},
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            payload = response.json()
        except Exception:
            return None

        items = payload.get("results") if isinstance(payload, dict) else None
        if not isinstance(items, list) or not items:
            return None

        picked = self._pick_best_czdb_match(query=query, year=year, items=items)
        if not picked:
            return None

        canonical_title = str(picked.get("nazev") or "").strip() or query
        original_title = self._clean_optional_text(picked.get("original"))
        alt_titles = self._split_alt_titles(picked.get("alt_nazev"))
        detail = self._fetch_czdb_detail(picked.get("csfd_id") or picked.get("id"))

        if detail:
            canonical_title = self._clean_optional_text(detail.get("nazev")) or canonical_title
            original_title = self._clean_optional_text(detail.get("original")) or original_title
            alt_titles = self._dedupe_texts([*alt_titles, *self._split_alt_titles(detail.get("alt_nazev"))])

        local_titles = self._dedupe_texts([canonical_title, *alt_titles])
        aliases = build_ordered_aliases(
            user_query=query,
            canonical_title=canonical_title,
            original_title=original_title,
            local_titles=local_titles,
            aliases=alt_titles,
            max_aliases=self.max_alias_count,
        )
        source_ids: dict[str, str | int | None] = {
            "czdb": picked.get("id"),
            "csfd": picked.get("csfd_id"),
        }
        csfd_url = self._clean_optional_text((detail or {}).get("csfd_url")) or self._clean_optional_text(picked.get("csfd_url"))
        if csfd_url:
            source_ids["csfd_url"] = csfd_url
        imdb_id = self._clean_optional_text((detail or {}).get("imdb_id"))
        if imdb_id and imdb_id != "0":
            source_ids["imdb"] = imdb_id
        tmdb_id = self._clean_optional_text((detail or {}).get("tmdb_id"))
        if tmdb_id and tmdb_id != "0":
            source_ids["tmdb"] = tmdb_id

        return TitleMetadata(
            kind="movie" if kind == "movie" else "tv",
            canonical_title=canonical_title,
            original_title=original_title,
            local_titles=local_titles,
            aliases=aliases,
            genres=self._split_genres((detail or {}).get("zanr")),
            summary=self._clean_summary_text((detail or {}).get("plot")),
            content_type=self._clean_optional_text((detail or {}).get("typ")),
            year=parse_year(picked.get("rok")) or year,
            source="czdb",
            source_ids=source_ids,
        )

    def _fetch_czdb_detail(self, czdb_id: Any) -> dict[str, Any] | None:
        if czdb_id in {None, ""}:
            return None
        try:
            response = self.session.get(
                CZDB_DETAIL_URL,
                params={"uid": czdb_id},
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            payload = response.json()
        except Exception:
            return None
        if isinstance(payload, dict):
            items = payload.get("results")
            if isinstance(items, list) and items and isinstance(items[0], dict):
                return items[0]
            return payload
        return None

    def _pick_best_czdb_match(self, *, query: str, year: int | None, items: list[dict[str, Any]]) -> dict[str, Any] | None:
        query_key = normalize_alias_key(query)
        best_item: dict[str, Any] | None = None
        best_score: tuple[int, int, int, int] | None = None

        for item in items:
            candidates = [
                self._clean_optional_text(item.get("nazev")),
                self._clean_optional_text(item.get("original")),
                *self._split_alt_titles(item.get("alt_nazev")),
            ]
            candidate_keys = [normalize_alias_key(value) for value in candidates if value]
            exact = 1 if query_key in candidate_keys else 0
            prefix = 1 if any(key.startswith(query_key) for key in candidate_keys if query_key) else 0
            contains = 1 if any(query_key and query_key in key for key in candidate_keys) else 0
            year_value = parse_year(item.get("rok"))
            year_score = 0
            if year is not None and year_value is not None:
                year_score = max(0, 100 - abs(year - year_value))
            elif year_value is not None:
                year_score = 1

            score = (exact, prefix, contains, year_score)
            if best_score is None or score > best_score:
                best_score = score
                best_item = item

        return best_item

    def _load_tvmaze_aliases(self, show: TvShowSummary | None) -> list[str]:
        if show is None:
            return []
        try:
            aliases = self.tv_client.get_akas(show.id)
        except Exception:
            aliases = []
        return self._dedupe_texts([show.name, *aliases])

    def _split_alt_titles(self, raw_value: Any) -> list[str]:
        if raw_value is None:
            return []
        parts = re.split(r"\s+\|\s+|\|", str(raw_value))
        cleaned = [part.strip() for part in parts if str(part).strip()]
        return self._dedupe_texts(cleaned)

    def _dedupe_texts(self, values: list[str]) -> list[str]:
        ordered: list[str] = []
        seen: set[str] = set()
        for value in values:
            text = value.strip()
            if not text:
                continue
            key = normalize_alias_key(text)
            if not key or key in seen:
                continue
            seen.add(key)
            ordered.append(text)
        return ordered

    def _merge_genres(self, primary: list[str], secondary: list[str]) -> list[str]:
        return self._dedupe_texts([*primary, *secondary])

    def _split_genres(self, raw_value: Any) -> list[str]:
        if raw_value is None:
            return []
        parts = re.split(r"\s*,\s*|\s+\|\s+|\|", str(raw_value))
        return self._dedupe_texts([part.strip() for part in parts if str(part).strip()])

    def _clean_optional_text(self, value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    def _clean_summary_text(self, value: Any) -> str | None:
        text = self._clean_optional_text(value)
        if not text:
            return None
        text = _HTML_TAG_RE.sub(" ", text)
        text = _SUMMARY_SPACE_RE.sub(" ", text).strip()
        return text or None

    def _build_imdb_title_url(self, value: Any) -> str | None:
        imdb_id = self._clean_optional_text(value)
        if not imdb_id:
            return None
        if not imdb_id.startswith("tt"):
            imdb_id = f"tt{imdb_id}"
        return f"https://www.imdb.com/title/{imdb_id}/"

    def _build_csfd_url(self, value: Any) -> str | None:
        csfd_id = self._clean_optional_text(value)
        if not csfd_id:
            return None
        return f"https://www.csfd.cz/film/{csfd_id}"

    def _metadata_from_dict(self, payload: dict[str, Any]) -> TitleMetadata:
        return TitleMetadata(
            kind=str(payload.get("kind") or "unknown"),
            canonical_title=str(payload.get("canonical_title") or ""),
            original_title=payload.get("original_title"),
            local_titles=list(payload.get("local_titles") or []),
            aliases=list(payload.get("aliases") or []),
            genres=list(payload.get("genres") or []),
            summary=self._clean_summary_text(payload.get("summary")),
            content_type=self._clean_optional_text(payload.get("content_type")),
            year=parse_year(payload.get("year")),
            source=str(payload.get("source") or "fallback"),
            source_ids=dict(payload.get("source_ids") or {}),
        )

    def _cache_entry_is_fresh(self, entry: dict[str, Any]) -> bool:
        updated_at = self._parse_cache_timestamp(entry.get("updated_at"))
        if updated_at is None:
            return False
        return datetime.utcnow() - updated_at <= self.cache_ttl

    def _parse_cache_timestamp(self, value: Any) -> datetime | None:
        text = self._clean_optional_text(value)
        if not text:
            return None
        try:
            return datetime.strptime(text, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return None


def _resolve_cache_ttl_hours(configured_value: int | None) -> int:
    if configured_value is not None:
        try:
            return max(1, int(configured_value))
        except (TypeError, ValueError):
            return DEFAULT_TITLE_METADATA_CACHE_TTL_HOURS

    raw = os.getenv("TITLE_METADATA_CACHE_TTL_HOURS", "").strip()
    if not raw:
        return DEFAULT_TITLE_METADATA_CACHE_TTL_HOURS
    try:
        return max(1, int(raw))
    except ValueError:
        return DEFAULT_TITLE_METADATA_CACHE_TTL_HOURS
