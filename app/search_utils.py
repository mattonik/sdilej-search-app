from __future__ import annotations

import re
from typing import Any, Callable

from .models import LanguageScope, SearchResult, TitleMetadata
from .sdilej_client import SdilejClient
from .title_metadata import MAX_ALIAS_COUNT, normalize_alias_key

MAX_EPISODE_QUERY_VARIANTS = 24
MAX_EFFECTIVE_TV_SEARCH_ALIASES = 2
TV_ALIAS_PROBE_RESULTS = 12


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
                f"{alias} {season}x{episode}",
            ]
        )
    return dedupe_queries(variants, limit=limit)


def select_effective_tv_search_aliases(
    *,
    client: SdilejClient,
    show_name: str,
    search_aliases: list[str],
    category: str,
    sort: str = "relevance",
    limit: int = MAX_EFFECTIVE_TV_SEARCH_ALIASES,
    probe_max_results: int = TV_ALIAS_PROBE_RESULTS,
) -> list[str]:
    aliases = dedupe_queries(search_aliases)
    if not aliases:
        fallback = show_name.strip()
        return [fallback] if fallback else []
    if len(aliases) <= limit:
        return aliases

    primary = aliases[0]
    scored: list[tuple[int, int, int, str]] = []
    for index, alias in enumerate(aliases[1:], start=1):
        score = _score_tv_alias_probe(
            client=client,
            alias=alias,
            category=category,
            sort=sort,
            max_results=probe_max_results,
        )
        if score > 0:
            scored.append((score, len(normalize_alias_key(alias).split()), -index, alias))

    if not scored:
        return aliases[:limit]

    scored.sort(reverse=True)
    selected = [primary]
    for _score, _words, _neg_index, alias in scored:
        if alias in selected:
            continue
        selected.append(alias)
        if len(selected) >= limit:
            break
    return selected


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


def build_tv_episode_result_scorer(
    *,
    show_aliases: list[str],
    season: int,
    episode: int,
    episode_name: str | None = None,
) -> Callable[[SearchResult, str], int | None]:
    alias_profiles = _build_tv_alias_profiles(show_aliases)
    episode_tokens = _build_episode_match_tokens(season=season, episode=episode)
    episode_title_bonus = _build_episode_title_bonus(episode_name)

    def score(result: SearchResult, _query: str) -> int | None:
        normalized_title = normalize_alias_key(result.title)
        if not normalized_title:
            return None
        padded_title = f" {normalized_title} "
        if not any(_contains_normalized_phrase(padded_title, token) for token in episode_tokens):
            return None

        best_score: int | None = None
        episode_bonus = _score_episode_title_bonus(padded_title, episode_title_bonus)
        for index, alias_profile in enumerate(alias_profiles):
            alias_score = _score_tv_alias_match(
                normalized_title=normalized_title,
                padded_title=padded_title,
                alias_key=alias_profile["key"],
                alias_index=index,
                is_weak=alias_profile["is_weak"],
                episode_tokens=episode_tokens,
            )
            if alias_score is None:
                continue
            total_score = alias_score + episode_bonus
            if best_score is None or total_score > best_score:
                best_score = total_score
        return best_score

    return score


def build_tv_episode_result_matcher(
    *,
    show_name: str,
    request_query: str | None = None,
    title_metadata: TitleMetadata | dict[str, Any] | None = None,
    season: int,
    episode: int,
    episode_name: str | None = None,
    search_aliases: list[str] | None = None,
) -> Callable[[SearchResult, str], bool]:
    effective_aliases = dedupe_queries(
        search_aliases
        or build_tv_search_aliases(
            show_name=show_name,
            request_query=request_query,
            title_metadata=title_metadata,
        )
    )
    scorer = build_tv_episode_result_scorer(
        show_aliases=effective_aliases,
        season=season,
        episode=episode,
        episode_name=episode_name,
    )

    def matches(result: SearchResult, query: str) -> bool:
        return scorer(result, query) is not None

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


