from app.downloader import DownloadWorker
from app.storage import Storage


def test_sdilej_filename_fallback_uses_detail_url_extension(tmp_path) -> None:
    worker = DownloadWorker(Storage(db_path=str(tmp_path / "app.db")))

    filename = worker._resolve_filename(
        content_disposition=None,
        fallback_title="Bluey S01E01 Magic Xylophone",
        fallback_url="https://sdilej.cz/123/bluey-s01e01.mkv",
    )

    assert filename == "Bluey S01E01 Magic Xylophone.mkv"


def test_sdilej_placeholder_bin_is_replaced_for_tv_filename(tmp_path) -> None:
    worker = DownloadWorker(Storage(db_path=str(tmp_path / "app.db")))

    filename = worker._resolve_filename(
        content_disposition='attachment; filename="download.bin"',
        fallback_title="Bluey S01E01",
        fallback_url="https://sdilej.cz/123/bluey-s01e01.mp4",
        job={
            "media_kind": "tv",
            "series_name": "Bluey",
            "season_number": 1,
            "episode_number": 1,
        },
    )

    assert filename == "Bluey - S01E01.mp4"
