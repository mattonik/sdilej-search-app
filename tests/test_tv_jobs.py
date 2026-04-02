from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import create_app
from app.models import TitleMetadata
from app.tv_search_worker import TvSearchWorker
from app.tvmaze_client import TvEpisode, TvShowSummary
from tests.conftest import (
    FakeTvMazeClient,
    StaticMetadataResolver,
    StaticSearchClientFactory,
    build_search_result,
)


def test_tv_media_classification_reuses_existing_alias_folder(app_factory, media_root) -> None:
    existing = media_root / "tv" / "Vesela farma"
    existing.mkdir(parents=True)
    metadata = TitleMetadata(
        kind="tv",
        canonical_title="Ovecka Shaun",
        original_title="Shaun the Sheep",
        local_titles=["Ovecka Shaun", "Vesela farma"],
        aliases=["Shaun the Sheep", "Vesela farma"],
        year=2007,
        source="czdb",
        source_ids={},
    )
    resolver = StaticMetadataResolver(metadata)
    app = app_factory(metadata_resolver_instance=resolver)

    with TestClient(app) as client:
        response = client.post(
            "/api/media/classify",
            json={
                "title": "Shaun the Sheep S01E01",
                "media_kind": "tv",
                "series_name": "Shaun the Sheep",
                "season_number": 1,
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["classification"]["series_name"] == "Vesela farma"
    assert payload["destination_subpath"].endswith("tv/Vesela farma/S01")


def test_sync_tv_search_marks_existing_episode_as_downloaded_and_skips_episode_queries(app_factory, media_root) -> None:
    season_dir = media_root / "tv" / "Vesela farma" / "S01"
    season_dir.mkdir(parents=True)
    (season_dir / "Vesela farma - S01E01.mkv").write_text("video")
    (season_dir / "Vesela farma - S01E01.srt").write_text("subtitle")
    metadata = TitleMetadata(
        kind="tv",
        canonical_title="Ovecka Shaun",
        original_title="Shaun the Sheep",
        local_titles=["Vesela farma"],
        aliases=["Shaun the Sheep", "Vesela farma"],
        year=2007,
        source="fallback",
        source_ids={},
    )
    fake_client = StaticSearchClientFactory({})(timeout_seconds=30)
    app = app_factory(
        client_instance=fake_client,
        tv_client_instance=FakeTvMazeClient(episodes=[FakeTvMazeClient().episodes[0]]),
        metadata_resolver_instance=StaticMetadataResolver(metadata),
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/tv/search",
            json={
                "show_id": 321,
                "show_name": "Shaun the Sheep",
                "seasons": [1],
                "episodes_by_season": {"1": [1]},
                "aliases": ["Shaun the Sheep", "Vesela farma"],
                "title_metadata": metadata.to_dict(),
            },
        )

    assert response.status_code == 200
    payload = response.json()
    episode = payload["seasons"][0]["episodes"][0]
    assert episode["status"] == "downloaded"
    assert episode["result_count"] == 0
    assert episode["downloaded_files"] == ["Vesela farma - S01E01.mkv"]
    assert all("S01E01" not in query for query in fake_client.calls)


def test_sync_tv_search_ignores_support_files_when_detecting_downloaded_episodes(app_factory, media_root) -> None:
    season_dir = media_root / "tv" / "Shaun the Sheep" / "S01"
    season_dir.mkdir(parents=True)
    (season_dir / "Shaun the Sheep - S01E01.srt").write_text("subtitle")
    (season_dir / "Shaun the Sheep - S01E01.nfo").write_text("nfo")
    (season_dir / "Shaun the Sheep - S01E01.mkv.part").write_text("partial")
    metadata = TitleMetadata(
        kind="tv",
        canonical_title="Shaun the Sheep",
        original_title="Shaun the Sheep",
        local_titles=[],
        aliases=["Shaun the Sheep"],
        year=2007,
        source="fallback",
        source_ids={},
    )
    fake_client = StaticSearchClientFactory(
        {
            "Shaun the Sheep S01E01": [build_search_result(file_id=1, title="Shaun the Sheep S01E01 SK DAB")],
        }
    )(timeout_seconds=30)
    app = app_factory(
        client_instance=fake_client,
        tv_client_instance=FakeTvMazeClient(episodes=[FakeTvMazeClient().episodes[0]]),
        metadata_resolver_instance=StaticMetadataResolver(metadata),
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/tv/search",
            json={
                "show_id": 321,
                "show_name": "Shaun the Sheep",
                "seasons": [1],
                "episodes_by_season": {"1": [1]},
                "aliases": ["Shaun the Sheep"],
                "title_metadata": metadata.to_dict(),
            },
        )

    assert response.status_code == 200
    episode = response.json()["seasons"][0]["episodes"][0]
    assert episode["status"] == "done"
    assert episode["result_count"] == 1


def test_manual_tv_episode_search_force_search_bypasses_downloaded_skip(app_factory, media_root) -> None:
    season_dir = media_root / "tv" / "Vesela farma" / "S01"
    season_dir.mkdir(parents=True)
    (season_dir / "Vesela farma - S01E01.mkv").write_text("video")
    metadata = TitleMetadata(
        kind="tv",
        canonical_title="Ovecka Shaun",
        original_title="Shaun the Sheep",
        local_titles=["Vesela farma"],
        aliases=["Shaun the Sheep", "Vesela farma"],
        year=2007,
        source="fallback",
        source_ids={},
    )
    fake_client = StaticSearchClientFactory(
        {
            "Shaun the Sheep S01E01": [build_search_result(file_id=1, title="Shaun the Sheep S01E01 SK DAB")],
            "Vesela farma S01E01": [build_search_result(file_id=2, title="Vesela farma S01E01 SK DAB")],
        }
    )(timeout_seconds=30)
    app = app_factory(
        client_instance=fake_client,
        tv_client_instance=FakeTvMazeClient(episodes=[FakeTvMazeClient().episodes[0]]),
        metadata_resolver_instance=StaticMetadataResolver(metadata),
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/tv/search-episode",
            json={
                "show_id": 321,
                "show_name": "Shaun the Sheep",
                "season_number": 1,
                "episode_number": 1,
                "episode_name": "Off the Baa!",
                "aliases": ["Shaun the Sheep", "Vesela farma"],
                "title_metadata": metadata.to_dict(),
                "alias_mode": "optimized",
                "force_search": True,
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["episode"]["status"] == "done"
    assert payload["episode"]["result_count"] >= 1
    assert any("S01E01" in query for query in fake_client.calls)


def test_tv_search_job_worker_processes_and_finalizes_job(app_factory, storage) -> None:
    search_factory = StaticSearchClientFactory(
        {
            "Shaun the Sheep S01E01": [build_search_result(file_id=1, title="Shaun the Sheep S01E01 SK DAB")],
            "Shaun the Sheep S01E02": [build_search_result(file_id=2, title="Shaun the Sheep S01E02 SK DAB")],
        }
    )
    metadata = TitleMetadata(
        kind="tv",
        canonical_title="Shaun the Sheep",
        original_title="Shaun the Sheep",
        local_titles=["Vesela farma"],
        aliases=["Shaun the Sheep"],
        year=2007,
        source="fallback",
        source_ids={},
    )
    app = app_factory(
        tv_client_instance=FakeTvMazeClient(),
        metadata_resolver_instance=StaticMetadataResolver(metadata),
    )

    with TestClient(app) as client:
        created = client.post(
            "/api/tv/search-jobs",
            json={
                "show_id": 321,
                "show_name": "Shaun the Sheep",
                "seasons": [1],
                "episodes_by_season": {"1": [1, 2]},
                "aliases": ["Shaun the Sheep"],
                "title_metadata": metadata.to_dict(),
            },
        )
        assert created.status_code == 200
        job_id = created.json()["id"]

    worker = TvSearchWorker(storage=storage, client_factory=search_factory)
    claimed = storage.claim_next_tv_search_job()
    assert claimed is not None
    assert claimed["id"] == job_id
    worker._process_job(claimed)

    job = storage.get_tv_search_job(job_id)
    assert job is not None
    assert job["status"] == "done"
    assert job["search_aliases"] == ["Shaun the Sheep", "Vesela farma"]
    assert job["completed_episodes"] == 2
    assert job["result_count"] == 2
    assert all(episode["status"] == "done" for season in job["seasons"] for episode in season["episodes"])


def test_tv_search_job_marks_downloaded_episodes_complete_before_worker_runs(app_factory, storage, media_root) -> None:
    season_dir = media_root / "tv" / "Shaun the Sheep" / "S01"
    season_dir.mkdir(parents=True)
    (season_dir / "Shaun the Sheep - S01E01.mkv").write_text("video")
    metadata = TitleMetadata(
        kind="tv",
        canonical_title="Shaun the Sheep",
        original_title="Shaun the Sheep",
        local_titles=[],
        aliases=["Shaun the Sheep"],
        year=2007,
        source="fallback",
        source_ids={},
    )
    job_search_client = StaticSearchClientFactory({})(timeout_seconds=30)
    worker_search_factory = StaticSearchClientFactory(
        {
            "Shaun the Sheep S01E02": [build_search_result(file_id=2, title="Shaun the Sheep S01E02 SK DAB")],
        }
    )
    app = app_factory(
        client_instance=job_search_client,
        tv_client_instance=FakeTvMazeClient(),
        metadata_resolver_instance=StaticMetadataResolver(metadata),
    )

    with TestClient(app) as client:
        created = client.post(
            "/api/tv/search-jobs",
            json={
                "show_id": 321,
                "show_name": "Shaun the Sheep",
                "seasons": [1],
                "episodes_by_season": {"1": [1, 2]},
                "aliases": ["Shaun the Sheep"],
                "title_metadata": metadata.to_dict(),
            },
        )
        assert created.status_code == 200
        created_payload = created.json()
        job_id = created_payload["id"]

    assert created_payload["completed_episodes"] == 1
    first_episode = created_payload["seasons"][0]["episodes"][0]
    second_episode = created_payload["seasons"][0]["episodes"][1]
    assert first_episode["status"] == "downloaded"
    assert first_episode["downloaded_files"] == ["Shaun the Sheep - S01E01.mkv"]
    assert second_episode["status"] == "pending"

    worker = TvSearchWorker(storage=storage, client_factory=worker_search_factory)
    claimed = storage.claim_next_tv_search_job()
    assert claimed is not None
    worker._process_job(claimed)

    job = storage.get_tv_search_job(job_id)
    assert job is not None
    assert job["status"] == "done"
    assert job["completed_episodes"] == 2
    assert worker_search_factory.instances[0].calls == ["Shaun the Sheep S01E02"]


def test_tv_search_job_partial_progress_is_visible(app_factory, storage) -> None:
    metadata = TitleMetadata(
        kind="tv",
        canonical_title="Shaun the Sheep",
        original_title="Shaun the Sheep",
        local_titles=["Vesela farma"],
        aliases=["Shaun the Sheep"],
        year=2007,
        source="fallback",
        source_ids={},
    )
    app = app_factory(
        tv_client_instance=FakeTvMazeClient(),
        metadata_resolver_instance=StaticMetadataResolver(metadata),
    )

    with TestClient(app) as client:
        created = client.post(
            "/api/tv/search-jobs",
            json={
                "show_id": 321,
                "show_name": "Shaun the Sheep",
                "seasons": [1],
                "episodes_by_season": {"1": [1, 2]},
                "aliases": ["Shaun the Sheep"],
                "title_metadata": metadata.to_dict(),
            },
        )
        job_id = created.json()["id"]

        claimed = storage.claim_next_tv_search_job()
        assert claimed is not None
        storage.mark_tv_search_episode_running(job_id, 1, 1)
        storage.complete_tv_search_episode(
            job_id,
            season_number=1,
            episode_number=1,
            query_variants=["Shaun the Sheep S01E01"],
            query_errors=[],
            results=[build_search_result(file_id=1, title="Shaun the Sheep S01E01 SK DAB").to_dict()],
        )
        job = client.get(f"/api/tv/search-jobs/{job_id}").json()

    assert job["status"] == "running"
    assert job["search_aliases"] == ["Shaun the Sheep", "Vesela farma"]
    assert job["completed_episodes"] == 1
    first_episode = job["seasons"][0]["episodes"][0]
    assert first_episode["status"] == "done"


def test_canceling_tv_search_job_marks_pending_work_canceled(app_factory, storage) -> None:
    metadata = TitleMetadata(
        kind="tv",
        canonical_title="Shaun the Sheep",
        original_title="Shaun the Sheep",
        local_titles=["Vesela farma"],
        aliases=["Shaun the Sheep"],
        year=2007,
        source="fallback",
        source_ids={},
    )
    app = app_factory(
        tv_client_instance=FakeTvMazeClient(),
        metadata_resolver_instance=StaticMetadataResolver(metadata),
    )

    with TestClient(app) as client:
        created = client.post(
            "/api/tv/search-jobs",
            json={
                "show_id": 321,
                "show_name": "Shaun the Sheep",
                "seasons": [1],
                "episodes_by_season": {"1": [1, 2]},
                "aliases": ["Shaun the Sheep"],
                "title_metadata": metadata.to_dict(),
            },
        )
        job_id = created.json()["id"]
        storage.claim_next_tv_search_job()
        canceled = client.post(f"/api/tv/search-jobs/{job_id}/cancel")

    assert canceled.status_code == 200
    job = storage.get_tv_search_job(job_id)
    assert job is not None
    assert job["status"] == "canceled"
    assert all(episode["status"] == "canceled" for season in job["seasons"] for episode in season["episodes"])


def test_recover_tv_search_queue_preserves_done_episodes(storage) -> None:
    metadata = TitleMetadata(
        kind="tv",
        canonical_title="Shaun the Sheep",
        original_title="Shaun the Sheep",
        local_titles=["Vesela farma"],
        aliases=["Shaun the Sheep"],
        year=2007,
        source="fallback",
        source_ids={},
    )
    job = storage.enqueue_tv_search_job(
        show={"id": 321, "name": "Shaun the Sheep", "source": "tvmaze"},
        title_metadata=metadata.to_dict(),
        aliases=["Shaun the Sheep"],
        search_aliases=["Shaun the Sheep"],
        selected_seasons=[1],
        episodes_by_season={"1": [1, 2]},
        category="video",
        language="SK",
        language_scope="any",
        strict_dubbing=False,
        max_results_per_variant=120,
        episodes=[
            {"season_number": 1, "episode_number": 1, "episode_name": "Off the Baa!", "airdate": "2007-03-05", "episode_code": "S01E01"},
            {"season_number": 1, "episode_number": 2, "episode_name": "Fetching", "airdate": "2007-03-06", "episode_code": "S01E02"},
        ],
    )
    job_id = job["id"]
    storage.claim_next_tv_search_job()
    storage.mark_tv_search_episode_running(job_id, 1, 1)
    storage.complete_tv_search_episode(
        job_id,
        season_number=1,
        episode_number=1,
        query_variants=["Shaun the Sheep S01E01"],
        query_errors=[],
        results=[build_search_result(file_id=1, title="Shaun the Sheep S01E01 SK DAB").to_dict()],
    )
    storage.mark_tv_search_episode_running(job_id, 1, 2)

    recovered = storage.recover_tv_search_queue_after_restart()

    assert recovered == 1
    refreshed = storage.get_tv_search_job(job_id)
    assert refreshed is not None
    assert refreshed["status"] == "queued"
    episode_statuses = [episode["status"] for season in refreshed["seasons"] for episode in season["episodes"]]
    assert episode_statuses == ["done", "pending"]


def test_legacy_sync_tv_search_uses_aliases(app_factory) -> None:
    metadata = TitleMetadata(
        kind="tv",
        canonical_title="Shaun the Sheep",
        original_title="Shaun the Sheep",
        local_titles=["Vesela farma"],
        aliases=["Shaun the Sheep", "Vesela farma"],
        year=2007,
        source="fallback",
        source_ids={},
    )
    fake_client = StaticSearchClientFactory(
        {
            "Shaun the Sheep S01E01": [build_search_result(file_id=1, title="Shaun the Sheep S01E01 SK DAB")],
            "Vesela farma S01E01": [build_search_result(file_id=2, title="Vesela farma S01E01 SK DAB")],
        }
    )(timeout_seconds=30)
    app = app_factory(
        client_instance=fake_client,
        tv_client_instance=FakeTvMazeClient(episodes=[FakeTvMazeClient().episodes[0]]),
        metadata_resolver_instance=StaticMetadataResolver(metadata),
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/tv/search",
            json={
                "show_id": 321,
                "show_name": "Shaun the Sheep",
                "seasons": [1],
                "episodes_by_season": {"1": [1]},
                "aliases": ["Shaun the Sheep", "Vesela farma"],
                "title_metadata": metadata.to_dict(),
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "done"
    assert payload["aliases"] == ["Shaun the Sheep", "Vesela farma"]
    assert payload["search_aliases"] == ["Shaun the Sheep", "Vesela farma"]
    assert payload["seasons"][0]["episodes"][0]["result_count"] == 2


def test_sync_tv_search_prefers_exact_show_results_over_generic_blue_titles(app_factory) -> None:
    bluey_show = TvShowSummary(
        id=777,
        name="Bluey",
        premiered="2018-10-01",
        language="English",
        type="Animation",
        genres=["Children", "Comedy"],
        summary="Bluey and her family turn everyday life into playful adventures.",
    )
    bluey_episode = TvEpisode(id=1001, season=1, number=1, name="Magic Xylophone", airdate="2018-10-01")
    metadata = TitleMetadata(
        kind="tv",
        canonical_title="Blue",
        original_title="Bluey",
        local_titles=["Blue"],
        aliases=["Bluey", "Blue"],
        year=2018,
        source="czdb",
        source_ids={"czdb": 28067},
    )
    fake_client = StaticSearchClientFactory(
        {
            "Bluey S01E01": [
                build_search_result(file_id=1, title="Women in Blue S01E01 CZtit V OBRAZE 1080p mkv", size="4.7 GB"),
                build_search_result(file_id=2, title="Boston Blue S01E01 1080p WEB h264 GRACE mkv", size="2.3 GB"),
                build_search_result(file_id=3, title="Rookie Blue S01E01 cz titulky avi", size="367 MB"),
                build_search_result(file_id=4, title="Bluey S01E01 1080p FHD SK CZ EN mkv", size="356 MB"),
                build_search_result(file_id=5, title="Bluey S01E01 Magic Xylophone", size="320 MB"),
                build_search_result(file_id=6, title="Bluey S01e01 mkv", size="300 MB"),
            ],
            "Bluey 1x01": [
                build_search_result(file_id=4, title="Bluey S01E01 1080p FHD SK CZ EN mkv", size="356 MB"),
                build_search_result(file_id=5, title="Bluey S01E01 Magic Xylophone", size="320 MB"),
            ],
            "Bluey Season 1 Episode 1": [
                build_search_result(file_id=5, title="Bluey S01E01 Magic Xylophone", size="320 MB"),
            ],
        }
    )(timeout_seconds=30)
    app = app_factory(
        client_instance=fake_client,
        tv_client_instance=FakeTvMazeClient(
            show=bluey_show,
            episodes=[bluey_episode],
            akas=["Blue"],
        ),
        metadata_resolver_instance=StaticMetadataResolver(metadata),
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/tv/search",
            json={
                "show_id": 321,
                "show_name": "Bluey",
                "seasons": [1],
                "episodes_by_season": {"1": [1]},
                "aliases": ["Bluey", "Blue"],
                "title_metadata": metadata.to_dict(),
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["search_aliases"] == ["Bluey"]
    assert fake_client.calls == ["Bluey S01E01"]
    results = payload["seasons"][0]["episodes"][0]["results"]
    assert [item["title"] for item in results] == [
        "Bluey S01E01 Magic Xylophone",
        "Bluey S01E01 1080p FHD SK CZ EN mkv",
        "Bluey S01e01 mkv",
    ]


def test_background_tv_search_job_uses_same_tv_ranking_rules(app_factory, storage) -> None:
    bluey_show = TvShowSummary(
        id=777,
        name="Bluey",
        premiered="2018-10-01",
        language="English",
        type="Animation",
        genres=["Children", "Comedy"],
        summary="Bluey and her family turn everyday life into playful adventures.",
    )
    bluey_episode = TvEpisode(id=1001, season=1, number=1, name="Magic Xylophone", airdate="2018-10-01")
    metadata = TitleMetadata(
        kind="tv",
        canonical_title="Blue",
        original_title="Bluey",
        local_titles=["Blue"],
        aliases=["Bluey", "Blue"],
        year=2018,
        source="czdb",
        source_ids={"czdb": 28067},
    )
    search_factory = StaticSearchClientFactory(
        {
            "Bluey S01E01": [
                build_search_result(file_id=1, title="Women in Blue S01E01 CZtit V OBRAZE 1080p mkv", size="4.7 GB"),
                build_search_result(file_id=2, title="Boston Blue S01E01 1080p WEB h264 GRACE mkv", size="2.3 GB"),
                build_search_result(file_id=3, title="Bluey S01E01 1080p FHD SK CZ EN mkv", size="356 MB"),
                build_search_result(file_id=4, title="Bluey S01E01 Magic Xylophone", size="320 MB"),
            ],
            "Bluey 1x01": [
                build_search_result(file_id=4, title="Bluey S01E01 Magic Xylophone", size="320 MB"),
            ],
            "Bluey Season 1 Episode 1": [
                build_search_result(file_id=4, title="Bluey S01E01 Magic Xylophone", size="320 MB"),
            ],
        }
    )
    app = app_factory(
        tv_client_instance=FakeTvMazeClient(show=bluey_show, episodes=[bluey_episode], akas=["Blue"]),
        metadata_resolver_instance=StaticMetadataResolver(metadata),
    )

    with TestClient(app) as client:
        created = client.post(
            "/api/tv/search-jobs",
            json={
                "show_id": 321,
                "show_name": "Bluey",
                "seasons": [1],
                "episodes_by_season": {"1": [1]},
                "aliases": ["Bluey", "Blue"],
                "title_metadata": metadata.to_dict(),
            },
        )
        assert created.status_code == 200
        job_id = created.json()["id"]

    worker = TvSearchWorker(storage=storage, client_factory=search_factory)
    claimed = storage.claim_next_tv_search_job()
    assert claimed is not None
    worker._process_job(claimed)

    job = storage.get_tv_search_job(job_id)
    assert job is not None
    assert job["status"] == "done"
    assert job["search_aliases"] == ["Bluey"]
    assert search_factory.instances[0].calls == ["Bluey S01E01"]
    results = job["seasons"][0]["episodes"][0]["results"]
    assert [item["title"] for item in results] == [
        "Bluey S01E01 Magic Xylophone",
        "Bluey S01E01 1080p FHD SK CZ EN mkv",
    ]


def test_sync_tv_search_probes_aliases_once_and_narrows_episode_queries(app_factory) -> None:
    metadata = TitleMetadata(
        kind="tv",
        canonical_title="Ovecka Shaun",
        original_title="Shaun the Sheep",
        local_titles=["Ovecka Shaun", "Vesela farma"],
        aliases=["Shaun the Sheep", "Ovecka Shaun", "Vesela farma"],
        year=2007,
        source="czdb",
        source_ids={"czdb": 101},
    )
    fake_client = StaticSearchClientFactory(
        {
            "Shaun the Sheep": [build_search_result(file_id=10, title="Shaun the Sheep collection")],
            "Ovecka Shaun": [],
            "Vesela farma": [build_search_result(file_id=11, title="Vesela farma archiv")],
            "Shaun the Sheep S01E01": [build_search_result(file_id=1, title="Shaun the Sheep S01E01 SK DAB")],
            "Vesela farma S01E01": [build_search_result(file_id=2, title="Vesela farma S01E01 SK DAB")],
        }
    )(timeout_seconds=30)
    app = app_factory(
        client_instance=fake_client,
        tv_client_instance=FakeTvMazeClient(episodes=[FakeTvMazeClient().episodes[0]]),
        metadata_resolver_instance=StaticMetadataResolver(metadata),
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/tv/search",
            json={
                "show_id": 321,
                "show_name": "Shaun the Sheep",
                "seasons": [1],
                "episodes_by_season": {"1": [1]},
                "aliases": ["Shaun the Sheep", "Ovecka Shaun", "Vesela farma"],
                "title_metadata": metadata.to_dict(),
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["search_aliases"] == ["Shaun the Sheep", "Vesela farma"]
    assert fake_client.calls == [
        "Ovecka Shaun",
        "Vesela farma",
        "Shaun the Sheep S01E01",
        "Vesela farma S01E01",
    ]
    assert payload["seasons"][0]["episodes"][0]["result_count"] == 2


def test_manual_tv_episode_search_can_use_all_safe_aliases(app_factory) -> None:
    metadata = TitleMetadata(
        kind="tv",
        canonical_title="Ovecka Shaun",
        original_title="Shaun the Sheep",
        local_titles=["Ovecka Shaun", "Vesela farma"],
        aliases=["Shaun the Sheep", "Ovecka Shaun", "Vesela farma"],
        year=2007,
        source="czdb",
        source_ids={"czdb": 101},
    )
    fake_client = StaticSearchClientFactory(
        {
            "Shaun the Sheep S01E01": [build_search_result(file_id=1, title="Shaun the Sheep S01E01 SK DAB")],
            "Ovecka Shaun S01E01": [],
            "Ovecka Shaun 1x01": [],
            "Ovecka Shaun 1x1": [],
            "Vesela farma S01E01": [build_search_result(file_id=2, title="Vesela farma S01E01 SK DAB")],
        }
    )(timeout_seconds=30)
    app = app_factory(
        client_instance=fake_client,
        tv_client_instance=FakeTvMazeClient(episodes=[FakeTvMazeClient().episodes[0]]),
        metadata_resolver_instance=StaticMetadataResolver(metadata),
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/tv/search-episode",
            json={
                "show_id": 321,
                "show_name": "Shaun the Sheep",
                "season_number": 1,
                "episode_number": 1,
                "episode_name": "Off the Baa!",
                "aliases": ["Shaun the Sheep", "Ovecka Shaun", "Vesela farma"],
                "title_metadata": metadata.to_dict(),
                "alias_mode": "all",
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["all_search_aliases"] == ["Shaun the Sheep", "Ovecka Shaun", "Vesela farma"]
    assert payload["search_aliases"] == ["Shaun the Sheep", "Ovecka Shaun", "Vesela farma"]
    assert payload["episode"]["alias_mode"] == "all"
    assert payload["episode"]["result_count"] == 2
    assert fake_client.calls == [
        "Shaun the Sheep S01E01",
        "Ovecka Shaun S01E01",
        "Ovecka Shaun 1x01",
        "Ovecka Shaun 1x1",
        "Vesela farma S01E01",
    ]


def test_healthz_reports_both_worker_flags(app_factory) -> None:
    app = app_factory()
    with TestClient(app) as client:
        response = client.get("/healthz")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert "worker_alive" in payload
    assert "tv_search_worker_alive" in payload
