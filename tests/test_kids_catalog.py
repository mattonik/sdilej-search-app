from __future__ import annotations

import responses
from fastapi.testclient import TestClient

from app.kids_catalog import BASE_URL, SHOWS_URL, VeseleRozpravkyClient
from app.main import create_app


SHOWS_HTML = """
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
  </div>
</body></html>
"""

SHOW_HTML = """
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

EPISODE_HTML = """
<html><head>
  <meta property="og:image" content="https://img.youtube.com/vi/1V3ZY_TXKwU/0.jpg">
</head><body>
  <h1>Máša a medveď: Ako sa stretli</h1>
  <script>var videoId = "1V3ZY_TXKwU";</script>
</body></html>
"""


@responses.activate
def test_veselerozpravky_client_parses_show_list_and_episodes() -> None:
    responses.get(SHOWS_URL, body=SHOWS_HTML)
    responses.get(f"{BASE_URL}/masa-a-medved/", body=SHOW_HTML)

    client = VeseleRozpravkyClient()

    shows = client.list_shows()
    show = client.get_show("masa-a-medved")

    assert shows == [
        {
            "slug": "masa-a-medved",
            "title": "Máša a medveď",
            "url": "https://www.veselerozpravky.sk/masa-a-medved/",
            "episode_count": 2,
            "thumbnail_url": None,
        }
    ]
    assert show["title"] == "Máša a medveď"
    assert show["episode_count"] == 2
    assert show["episodes"][0]["episode_number"] == 1
    assert show["episodes"][0]["duration"] == "06:54"


@responses.activate
def test_veselerozpravky_client_resolves_youtube_url() -> None:
    episode_url = f"{BASE_URL}/masa-a-medved-ako-sa-stretli/"
    responses.get(episode_url, body=EPISODE_HTML)

    resolved = VeseleRozpravkyClient().resolve_episode(episode_url)

    assert resolved["youtube_video_id"] == "1V3ZY_TXKwU"
    assert resolved["youtube_url"] == "https://www.youtube.com/watch?v=1V3ZY_TXKwU"


@responses.activate
def test_kids_catalog_api_endpoints(storage) -> None:
    responses.get(SHOWS_URL, body=SHOWS_HTML)
    responses.get(f"{BASE_URL}/masa-a-medved/", body=SHOW_HTML)
    responses.get(f"{BASE_URL}/masa-a-medved-ako-sa-stretli/", body=EPISODE_HTML)
    app = create_app(storage_instance=storage, start_workers=False)

    with TestClient(app) as client:
        shows = client.get("/api/kids-catalog/shows")
        show = client.get("/api/kids-catalog/shows/masa-a-medved")
        resolved = client.post(
            "/api/kids-catalog/resolve",
            json={"episode_url": f"{BASE_URL}/masa-a-medved-ako-sa-stretli/"},
        )

    assert shows.status_code == 200
    assert shows.json()["items"][0]["slug"] == "masa-a-medved"
    assert show.status_code == 200
    assert show.json()["episodes"][0]["episode_number"] == 1
    assert resolved.status_code == 200
    assert resolved.json()["youtube_url"] == "https://www.youtube.com/watch?v=1V3ZY_TXKwU"
