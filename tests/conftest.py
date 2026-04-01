from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from app.main import create_app
from app.models import SearchResponse, SearchResult, TitleMetadata
from app.storage import Storage
from app.tv_search_worker import TvSearchWorker
from app.tvmaze_client import TvEpisode, TvShowSummary


def build_sdilej_search_html(cards: list[dict[str, Any]]) -> str:
    card_html: list[str] = []
    for card in cards:
        playable = "<span class='playable'></span>" if card.get("playable") else ""
        image_html = f"<img class='img-responsive' src='{card['thumbnail']}' />" if card.get("thumbnail") else ""
        meta_html = f"<p>meta</p><p>{card.get('meta', '')}</p>"
        card_html.append(
            f"""
            <div class="videobox">
              <a href="{card['detail_url']}" title="{card['title']}">
                {image_html}
              </a>
              <div class="videobox-title">
                <a href="{card['detail_url']}">{card['title']}</a>
              </div>
              <div class="videobox-desc">
                {meta_html}
              </div>
              {playable}
            </div>
            """
        )
    return f"<html><body>{''.join(card_html)}</body></html>"


def build_search_result(
    *,
    file_id: int,
    title: str,
    detail_url: str | None = None,
    size: str = "700 MB",
    detected_languages: list[str] | None = None,
) -> SearchResult:
    return SearchResult(
        file_id=file_id,
        title=title,
        detail_url=detail_url or f"https://sdilej.cz/{file_id}/file-{file_id}.mkv",
        thumbnail_url=None,
        size=size,
        duration="00:21:00",
        is_playable=True,
        extension="mkv",
        detected_years=[2020],
        primary_year=2020,
        detected_languages=detected_languages or [],
        has_dub_hint="dab" in title.lower() or "sk" in title.lower(),
        has_subtitle_hint="tit" in title.lower(),
    )


def build_search_response(query: str, results: list[SearchResult]) -> SearchResponse:
    return SearchResponse(
        query=query,
        effective_query=query,
        slug=query.lower().replace(" ", "-"),
        category="video",
        sort="relevance",
        language=None,
        language_scope="any",
        strict_dubbing=False,
        release_year=None,
        search_url=f"https://sdilej.cz/{query.lower().replace(' ', '-')}/s/video-",
        unfiltered_result_count=len(results),
        result_count=len(results),
        results=results,
    )


class FakeSdilejClient:
    def __init__(self, timeout_seconds: int = 20, responses_by_query: dict[str, list[SearchResult]] | None = None) -> None:
        self.timeout_seconds = timeout_seconds
        self.responses_by_query = responses_by_query or {}
        self.calls: list[str] = []

    def search(
        self,
        query: str,
        category: str = "video",
        sort: str = "relevance",
        max_results: int = 150,
        language: str | None = None,
        language_scope: str = "any",
        strict_dubbing: bool = False,
        release_year: int | None = None,
    ) -> SearchResponse:
        self.calls.append(query)
        results = list(self.responses_by_query.get(query, []))[:max_results]
        return build_search_response(query, results)

    def normalize_language(self, language: str | None) -> str | None:
        if language is None:
            return None
        text = language.strip()
        return text.upper() if text else None

    def language_match_priority(
        self,
        *,
        title: str,
        language: str | None,
        scope: str = "any",
        strict_dubbing: bool = False,
    ) -> int:
        if not language:
            return 0
        normalized = language.upper()
        upper_title = title.upper()
        if f"{normalized} DAB" in upper_title or f"{normalized} DUB" in upper_title:
            return 30
        if f"{normalized} TIT" in upper_title or f"{normalized} SUB" in upper_title:
            return 15
        if normalized in upper_title:
            return 20
        return 0

    def autocomplete(self, term: str, limit: int = 10) -> list[str]:
        return [term]


class FakeTvMazeClient:
    def __init__(
        self,
        *,
        show: TvShowSummary | None = None,
        episodes: list[TvEpisode] | None = None,
        akas: list[str] | None = None,
    ) -> None:
        self.show = show or TvShowSummary(id=321, name="Shaun the Sheep", premiered="2007-03-01", language="English")
        self.episodes = episodes or [
            TvEpisode(id=1, season=1, number=1, name="Off the Baa!", airdate="2007-03-05"),
            TvEpisode(id=2, season=1, number=2, name="Fetching", airdate="2007-03-06"),
        ]
        self.akas = akas or ["Vesela farma", "Ovecka Shaun"]

    def lookup_show(self, show_name: str) -> TvShowSummary:
        return self.show

    def get_episodes(self, show_id: int) -> list[TvEpisode]:
        return list(self.episodes)

    def get_akas(self, show_id: int) -> list[str]:
        return list(self.akas)


