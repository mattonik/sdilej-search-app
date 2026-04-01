from __future__ import annotations

import re
from typing import Any, Callable

from .models import LanguageScope, SearchResult, TitleMetadata
from .sdilej_client import SdilejClient
from .title_metadata import MAX_ALIAS_COUNT, normalize_alias_key

MAX_EPISODE_QUERY_VARIANTS = 24


def parse_size_to_bytes(size_text: str | None) -> int:
    if not size_text:
        return 0
    match = re.search(r"([0-9]+(?:[.,][0-9]+)?)\s*([KMGTP]?B)", size_text.strip(), re.IGNORECASE)
    if not match:
        return 0
    number_raw = match.group(1).replace(",", ".")
    unit = match.group(2).upper()
    try:
        value = float(number_raw)
    except ValueError:
        return 0
    factors = {
        "B": 1,
        "KB": 1024,
        "MB": 1024**2,
        "GB": 1024**3,
        "TB": 1024**4,
        "PB": 1024**5,
    }
    return int(value * factors.get(unit, 1))


def dedupe_queries(values: list[str], *, limit: int | None = None) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = value.strip()
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        ordered.append(text)
        if limit is not None and len(ordered) >= limit:
            break
    return ordered


def build_episode_query_variants(
    show_aliases: list[str],
    season: int,
    episode: int,
    *,
    limit: int = MAX_EPISODE_QUERY_VARIANTS,
    ) -> list[str]:
    variants: list[str] = []
    for alias in dedupe_queries(show_aliases):
        variants.extend(
            [
                f"{alias} S{season:02d}E{episode:02d}",
                f"{alias} {season}x{episode:02d}",
                f"{alias} Season {season} Episode {episode}",
            ]
        )
    return dedupe_queries(variants, limit=limit)


def build_tv_search_aliases(
    *,
    show_name: str,
    request_query: str | None = None,
    title_metadata: TitleMetadata | dict[str, Any] | None = None,
    limit: int = MAX_ALIAS_COUNT,
) -> list[str]:
    metadata = _coerce_title_metadata(title_metadata)
    ordered = _build_tv_alias_candidates(
        show_name=show_name,
        request_query=request_query,
        title_metadata=metadata,
    )
    always_keep_keys = {
        normalize_alias_key(value)
        for value in [show_name, request_query, metadata.original_title if metadata else None]
        if normalize_alias_key(value)
    }

    kept: list[str] = []
    kept_keys: list[str] = []
    for value in ordered:
        key = normalize_alias_key(value)
        if not key:
            continue
        is_single_token = " " not in key
        is_short = len(key.replace(" ", "")) < 5
        is_prefix_of_stronger = any(existing.startswith(key) and existing != key for existing in kept_keys)
        is_risky = is_single_token and key not in always_keep_keys and (is_short or is_prefix_of_stronger)
        if is_risky:
            continue
        kept.append(value)
        kept_keys.append(key)
        if len(kept) >= limit:
            break

    if kept:
        return kept
    fallback = show_name.strip() or (request_query or "").strip()
    return [fallback] if fallback else []


def build_tv_episode_result_matcher(
    *,
    show_name: str,
    request_query: str | None = None,
    title_metadata: TitleMetadata | dict[str, Any] | None = None,
    season: int,
    episode: int,
) -> Callable[[SearchResult, str], bool]:
    metadata = _coerce_title_metadata(title_metadata)
    alias_candidates = _build_tv_alias_candidates(
        show_name=show_name,
        request_query=request_query,
        title_metadata=metadata,
    )
    trusted_alias_keys = {
        normalize_alias_key(value)
        for value in [show_name, request_query, metadata.original_title if metadata else None]
        if normalize_alias_key(value)
    }
    weak_alias_keys: set[str] = set()

    for alias in alias_candidates:
        key = normalize_alias_key(alias)
        if not key:
            continue
        if " " in key:
            trusted_alias_keys.add(key)
        elif key not in trusted_alias_keys:
            weak_alias_keys.add(key)

    episode_tokens = _build_episode_match_tokens(season=season, episode=episode)

    def matches(result: SearchResult, _query: str) -> bool:
        normalized_title = normalize_alias_key(result.title)
        if not normalized_title:
            return False
        padded_title = f" {normalized_title} "
        if not any(_contains_normalized_phrase(padded_title, token) for token in episode_tokens):
            return False

        for alias_key in trusted_alias_keys:
            if _contains_normalized_phrase(padded_title, alias_key):
                return True

        for alias_key in weak_alias_keys:
            for token in episode_tokens:
                if _contains_normalized_phrase(padded_title, f"{alias_key} {token}"):
                    return True
        return False

    return matches


