from __future__ import annotations

import requests

from .dataclass_compat import dataclass

TVMAZE_BASE_URL = "https://api.tvmaze.com"


class TvMazeClientError(RuntimeError):
    pass


@dataclass(slots=True)
class TvEpisode:
    id: int
    season: int
    number: int
    name: str | None
    airdate: str | None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "season": self.season,
            "number": self.number,
            "name": self.name,
            "airdate": self.airdate,
        }


@dataclass(slots=True)
class TvShowSummary:
    id: int
    name: str
    premiered: str | None
    language: str | None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "premiered": self.premiered,
            "language": self.language,
            "source": "tvmaze",
        }


class TvMazeClient:
    def __init__(self, timeout_seconds: int = 20) -> None:
        self.timeout_seconds = timeout_seconds
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "sdilej-search-app/1.0"})

    def lookup_show(self, show_name: str) -> TvShowSummary:
        query = show_name.strip()
        if not query:
            raise TvMazeClientError("show_name is required.")

        response = self.session.get(
            f"{TVMAZE_BASE_URL}/search/shows",
            params={"q": query},
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        items = response.json()
        if not isinstance(items, list) or not items:
            raise TvMazeClientError(f"No TV show found for '{query}'.")

        picked = self._pick_best_match(query, items)
        show = picked.get("show") or {}
        show_id = show.get("id")
        name = (show.get("name") or "").strip()
        if not show_id or not name:
            raise TvMazeClientError("TV metadata response is incomplete.")

        return TvShowSummary(
            id=int(show_id),
            name=name,
            premiered=show.get("premiered"),
            language=show.get("language"),
        )

    def get_episodes(self, show_id: int) -> list[TvEpisode]:
        response = self.session.get(
            f"{TVMAZE_BASE_URL}/shows/{show_id}/episodes",
            timeout=self.timeout_seconds,
        )
        if response.status_code == 404:
            raise TvMazeClientError("Show was not found on TVmaze.")
        response.raise_for_status()

        raw_items = response.json()
        if not isinstance(raw_items, list):
            raise TvMazeClientError("Unexpected TVmaze episodes response.")

        episodes: list[TvEpisode] = []
        for item in raw_items:
            season = item.get("season")
            number = item.get("number")
            episode_id = item.get("id")
            if episode_id is None or season is None or number is None:
                continue
            try:
                season_value = int(season)
                number_value = int(number)
                episode_id_value = int(episode_id)
            except (TypeError, ValueError):
                continue
            if season_value < 1 or number_value < 1:
                continue
            episodes.append(
                TvEpisode(
                    id=episode_id_value,
                    season=season_value,
                    number=number_value,
                    name=(item.get("name") or None),
                    airdate=(item.get("airdate") or None),
                )
            )

        episodes.sort(key=lambda ep: (ep.season, ep.number, ep.id))
        return episodes

    def get_akas(self, show_id: int) -> list[str]:
        response = self.session.get(
            f"{TVMAZE_BASE_URL}/shows/{show_id}/akas",
            timeout=self.timeout_seconds,
        )
        if response.status_code == 404:
            raise TvMazeClientError("Show was not found on TVmaze.")
        response.raise_for_status()

        raw_items = response.json()
        if not isinstance(raw_items, list):
            raise TvMazeClientError("Unexpected TVmaze AKA response.")

        aliases: list[str] = []
        seen: set[str] = set()
        for item in raw_items:
            name = str((item or {}).get("name") or "").strip()
            key = name.lower()
            if not name or key in seen:
                continue
            seen.add(key)
            aliases.append(name)
        return aliases

    def _pick_best_match(self, query: str, items: list[dict]) -> dict:
        query_norm = query.strip().lower()

        def sort_key(item: dict) -> tuple[int, float, str]:
            show = item.get("show") or {}
            name = str(show.get("name") or "").strip()
            name_norm = name.lower()
            exact = 1 if name_norm == query_norm else 0
            starts = 1 if name_norm.startswith(query_norm) else 0
            score = float(item.get("score") or 0.0)
            return (exact + starts, score, name_norm)

        return max(items, key=sort_key)
