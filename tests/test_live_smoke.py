from __future__ import annotations

import os

import pytest

from app.sdilej_client import SdilejClient
from app.storage import Storage
from app.title_metadata import TitleMetadataResolver
from app.tvmaze_client import TvMazeClient


pytestmark = pytest.mark.live


def _require_live_smoke() -> None:
    if os.getenv("RUN_LIVE_SMOKE") != "1":
        pytest.skip("Set RUN_LIVE_SMOKE=1 to run live smoke tests.")


def test_live_czdb_lookup_returns_metadata(tmp_path) -> None:
    _require_live_smoke()
    storage = Storage(db_path=str(tmp_path / "live.db"))
    storage.init_db()
    resolver = TitleMetadataResolver(storage=storage, tv_client=TvMazeClient())

    metadata = resolver.resolve_movie("Matrix", 1999)

    assert metadata.canonical_title
    assert metadata.aliases


def test_live_tvmaze_lookup_and_aliases(tmp_path) -> None:
    _require_live_smoke()
    storage = Storage(db_path=str(tmp_path / "live-tv.db"))
    storage.init_db()
    tv_client = TvMazeClient()
    resolver = TitleMetadataResolver(storage=storage, tv_client=tv_client)

    show = tv_client.lookup_show("Bluey")
    episodes = tv_client.get_episodes(show.id)
    metadata = resolver.resolve_tv("Bluey", show=show)

    assert show.id > 0
    assert episodes
    assert metadata.aliases


def test_live_sdilej_search_returns_parseable_shape() -> None:
    _require_live_smoke()
    client = SdilejClient()

    response = client.search(query="matrix", category="video", max_results=5)

    assert response.search_url
    assert isinstance(response.results, list)