def aggregate_query_results(
    *,
    client: SdilejClient,
    queries: list[str],
    category: str,
    sort: str = "relevance",
    language: str | None,
    language_scope: LanguageScope,
    strict_dubbing: bool,
    release_year: int | None,
    max_results_per_query: int,
    max_results_total: int | None = None,
    result_filter: Callable[[SearchResult, str], bool] | None = None,
) -> dict[str, Any]:
    normalized_language = client.normalize_language(language)
    expanded_queries = dedupe_queries(queries)
    aggregated: dict[str, dict[str, Any]] = {}
    query_errors: list[str] = []
    first_response_meta: dict[str, Any] | None = None

    for query_index, query in enumerate(expanded_queries):
        try:
            search_response = client.search(
                query=query,
                category=category,
                sort=sort,
                language=None,
                language_scope=language_scope,
                strict_dubbing=False,
                release_year=release_year,
                max_results=max_results_per_query,
            )
        except Exception as exc:  # noqa: BLE001
            query_errors.append(f"{query}: {exc}")
            continue

        if first_response_meta is None:
            first_response_meta = {
                "effective_query": search_response.effective_query,
                "slug": search_response.slug,
                "search_url": search_response.search_url,
            }

        for result in search_response.results:
            if result_filter is not None and not result_filter(result, query):
                continue
            language_priority = client.language_match_priority(
                title=result.title,
                language=normalized_language,
                scope=language_scope,
                strict_dubbing=strict_dubbing,
            )
            if normalized_language is not None and language_priority <= 0:
                continue

            size_bytes = parse_size_to_bytes(result.size)
            key = f"id:{result.file_id}" if result.file_id is not None else f"url:{result.detail_url}"
            if key not in aggregated:
                item = result.to_dict()
                item["language_priority"] = language_priority
                item["size_bytes"] = size_bytes
                item["query_priority"] = query_index
                item["query_hits"] = [query]
                aggregated[key] = item
                continue

            current = aggregated[key]
            current["language_priority"] = max(int(current.get("language_priority") or 0), language_priority)
            current["size_bytes"] = max(int(current.get("size_bytes") or 0), size_bytes)
            current_query_priority = current.get("query_priority")
            if current_query_priority is None:
                current_query_priority = query_index
            current["query_priority"] = min(int(current_query_priority), query_index)
            current_hits = set(current.get("query_hits") or [])
            current_hits.add(query)
            current["query_hits"] = sorted(current_hits)

    sorted_items = sorted(
        aggregated.values(),
        key=lambda item: (
            int(item.get("query_priority") or 0),
            -int(item.get("language_priority") or 0),
            -int(item.get("size_bytes") or 0),
            str(item.get("title") or "").lower(),
        ),
    )
    if max_results_total is not None:
        sorted_items = sorted_items[:max_results_total]

    if first_response_meta is None:
        first_response_meta = {
            "effective_query": expanded_queries[0] if expanded_queries else "",
            "slug": "",
            "search_url": "",
        }

    return {
        "items": sorted_items,
        "query_errors": query_errors,
        "expanded_queries": expanded_queries,
        "effective_query": first_response_meta["effective_query"],
        "slug": first_response_meta["slug"],
        "search_url": first_response_meta["search_url"],
        "unfiltered_result_count": len(aggregated),
    }


def strip_internal_result_fields(item: dict[str, Any]) -> SearchResult:
    payload = dict(item)
    payload.pop("language_priority", None)
    payload.pop("size_bytes", None)
    payload.pop("query_priority", None)
    return SearchResult(**payload)


def _coerce_title_metadata(title_metadata: TitleMetadata | dict[str, Any] | None) -> TitleMetadata | None:
    if title_metadata is None:
        return None
    if isinstance(title_metadata, TitleMetadata):
        return title_metadata
    return TitleMetadata(
        kind=str(title_metadata.get("kind") or "unknown"),
        canonical_title=str(title_metadata.get("canonical_title") or ""),
        original_title=title_metadata.get("original_title"),
        local_titles=list(title_metadata.get("local_titles") or []),
        aliases=list(title_metadata.get("aliases") or []),
        year=title_metadata.get("year"),
        source=str(title_metadata.get("source") or "fallback"),
        source_ids=dict(title_metadata.get("source_ids") or {}),
    )


def _build_tv_alias_candidates(
    *,
    show_name: str,
    request_query: str | None,
    title_metadata: TitleMetadata | None,
) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()

    def add(value: str | None) -> None:
        text = (value or "").strip()
        key = normalize_alias_key(text)
        if not key or key in seen:
            return
        seen.add(key)
        ordered.append(text)

    add(show_name)
    add(request_query)
    if title_metadata is not None:
        add(title_metadata.original_title)
        add(title_metadata.canonical_title)
        for value in title_metadata.local_titles:
            add(value)
        for value in title_metadata.aliases:
            add(value)
    return ordered


def _build_episode_match_tokens(*, season: int, episode: int) -> list[str]:
    return [
        f"s{season:02d}e{episode:02d}",
        f"{season}x{episode:02d}",
        f"season {season} episode {episode}",
    ]


def _contains_normalized_phrase(padded_title: str, phrase: str) -> bool:
    normalized_phrase = normalize_alias_key(phrase)
    if not normalized_phrase:
        return False
    return f" {normalized_phrase} " in padded_title
