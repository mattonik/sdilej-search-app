from __future__ import annotations

import responses
from fastapi.testclient import TestClient

from app.main import create_app
from app.models import TitleMetadata
from app.routes.discovery import _parse_size_bytes, _score_candidate
from app.sdilej_client import SdilejClientError
from app.storage import Storage
from app.title_metadata import CZDB_DETAIL_URL, CZDB_SEARCH_URL
from app.tmdb_client import TMDB_BASE_URL, TmdbClient
from app.tvmaze_client import TVMAZE_BASE_URL
from app.youtube_downloader import YoutubeDownloader
from tests.conftest import FakeSdilejClient, StaticMetadataResolver, build_search_result


class FailingSearchClient(FakeSdilejClient):
    def search(self, *args, **kwargs):  # noqa: ANN002, ANN003
        raise SdilejClientError("sdilej timeout")


def test_tmdb_client_parse_movie_handles_missing_optional_fields() -> None:
    movie = TmdbClient(token="token")._parse_movie(  # noqa: SLF001
        {
            "id": 42,
            "title": "",
            "name": "Fallback Title",
            "release_date": "",
            "poster_path": "",
            "genre_ids": [12, "ignored"],
        }
    )

    assert movie.tmdb_id == 42
    assert movie.title == "Fallback Title"
    assert movie.year is None
    assert movie.poster_url is None
    assert movie.vote_average is None
    assert movie.vote_count is None
    assert movie.genre_ids == [12]


@responses.activate
def test_movie_lookup_endpoint_returns_metadata(
    storage,
    sample_czdb_movie_response,
) -> None:
    responses.get(CZDB_SEARCH_URL, json=sample_czdb_movie_response)
    app = create_app(storage_instance=storage, start_workers=False)

    with TestClient(app) as client:
        response = client.post("/api/movie/lookup", json={"title": "Matrix", "year": 1999})

    assert response.status_code == 200
    payload = response.json()
    assert payload["title_metadata"]["canonical_title"] == "Matrix"
    assert "The Matrix" in payload["aliases"]


