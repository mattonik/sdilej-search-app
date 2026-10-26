from __future__ import annotations

import responses

from app.sdilej_client import BASE_URL, SEARCH_ENTRYPOINT, USER_DOWNLOADS_URL, SdilejClient
from tests.conftest import build_sdilej_search_html


@responses.activate
def test_sdilej_client_search_parses_mocked_html() -> None:
    responses.get(
        SEARCH_ENTRYPOINT,
        status=302,
        headers={"Location": "/shaun-the-sheep/s/"},
    )
    responses.get(
        f"{BASE_URL}/shaun-the-sheep/s/video-",
        body=build_sdilej_search_html(
            [
                {
                    "detail_url": "/123456/shaun-the-sheep-s01e01.mkv",
                    "title": "Shaun the Sheep S01E01 SK dabing 2020",
                    "thumbnail": "/thumb/1.jpg",
                    "meta": "700 MB / Delka: 00:21:00",
                    "playable": True,
                },
                {
                    "detail_url": "/123456/shaun-the-sheep-s01e01.mkv",
                    "title": "Shaun the Sheep S01E01 SK dabing 2020",
                    "thumbnail": "/thumb/1.jpg",
                    "meta": "700 MB / Delka: 00:21:00",
                    "playable": True,
                },
            ]
        ),
    )

    client = SdilejClient()
    response = client.search(query="Shaun the Sheep", category="video", max_results=10)

    assert response.slug == "shaun-the-sheep"
    assert response.result_count == 1
    result = response.results[0]
    assert result.file_id == 123456
    assert result.detected_languages == ["SK"]
    assert result.has_dub_hint is True


@responses.activate
def test_sdilej_client_lists_current_user_downloads() -> None:
    responses.get(
        USER_DOWNLOADS_URL,
        body=build_sdilej_search_html(
            [
                {
                    "detail_url": "/123456/reacher-s02e08.mkv",
                    "title": "Reacher S02E08 Fly Boy EN 1080p mkv",
                    "thumbnail": "/thumb/1.jpg",
                    "meta": "1.2 GB / Delka: 00:45:00",
                    "playable": True,
                },
                {
                    "detail_url": "/123456/reacher-s02e08.mkv",
                    "title": "Reacher S02E08 Fly Boy EN 1080p mkv",
                    "thumbnail": "/thumb/1.jpg",
                    "meta": "1.2 GB / Delka: 00:45:00",
                    "playable": True,
                },
            ]
        ),
    )

    results = SdilejClient().list_user_downloads(max_results=10)

    assert len(results) == 1
    assert results[0].file_id == 123456
    assert results[0].size == "1.2 GB"