class StaticMetadataResolver:
    def __init__(self, metadata: TitleMetadata) -> None:
        self.metadata = metadata
        self.movie_calls: list[tuple[str, int | None]] = []
        self.tv_calls: list[tuple[str, int | None]] = []

    def resolve_movie(self, title: str, year: int | None = None) -> TitleMetadata:
        self.movie_calls.append((title, year))
        return self.metadata

    def resolve_tv(self, title: str, *, show=None, year: int | None = None) -> TitleMetadata:
        self.tv_calls.append((title, year))
        return self.metadata


class StaticSearchClientFactory:
    def __init__(self, responses_by_query: dict[str, list[SearchResult]]) -> None:
        self.responses_by_query = responses_by_query
        self.instances: list[FakeSdilejClient] = []

    def __call__(self, timeout_seconds: int = 30) -> FakeSdilejClient:
        client = FakeSdilejClient(timeout_seconds=timeout_seconds, responses_by_query=self.responses_by_query)
        self.instances.append(client)
        return client


@pytest.fixture
def sample_movie_metadata() -> TitleMetadata:
    return TitleMetadata(
        kind="movie",
        canonical_title="Ovecka Shaun",
        original_title="Shaun the Sheep",
        local_titles=["Ovecka Shaun", "Vesela farma"],
        aliases=["Shaun the Sheep", "Ovecka Shaun", "Vesela farma"],
        year=2007,
        source="czdb",
        source_ids={"czdb": 123},
    )


@pytest.fixture
def storage(tmp_path: Path) -> Storage:
    db_path = tmp_path / "app.db"
    store = Storage(db_path=str(db_path))
    store.init_db()
    return store


@pytest.fixture
def media_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "media"
    root.mkdir()
    monkeypatch.setenv("DOWNLOAD_DIR", str(root))
    return root


@pytest.fixture
def app_factory(storage: Storage, media_root: Path):
    def _make(**kwargs):
        kwargs.setdefault("storage_instance", storage)
        kwargs.setdefault("start_workers", False)
        return create_app(**kwargs)

    return _make


@pytest.fixture
def sample_czdb_movie_response() -> dict[str, Any]:
    return {
        "results": [
            {
                "id": 43840,
                "csfd_id": 9499,
                "nazev": "Matrix",
                "original": "The Matrix",
                "alt_nazev": "Matrix | Matrix Reloaded? | The Matrix",
                "rok": 1999,
                "csfd_url": "https://www.csfd.cz/film/9499",
            }
        ],
        "response": "True",
    }


@pytest.fixture
def sample_czdb_show_response() -> dict[str, Any]:
    return {
        "results": [
            {
                "id": 101,
                "csfd_id": 202,
                "nazev": "Ovecka Shaun",
                "original": "Shaun the Sheep",
                "alt_nazev": "Shaun the Sheep | Vesela farma | Ovecka Shaun",
                "rok": 2007,
                "csfd_url": "https://www.csfd.cz/film/202",
            }
        ],
        "response": "True",
    }


@pytest.fixture
def sample_tvmaze_show_payload() -> list[dict[str, Any]]:
    return [
        {
            "score": 10.0,
            "show": {
                "id": 321,
                "name": "Shaun the Sheep",
                "premiered": "2007-03-05",
                "language": "English",
            },
        }
    ]


@pytest.fixture
def sample_tvmaze_episode_payload() -> list[dict[str, Any]]:
    return [
        {"id": 1, "season": 1, "number": 1, "name": "Off the Baa!", "airdate": "2007-03-05"},
        {"id": 2, "season": 1, "number": 2, "name": "Fetching", "airdate": "2007-03-06"},
    ]


@pytest.fixture
def sample_tvmaze_akas_payload() -> list[dict[str, Any]]:
    return [
        {"name": "Vesela farma", "country": {"code": "SK"}},
        {"name": "Ovecka Shaun", "country": {"code": "CZ"}},
    ]
