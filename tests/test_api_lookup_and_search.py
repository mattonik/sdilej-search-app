from __future__ import annotations

import responses
from fastapi.testclient import TestClient

from app.main import create_app
from app.models import TitleMetadata
from app.title_metadata import CZDB_SEARCH_URL
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
