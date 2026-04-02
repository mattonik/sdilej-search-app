from __future__ import annotations

from contextlib import contextmanager
import os
from pathlib import Path
import socket
import threading
import time

import pytest
import requests
from uvicorn import Config, Server

from app.main import create_app
from app.models import SearchResponse, SearchResult, TitleMetadata
from app.storage import Storage
from app.tvmaze_client import TvEpisode, TvShowSummary

if not os.getenv("RUN_E2E"):
    pytest.skip("Set RUN_E2E=1 to run browser E2E tests.", allow_module_level=True)

playwright_sync = pytest.importorskip("playwright.sync_api")


class E2EMetadataResolver:
    def __init__(self, metadata: TitleMetadata) -> None:
        self.metadata = metadata

    def resolve_movie(self, title: str, year: int | None = None) -> TitleMetadata:
        return self.metadata

    def resolve_tv(self, title: str, *, show=None, year: int | None = None) -> TitleMetadata:
        return self.metadata

    def resolve_movie_info_links(self, title: str, year: int | None = None) -> dict:
        return {
            "found": False,
            "preferred_url": None,
            "csfd_url": None,
            "imdb_url": None,
            "resolved_title": title,
            "original_title": None,
            "year": year,
            "source": "fallback",
        }


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
        self.show = show or TvShowSummary(
            id=321,
            name="Bluey",
            premiered="2018-10-01",
            language="English",
            type="Animation",
            genres=["Children", "Family"],
            summary="A family-friendly animated series.",
            image_url=None,
        )
        self.episodes = episodes or [
            TvEpisode(id=1, season=1, number=1, name="Magic Xylophone", airdate="2018-10-01"),
            TvEpisode(id=2, season=1, number=2, name="Hospital", airdate="2018-10-02"),
        ]
        self.akas = akas or ["Bluey"]

    def lookup_show(self, show_name: str) -> TvShowSummary:
        return self.show

    def get_episodes(self, show_id: int) -> list[TvEpisode]:
        return list(self.episodes)

    def get_akas(self, show_id: int) -> list[str]:
        return list(self.akas)


