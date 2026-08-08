from __future__ import annotations

from contextlib import contextmanager
import json
import os
from pathlib import Path
import socket
import threading
import time

import pytest
import requests
import responses
from uvicorn import Config, Server

from app.kids_catalog import BASE_URL, SHOWS_URL
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


def dump_search_result(result: SearchResult) -> dict:
    if hasattr(result, "model_dump"):
        return result.model_dump(mode="json")
    if hasattr(result, "to_dict"):
        return result.to_dict()
    return dict(result)


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


KIDS_SHOWS_HTML = """
<html><body>
  <div class="media-index">
    <div class="media-img">
      <a href="https://www.veselerozpravky.sk/masa-a-medved/">
        <div class="media-grid">
          <span>2 časti</span>
          <h2 class="media-heading col-xs-12">Máša a medveď</h2>
        </div>
      </a>
    </div>
    <div class="media-img">
      <a href="https://www.veselerozpravky.sk/krtko/">
        <div class="media-grid">
          <span>1 časť</span>
          <h2 class="media-heading col-xs-12">Krtko</h2>
        </div>
      </a>
    </div>
  </div>
</body></html>
"""

KIDS_SHOW_HTML = """
<html><body>
  <h1 class="page-header-cat">Máša a medveď - video rozprávka</h1>
  <div class="media-index">
    <a href="https://www.veselerozpravky.sk/masa-a-medved-ako-sa-stretli/">
      <div class="media-grid">
        06:54
        <h2 class="media-heading col-xs-12">1. Máša a medveď: Ako sa stretli</h2>
      </div>
    </a>
    <a href="https://www.veselerozpravky.sk/masa-a-medved-do-jari-nebudit/">
      <div class="media-grid">
        06:54
        <h2 class="media-heading col-xs-12">2. Máša a medveď: Do jari nebudiť</h2>
      </div>
    </a>
  </div>
</body></html>
"""

KIDS_EPISODE_HTML = """
<html><head>
  <meta property="og:image" content="https://img.youtube.com/vi/1V3ZY_TXKwU/0.jpg">
</head><body>
  <h1>Máša a medveď: Ako sa stretli</h1>
  <script>var videoId = "1V3ZY_TXKwU";</script>
</body></html>
"""


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
    media_root = tmp_path / "media"
    os.environ["DOWNLOAD_DIR"] = str(media_root)
    (media_root / "tv" / "Reacher").mkdir(parents=True, exist_ok=True)
    (media_root / "kids" / "tv" / "Bluey").mkdir(parents=True, exist_ok=True)

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


def _build_reacher_tv_search_app(tmp_path: Path):
    storage = Storage(db_path=str(tmp_path / "reacher-tv.db"))
    storage.init_db()
    metadata = TitleMetadata(
        kind="tv",
        canonical_title="Reacher",
        original_title="Reacher",
        local_titles=["Reacher"],
        aliases=["Reacher"],
        genres=["Drama", "Action", "Thriller"],
        summary="Reacher is wrongly accused of murder while visiting a small town.",
        content_type="Scripted",
        year=2022,
        source="test",
        source_ids={},
    )
    show = TvShowSummary(
        id=43031,
        name="Reacher",
        premiered="2022-02-04",
        language="English",
        image_url="https://example.com/reacher-poster.jpg",
        type="Scripted",
        genres=["Drama", "Action", "Thriller"],
        summary="Reacher is wrongly accused of murder while visiting a small town.",
    )
    episodes = [
        TvEpisode(id=2229078, season=1, number=1, name="Welcome to Margrave", airdate="2022-02-04"),
        TvEpisode(id=2229079, season=1, number=2, name="First Dance", airdate="2022-02-04"),
    ]
    client = FakeSdilejClient(
        responses_by_query={
            "Reacher S01E01": [build_search_result(file_id=301, title="Reacher S01E01 Welcome to Margrave")],
            "Reacher S01E02": [build_search_result(file_id=302, title="Reacher S01E02 First Dance")],
        }
    )
    app = create_app(
        storage_instance=storage,
        client_instance=client,
        tv_client_instance=FakeTvMazeClient(show=show, episodes=episodes, akas=["Reacher"]),
        metadata_resolver_instance=E2EMetadataResolver(metadata),
        start_workers=True,
    )
    return app


def _build_tv_polling_app(
    tmp_path: Path,
    *,
    search_responses: dict[str, list[SearchResult]] | None = None,
    downloaded_episode_codes: tuple[str, ...] = (),
):
    media_root = tmp_path / "media"
    os.environ["DOWNLOAD_DIR"] = str(media_root)
    season_dir = media_root / "kids" / "tv" / "Bluey" / "S01"
    season_dir.mkdir(parents=True, exist_ok=True)
    for code in downloaded_episode_codes:
        (season_dir / f"Bluey.{code}.mkv").write_text("video", encoding="utf-8")

    storage = Storage(db_path=str(tmp_path / "tv-polling.db"))
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
    client = FakeSdilejClient(
        responses_by_query=search_responses
        or {
            "Bluey S01E01": [build_search_result(file_id=201, title="Bluey S01E01 Magic Xylophone")],
            "Bluey S01E02": [build_search_result(file_id=202, title="Bluey S01E02 Hospital")],
        }
    )
    app = create_app(
        storage_instance=storage,
        client_instance=client,
        tv_client_instance=FakeTvMazeClient(),
        metadata_resolver_instance=E2EMetadataResolver(metadata),
        start_workers=False,
    )
    return app, storage, media_root


