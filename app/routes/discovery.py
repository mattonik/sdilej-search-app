from __future__ import annotations

import re
import unicodedata

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse

from ..diagnostics import error_response
from ..main import _get_services
from ..models import SearchResult
from ..sdilej_client import SdilejClientError
from ..tmdb_client import DiscoveryMode, TmdbClient, TmdbClientError

router = APIRouter()


def _normalize_key(value: str | None) -> str:
    return (
        unicodedata.normalize("NFKD", value or "")
        .encode("ascii", "ignore")
        .decode("ascii")
        .lower()
    )


def _parse_size_bytes(value: str | None) -> int:
    if not value:
        return 0
    match = re.search(r"(\d+(?:[.,]\d+)?)\s*([kmgt])?b", value, re.IGNORECASE)
    if not match:
        return 0
    amount = float(match.group(1).replace(",", "."))
    unit = (match.group(2) or "").lower()
    multiplier = {"k": 1024, "m": 1024**2, "g": 1024**3, "t": 1024**4}.get(unit, 1)
    return int(amount * multiplier)


def _score_candidate(result: SearchResult, *, movie: dict) -> int:
    title_key = _normalize_key(result.title)
    movie_titles = [movie.get("title"), movie.get("original_title")]
    score = 0
    title_matches = False
    for candidate in movie_titles:
        candidate_key = _normalize_key(candidate)
        if candidate_key and candidate_key in title_key:
            score += 50
            title_matches = True
            break
    if not title_matches:
        return 0
    if movie.get("year") and movie.get("year") in result.detected_years:
        score += 20
    if result.is_playable:
        score += 10
    score += min(_parse_size_bytes(result.size) // (700 * 1024 * 1024), 8)
    return score


def _availability_for_movie(request: Request, movie: dict, *, language: str | None) -> dict:
    services = _get_services(request)
    queries: list[str] = []
    for value in [movie.get("title"), movie.get("original_title")]:
        text = str(value or "").strip()
        if text and text.lower() not in {item.lower() for item in queries}:
            queries.append(text)

    best_result = None
    best_score = -1
    best_query = None
    total_results = 0
    for query in queries[:2]:
        response = services.client.search(
            query=query,
            category="video",
            sort="downloads",
            language=language or "",
            language_scope="any",
            strict_dubbing=False,
            release_year=movie.get("year"),
            max_results=8,
        )
        total_results += response.result_count
        for result in response.results:
            score = _score_candidate(result, movie=movie)
            if score > 0 and score > best_score:
                best_score = score
                best_result = result
                best_query = query

    if best_result is None:
        return {"status": "not_found", "query": queries[0] if queries else "", "result_count": 0, "best_result": None}

    status = "available" if best_score >= 55 else "weak_match"
    return {
        "status": status,
        "query": best_query,
        "result_count": total_results,
        "best_result": best_result.to_dict(),
    }


@router.get("/api/discovery/movie-genres")
def api_discovery_movie_genres(
    request: Request,
    language: str = Query(default="sk-SK", max_length=16),
):
    try:
        return JSONResponse({"configured": True, "items": TmdbClient().list_movie_genres(language=language)})
    except TmdbClientError as exc:
        return JSONResponse(
            {
                "configured": False,
                "items": [],
                "error": str(exc),
                "hint": "Set TMDB_BEARER_TOKEN to enable movie discovery.",
            }
        )
    except Exception as exc:  # noqa: BLE001
        return error_response(
            request,
            status_code=502,
            error="Movie genres could not be loaded.",
            error_code="tmdb_genres_failed",
            hint="Retry the request or check TMDB connectivity.",
            retryable=True,
            details=str(exc),
        )


@router.get("/api/discovery/movies")
def api_discovery_movies(
    request: Request,
    mode: DiscoveryMode = Query(default="trending"),
    time_window: str = Query(default="week", pattern="^(day|week)$"),
    genre: int | None = Query(default=None, ge=1),
    year: int | None = Query(default=None, ge=1900, le=2099),
    region: str = Query(default="SK", max_length=8),
    language: str = Query(default="sk-SK", max_length=16),
    sdilej_language: str = Query(default="", max_length=32),
    limit: int = Query(default=12, ge=1, le=20),
):
    try:
        movies = TmdbClient().discover_movies(
            mode=mode,
            language=language,
            region=region,
            genre=genre,
            year=year,
            time_window="day" if time_window == "day" else "week",
            limit=limit,
        )
        items = []
        for movie in movies:
            try:
                availability = _availability_for_movie(request, movie, language=sdilej_language)
            except SdilejClientError as exc:
                availability = {
                    "status": "error",
                    "query": movie.get("title") or movie.get("original_title") or "",
                    "result_count": 0,
                    "best_result": None,
                    "error": str(exc),
                }
            items.append({**movie, "availability": availability})
        return JSONResponse({"configured": True, "items": items})
    except TmdbClientError as exc:
        return JSONResponse(
            {
                "configured": False,
                "items": [],
                "error": str(exc),
                "hint": "Set TMDB_BEARER_TOKEN to enable movie discovery.",
            }
        )
    except Exception as exc:  # noqa: BLE001
        return error_response(
            request,
            status_code=502,
            error="Movie discovery failed.",
            error_code="tmdb_discovery_failed",
            hint="Retry the request or check TMDB and sdilej connectivity.",
            retryable=True,
            details=str(exc),
        )
