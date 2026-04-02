from __future__ import annotations

import responses
from fastapi.testclient import TestClient

from app.main import create_app
from app.models import TitleMetadata
from app.title_metadata import CZDB_DETAIL_URL, CZDB_SEARCH_URL
from app.tvmaze_client import TVMAZE_BASE_URL
from tests.conftest import FakeSdilejClient, StaticMetadataResolver, build_search_result


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
