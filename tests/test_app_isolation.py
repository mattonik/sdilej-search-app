from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import create_app
from app.storage import Storage


def test_create_app_instances_do_not_share_storage_state(tmp_path) -> None:
    storage_one = Storage(db_path=str(tmp_path / "one.db"))
    storage_two = Storage(db_path=str(tmp_path / "two.db"))
    storage_one.init_db()
    storage_two.init_db()

    storage_one.upsert_saved_candidate(
        file_id=11,
        title="Bluey S01E01",
        detail_url="/11/bluey-s01e01",
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

    app_one = create_app(storage_instance=storage_one, start_workers=False)
    app_two = create_app(storage_instance=storage_two, start_workers=False)

    with TestClient(app_one) as client_one, TestClient(app_two) as client_two:
        response_one = client_one.get("/api/saved")
        response_two = client_two.get("/api/saved")

    assert response_one.status_code == 200
    assert response_two.status_code == 200
    assert len(response_one.json()["items"]) == 1
    assert response_two.json()["items"] == []