@pytest.mark.e2e
def test_file_search_view_and_filter_state_persist(tmp_path) -> None:
    app = _build_file_search_app(tmp_path)

    with run_test_server(app) as base_url, launch_browser() as browser:
        page = browser.new_page()
        page.goto(f"{base_url}/?query=Bluey&category=video", wait_until="networkidle")
        page.wait_for_selector("#fileResultsToolbar")
        page.wait_for_selector(".result-card .copy-link-btn")

        page.click("#fileResultsListBtn")
        page.locator('.file-results-filter-chip[data-filter="saved"]').click()

        page.reload(wait_until="networkidle")

        assert page.evaluate("window.localStorage.getItem('fileResultsView')") == "list"
        assert page.evaluate("window.localStorage.getItem('fileResultsFilter')") == "saved"
        assert page.locator("#fileResultsToolbar").count() == 1


@pytest.mark.e2e
def test_file_search_url_overrides_stale_search_mode(tmp_path) -> None:
    app = _build_file_search_app(tmp_path)

    with run_test_server(app) as base_url, launch_browser() as browser:
        page = browser.new_page()
        page.goto(base_url, wait_until="networkidle")
        page.click("#discoverySearchModeBtn")
        assert page.locator("#movieDiscoveryPanel").is_visible()

        page.goto(f"{base_url}/?query=Bluey&category=video", wait_until="networkidle")
        page.wait_for_selector("#fileSearchPanel:not(.hidden)")
        page.wait_for_selector("#fileResultsToolbar:not(.hidden)")
        assert page.locator("#fileSearchModeBtn").evaluate("node => node.classList.contains('active')")
        assert page.locator("#movieDiscoveryPanel").is_hidden()

        page.goto(f"{base_url}/?query=Bluey&category=audio", wait_until="networkidle")
        page.wait_for_selector("#musicSearchPanel:not(.hidden)")
        page.wait_for_selector("#fileResultsToolbar:not(.hidden)")
        assert page.locator("#musicSearchModeBtn").evaluate("node => node.classList.contains('active')")


@pytest.mark.e2e
def test_mobile_navigation_and_search_mode_tabs_stay_compact(tmp_path) -> None:
    app = _build_file_search_app(tmp_path)

    with run_test_server(app) as base_url, launch_browser() as browser:
        page = browser.new_page(viewport={"width": 390, "height": 844})
        page.goto(base_url, wait_until="networkidle")

        nav_box = page.locator(".workspace-tabs").bounding_box()
        assert nav_box and nav_box["height"] < 70
        assert page.locator("#fileSearchModeBtn").get_attribute("role") == "tab"
        assert page.locator("#fileSearchModeBtn").get_attribute("aria-selected") == "true"

        page.click("#tvSearchModeBtn")
        assert page.locator("#tvSearchModeBtn").get_attribute("aria-selected") == "true"
        assert page.locator("#tvModePanel").get_attribute("role") == "tabpanel"


@pytest.mark.e2e
def test_download_job_card_exposes_copy_action(tmp_path) -> None:
    app = _build_file_search_app(tmp_path)

    with run_test_server(app) as base_url, launch_browser() as browser:
        page = browser.new_page()
        page_errors = []
        page.on("pageerror", lambda error: page_errors.append(str(error)))
        page.goto(base_url, wait_until="networkidle")
        page.click('.workspace-tab[data-tab="downloads"]')
        page.wait_for_selector("#refreshDownloadsBtn")
        queue_top = page.locator(".download-queue-section").bounding_box()["y"]
        add_top = page.locator(".download-add-section").bounding_box()["y"]
        settings_open = page.locator(".download-settings-section").get_attribute("open")
        assert queue_top < add_top
        assert settings_open is None
        page.click("#refreshDownloadsBtn")
        page.wait_for_selector('#downloadJobs [data-action="copy"]', state="attached")
        assert page.locator('#downloadJobs [data-action="copy"]').count() >= 1
        assert "downloads_refresh_ui_failed" not in (page.locator("#downloadStatus").text_content() or "")
        assert page_errors == []


@pytest.mark.e2e
def test_queue_dialog_destination_preset_routes_to_kids_movies(tmp_path) -> None:
    app = _build_file_search_app(tmp_path)

    with run_test_server(app) as base_url, launch_browser() as browser:
        page = browser.new_page()
        page.goto(f"{base_url}/?query=Bluey&category=video", wait_until="networkidle")
        page.locator('.queue-dialog-btn[data-file-id="103"]').click()
        page.wait_for_selector("#queueDialogBackdrop:not(.hidden)")

        page.select_option("#queueDialogDestinationPreset", "kids_movies")
        page.wait_for_function("document.querySelector('#queueDialogPreview')?.textContent.includes('kids/movies')")
        with page.expect_response(lambda response: response.request.method == "POST" and response.url.endswith("/api/downloads")) as response_info:
            page.click("#queueDialogConfirm")

        assert response_info.value.status == 200
        page.click('.workspace-tab[data-tab="downloads"]')
        page.wait_for_function("document.querySelector('#downloadJobs')?.textContent.includes('kids/movies')")
        job_text = page.locator("#downloadJobs").text_content() or ""
        assert "Bluey S01E03 EN" in job_text
        assert "kids/movies" in job_text


@pytest.mark.e2e
def test_search_queue_action_reports_status_on_search_tab(tmp_path) -> None:
    app = _build_file_search_app(tmp_path)

    with run_test_server(app) as base_url, launch_browser() as browser:
        page = browser.new_page()

        def fail_enqueue(route) -> None:
            if route.request.method == "POST" and route.request.url.endswith("/api/downloads"):
                route.fulfill(
                    status=500,
                    json={
                        "error": "Failed to enqueue job.",
                        "error_code": "download_enqueue_failed",
                        "hint": "Retry the enqueue.",
                        "details": "test failure",
                    },
                )
                return
            route.continue_()

        page.route("**/api/downloads*", fail_enqueue)
        page.goto(f"{base_url}/?query=Bluey&category=video", wait_until="networkidle")
        page.locator('.queue-dialog-btn[data-file-id="103"]').click()
        page.wait_for_selector("#queueDialogBackdrop:not(.hidden)")
        page.click("#queueDialogConfirm")
        page.wait_for_function(
            "() => document.querySelector('#downloadStatus')?.textContent.includes('Failed to enqueue job.')"
        )
        assert page.locator("#downloadStatus").is_visible()