@responses.activate
def test_movie_info_link_endpoint_prefers_csfd_and_strips_release_noise(
    storage,
    sample_czdb_movie_response,
    sample_czdb_movie_detail_payload,
) -> None:
    responses.get(
        CZDB_SEARCH_URL,
        json=sample_czdb_movie_response,
        match=[responses.matchers.query_param_matcher({"q": "Matrix", "y": "1999"})],
    )
    responses.get(
        CZDB_DETAIL_URL,
        json=sample_czdb_movie_detail_payload,
        match=[responses.matchers.query_param_matcher({"uid": "9499"})],
    )
    app = create_app(storage_instance=storage, start_workers=False)

    with TestClient(app) as client:
        response = client.post(
            "/api/movie/info-link",
            json={
                "title": "Matrix.1999.1080p.BluRay.CZ.dabing.mkv",
                "primary_year": 1999,
                "search_query": "Matrix",
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["found"] is True
    assert payload["preferred_url"] == "https://www.csfd.cz/film/9499-matrix/"
    assert payload["csfd_url"] == "https://www.csfd.cz/film/9499-matrix/"
    assert payload["resolved_title"] == "Matrix"
    assert payload["original_title"] == "The Matrix"


@responses.activate
def test_movie_info_link_endpoint_builds_csfd_url_from_csfd_id_when_direct_url_missing(storage) -> None:
    responses.get(
        CZDB_SEARCH_URL,
        json={
            "results": [
                {
                    "id": 43840,
                    "csfd_id": 9499,
                    "nazev": "Matrix",
                    "original": "The Matrix",
                    "rok": 1999,
                }
            ],
            "response": "True",
        },
        match=[responses.matchers.query_param_matcher({"q": "Matrix", "y": "1999"})],
    )
    responses.get(
        CZDB_DETAIL_URL,
        json={
            "results": [
                {
                    "id": 43840,
                    "csfd_id": 9499,
                    "nazev": "Matrix",
                    "original": "The Matrix",
                    "rok": 1999,
                    "imdb_id": "tt0133093",
                }
            ],
            "response": "True",
        },
        match=[responses.matchers.query_param_matcher({"uid": "9499"})],
    )
    app = create_app(storage_instance=storage, start_workers=False)

    with TestClient(app) as client:
        response = client.post(
            "/api/movie/info-link",
            json={"title": "Matrix 1999 REMUX", "primary_year": 1999},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["found"] is True
    assert payload["preferred_url"] == "https://www.csfd.cz/film/9499"
    assert payload["csfd_url"] == "https://www.csfd.cz/film/9499"
    assert payload["imdb_url"] == "https://www.imdb.com/title/tt0133093/"


def test_movie_info_link_endpoint_rejects_obvious_tv_titles(app_factory) -> None:
    app = app_factory()

    with TestClient(app) as client:
        response = client.post(
            "/api/movie/info-link",
            json={"title": "Bluey S02E01 Dance Mode 1080p.mkv", "primary_year": 2024},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["found"] is False
    assert "TV episode" in payload["error"]


def test_movie_discovery_endpoint_reports_missing_tmdb_token(app_factory, monkeypatch) -> None:
    monkeypatch.delenv("TMDB_BEARER_TOKEN", raising=False)
    app = app_factory()

    with TestClient(app) as client:
        response = client.get("/api/discovery/movies?mode=popular&limit=1")

    assert response.status_code == 200
    payload = response.json()
    assert payload["configured"] is False
    assert payload["items"] == []
    assert "TMDB_BEARER_TOKEN" in payload["hint"]


def test_movie_discovery_size_parser_and_candidate_scoring() -> None:
    movie = {"title": "Matrix", "original_title": "The Matrix", "year": 2020}
    strong = build_search_result(file_id=1, title="Matrix 2020 CZ 1080p", size="4.2 GB")
    weak = build_search_result(file_id=2, title="Unrelated 2020 CZ 1080p", size="4.2 GB")

    assert _parse_size_bytes("1.5 GB") == 1610612736
    assert _parse_size_bytes("700 MB") == 734003200
    assert _parse_size_bytes("unknown") == 0
    assert _score_candidate(strong, movie=movie) > _score_candidate(weak, movie=movie)


@responses.activate
def test_movie_discovery_endpoint_marks_best_sdilej_availability(app_factory, monkeypatch) -> None:
    monkeypatch.setenv("TMDB_BEARER_TOKEN", "test-token")
    responses.get(
        f"{TMDB_BASE_URL}/movie/popular",
        json={
            "results": [
                {
                    "id": 603,
                    "title": "Matrix",
                    "original_title": "The Matrix",
                    "overview": "A hacker discovers a simulated reality.",
                    "release_date": "1999-03-31",
                    "poster_path": "/matrix.jpg",
                    "vote_average": 8.2,
                    "vote_count": 1000,
                    "popularity": 99.0,
                    "genre_ids": [28],
                }
            ]
        },
    )
    app = app_factory(
        client_instance=FakeSdilejClient(
            responses_by_query={
                "Matrix": [
                    build_search_result(
                        file_id=900,
                        title="Matrix 1999 CZ 1080p mkv",
                        size="4.0 GB",
                        detected_languages=["CZ"],
                    )
                ]
            }
        )
    )

    with TestClient(app) as client:
        response = client.get("/api/discovery/movies?mode=popular&limit=1&sdilej_language=CZ")

    assert response.status_code == 200
    payload = response.json()
    assert payload["configured"] is True
    assert payload["items"][0]["title"] == "Matrix"
    assert payload["items"][0]["poster_url"] == "https://image.tmdb.org/t/p/w342/matrix.jpg"
    availability = payload["items"][0]["availability"]
    assert availability["status"] == "available"
    assert availability["query"] == "Matrix"
    assert availability["best_result"]["file_id"] == 900
    assert availability["best_result"]["size"] == "4.0 GB"


@responses.activate
def test_movie_discovery_endpoint_reports_weak_and_not_found_availability(app_factory, monkeypatch) -> None:
    monkeypatch.setenv("TMDB_BEARER_TOKEN", "test-token")
    responses.get(
        f"{TMDB_BASE_URL}/movie/popular",
        json={
            "results": [
                {
                    "id": 1,
                    "title": "Known Film",
                    "original_title": "Known Film",
                    "release_date": "2020-01-01",
                    "genre_ids": [],
                },
                {
                    "id": 2,
                    "title": "Missing Film",
                    "original_title": "Missing Film",
                    "release_date": "2020-01-01",
                    "genre_ids": [],
                },
            ]
        },
    )
    fake_client = FakeSdilejClient(
        responses_by_query={
            "Known Film": [build_search_result(file_id=901, title="Unrelated 2020 1080p", size="700 MB")]
        }
    )
    app = app_factory(client_instance=fake_client)

    with TestClient(app) as client:
        response = client.get("/api/discovery/movies?mode=popular&limit=2")

    assert response.status_code == 200
    items = response.json()["items"]
    assert items[0]["availability"]["status"] == "not_found"
    assert items[0]["availability"]["best_result"] is None
    assert items[1]["availability"]["status"] == "not_found"
    assert fake_client.calls == ["Known Film", "Missing Film"]


@responses.activate
def test_movie_discovery_endpoint_reports_sdilej_availability_errors(app_factory, monkeypatch) -> None:
    monkeypatch.setenv("TMDB_BEARER_TOKEN", "test-token")
    responses.get(
        f"{TMDB_BASE_URL}/movie/popular",
        json={
            "results": [
                {
                    "id": 1,
                    "title": "Known Film",
                    "original_title": "Known Film",
                    "release_date": "2020-01-01",
                    "genre_ids": [],
                }
            ]
        },
    )
    app = app_factory(client_instance=FailingSearchClient())

    with TestClient(app) as client:
        response = client.get("/api/discovery/movies?mode=popular&limit=1")

    assert response.status_code == 200
    availability = response.json()["items"][0]["availability"]
    assert availability["status"] == "error"
    assert availability["error"] == "sdilej timeout"
    assert availability["best_result"] is None


@responses.activate
def test_movie_info_link_endpoint_returns_not_found_for_unmatched_titles(storage) -> None:
    responses.get(
        CZDB_SEARCH_URL,
        json={"results": [], "response": "False"},
        match=[responses.matchers.query_param_matcher({"q": "Unknown Film"})],
    )
    app = create_app(storage_instance=storage, start_workers=False)

    with TestClient(app) as client:
        response = client.post("/api/movie/info-link", json={"title": "Unknown Film.mkv"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["found"] is False
    assert payload["preferred_url"] is None
    assert payload["error"] == "No external movie info link was found for this result."


@responses.activate
def test_movie_info_link_endpoint_falls_back_to_search_context_when_card_title_is_too_noisy(
    storage,
    sample_czdb_movie_response,
    sample_czdb_movie_detail_payload,
) -> None:
    responses.get(
        CZDB_SEARCH_URL,
        json={"results": [], "response": "False"},
        match=[responses.matchers.query_param_matcher({"q": "Some Release Group Internal"})],
    )
    responses.get(
        CZDB_SEARCH_URL,
        json=sample_czdb_movie_response,
        match=[responses.matchers.query_param_matcher({"q": "Matrix", "y": "1999"})],
    )
    responses.get(
        CZDB_DETAIL_URL,
        json=sample_czdb_movie_detail_payload,
        match=[responses.matchers.query_param_matcher({"uid": "9499"})],
    )
    app = create_app(storage_instance=storage, start_workers=False)

    with TestClient(app) as client:
        response = client.post(
            "/api/movie/info-link",
            json={
                "title": "Some.Release.Group.Internal.mkv",
                "primary_year": 1999,
                "search_query": "Matrix",
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["found"] is True
    assert payload["preferred_url"] == "https://www.csfd.cz/film/9499-matrix/"


@responses.activate
def test_tv_lookup_endpoint_returns_aliases_and_metadata(
    storage,
    sample_czdb_show_response,
    sample_tvmaze_show_payload,
    sample_tvmaze_episode_payload,
    sample_tvmaze_akas_payload,
) -> None:
    responses.get(f"{TVMAZE_BASE_URL}/search/shows", json=sample_tvmaze_show_payload)
    responses.get(f"{TVMAZE_BASE_URL}/shows/321/episodes", json=sample_tvmaze_episode_payload)
    responses.get(f"{TVMAZE_BASE_URL}/shows/321/akas", json=sample_tvmaze_akas_payload)
    responses.get(CZDB_SEARCH_URL, json=sample_czdb_show_response)
    app = create_app(storage_instance=storage, start_workers=False)

    with TestClient(app) as client:
        response = client.post("/api/tv/lookup", json={"show_name": "Shaun the Sheep"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["show"]["name"] == "Shaun the Sheep"
    assert payload["show"]["image_url"] == "https://images.example.test/shaun-the-sheep-original.jpg"
    assert payload["title_metadata"]["canonical_title"] == "Ovecka Shaun"
    assert "Vesela farma" in payload["aliases"]
    assert payload["search_aliases"] == ["Shaun the Sheep", "Ovecka Shaun", "Vesela farma"]
    assert payload["episode_count"] == 2


def test_video_search_expands_aliases_and_merges_query_hits(app_factory, sample_movie_metadata) -> None:
    fake_client = FakeSdilejClient(
        responses_by_query={
            "Shaun the Sheep": [
                build_search_result(file_id=1, title="Shaun the Sheep SK", size="700 MB"),
                build_search_result(file_id=2, title="Shaun the Sheep SK DAB", size="500 MB"),
            ],
            "Vesela farma": [
                build_search_result(file_id=1, title="Shaun the Sheep SK", size="700 MB"),
                build_search_result(file_id=3, title="Vesela farma SK DAB", size="900 MB"),
            ],
        }
    )
    resolver = StaticMetadataResolver(sample_movie_metadata)
    app = app_factory(client_instance=fake_client, metadata_resolver_instance=resolver)

    with TestClient(app) as client:
        response = client.get(
            "/api/search",
            params={
                "query": "Shaun the Sheep",
                "category": "video",
                "language": "sk",
                "max_results": 10,
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["expanded_queries"][:2] == ["Shaun the Sheep", "Ovecka Shaun"]
    assert [item["file_id"] for item in payload["results"]] == [2, 1, 3]
    merged = next(item for item in payload["results"] if item["file_id"] == 1)
    assert sorted(merged["query_hits"]) == ["Shaun the Sheep", "Vesela farma"]


def test_non_video_search_keeps_single_query(app_factory, sample_movie_metadata) -> None:
    fake_client = FakeSdilejClient(
        responses_by_query={
            "podcast": [build_search_result(file_id=10, title="Podcast Episode", size="50 MB")],
        }
    )
    resolver = StaticMetadataResolver(sample_movie_metadata)
    app = app_factory(client_instance=fake_client, metadata_resolver_instance=resolver)

    with TestClient(app) as client:
        response = client.get("/api/search", params={"query": "podcast", "category": "audio"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["expanded_queries"] == []
    assert fake_client.calls == ["podcast"]


def test_movie_search_page_renders_info_buttons(app_factory, sample_movie_metadata) -> None:
    fake_client = FakeSdilejClient(
        responses_by_query={
            "Shaun the Sheep": [build_search_result(file_id=10, title="Shaun the Sheep 2007 SK dabing.mkv")],
        }
    )
    resolver = StaticMetadataResolver(sample_movie_metadata)
    app = app_factory(client_instance=fake_client, metadata_resolver_instance=resolver)

    with TestClient(app) as client:
        response = client.get("/", params={"query": "Shaun the Sheep", "category": "video"})

    assert response.status_code == 200
    assert "movie-info-btn" in response.text
    assert "movie-info-status" in response.text
    assert "card-queue-state hidden" in response.text
    assert "card-saved-state hidden" in response.text
    assert "queue-manage-btn" in response.text
    assert 'data-default-label="Add to queue..."' in response.text
    assert 'id="fileResultsToolbar"' in response.text
    assert 'id="fileSearchAdvancedFilters"' in response.text
    assert 'class="file-results-filter-chip btn btn-pill btn-sm active"' in response.text
    assert 'id="fileResultsGrid"' in response.text
    assert 'data-view="cards"' in response.text
    assert 'class="result-details"' in response.text


def test_video_search_page_keeps_info_buttons_even_for_tv_like_searches(app_factory) -> None:
    fake_client = FakeSdilejClient(
        responses_by_query={
            "Bluey": [build_search_result(file_id=12, title="Bluey S02E01 SK dabing.mkv")],
        }
    )
    resolver = StaticMetadataResolver(
        TitleMetadata(
            kind="tv",
            canonical_title="Bluey",
            original_title="Bluey",
            local_titles=["Bluey"],
            aliases=["Bluey"],
            year=2018,
            source="tvmaze",
            source_ids={"tvmaze": 1},
        )
    )
    app = app_factory(client_instance=fake_client, metadata_resolver_instance=resolver)

    with TestClient(app) as client:
        response = client.get("/", params={"query": "Bluey", "category": "video"})

    assert response.status_code == 200
    assert "movie-info-btn" in response.text


def test_download_enqueue_returns_duplicate_job_for_active_match(app_factory) -> None:
    app = app_factory()

    payload = {
        "detail_url": "https://sdilej.cz/12345/example-file.mkv",
        "file_id": 12345,
        "title": "Matrix 1999 CZ dabing.mkv",
        "preferred_mode": "premium",
    }

    with TestClient(app) as client:
        first = client.post("/api/downloads", json=payload)
        second = client.post("/api/downloads", json=payload)

    assert first.status_code == 200
    assert second.status_code == 409
    duplicate = second.json()["duplicate_job"]
    assert duplicate["id"] == first.json()["id"]
    assert duplicate["status"] == "queued"


def test_download_enqueue_accepts_youtube_source(app_factory) -> None:
    app = app_factory()

    payload = {
        "detail_url": "https://www.youtube.com/watch?v=abc123XYZ",
        "title": "Máša a medveď: Ako sa stretli",
        "source_type": "youtube",
        "preferred_mode": "premium",
        "media_kind": "tv",
        "is_kids": True,
        "series_name": "Máša a medveď",
        "season_number": 1,
        "episode_number": 1,
        "source_metadata": {"provider": "veselerozpravky"},
    }

    with TestClient(app) as client:
        response = client.post("/api/downloads", json=payload)

    assert response.status_code == 200
    job = response.json()
    assert job["source_type"] == "youtube"
    assert job["preferred_mode"] == "auto"
    assert job["source_metadata"]["provider"] == "veselerozpravky"
    assert job["media_kind"] == "tv"
    assert job["is_kids"] is True


def test_download_enqueue_accepts_direct_youtube_quick_payload(app_factory) -> None:
    app = app_factory()

    payload = {
        "detail_url": "https://www.youtube.com/watch?v=abc123XYZ",
        "title": "YouTube video",
        "source_type": "youtube",
        "preferred_mode": "auto",
        "media_kind": "movie",
        "is_kids": False,
        "source_metadata": {
            "provider": "youtube_direct",
            "prefer_metadata_title": True,
        },
    }

    with TestClient(app) as client:
        response = client.post("/api/downloads", json=payload)

    assert response.status_code == 200
    job = response.json()
    assert job["source_type"] == "youtube"
    assert job["title"] == "YouTube video"
    assert job["preferred_mode"] == "auto"
    assert job["media_kind"] == "movie"
    assert job["is_kids"] is False
    assert job["source_metadata"]["provider"] == "youtube_direct"
    assert job["source_metadata"]["prefer_metadata_title"] is True


def test_library_tv_show_suggestions_reads_local_tv_roots(app_factory, media_root) -> None:
    app = app_factory()
    (media_root / "tv" / "Reacher").mkdir(parents=True)
    (media_root / "tv" / "Bluey").mkdir(parents=True)
    (media_root / "tv" / "ignore.txt").write_text("x", encoding="utf-8")
    (media_root / "kids" / "tv" / "Masa a medved").mkdir(parents=True)

    with TestClient(app) as client:
        response = client.get("/api/library/tv/shows?q=bl")
        kids_response = client.get("/api/library/tv/shows?is_kids=true")

    assert response.status_code == 200
    assert response.json()["items"] == ["Bluey"]
    assert kids_response.status_code == 200
    assert kids_response.json()["items"] == ["Masa a medved"]


def test_youtube_auth_saves_pasted_cookies_without_returning_secret(app_factory, tmp_path, monkeypatch) -> None:
    managed_path = tmp_path / "secrets" / "youtube-cookies.txt"
    monkeypatch.setenv("YOUTUBE_MANAGED_COOKIES_PATH", str(managed_path))
    app = app_factory()
    cookies_text = "# Netscape HTTP Cookie File\n.youtube.com\tTRUE\t/\tTRUE\t1893456000\tSID\tsecret-value\n"

    with TestClient(app) as client:
        save_response = client.post(
            "/api/youtube-auth",
            json={"mode": "cookies_file", "cookies_text": cookies_text},
        )
        get_response = client.get("/api/youtube-auth")

    assert save_response.status_code == 200
    assert managed_path.read_text(encoding="utf-8") == cookies_text.strip()
    payload = get_response.json()
    assert payload["configured"] is True
    assert payload["mode"] == "cookies_file"
    assert payload["managed_cookies"] is True
    assert payload["cookies_path"] == str(managed_path.resolve())
    assert "secret-value" not in str(payload)


def test_youtube_auth_test_probes_configured_runtime(app_factory, monkeypatch) -> None:
    app = app_factory()
    monkeypatch.setattr(
        YoutubeDownloader,
        "probe",
        lambda self, url, auth=None: {"title": "Private clip", "webpage_url": url},
    )

    with TestClient(app) as client:
        client.post("/api/youtube-auth", json={"mode": "cookies_from_browser", "cookies_from_browser": "firefox"})
        response = client.post(
            "/api/youtube-auth/test",
            json={"detail_url": "https://www.youtube.com/watch?v=private"},
        )

    assert response.status_code == 200
    assert response.json() == {
        "ok": True,
        "title": "Private clip",
        "webpage_url": "https://www.youtube.com/watch?v=private",
    }


def test_youtube_auth_test_requires_saved_auth(app_factory) -> None:
    app = app_factory()

    with TestClient(app) as client:
        response = client.post(
            "/api/youtube-auth/test",
            json={"detail_url": "https://www.youtube.com/watch?v=private"},
        )

    assert response.status_code == 400
    assert response.json()["error_code"] == "youtube_auth_not_configured"


def test_youtube_auth_defaults_managed_cookies_next_to_app_db(app_factory, tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("YOUTUBE_MANAGED_COOKIES_PATH", raising=False)
    db_path = tmp_path / "config" / "app.db"
    monkeypatch.setenv("APP_DB_PATH", str(db_path))
    storage = Storage(db_path=str(db_path))
    storage.init_db()
    app = create_app(storage_instance=storage, start_workers=False)

    with TestClient(app) as client:
        response = client.post(
            "/api/youtube-auth",
            json={"mode": "cookies_file", "cookies_text": "cookie-data"},
        )

    assert response.status_code == 200
    managed_path = tmp_path / "config" / "secrets" / "youtube-cookies.txt"
    assert managed_path.read_text(encoding="utf-8") == "cookie-data"
    assert response.json()["cookies_path"] == str(managed_path.resolve())


def test_youtube_auth_rejects_missing_cookies_file(app_factory, tmp_path) -> None:
    app = app_factory()

    with TestClient(app) as client:
        response = client.post(
            "/api/youtube-auth",
            json={"mode": "cookies_file", "cookies_path": str(tmp_path / "missing.txt")},
        )

    assert response.status_code == 400
    assert response.json()["error_code"] == "youtube_auth_cookies_file_missing"


def test_youtube_auth_clear_deletes_managed_cookies(app_factory, tmp_path, monkeypatch) -> None:
    managed_path = tmp_path / "secrets" / "youtube-cookies.txt"
    monkeypatch.setenv("YOUTUBE_MANAGED_COOKIES_PATH", str(managed_path))
    app = app_factory()

    with TestClient(app) as client:
        client.post("/api/youtube-auth", json={"mode": "cookies_file", "cookies_text": "cookie-data"})
        response = client.delete("/api/youtube-auth")
        status_response = client.get("/api/youtube-auth")

    assert response.status_code == 200
    assert response.json()["cleared"] is True
    assert not managed_path.exists()
    assert status_response.json()["configured"] is False


@responses.activate
def test_download_enqueue_resolves_veselerozpravky_episode_url(app_factory) -> None:
    episode_url = "https://www.veselerozpravky.sk/masa-a-medved-ako-sa-stretli/"
    responses.get(
        episode_url,
        body="""
        <html><body>
          <h1>Máša a medveď: Ako sa stretli</h1>
          <script>var videoId = "1V3ZY_TXKwU";</script>
        </body></html>
        """,
    )
    app = app_factory()

    with TestClient(app) as client:
        response = client.post(
            "/api/downloads",
            json={
                "detail_url": episode_url,
                "source_type": "youtube",
                "media_kind": "tv",
                "is_kids": True,
                "series_name": "Máša a medveď",
                "season_number": 1,
                "episode_number": 1,
            },
        )

    assert response.status_code == 200
    job = response.json()
    assert job["detail_url"] == "https://www.youtube.com/watch?v=1V3ZY_TXKwU"
    assert job["source_type"] == "youtube"
    assert job["source_metadata"]["kids_catalog"]["youtube_video_id"] == "1V3ZY_TXKwU"


def test_download_queue_refresh_error_returns_diagnostic_payload_and_request_id(app_factory) -> None:
    app = app_factory()
    app.state.services.storage.list_download_jobs = lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("boom"))  # type: ignore[assignment]

    with TestClient(app) as client:
        response = client.get("/api/downloads")

    assert response.status_code == 500
    payload = response.json()
    assert payload["error_code"] == "downloads_refresh_failed"
    assert payload["request_id"]
    assert response.headers["x-request-id"] == payload["request_id"]
    assert payload["hint"]


def test_media_classify_uses_movie_metadata_for_kids_detection(app_factory) -> None:
    resolver = StaticMetadataResolver(
        TitleMetadata(
            kind="movie",
            canonical_title="Ledové království",
            original_title="Frozen",
            local_titles=["Ledové království"],
            aliases=["Frozen", "Ledové království"],
            genres=["Animovaný", "Rodinný", "Komedie"],
            summary="A family adventure for children about two sisters.",
            content_type="movie",
            year=2013,
            source="czdb",
            source_ids={"czdb": 84178},
        )
    )
    app = app_factory(metadata_resolver_instance=resolver)

    with TestClient(app) as client:
        response = client.post("/api/media/classify", json={"title": "Frozen.2013.1080p.BluRay.mkv"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["classification"]["media_kind"] == "movie"
    assert payload["classification"]["is_kids"] is True
    assert payload["destination_subpath"].endswith("kids/movies")


def test_media_classify_uses_tv_metadata_for_kids_detection(app_factory) -> None:
    resolver = StaticMetadataResolver(
        TitleMetadata(
            kind="tv",
            canonical_title="Blue",
            original_title="Bluey",
            local_titles=["Blue"],
            aliases=["Bluey", "Blue"],
            genres=["Animovaný", "Rodinný", "Children"],
            summary="A playful family series for children following Bluey and her family.",
            content_type="Animation",
            year=2018,
            source="czdb",
            source_ids={"czdb": 28067},
        )
    )
    app = app_factory(metadata_resolver_instance=resolver)

    with TestClient(app) as client:
        response = client.post(
            "/api/media/classify",
            json={
                "title": "Bluey S02E01 Dance Mode",
                "media_kind": "tv",
                "series_name": "Bluey",
                "season_number": 2,
                "episode_number": 1,
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["classification"]["media_kind"] == "tv"
    assert payload["classification"]["is_kids"] is True
    assert payload["destination_subpath"].endswith("kids/tv/Bluey/S02")


def test_media_classify_destination_preset_tv_requires_series_and_season(app_factory) -> None:
    app = app_factory()

    with TestClient(app) as client:
        response = client.post(
            "/api/media/classify",
            json={"title": "Some Episode", "destination_preset": "tv"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["destination_preset"] == "tv"
    assert payload["classification"]["media_kind"] == "tv"
    assert payload["classification"]["is_kids"] is False
    assert payload["requires_confirmation"] is True


def test_download_enqueue_destination_preset_kids_movies(app_factory) -> None:
    app = app_factory()

    with TestClient(app) as client:
        response = client.post(
            "/api/downloads",
            json={
                "detail_url": "https://sdilej.cz/771/frozen.mkv",
                "file_id": 771,
                "title": "Frozen.2013.1080p.mkv",
                "destination_preset": "kids_movies",
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["media_kind"] == "movie"
    assert payload["is_kids"] is True
    assert payload["destination_subpath"].endswith("kids/movies")


def test_media_classify_destination_preset_music_routes_to_music(app_factory) -> None:
    app = app_factory()

    with TestClient(app) as client:
        response = client.post(
            "/api/media/classify",
            json={"title": "Artist - Track.flac", "destination_preset": "music"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["classification"]["media_kind"] == "music"
    assert payload["classification"]["is_kids"] is False
    assert payload["destination_subpath"].endswith("music")
    assert payload["requires_confirmation"] is False


def test_download_enqueue_destination_preset_music(app_factory) -> None:
    app = app_factory()

    with TestClient(app) as client:
        response = client.post(
            "/api/downloads",
            json={
                "detail_url": "https://sdilej.cz/774/artist-track.flac",
                "file_id": 774,
                "title": "Artist - Track.flac",
                "destination_preset": "music",
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["media_kind"] == "music"
    assert payload["is_kids"] is False
    assert payload["destination_subpath"].endswith("music")


def test_library_paths_roundtrip_includes_music_dir(app_factory) -> None:
    app = app_factory()

    with TestClient(app) as client:
        response = client.post(
            "/api/downloads/library-paths",
            json={
                "movies_dir": "/films",
                "tv_dir": "/series",
                "kids_movies_dir": "/kids/films",
                "kids_tv_dir": "/kids/series",
                "music_dir": "/audio",
                "unsorted_dir": "/inbox",
                "confirm_on_uncertain": False,
            },
        )
        assert response.status_code == 200
        assert response.json()["music_dir"] == "/audio"

        loaded = client.get("/api/downloads/library-paths")

    assert loaded.status_code == 200
    payload = loaded.json()
    assert payload["music_dir"] == "/audio"
    assert payload["confirm_on_uncertain"] is False


def test_download_recategorize_music_clears_previous_tv_metadata(app_factory) -> None:
    app = app_factory()

    with TestClient(app) as client:
        queued = client.post(
            "/api/downloads",
            json={
                "detail_url": "https://sdilej.cz/775/bluey-s01e01.mkv",
                "file_id": 775,
                "title": "Bluey S01E01",
                "media_kind": "tv",
                "is_kids": True,
                "series_name": "Bluey",
                "season_number": 1,
            },
        )
        assert queued.status_code == 200
        response = client.post(
            f"/api/downloads/{queued.json()['id']}/classification",
            json={"destination_preset": "music"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["media_kind"] == "music"
    assert payload["is_kids"] is False
    assert payload["series_name"] is None
    assert payload["season_number"] is None
    assert payload["destination_subpath"].endswith("music")


def test_download_enqueue_destination_preset_unsorted_bypasses_uncertain_confirmation(app_factory) -> None:
    app = app_factory()

    with TestClient(app) as client:
        response = client.post(
            "/api/downloads",
            json={
                "detail_url": "https://sdilej.cz/772/unknown-episode.mkv",
                "file_id": 772,
                "title": "Unknown Episode",
                "destination_preset": "unsorted",
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["media_kind"] == "unknown"
    assert payload["destination_subpath"].endswith("unsorted")


def test_download_recategorize_destination_preset_unsorted_updates_route(app_factory) -> None:
    app = app_factory()

    with TestClient(app) as client:
        queued = client.post(
            "/api/downloads",
            json={
                "detail_url": "https://sdilej.cz/773/bluey-s01e01.mkv",
                "file_id": 773,
                "title": "Bluey S01E01",
                "media_kind": "tv",
                "is_kids": True,
                "series_name": "Bluey",
                "season_number": 1,
            },
        )
        assert queued.status_code == 200
        response = client.post(
            f"/api/downloads/{queued.json()['id']}/classification",
            json={"destination_preset": "unsorted"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["media_kind"] == "unknown"
    assert payload["destination_subpath"].endswith("unsorted")


def test_saved_upsert_uses_metadata_for_kids_detection(app_factory) -> None:
    resolver = StaticMetadataResolver(
        TitleMetadata(
            kind="movie",
            canonical_title="Ledové království",
            original_title="Frozen",
            local_titles=["Ledové království"],
            aliases=["Frozen", "Ledové království"],
            genres=["Animovaný", "Rodinný"],
            summary="A family-friendly animated adventure.",
            content_type="movie",
            year=2013,
            source="czdb",
            source_ids={"czdb": 84178},
        )
    )
    app = app_factory(metadata_resolver_instance=resolver)

    with TestClient(app) as client:
        response = client.post(
            "/api/saved",
            json={
                "file_id": 555,
                "title": "Frozen.2013.1080p.BluRay.mkv",
                "detail_url": "https://sdilej.cz/555/frozen.mkv",
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["media_kind"] == "movie"
    assert payload["is_kids"] is True
