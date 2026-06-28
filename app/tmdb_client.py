from __future__ import annotations

import os
from dataclasses import asdict
from typing import Any, Literal

import requests

from .dataclass_compat import dataclass

TMDB_BASE_URL = "https://api.themoviedb.org/3"
TMDB_IMAGE_BASE_URL = "https://image.tmdb.org/t/p/w342"

DiscoveryMode = Literal["trending", "popular", "now_playing", "upcoming", "top_rated"]


class TmdbClientError(RuntimeError):
    pass


@dataclass(slots=True)
class TmdbMovie:
    tmdb_id: int
    title: str
    original_title: str | None
    overview: str | None
    release_date: str | None
    year: int | None
    vote_average: float | None
    vote_count: int | None
    popularity: float | None
    poster_url: str | None
    genre_ids: list[int]

    def to_dict(self) -> dict:
        return asdict(self)


class TmdbClient:
    def __init__(self, token: str | None = None, timeout_seconds: int = 20) -> None:
        self.token = (token if token is not None else os.getenv("TMDB_BEARER_TOKEN", "")).strip()
        self.timeout_seconds = timeout_seconds
        self.session = requests.Session()

    @property
    def configured(self) -> bool:
        return bool(self.token)

    def discover_movies(
        self,
        *,
        mode: DiscoveryMode,
        language: str,
        region: str | None,
        genre: int | None,
        year: int | None,
        time_window: Literal["day", "week"] = "week",
        limit: int = 12,
    ) -> list[dict]:
        if not self.configured:
            raise TmdbClientError("TMDB_BEARER_TOKEN is not configured.")

        endpoint = self._endpoint_for_mode(mode, time_window=time_window)
        params: dict[str, Any] = {"language": language, "page": 1}
        if region:
            params["region"] = region
        if genre and mode != "trending":
            params["with_genres"] = str(genre)
        if year and mode != "trending":
            params["primary_release_year"] = year

        payload = self._get(endpoint, params=params)
        movies = [self._parse_movie(item) for item in payload.get("results", []) if isinstance(item, dict)]

        if mode == "trending" and (genre or year):
            movies = [
                movie
                for movie in movies
                if (not genre or genre in movie.genre_ids) and (not year or movie.year == year)
            ]

        return [movie.to_dict() for movie in movies[: max(1, min(limit, 20))]]

    def list_movie_genres(self, *, language: str) -> list[dict]:
        if not self.configured:
            raise TmdbClientError("TMDB_BEARER_TOKEN is not configured.")
        payload = self._get("/genre/movie/list", params={"language": language})
        return [
            {"id": item.get("id"), "name": item.get("name")}
            for item in payload.get("genres", [])
            if isinstance(item, dict) and item.get("id") and item.get("name")
        ]

    def _endpoint_for_mode(self, mode: DiscoveryMode, *, time_window: Literal["day", "week"]) -> str:
        if mode == "trending":
            return f"/trending/movie/{time_window if time_window in {'day', 'week'} else 'week'}"
        return {
            "popular": "/movie/popular",
            "now_playing": "/movie/now_playing",
            "upcoming": "/movie/upcoming",
            "top_rated": "/movie/top_rated",
        }.get(mode, "/movie/popular")

    def _get(self, path: str, *, params: dict[str, Any]) -> dict:
        response = self.session.get(
            f"{TMDB_BASE_URL}{path}",
            params=params,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/json",
            },
            timeout=self.timeout_seconds,
        )
        if response.status_code == 401:
            raise TmdbClientError("TMDB token was rejected.")
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise TmdbClientError("TMDB returned an invalid response.")
        return payload

    def _parse_movie(self, item: dict) -> TmdbMovie:
        release_date = str(item.get("release_date") or "").strip() or None
        year = None
        if release_date and len(release_date) >= 4 and release_date[:4].isdigit():
            year = int(release_date[:4])
        poster_path = str(item.get("poster_path") or "").strip()
        return TmdbMovie(
            tmdb_id=int(item.get("id") or 0),
            title=str(item.get("title") or item.get("name") or "").strip(),
            original_title=str(item.get("original_title") or "").strip() or None,
            overview=str(item.get("overview") or "").strip() or None,
            release_date=release_date,
            year=year,
            vote_average=float(item["vote_average"]) if isinstance(item.get("vote_average"), (int, float)) else None,
            vote_count=int(item["vote_count"]) if isinstance(item.get("vote_count"), int) else None,
            popularity=float(item["popularity"]) if isinstance(item.get("popularity"), (int, float)) else None,
            poster_url=f"{TMDB_IMAGE_BASE_URL}{poster_path}" if poster_path else None,
            genre_ids=[int(value) for value in item.get("genre_ids", []) if isinstance(value, int)],
        )
