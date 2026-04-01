from __future__ import annotations

import responses

from app.sdilej_client import BASE_URL, SEARCH_ENTRYPOINT, SdilejClient
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