def search_tv_episode_results(
    *,
    client: SdilejClient,
    show_aliases: list[str],
    season: int,
    episode: int,
    category: str,
    sort: str = "relevance",
    language: str | None,
    language_scope: LanguageScope,
    strict_dubbing: bool,
    release_year: int | None,
    max_results_per_query: int,
    result_scorer: Callable[[SearchResult, str], int | None] | None = None,
) -> dict[str, Any]:
    normalized_language = client.normalize_language(language)
    alias_queries = dedupe_queries(show_aliases)
    aggregated: dict[str, dict[str, Any]] = {}
    query_errors: list[str] = []
    expanded_queries: list[str] = []
    first_response_meta: dict[str, Any] | None = None

    for alias in alias_queries:
        alias_found_results = False
        for query in build_episode_query_variants([alias], season, episode):
            expanded_queries.append(query)
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

            query_added_any = False
            for result in search_response.results:
                title_match_score = result_scorer(result, query) if result_scorer is not None else 0
                if result_scorer is not None and title_match_score is None:
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
                    item["title_match_score"] = int(title_match_score or 0)
                    item["language_priority"] = language_priority
                    item["size_bytes"] = size_bytes
                    item["query_priority"] = len(expanded_queries) - 1
                    item["query_hits"] = [query]
                    aggregated[key] = item
                else:
                    current = aggregated[key]
                    current["title_match_score"] = max(int(current.get("title_match_score") or 0), int(title_match_score or 0))
                    current["language_priority"] = max(int(current.get("language_priority") or 0), language_priority)
                    current["size_bytes"] = max(int(current.get("size_bytes") or 0), size_bytes)
                    current["query_priority"] = min(int(current.get("query_priority") or 0), len(expanded_queries) - 1)
                    current_hits = set(current.get("query_hits") or [])
                    current_hits.add(query)
                    current["query_hits"] = sorted(current_hits)
                query_added_any = True

            if query_added_any:
                alias_found_results = True
                break

        if alias_found_results:
            continue

    sorted_items = sorted(
        aggregated.values(),
        key=lambda item: (
            -int(item.get("title_match_score") or 0),
            -int(item.get("language_priority") or 0),
            -int(item.get("size_bytes") or 0),
            int(item.get("query_priority") or 0),
            str(item.get("title") or "").lower(),
        ),
    )
    visible_items = []
    for item in sorted_items:
        visible = dict(item)
        visible.pop("title_match_score", None)
        visible_items.append(visible)

    if first_response_meta is None:
        first_response_meta = {
            "effective_query": expanded_queries[0] if expanded_queries else "",
            "slug": "",
            "search_url": "",
        }

    return {
        "items": visible_items,
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


def _score_tv_alias_probe(
    *,
    client: SdilejClient,
    alias: str,
    category: str,
    sort: str,
    max_results: int,
) -> int:
    alias_key = normalize_alias_key(alias)
    if not alias_key:
        return 0
    try:
        search_response = client.search(
            query=alias,
            category=category,
            sort=sort,
            language=None,
            language_scope="any",
            strict_dubbing=False,
            release_year=None,
            max_results=max_results,
        )
    except Exception:
        return 0

    score = 0
    phrase = f" {alias_key} "
    for result in search_response.results:
        normalized_title = normalize_alias_key(result.title)
        if not normalized_title:
            continue
        padded_title = f" {normalized_title} "
        if phrase in padded_title:
            score += 3
            if normalized_title.startswith(alias_key):
                score += 1
    return score


def _build_episode_match_tokens(*, season: int, episode: int) -> list[str]:
    return [
        f"s{season:02d}e{episode:02d}",
        f"{season}x{episode:02d}",
        f"{season}x{episode}",
        f"season {season} episode {episode}",
    ]


def _contains_normalized_phrase(padded_title: str, phrase: str) -> bool:
    normalized_phrase = normalize_alias_key(phrase)
    if not normalized_phrase:
        return False
    return f" {normalized_phrase} " in padded_title


def _build_tv_alias_profiles(show_aliases: list[str]) -> list[dict[str, Any]]:
    profiles: list[dict[str, Any]] = []
    kept_keys: list[str] = []
    for alias in dedupe_queries(show_aliases):
        key = normalize_alias_key(alias)
        if not key:
            continue
        profiles.append(
            {
                "key": key,
                "is_weak": _is_weak_tv_alias_key(key, kept_keys),
            }
        )
        kept_keys.append(key)
    return profiles


def _is_weak_tv_alias_key(alias_key: str, existing_alias_keys: list[str]) -> bool:
    if " " in alias_key:
        return False
    compact = alias_key.replace(" ", "")
    if len(compact) < 5:
        return True
    return any(existing.startswith(alias_key) and existing != alias_key for existing in existing_alias_keys)


def _build_episode_title_bonus(episode_name: str | None) -> dict[str, Any] | None:
    normalized = normalize_alias_key(episode_name)
    if not normalized:
        return None
    significant_words = [word for word in normalized.split() if len(word) >= 4]
    return {
        "phrase": normalized,
        "words": significant_words,
    }


def _score_episode_title_bonus(padded_title: str, episode_title_bonus: dict[str, Any] | None) -> int:
    if not episode_title_bonus:
        return 0
    if _contains_normalized_phrase(padded_title, str(episode_title_bonus["phrase"])):
        return 60
    matched_words = sum(1 for word in episode_title_bonus["words"] if _contains_normalized_phrase(padded_title, word))
    if matched_words >= 2:
        return 25
    return 0


def _score_tv_alias_match(
    *,
    normalized_title: str,
    padded_title: str,
    alias_key: str,
    alias_index: int,
    is_weak: bool,
    episode_tokens: list[str],
) -> int | None:
    if is_weak:
        if any(normalized_title.startswith(f"{alias_key} {token}") for token in episode_tokens):
            return 120 - (alias_index * 5)
        return None

    if normalized_title.startswith(f"{alias_key} "):
        return 240 - (alias_index * 5)
    if _contains_normalized_phrase(padded_title, alias_key):
        return 200 - (alias_index * 5)
    return None