@pytest.mark.e2e
def test_music_search_routes_audio_results_to_music_preset(tmp_path) -> None:
    app = _build_file_search_app(tmp_path)

    with run_test_server(app) as base_url, launch_browser() as browser:
        page = browser.new_page()
        page.goto(base_url, wait_until="networkidle")
        assert page.locator("#fileSearchPanel").is_visible()
        assert page.locator("#musicSearchPanel").is_hidden()
        assert page.locator("#movieDiscoveryPanel").is_hidden()
        page.click("#musicSearchModeBtn")
        assert page.locator("#musicSearchPanel").is_visible()
        assert page.locator("#fileSearchPanel").is_hidden()
        page.fill("#musicSearchQuery", "Bluey")
        page.click('#musicSearchForm button[type="submit"]')
        page.wait_for_url("**/?query=Bluey&category=audio**")
        page.wait_for_selector("#musicSearchPanel:not(.hidden)")
        page.wait_for_selector('.queue-dialog-btn[data-file-id="103"]')

        page.locator('.queue-dialog-btn[data-file-id="103"]').click()
        page.wait_for_selector("#queueDialogBackdrop:not(.hidden)")
        assert page.locator("#queueDialogDestinationPreset").input_value() == "music"
        assert page.locator("#queueDialogMediaKind").input_value() == "music"

        with page.expect_response(lambda response: response.request.method == "POST" and response.url.endswith("/api/downloads")) as response_info:
            page.click("#queueDialogConfirm")

        assert response_info.value.status == 200
        queued_payload = response_info.value.json()
        assert queued_payload["media_kind"] == "music"
        assert queued_payload["destination_subpath"].endswith("music")
        page.click('.workspace-tab[data-tab="downloads"]')
        page.wait_for_function("document.querySelector('#downloadJobs')?.textContent.includes('Dest: music')")
        job_text = page.locator("#downloadJobs").text_content() or ""
        assert "Bluey S01E03 EN" in job_text
        assert "Dest: music" in job_text


@pytest.mark.e2e
def test_music_search_can_queue_all_results_as_music(tmp_path) -> None:
    app = _build_file_search_app(tmp_path)

    with run_test_server(app) as base_url, launch_browser() as browser:
        page = browser.new_page()
        page.goto(f"{base_url}/?query=Bluey&category=audio", wait_until="networkidle")
        page.wait_for_selector("#musicSearchPanel:not(.hidden)")
        page.wait_for_selector("#musicQueueAllBtn")
        with page.expect_response(lambda response: response.request.method == "POST" and response.url.endswith("/api/downloads")) as first_response:
            page.click("#musicQueueAllBtn")
        assert first_response.value.status == 200
        page.wait_for_function("document.querySelector('#musicAlbumQueueStatus')?.textContent.includes('2 music results queued')")


