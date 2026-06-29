from __future__ import annotations

import sys
import types
from pathlib import Path

from app.youtube_downloader import YoutubeDownloader


class FakeYoutubeDL:
    captured_options: dict | None = None

    def __init__(self, options: dict) -> None:
        FakeYoutubeDL.captured_options = options

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:  # noqa: ANN001
        return None

    def extract_info(self, url: str, *, download: bool) -> dict:
        output_template = FakeYoutubeDL.captured_options["outtmpl"]
        final_path = Path(output_template.replace("%(ext)s", "mp4"))
        final_path.parent.mkdir(parents=True, exist_ok=True)
        final_path.write_bytes(b"video")
        for hook in FakeYoutubeDL.captured_options.get("progress_hooks", []):
            hook({"status": "finished", "filename": str(final_path), "downloaded_bytes": 5, "total_bytes": 5})
        return {"id": "abc123", "webpage_url": url, "download": download}


def install_fake_ytdlp(monkeypatch) -> None:  # noqa: ANN001
    fake_module = types.SimpleNamespace(YoutubeDL=FakeYoutubeDL)
    monkeypatch.setitem(sys.modules, "yt_dlp", fake_module)
    FakeYoutubeDL.captured_options = None


def test_youtube_downloader_applies_cookies_file_option(tmp_path, monkeypatch) -> None:
    install_fake_ytdlp(monkeypatch)
    cookies_path = tmp_path / "cookies.txt"
    cookies_path.write_text("cookies", encoding="utf-8")
    downloader = YoutubeDownloader(is_canceled=lambda: False, on_progress=lambda payload: None)

    result = downloader.download(
        "https://www.youtube.com/watch?v=abc123",
        output_template=str(tmp_path / "video.%(ext)s"),
        auth={"mode": "cookies_file", "cookies_path": str(cookies_path)},
    )

    assert result["filepath"].endswith("video.mp4")
    assert FakeYoutubeDL.captured_options["cookiefile"] == str(cookies_path)


def test_youtube_downloader_applies_browser_cookies_option(tmp_path, monkeypatch) -> None:
    install_fake_ytdlp(monkeypatch)
    downloader = YoutubeDownloader(is_canceled=lambda: False, on_progress=lambda payload: None)

    downloader.download(
        "https://www.youtube.com/watch?v=abc123",
        output_template=str(tmp_path / "video.%(ext)s"),
        auth={"mode": "cookies_from_browser", "cookies_from_browser": "chrome:Profile 1"},
    )

    assert FakeYoutubeDL.captured_options["cookiesfrombrowser"] == ("chrome", "Profile 1", None, None)


def test_youtube_downloader_parses_browser_keyring_and_container(tmp_path, monkeypatch) -> None:
    install_fake_ytdlp(monkeypatch)
    downloader = YoutubeDownloader(is_canceled=lambda: False, on_progress=lambda payload: None)

    downloader.download(
        "https://www.youtube.com/watch?v=abc123",
        output_template=str(tmp_path / "video.%(ext)s"),
        auth={"mode": "cookies_from_browser", "cookies_from_browser": "firefox+kwallet:default::youtube"},
    )

    assert FakeYoutubeDL.captured_options["cookiesfrombrowser"] == ("firefox", "default", "kwallet", "youtube")
