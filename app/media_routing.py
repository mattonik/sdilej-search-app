from __future__ import annotations

import re
import unicodedata
from dataclasses import asdict, dataclass
from pathlib import PurePosixPath
from typing import Literal

MediaKind = Literal["movie", "tv", "unknown"]
ClassificationConfidence = Literal["strict", "loose", "unknown", "manual"]


_DEFAULT_LIBRARY_PATHS = {
    "movies_dir": "/movies",
    "tv_dir": "/tv",
    "kids_movies_dir": "/kids/movies",
    "kids_tv_dir": "/kids/tv",
    "unsorted_dir": "/unsorted",
}

_STRICT_TV_RE = re.compile(r"\bS(?P<season>\d{1,2})\s*[.\-_ ]*E(?P<episode>\d{1,3})\b", re.IGNORECASE)
_LOOSE_TV_RE = re.compile(r"\b(?P<season>\d{1,2})\s*[xX]\s*(?P<episode>\d{1,3})\b")
_SEASON_EPISODE_RE = re.compile(
    r"\bseason\s*(?P<season>\d{1,2})\b.*?\b(?:episode|ep|e)\s*(?P<episode>\d{1,3})\b",
    re.IGNORECASE,
)
_TV_HINT_RE = re.compile(r"\b(?:s\d{1,2}|season|episode|ep\.?|epizod|serial|series)\b", re.IGNORECASE)
_KIDS_HINT_RE = re.compile(
    r"\b(?:kids?|child(?:ren)?|cartoon|anim(?:e|ated)|detsk|deti|rozpravk|bluey|paw\s*patrol|peppa)\b",
    re.IGNORECASE,
)
_FILE_EXT_RE = re.compile(r"\.[A-Za-z0-9]{2,5}$")


@dataclass(slots=True)
class MediaClassification:
    media_kind: MediaKind
    is_kids: bool
    series_name: str | None
    season_number: int | None
    episode_number: int | None
    confidence: ClassificationConfidence
    uncertain_reason: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def default_library_paths() -> dict[str, str]:
    return dict(_DEFAULT_LIBRARY_PATHS)


def classify_media_title(
    title: str,
    *,
    media_kind_override: MediaKind | None = None,
    is_kids_override: bool | None = None,
    series_name_override: str | None = None,
    season_number_override: int | None = None,
    episode_number_override: int | None = None,
) -> MediaClassification:
    text = title.strip()
    stem = _strip_file_extension(text)
    is_kids_detected = bool(_KIDS_HINT_RE.search(_normalize_text(stem)))

    if media_kind_override in {"movie", "tv"}:
        return MediaClassification(
            media_kind=media_kind_override,
            is_kids=is_kids_detected if is_kids_override is None else bool(is_kids_override),
            series_name=_normalize_optional_text(series_name_override),
            season_number=season_number_override,
            episode_number=episode_number_override,
            confidence="manual",
            uncertain_reason=None,
        )

    strict_match = _STRICT_TV_RE.search(stem)
    if strict_match:
        season = int(strict_match.group("season"))
        episode = int(strict_match.group("episode"))
        series = _extract_series_name(stem, strict_match.start())
        if series:
            return MediaClassification(
                media_kind="tv",
                is_kids=is_kids_detected if is_kids_override is None else bool(is_kids_override),
                series_name=series,
                season_number=season,
                episode_number=episode,
                confidence="strict",
                uncertain_reason=None,
            )

    loose_match = _LOOSE_TV_RE.search(stem)
    if loose_match:
        season = int(loose_match.group("season"))
        episode = int(loose_match.group("episode"))
        series = _extract_series_name(stem, loose_match.start())
        if series:
            return MediaClassification(
                media_kind="tv",
                is_kids=is_kids_detected if is_kids_override is None else bool(is_kids_override),
                series_name=series,
                season_number=season,
                episode_number=episode,
                confidence="loose",
                uncertain_reason=None,
            )

    season_episode_match = _SEASON_EPISODE_RE.search(stem)
    if season_episode_match:
        season = int(season_episode_match.group("season"))
        episode = int(season_episode_match.group("episode"))
        series = _extract_series_name(stem, season_episode_match.start())
        if series:
            return MediaClassification(
                media_kind="tv",
                is_kids=is_kids_detected if is_kids_override is None else bool(is_kids_override),
                series_name=series,
                season_number=season,
                episode_number=episode,
                confidence="loose",
                uncertain_reason=None,
            )

    if _TV_HINT_RE.search(_normalize_text(stem)):
        return MediaClassification(
            media_kind="unknown",
            is_kids=is_kids_detected if is_kids_override is None else bool(is_kids_override),
            series_name=_normalize_optional_text(series_name_override),
            season_number=season_number_override,
            episode_number=episode_number_override,
            confidence="unknown",
            uncertain_reason="TV markers detected but season/episode pattern was not clear.",
        )

    return MediaClassification(
        media_kind="movie",
        is_kids=is_kids_detected if is_kids_override is None else bool(is_kids_override),
        series_name=None,
        season_number=None,
        episode_number=None,
        confidence="loose",
        uncertain_reason=None,
    )


def requires_classification_confirmation(classification: MediaClassification) -> bool:
    if classification.confidence == "manual":
        return False
    if classification.media_kind == "unknown":
        return True
    if classification.media_kind == "tv":
        return not bool(classification.series_name and classification.season_number)
    return False


def resolve_destination_subpath(
    classification: MediaClassification,
    *,
    library_paths: dict[str, str],
) -> str:
    if classification.media_kind == "movie":
        key = "kids_movies_dir" if classification.is_kids else "movies_dir"
        return _normalize_route(library_paths.get(key) or _DEFAULT_LIBRARY_PATHS[key])

    if classification.media_kind == "tv":
        key = "kids_tv_dir" if classification.is_kids else "tv_dir"
        base_route = _normalize_route(library_paths.get(key) or _DEFAULT_LIBRARY_PATHS[key])
        series = _sanitize_segment(classification.series_name or "unknown-series")
        season_number = classification.season_number if classification.season_number is not None else 1
        season = f"season{max(1, season_number):02d}"
        return str(PurePosixPath(base_route) / series / season)

    return _normalize_route(library_paths.get("unsorted_dir") or _DEFAULT_LIBRARY_PATHS["unsorted_dir"])


def _normalize_text(value: str) -> str:
    return (
        unicodedata.normalize("NFKD", value)
        .encode("ascii", "ignore")
        .decode("ascii")
        .lower()
    )


def _strip_file_extension(value: str) -> str:
    return _FILE_EXT_RE.sub("", value).strip()


def _extract_series_name(title: str, marker_index: int) -> str | None:
    candidate = title[:marker_index].strip(" -._()[]")
    candidate = re.sub(r"\([^)]*\)$", "", candidate).strip(" -._")
    if not candidate:
        return None
    return candidate


def _normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    text = value.strip()
    return text or None


def _normalize_route(route: str) -> str:
    parts = [
        _sanitize_segment(part)
        for part in route.replace("\\", "/").split("/")
        if part and part not in {".", ".."}
    ]
    return str(PurePosixPath(*parts)) if parts else "unsorted"


def _sanitize_segment(segment: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._ -]+", "_", segment).strip(" .")
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned or "unknown"