@pytest.mark.e2e
def test_movie_discovery_without_tmdb_token_shows_setup_state(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("TMDB_BEARER_TOKEN", raising=False)
    app = _build_file_search_app(tmp_path)

    with run_test_server(app) as base_url, launch_browser() as browser:
        page = browser.new_page()
        page.goto(base_url, wait_until="networkidle")
        page.click("#discoverySearchModeBtn")
        assert page.locator("#movieDiscoveryPanel").is_visible()
        assert page.locator("#fileSearchPanel").is_hidden()
        page.click('#movieDiscoveryForm button[type="submit"]')
        page.wait_for_function(
            "document.querySelector('#movieDiscoveryStatus')?.textContent.includes('TMDB_BEARER_TOKEN')"
        )
        assert "TMDB_BEARER_TOKEN" in (page.locator("#movieDiscoveryResults").text_content() or "")


@pytest.mark.e2e
def test_movie_discovery_opens_full_search_for_available_movie(tmp_path) -> None:
    app = _build_file_search_app(tmp_path)

    with run_test_server(app) as base_url, launch_browser() as browser:
        page = browser.new_page()
        page.route(
            "**/api/discovery/movie-genres**",
            lambda route: route.fulfill(json={"configured": True, "items": []}),
        )
        page.route(
            "**/api/discovery/movies**",
            lambda route: route.fulfill(
                json={
                    "configured": True,
                    "items": [
                        {
                            "title": "The Matrix",
                            "year": 1999,
                            "vote_average": 8.7,
                            "vote_count": 100,
                            "availability": {
                                "status": "available",
                                "best_result": {
                                    "file_id": 901,
                                    "title": "The Matrix 1999 1080p",
                                    "detail_url": "https://sdilej.cz/901/matrix",
                                    "size": "4 GB",
                                    "primary_year": 1999,
                                    "detected_languages": ["EN"],
                                },
                            },
                        }
                    ],
                }
            ),
        )
        page.goto(base_url, wait_until="networkidle")
        page.click("#discoverySearchModeBtn")
        page.click('#movieDiscoveryForm button[type="submit"]')
        page.wait_for_selector(".movie-discovery-search")
        page.click(".movie-discovery-search")
        page.wait_for_url("**/?query=The+Matrix+1080p&category=video&language=EN&language_scope=audio&sort=size_asc&release_year=1999#search")


@pytest.mark.e2e
def test_movie_discovery_offers_full_search_for_unavailable_movie(tmp_path) -> None:
    app = _build_file_search_app(tmp_path)

    with run_test_server(app) as base_url, launch_browser() as browser:
        page = browser.new_page()
        page.route(
            "**/api/discovery/movie-genres**",
            lambda route: route.fulfill(json={"configured": True, "items": []}),
        )
        page.route(
            "**/api/discovery/movies**",
            lambda route: route.fulfill(
                json={
                    "configured": True,
                    "items": [
                        {
                            "title": "Unknown Film",
                            "year": 2024,
                            "availability": {"status": "not_found", "best_result": None},
                        }
                    ],
                }
            ),
        )
        page.goto(base_url, wait_until="networkidle")
        page.click("#discoverySearchModeBtn")
        page.click('#movieDiscoveryForm button[type="submit"]')
        page.wait_for_selector(".movie-discovery-search")
        assert "Not found" in (page.locator(".movie-discovery-card").text_content() or "")
        page.click(".movie-discovery-search")
        page.wait_for_url("**/?query=Unknown+Film+1080p&category=video&language=EN&language_scope=audio&sort=size_asc&release_year=2024#search")


@pytest.mark.e2e
def test_youtube_quick_download_enqueues_direct_link(tmp_path) -> None:
    app = _build_file_search_app(tmp_path)

    with run_test_server(app) as base_url, launch_browser() as browser:
        page = browser.new_page()
        page.goto(base_url, wait_until="networkidle")
        page.click('.workspace-tab[data-tab="downloads"]')
        page.fill("#youtubeQuickUrl", "https://www.youtube.com/watch?v=abc123XYZ")
        with page.expect_response(lambda response: response.request.method == "POST" and response.url.endswith("/api/downloads")) as response_info:
            page.click("#youtubeQuickSubmit")
        assert response_info.value.status == 200
        page.wait_for_function("document.querySelector('#downloadJobs')?.textContent.includes('YouTube video')")

        job_text = page.locator("#downloadJobs").text_content() or ""
        assert "YouTube video" in job_text
        assert "youtube" in job_text


@pytest.mark.e2e
def test_youtube_quick_download_tv_destination_uses_local_show_picker(tmp_path) -> None:
    app = _build_file_search_app(tmp_path)

    with run_test_server(app) as base_url, launch_browser() as browser:
        page = browser.new_page()
        page.goto(base_url, wait_until="networkidle")
        page.click('.workspace-tab[data-tab="downloads"]')
        page.select_option("#youtubeQuickDestinationPreset", "tv")
        page.wait_for_selector("#youtubeQuickTvFields:not(.hidden)")
        page.locator("#youtubeQuickSeriesName").focus()
        page.wait_for_function(
            "() => Array.from(document.querySelectorAll('#youtubeQuickSeriesSuggestions option')).some((option) => option.value === 'Reacher')"
        )
        page.fill("#youtubeQuickSeriesName", "Reacher")
        page.fill("#youtubeQuickSeasonNumber", "1")
        page.fill("#youtubeQuickUrl", "https://www.youtube.com/watch?v=tv123XYZ")
        with page.expect_response(lambda response: response.request.method == 'POST' and response.url.endswith('/api/downloads')) as response_info:
            page.click("#youtubeQuickSubmit")
        assert response_info.value.status == 200
        payload = json.loads(response_info.value.request.post_data or "{}")
        assert payload["destination_preset"] == "tv"
        assert payload["media_kind"] == "tv"
        assert payload["is_kids"] is False
        assert payload["series_name"] == "Reacher"
        assert payload["season_number"] == 1


@pytest.mark.e2e
@responses.activate
def test_kids_catalog_episode_enqueue_updates_visible_state(tmp_path) -> None:
    responses.add_passthru("http://127.0.0.1")
    responses.get(SHOWS_URL, body=KIDS_SHOWS_HTML)
    responses.get(f"{BASE_URL}/masa-a-medved/", body=KIDS_SHOW_HTML)
    responses.get(f"{BASE_URL}/masa-a-medved-ako-sa-stretli/", body=KIDS_EPISODE_HTML)
    app = _build_file_search_app(tmp_path)

    with run_test_server(app) as base_url, launch_browser() as browser:
        page = browser.new_page(viewport={"width": 390, "height": 900})
        page.goto(base_url, wait_until="networkidle")
        page.click("#kidsSearchModeBtn")
        page.click("#kidsCatalogLoadBtn")
        page.wait_for_selector(".kids-catalog-show")
        page.locator(".kids-catalog-show", has_text="Máša").click()
        page.wait_for_selector(".kids-catalog-episode")
        page.wait_for_function("document.querySelector('#kidsCatalogEpisodes')?.getBoundingClientRect().top < 700")

        shows_box = page.locator("#kidsCatalogShows").bounding_box()
        episodes_box = page.locator("#kidsCatalogEpisodes").bounding_box()
        assert shows_box["height"] < 90
        assert episodes_box["y"] < 700

        first_episode = page.locator(".kids-catalog-episode").first
        with page.expect_response(lambda response: response.request.method == "POST" and response.url.endswith("/api/downloads")) as response_info:
            first_episode.locator(".kids-catalog-enqueue-btn").click()
        assert response_info.value.status == 200
        page.wait_for_function(
            """() => {
              const card = document.querySelector('.kids-catalog-episode');
              const btn = card?.querySelector('.kids-catalog-enqueue-btn');
              const manage = card?.querySelector('.kids-catalog-manage-btn');
              return Boolean(card?.classList.contains('queue-active') && btn?.disabled && /Queued #/.test(btn.textContent || '') && manage && !manage.classList.contains('hidden'));
            }"""
        )


@pytest.mark.e2e
def test_download_queue_refresh_error_exposes_diagnostic_details(tmp_path) -> None:
    app = _build_file_search_app(tmp_path)

    with run_test_server(app) as base_url, launch_browser() as browser:
        page = browser.new_page()
        failures = {"count": 0}

        def fail_downloads(route) -> None:
            request = route.request
            if request.method == "GET" and "/api/downloads" in request.url and "limit=" in request.url:
                failures["count"] += 1
                if failures["count"] > 1:
                    route.continue_()
                    return
                route.fulfill(
                    status=500,
                    json={
                        "error": "Queue refresh failed.",
                        "error_code": "downloads_refresh_failed",
                        "request_id": "req-downloads-123",
                        "hint": "Check the download worker health.",
                        "retryable": True,
                        "details": "boom",
                    },
                )
                return
            route.continue_()

        page.route("**/api/downloads*", fail_downloads)
        page.goto(base_url, wait_until="networkidle")
        page.click('.workspace-tab[data-tab="downloads"]')
        page.wait_for_selector("#refreshDownloadsBtn")
        page.wait_for_selector("#downloadStatus .status-details", state="attached")
        page.locator("#downloadStatus details summary").click()
        page.wait_for_selector("#downloadStatus .status-detail-row")
        status_text = page.locator("#downloadStatus").text_content() or ""
        assert "Queue refresh failed. Retrying in background." in status_text
        assert "req-downloads-123" in status_text
        assert "downloads_refresh_failed" in status_text
        assert "500" in status_text
        assert "/api/downloads" in status_text
        assert "phase" in status_text
        assert "backend error" in status_text
        assert page.locator("#downloadStatus .status-copy-btn").count() == 1


@pytest.mark.e2e
def test_account_tab_is_separate_and_collapsed_by_default(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("YOUTUBE_MANAGED_COOKIES_PATH", str(tmp_path / "secrets" / "youtube-cookies.txt"))
    app = _build_file_search_app(tmp_path)

    with run_test_server(app) as base_url, launch_browser() as browser:
        page = browser.new_page()
        page.goto(base_url, wait_until="networkidle")

        page.click('.workspace-tab[data-tab="downloads"]')
        page.wait_for_selector("#openAccountTabBtn")
        assert page.locator("#accountForm").is_hidden()

        page.click("#openAccountTabBtn")
        page.wait_for_selector('.workspace-tab.active[data-tab="account"]')
        page.wait_for_selector("#accountStatus")
        assert "Free" in page.locator("#accountStatus").text_content()
        assert page.locator("#accountDetails").get_attribute("open") is None
        assert page.locator("#youtubeAuthDetails").get_attribute("open") is None
        assert page.locator("#youtubeAuthForm").is_hidden()

        page.locator("#accountDetails > summary").click()
        page.wait_for_selector("#accountForm")
        assert page.locator("#accountForm").is_visible()

        page.locator("#youtubeAuthDetails > summary").click()
        page.click('#youtubeAuthForm button[type="submit"]')
        page.wait_for_function(
            "() => document.querySelector('#youtubeAuthStatus')?.textContent?.includes('Choose Cookies file')"
        )
        page.select_option("#youtubeAuthMode", "cookies_file")
        page.fill("#youtubeCookiesText", "# Netscape HTTP Cookie File\n.youtube.com\tTRUE\t/\tTRUE\t1893456000\tSID\tsecret-value")
        page.click('#youtubeAuthForm button[type="submit"]')
        page.wait_for_function("() => document.querySelector('#youtubeAuthStatus')?.textContent?.includes('Cookies file configured')")
        auth_text = page.locator("#youtubeAuthDetails").text_content() or ""
        assert "secret-value" not in auth_text


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
        assert page.locator("#tvSearchBtn").is_enabled()
        page.click("#tvSearchBtn")
        page.wait_for_selector("#tvResults details.tv-season")
        page.locator("#tvResults details.tv-season summary").first.click()
        page.wait_for_selector("#tvResults details.tv-season[open] .tv-episode-card")

        first_episode = page.locator("#tvResults details.tv-season[open] .tv-episode-card").first
        expect_text = first_episode.locator(".tv-episode-status")
        expect_text.wait_for(state="visible")
        assert "downloaded" in expect_text.text_content().lower()
        assert first_episode.locator("button", has_text="Search anyway").count() == 1


@pytest.mark.e2e
def test_library_missing_tv_scan_and_search_missing_flow(tmp_path) -> None:
    app = _build_tv_search_app(tmp_path)

    with run_test_server(app) as base_url, launch_browser() as browser:
        page = browser.new_page()
        page.goto(base_url, wait_until="networkidle")
        page.click('.workspace-tab[data-tab="library"]')
        page.fill("#libraryTvShowName", "Bluey")
        page.click('#libraryTvMissingForm button[type="submit"]')
        page.wait_for_selector(".library-summary-card")
        results_text = page.locator("#libraryTvMissingResults").text_content() or ""
        assert "1 downloaded" in results_text
        assert "1 missing" in results_text
        assert "Bluey.S01E01.mkv" in results_text
        assert "S01E02" in results_text

        page.locator('.library-episode[data-status="missing"] .library-search-missing').first.click()
        page.wait_for_function("window.location.hash === '#search'")
        page.wait_for_selector("#tvModePanel:not(.hidden)")
        page.wait_for_function("document.querySelector('#tvShowName')?.value === 'Bluey'")
        page.wait_for_selector('.tv-season-select[data-season-number="1"] input.tv-episode-check[value="2"]:checked')
        assert page.locator("#tvSearchBtn").is_enabled()


@pytest.mark.e2e
def test_library_folder_scan_deep_scan_and_missing_search(tmp_path) -> None:
    app = _build_tv_search_app(tmp_path)

    with run_test_server(app) as base_url, launch_browser() as browser:
        page = browser.new_page()
        page.goto(base_url, wait_until="networkidle")
        page.click('.workspace-tab[data-tab="library"]')
        page.select_option("#libraryFolderKind", "kids")
        page.click("#libraryFoldersScanBtn")
        page.wait_for_selector('.library-folder-card[data-folder-name="Bluey"]')
        page.click('.library-deep-scan[data-folder-name="Bluey"]')
        page.wait_for_selector(".library-deep-scan-card")
        assert "S01E01" in (page.locator("#libraryDeepScanResults").text_content() or "")
        page.click(".library-search-folder")
        page.wait_for_selector(".library-summary-card")
        assert "Bluey.S01E01.mkv" in (page.locator("#libraryTvMissingResults").text_content() or "")


@pytest.mark.e2e
def test_library_music_scan_deep_scan_and_search(tmp_path) -> None:
    app = _build_tv_search_app(tmp_path)
    album = tmp_path / "media" / "music" / "Daft Punk" / "Discovery"
    album.mkdir(parents=True)
    (album / "01 One More Time.flac").write_bytes(b"audio")

    with run_test_server(app) as base_url, launch_browser() as browser:
        page = browser.new_page()
        page.goto(base_url, wait_until="networkidle")
        page.click('.workspace-tab[data-tab="library"]')
        page.click("#libraryMusicFoldersScanBtn")
        page.wait_for_selector('.library-music-artist[data-artist-name="Daft Punk"]')
        page.click('.library-music-album[data-album-name="Discovery"]')
        page.wait_for_selector(".library-music-file-list")
        assert "01 One More Time.flac" in (page.locator("#libraryMusicDeepScanResults").text_content() or "")
        page.click(".library-search-music")
        page.wait_for_url("**/?query=Daft+Punk+Discovery&category=audio#search")


@pytest.mark.e2e
def test_tv_search_job_error_exposes_diagnostic_details(tmp_path) -> None:
    app = _build_tv_search_app(tmp_path)

    with run_test_server(app) as base_url, launch_browser() as browser:
        page = browser.new_page()

        def fail_tv_search(route) -> None:
            request = route.request
            if request.method == "POST" and request.url.endswith("/api/tv/search-jobs"):
                route.fulfill(
                    status=500,
                    json={
                        "error": "TV search failed.",
                        "error_code": "tv_search_failed",
                        "request_id": "req-tv-123",
                        "hint": "Check the TV worker health.",
                        "retryable": True,
                        "details": "boom",
                    },
                )
                return
            route.continue_()

        page.route("**/api/tv/search-jobs", fail_tv_search)
        page.goto(base_url, wait_until="networkidle")
        page.click("#tvSearchModeBtn")
        page.fill("#tvShowName", "Bluey")
        page.press("#tvShowName", "Enter")
        page.wait_for_selector("#tvShowSummaryCard")
        assert page.locator("#tvSearchBtn").is_enabled()
        page.click("#tvSelectAllSeasons")
        page.click("#tvSearchBtn")
        page.wait_for_selector("#tvStatus .status-details", state="attached")
        page.locator("#tvStatus details summary").click()
        page.wait_for_selector("#tvStatus .status-detail-row")
        status_text = page.locator("#tvStatus").text_content() or ""
        assert "TV search failed." in status_text
        assert "req-tv-123" in status_text
        assert "tv_search_failed" in status_text
        assert page.locator("#tvStatus .status-copy-btn").count() == 1


@pytest.mark.e2e
def test_tv_episode_results_show_size_and_sort_by_size(tmp_path) -> None:
    app = _build_reacher_tv_search_app(tmp_path)
    tv_lookup_payload = {
        "show": {
            "id": 43031,
            "name": "Reacher",
            "premiered": "2022-02-04",
            "language": "English",
            "image_url": "https://example.com/reacher-poster.jpg",
            "type": "Scripted",
            "genres": ["Drama", "Action", "Thriller"],
            "summary": "Reacher is wrongly accused of murder while visiting a small town.",
            "source": "tvmaze",
        },
        "title_metadata": {
            "kind": "tv",
            "canonical_title": "Reacher",
            "original_title": "Reacher",
            "local_titles": ["Reacher"],
            "aliases": ["Reacher"],
            "genres": ["Drama", "Action", "Thriller"],
            "summary": "Reacher is wrongly accused of murder while visiting a small town.",
            "content_type": "Scripted",
            "year": 2022,
            "source": "test",
            "source_ids": {},
        },
        "aliases": ["Reacher"],
        "all_search_aliases": ["Reacher"],
        "search_aliases": ["Reacher"],
        "seasons": [
            {"season_number": 1, "episode_count": 1, "completed_episodes": 1, "result_count": 3, "episodes": []}
        ],
        "status": "done",
        "total_episodes": 1,
        "completed_episodes": 1,
        "result_count": 3,
    }
    tv_search_payload = {
        "show": tv_lookup_payload["show"],
        "title_metadata": tv_lookup_payload["title_metadata"],
        "aliases": ["Reacher"],
        "all_search_aliases": ["Reacher"],
        "search_aliases": ["Reacher"],
        "max_results_per_variant": 120,
        "status": "done",
        "total_episodes": 1,
        "completed_episodes": 1,
        "result_count": 3,
        "seasons": [
            {
                "season_number": 1,
                "episode_count": 1,
                "completed_episodes": 1,
                "result_count": 3,
                "episodes": [
                    {
                        "season_number": 1,
                        "episode_number": 1,
                        "episode_code": "S01E01",
                        "episode_name": "Welcome to Margrave",
                        "status": "done",
                        "result_count": 3,
                        "query_variants": ["Reacher S01E01"],
                        "query_errors": [],
                        "results": [
                            dump_search_result(build_search_result(file_id=301, title="Reacher S01E01 720p", size="850 MB")),
                            dump_search_result(build_search_result(file_id=302, title="Reacher S01E01 1080p", size="1.8 GB")),
                            dump_search_result(build_search_result(file_id=303, title="Reacher S01E01 480p", size="420 MB")),
                        ],
                    }
                ],
            }
        ],
    }

    with run_test_server(app) as base_url, launch_browser() as browser:
        page = browser.new_page()
        def fulfill_tv_search(route) -> None:
            request = route.request
            if request.method == "POST" and request.url.endswith("/api/tv/search-jobs"):
                route.fulfill(status=200, json={**tv_search_payload, "id": 999})
                return
            if request.method == "GET" and "/api/tv/search-jobs/999" in request.url:
                route.fulfill(status=200, json={**tv_search_payload, "id": 999})
                return
            route.continue_()

        page.route("**/api/tv/search-jobs*", fulfill_tv_search)
        page.goto(base_url, wait_until="networkidle")
        page.click("#tvSearchModeBtn")
        page.fill("#tvShowName", "Reacher")
        page.press("#tvShowName", "Enter")
        page.wait_for_selector("#tvShowSummaryCard")
        assert page.locator("#tvSearchBtn").is_enabled()
        page.click("#tvSelectAllSeasons")
        page.click("#tvSearchBtn")
        page.wait_for_selector("#tvResults details.tv-season")
        page.locator("#tvResults details.tv-season summary").first.click()
        page.wait_for_selector("#tvResults details.tv-season[open] .tv-episode-card")
        episode_card = page.locator("#tvResults details.tv-season[open] .tv-episode-card").first
        assert "Size:" in (episode_card.locator(".tv-result-size").first.text_content() or "")

        page.locator("#tvResults .tv-results-sort-select").select_option("size_desc")
        page.wait_for_function(
            """() => document.querySelector('#tvResults .tv-results-sort-select')?.value === 'size_desc'""",
            timeout=3000,
        )
        page.wait_for_timeout(500)
        titles = page.locator("#tvResults details.tv-season[open] .tv-result-item .tv-result-title-row a").all_text_contents()
        assert titles[0] == "Reacher S01E01 1080p"


@pytest.mark.e2e
def test_reacher_tv_episode_search_runs_without_extra_selection(tmp_path) -> None:
    app = _build_reacher_tv_search_app(tmp_path)

    with run_test_server(app) as base_url, launch_browser() as browser:
        page = browser.new_page()
        page.goto(base_url, wait_until="networkidle")
        page.click("#tvSearchModeBtn")
        page.fill("#tvShowName", "Reacher")
        page.press("#tvShowName", "Enter")
        page.wait_for_selector("#tvShowSummaryCard")

        assert page.locator("#tvSearchBtn").is_enabled()
        page.click("#tvSearchBtn")

        page.wait_for_function(
            """() => {
              const status = document.querySelector('#tvStatus');
              return Boolean(status && /TV search complete/i.test(status.textContent || ''));
            }""",
            timeout=10000,
        )
        page.locator("#tvResults details.tv-season summary").first.click()
        page.wait_for_selector("#tvResults details.tv-season[open] .tv-episode-card")
        first_episode = page.locator("#tvResults details.tv-season[open] .tv-episode-card").first
        assert "done" in first_episode.locator(".tv-episode-status").text_content().lower()
        assert first_episode.locator(".tv-result-item a").first.text_content().lower().find("reacher") >= 0


@pytest.mark.e2e
def test_tv_polling_preserves_open_season_and_selected_filter(tmp_path) -> None:
    app, storage, _ = _build_tv_polling_app(tmp_path, downloaded_episode_codes=("S01E01",))

    with run_test_server(app) as base_url, launch_browser() as browser:
        page = browser.new_page()
        page.goto(base_url, wait_until="networkidle")
        page.click("#tvSearchModeBtn")
        page.fill("#tvShowName", "Bluey")
        page.press("#tvShowName", "Enter")
        page.wait_for_selector("#tvShowSummaryCard")
        page.click("#tvSelectAllSeasons")
        page.click("#tvSearchBtn")
        page.wait_for_selector("#tvResults details.tv-season")

        season = page.locator("#tvResults details.tv-season").first
        season.locator(":scope > summary").click()
        page.wait_for_selector("#tvResults details.tv-season[open] .tv-episode-card")
        page.locator('.tv-results-filter-chip[data-filter="downloaded"]').click()

        job_id = storage.list_tv_search_jobs(limit=10)[0]["id"]
        claimed = storage.claim_next_tv_search_job()
        assert claimed is not None
        assert claimed["id"] == job_id
        storage.mark_tv_search_episode_running(job_id, 1, 2)
        storage.complete_tv_search_episode(
            job_id,
            season_number=1,
            episode_number=2,
            query_variants=["Bluey S01E02"],
            query_errors=[],
            results=[dump_search_result(build_search_result(file_id=202, title="Bluey S01E02 Hospital"))],
        )
        storage.finalize_tv_search_job(job_id)

        assert season.get_attribute("open") is not None
        assert page.locator('.tv-results-filter-chip[data-filter="downloaded"].active').count() == 1
        assert "downloaded" in page.locator("#tvResults .tv-episode-status").first.text_content().lower()


@pytest.mark.e2e
def test_tv_show_summary_persists_without_re_rendering_poster(tmp_path) -> None:
    media_root = tmp_path / "media"
    os.environ["DOWNLOAD_DIR"] = str(media_root)
    (media_root / "kids" / "tv" / "Bluey" / "S01").mkdir(parents=True, exist_ok=True)
    (media_root / "kids" / "tv" / "Bluey" / "S01" / "Bluey.S01E01.mkv").write_text("video", encoding="utf-8")

    storage = Storage(db_path=str(tmp_path / "tv-summary.db"))
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
        client_instance=FakeSdilejClient(
            responses_by_query={
                "Bluey S01E02": [build_search_result(file_id=202, title="Bluey S01E02 Hospital")]
            }
        ),
        tv_client_instance=FakeTvMazeClient(
            show=TvShowSummary(
                id=321,
                name="Bluey",
                premiered="2018-10-01",
                language="English",
                image_url="https://example.com/bluey-poster.jpg",
                type="Animation",
                genres=["Children", "Family"],
                summary="A family-friendly animated series.",
            )
        ),
        metadata_resolver_instance=E2EMetadataResolver(metadata),
        start_workers=False,
    )

    with run_test_server(app) as base_url, launch_browser() as browser:
        page = browser.new_page()
        page.goto(base_url, wait_until="networkidle")
        page.click("#tvSearchModeBtn")
        page.fill("#tvShowName", "Bluey")
        page.press("#tvShowName", "Enter")
        page.wait_for_selector("#tvShowSummaryCard img")
        page.click("#tvSelectAllSeasons")
        page.click("#tvSearchBtn")
        page.wait_for_selector("#tvResults details.tv-season")
        page.locator("#tvResults details.tv-season summary").first.click()
        page.wait_for_selector("#tvResults details.tv-season[open] .tv-episode-card")

        poster_src = page.locator("#tvShowSummaryCard img").get_attribute("src")
        assert poster_src == "https://example.com/bluey-poster.jpg"
        page.evaluate("window.__tvPosterNode = document.querySelector('#tvShowSummaryCard img')")

        job_id = storage.list_tv_search_jobs(limit=10)[0]["id"]
        storage.mark_tv_search_episode_running(job_id, 1, 2)
        storage.complete_tv_search_episode(
            job_id,
            season_number=1,
            episode_number=2,
            query_variants=["Bluey S01E02"],
            query_errors=[],
            results=[dump_search_result(build_search_result(file_id=202, title="Bluey S01E02 Hospital"))],
        )
        storage.finalize_tv_search_job(job_id)

        page.wait_for_function(
            """() => {
              const summary = document.querySelector('#tvShowSummaryCard');
              return Boolean(summary && /Bluey/.test(summary.textContent || '') && /family-friendly/i.test(summary.textContent || ''));
            }""",
            timeout=10000,
        )
        assert page.evaluate(
            """() => window.__tvPosterNode === document.querySelector('#tvShowSummaryCard img')"""
        )


@pytest.mark.e2e
def test_tv_episode_queue_state_transitions_to_downloaded(tmp_path) -> None:
    app, storage, media_root = _build_tv_polling_app(tmp_path)

    with run_test_server(app) as base_url, launch_browser() as browser:
        page = browser.new_page()
        page.goto(base_url, wait_until="networkidle")
        page.click("#tvSearchModeBtn")
        page.fill("#tvShowName", "Bluey")
        page.press("#tvShowName", "Enter")
        page.wait_for_selector("#tvShowSummaryCard")
        page.click("#tvSelectAllSeasons")
        page.click("#tvSearchBtn")
        page.wait_for_selector("#tvResults details.tv-season")

        season = page.locator("#tvResults details.tv-season").first
        season.locator(":scope > summary").click()
        page.wait_for_function(
            """() => Boolean(document.querySelector('#tvResults details.tv-season[open]'))""",
            timeout=10000,
        )
        episode_card = page.locator("#tvResults .tv-episode-card").first
        episode_card.wait_for(state="attached")
        job_id = storage.list_tv_search_jobs(limit=10)[0]["id"]
        claimed = storage.claim_next_tv_search_job()
        assert claimed is not None
        assert claimed["id"] == job_id
        storage.mark_tv_search_episode_running(job_id, 1, 1)
        storage.complete_tv_search_episode(
            job_id,
            season_number=1,
            episode_number=1,
            query_variants=["Bluey S01E01"],
            query_errors=[],
            results=[dump_search_result(build_search_result(file_id=201, title="Bluey S01E01 Magic Xylophone"))],
        )
        storage.mark_tv_search_episode_running(job_id, 1, 2)
        storage.complete_tv_search_episode(
            job_id,
            season_number=1,
            episode_number=2,
            query_variants=["Bluey S01E02"],
            query_errors=[],
            results=[dump_search_result(build_search_result(file_id=202, title="Bluey S01E02 Hospital"))],
        )
        storage.finalize_tv_search_job(job_id)

        response = requests.get(f"{base_url}/api/tv/search-jobs/{job_id}", timeout=5)
        assert response.ok
        payload = response.json()
        assert payload["status"] == "done"
        first_season = payload["seasons"][0]
        assert first_season["completed_episodes"] >= 2
        assert first_season["episodes"][0]["status"] == "done"


@pytest.mark.e2e
def test_tv_search_anyway_replaces_downloaded_state_with_live_results(tmp_path) -> None:
    app, _, _ = _build_tv_polling_app(
        tmp_path,
        search_responses={
            "Bluey S01E01": [build_search_result(file_id=201, title="Bluey S01E01 Magic Xylophone")],
            "Bluey 1x01": [build_search_result(file_id=201, title="Bluey S01E01 Magic Xylophone")],
            "Bluey 1x1": [build_search_result(file_id=201, title="Bluey S01E01 Magic Xylophone")],
        },
        downloaded_episode_codes=("S01E01",),
    )

    with run_test_server(app) as base_url, launch_browser() as browser:
        page = browser.new_page()
        page.goto(base_url, wait_until="networkidle")
        page.click("#tvSearchModeBtn")
        page.fill("#tvShowName", "Bluey")
        page.press("#tvShowName", "Enter")
        page.wait_for_selector("#tvShowSummaryCard")
        page.click("#tvSelectAllSeasons")
        page.click("#tvSearchBtn")
        page.wait_for_selector("#tvResults details.tv-season")

        page.locator("#tvResults details.tv-season summary").first.click()
        episode_card = page.locator("#tvResults details.tv-season[open] .tv-episode-card").first
        episode_card.locator("button", has_text="Search anyway").click()

        page.wait_for_function(
            """() => {
              const link = document.querySelector('#tvResults details.tv-season[open] .tv-episode-card .tv-result-item a');
              const copyBtn = document.querySelector('#tvResults details.tv-season[open] .tv-episode-card .tv-copy-link-btn');
              const status = document.querySelector('#tvResults details.tv-season[open] .tv-episode-card .tv-episode-status');
              return Boolean(link && copyBtn && /Bluey S01E01 Magic Xylophone/i.test(link.textContent || '') && status && /done/i.test(status.textContent || ''));
            }""",
            timeout=10000,
        )
        assert episode_card.locator(".tv-episode-status").text_content().lower().find("done") >= 0