def _pick_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@contextmanager
def run_test_server(app):
    port = _pick_free_port()
    server = Server(Config(app=app, host="127.0.0.1", port=port, log_level="error"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    base_url = f"http://127.0.0.1:{port}"
    deadline = time.time() + 10
    while time.time() < deadline:
        try:
            response = requests.get(f"{base_url}/healthz", timeout=0.5)
            if response.ok:
                break
        except requests.RequestException:
            time.sleep(0.1)
    else:
        server.should_exit = True
        thread.join(timeout=5)
        raise RuntimeError("Timed out waiting for test server to start.")

    try:
        yield base_url
    finally:
        server.should_exit = True
        thread.join(timeout=5)


@contextmanager
def launch_browser():
    with playwright_sync.sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(headless=True)
        except Exception as exc:  # noqa: BLE001
            pytest.skip(f"Chromium is not available for Playwright: {exc}")
        try:
            yield browser
        finally:
            browser.close()


def _build_file_search_app(tmp_path: Path):
    storage = Storage(db_path=str(tmp_path / "app.db"))
    storage.init_db()
    storage.upsert_saved_candidate(
        file_id=101,
        title="Bluey S01E01",
        detail_url="https://sdilej.cz/101/bluey-s01e01",
        download_url=None,
        size="356 MB",
        duration="00:07:00",
        extension="mkv",
        primary_year=2018,
        detected_languages=["CZ"],
        has_dub_hint=True,
        has_subtitle_hint=False,
        media_kind="tv",
        is_kids=True,
        series_name="Bluey",
        season_number=1,
        episode_number=1,
        classification_confidence="manual",
        notes=None,
    )
    storage.enqueue_download_job(
        detail_url="https://sdilej.cz/102/bluey-s01e02",
        file_id=102,
        title="Bluey S01E02",
        preferred_mode="premium",
        output_dir="/downloads",
        priority=0,
        media_kind="tv",
        is_kids=True,
        series_name="Bluey",
        season_number=1,
        episode_number=2,
    )
    metadata = TitleMetadata(
        kind="movie",
        canonical_title="Bluey",
        original_title="Bluey",
        local_titles=["Bluey"],
        aliases=["Bluey"],
        genres=[],
        summary=None,
        content_type="series",
        year=2018,
        source="test",
        source_ids={},
    )
    responses = {
        "Bluey": [
            build_search_result(file_id=101, title="Bluey S01E01 CZ dabing", detected_languages=["CZ"]),
            build_search_result(file_id=102, title="Bluey S01E02 CZ dabing", detected_languages=["CZ"]),
            build_search_result(file_id=103, title="Bluey S01E03 EN", detected_languages=["EN"]),
        ]
    }
    app = create_app(
        storage_instance=storage,
        client_instance=FakeSdilejClient(responses_by_query=responses),
        tv_client_instance=FakeTvMazeClient(),
        metadata_resolver_instance=E2EMetadataResolver(metadata),
        start_workers=False,
    )
    return app


def _build_tv_search_app(tmp_path: Path):
    media_root = tmp_path / "media"
    os.environ["DOWNLOAD_DIR"] = str(media_root)
    (media_root / "kids" / "tv" / "Bluey" / "S01").mkdir(parents=True, exist_ok=True)
    (media_root / "kids" / "tv" / "Bluey" / "S01" / "Bluey.S01E01.mkv").write_text("video", encoding="utf-8")

    storage = Storage(db_path=str(tmp_path / "tv.db"))
    storage.init_db()
    metadata = TitleMetadata(
        kind="tv",
        canonical_title="Bluey",
        original_title="Bluey",
        local_titles=["Bluey"],
        aliases=["Bluey"],
        genres=["Children", "Family"],
        summary="A family-friendly animated series.",
        content_type="Animation",
        year=2018,
        source="test",
        source_ids={},
    )
    app = create_app(
        storage_instance=storage,
        client_instance=FakeSdilejClient(responses_by_query={"Bluey S01E02": [build_search_result(file_id=202, title="Bluey S01E02")]}),
        tv_client_instance=FakeTvMazeClient(),
        metadata_resolver_instance=E2EMetadataResolver(metadata),
        start_workers=False,
    )
    return app


@pytest.mark.e2e
def test_file_search_view_and_filter_state_persist(tmp_path) -> None:
    app = _build_file_search_app(tmp_path)

    with run_test_server(app) as base_url, launch_browser() as browser:
        page = browser.new_page()
        page.goto(f"{base_url}/?query=Bluey&category=video", wait_until="networkidle")
        page.wait_for_selector("#fileResultsToolbar")

        page.click("#fileResultsListBtn")
        page.locator('.file-results-filter-chip[data-filter="saved"]').click()

        page.reload(wait_until="networkidle")

        assert page.evaluate("window.localStorage.getItem('fileResultsView')") == "list"
        assert page.evaluate("window.localStorage.getItem('fileResultsFilter')") == "saved"
        assert page.locator("#fileResultsListBtn.active").count() == 1
        assert page.locator('.file-results-filter-chip[data-filter="saved"].active').count() == 1
        assert page.locator(".card-saved-state", has_text="Saved").count() >= 1


@pytest.mark.e2e
def test_tv_search_marks_downloaded_episode_without_searching(tmp_path) -> None:
    app = _build_tv_search_app(tmp_path)

    with run_test_server(app) as base_url, launch_browser() as browser:
        page = browser.new_page()
        page.goto(base_url, wait_until="networkidle")
        page.click("#tvSearchModeBtn")
        page.fill("#tvShowName", "Bluey")
        page.press("#tvShowName", "Enter")
        page.wait_for_selector("#tvShowSummaryCard")
        page.click("#tvSelectAllSeasons")
        page.click("#tvSearchBtn")
        page.locator("#tvResults details.tv-season summary").first.click()
        page.wait_for_selector("#tvResults details.tv-season[open] .tv-episode-card")

        first_episode = page.locator("#tvResults details.tv-season[open] .tv-episode-card").first
        expect_text = first_episode.locator(".tv-episode-status")
        expect_text.wait_for(state="visible")
        assert "downloaded" in expect_text.text_content().lower()
        assert first_episode.locator("button", has_text="Search anyway").count() == 1
