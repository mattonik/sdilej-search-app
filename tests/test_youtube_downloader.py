from __future__ import annotations

import sys
import types
from pathlib import Path
import pytest

from app.youtube_downloader import YoutubeDownloader

COOKIES = "# Netscape HTTP Cookie File\n.youtube.com\tTRUE\t/\tTRUE\t2000000000\tSID\tfixture\n"


class FakeYoutubeDL:
    captured_options: dict | None = None

    def __init__(self, options: dict) -> None:
        FakeYoutubeDL.captured_options = options

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:  # noqa: ANN001
        return None

    def extract_info(self, url: str, *, download: bool) -> dict:
        if not download:
            return {"id": "abc123", "title": "Probe clip", "webpage_url": url}
        output_template = FakeYoutubeDL.captured_options["outtmpl"]
        final_path = Path(output_template.replace("%(ext)s", "mp4"))
        final_path.parent.mkdir(parents=True, exist_ok=True)
        final_path.write_bytes(b"video")
        for hook in FakeYoutubeDL.captured_options.get("progress_hooks", []):
            hook({"status": "finished", "filename": str(final_path), "downloaded_bytes": 5, "total_bytes": 5})
        for hook in FakeYoutubeDL.captured_options.get("post_hooks", []):
            hook(str(final_path))
        return {"id": "abc123", "webpage_url": url, "download": download}


def install_fake_ytdlp(monkeypatch) -> None:  # noqa: ANN001
    fake_module = types.SimpleNamespace(YoutubeDL=FakeYoutubeDL)
    monkeypatch.setitem(sys.modules, "yt_dlp", fake_module)
    FakeYoutubeDL.captured_options = None


def test_youtube_downloader_applies_cookies_file_option(tmp_path, monkeypatch) -> None:
    install_fake_ytdlp(monkeypatch)
    cookies_path = tmp_path / "cookies.txt"
    cookies_path.write_text(COOKIES, encoding="utf-8")
    downloader = YoutubeDownloader(is_canceled=lambda: False, on_progress=lambda payload: None)

    result = downloader.download(
        "https://www.youtube.com/watch?v=abc123",
        output_template=str(tmp_path / "video.%(ext)s"),
        auth={"mode": "cookies_file", "cookies_path": str(cookies_path)},
    )

    assert result["filepath"].endswith("video.mp4")
    assert FakeYoutubeDL.captured_options["cookiefile"] != str(cookies_path)
    assert not Path(FakeYoutubeDL.captured_options["cookiefile"]).exists()
    assert cookies_path.read_text() == COOKIES


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


def test_youtube_downloader_uses_audio_mode_for_music(tmp_path, monkeypatch) -> None:
    install_fake_ytdlp(monkeypatch)
    downloader = YoutubeDownloader(is_canceled=lambda: False, on_progress=lambda payload: None)

    downloader.download(
        "https://www.youtube.com/watch?v=abc123",
        output_template=str(tmp_path / "music.%(ext)s"),
        media_kind="music",
    )

    assert FakeYoutubeDL.captured_options["format"] == "bestaudio/best"
    assert FakeYoutubeDL.captured_options["postprocessors"][0]["key"] == "FFmpegExtractAudio"


def test_youtube_downloader_allows_full_playlist(tmp_path, monkeypatch) -> None:
    install_fake_ytdlp(monkeypatch)
    downloader = YoutubeDownloader(is_canceled=lambda: False, on_progress=lambda payload: None)

    downloader.download(
        "https://www.youtube.com/playlist?list=abc123",
        output_template=str(tmp_path / "playlist.%(ext)s"),
        download_playlist=True,
    )

    assert FakeYoutubeDL.captured_options["noplaylist"] is False


def test_youtube_downloader_probe_does_not_download(tmp_path, monkeypatch) -> None:
    install_fake_ytdlp(monkeypatch)
    downloader = YoutubeDownloader(is_canceled=lambda: False, on_progress=lambda payload: None)

    result = downloader.probe("https://www.youtube.com/watch?v=abc123")

    assert result["title"] == "Probe clip"
    assert "outtmpl" not in FakeYoutubeDL.captured_options


def test_youtube_downloader_rejects_missing_cookie_file(tmp_path, monkeypatch) -> None:
    install_fake_ytdlp(monkeypatch)
    downloader = YoutubeDownloader(is_canceled=lambda: False, on_progress=lambda payload: None)

    try:
        downloader.probe(
            "https://www.youtube.com/watch?v=abc123",
            auth={"mode": "cookies_file", "cookies_path": str(tmp_path / "missing.txt")},
        )
    except Exception as exc:  # noqa: BLE001
        assert "was not found" in str(exc)
    else:
        raise AssertionError("missing cookies file should fail before yt-dlp is called")


@pytest.mark.parametrize("probe_only", [True, False])
def test_youtube_operation_cannot_overwrite_new_cookie_export(tmp_path, monkeypatch, probe_only):
    import yt_dlp
    original = tmp_path / "cookies.txt"
    original.write_text(COOKIES)
    fresh = COOKIES.replace("fixture", "fresh-fixture")

    def extract(ydl, url, *, download):
        assert list(ydl.cookiejar)[0].value == "fixture"
        original.write_text(fresh)
        if download:
            final = tmp_path / "merged.mp4"
            final.write_bytes(b"media")
            for hook in ydl.params["post_hooks"]:
                hook(str(final))
        return {"title": "Fixture"}

    monkeypatch.setattr(yt_dlp.YoutubeDL, "extract_info", extract)
    worker = YoutubeDownloader(is_canceled=lambda: False, on_progress=lambda _: None)
    auth = {"mode": "cookies_file", "cookies_path": str(original)}
    if probe_only:
        worker.probe("https://youtube.com/watch?v=fixture", auth=auth)
    else:
        worker.download("https://youtube.com/watch?v=fixture", auth=auth, output_template=str(tmp_path / "%(title)s.%(ext)s"))
    assert original.read_text() == fresh


@pytest.mark.parametrize("suffix", ["mp4", "m4a"])
def test_youtube_uses_final_postprocessed_path(tmp_path, monkeypatch, suffix):
    install_fake_ytdlp(monkeypatch)
    final = tmp_path / f"Clip [abc].{suffix}"
    def extract(self, url, *, download):
        intermediate = tmp_path / "Clip [abc].f140.webm"
        intermediate.write_bytes(b"audio")
        for hook in self.captured_options["progress_hooks"]:
            hook({"filename": str(intermediate), "status": "finished"})
        intermediate.unlink()
        final.write_bytes(b"merged media")
        for hook in self.captured_options["post_hooks"]:
            hook(str(final))
        return {}
    monkeypatch.setattr(FakeYoutubeDL, "extract_info", extract)
    result = YoutubeDownloader(is_canceled=lambda: False, on_progress=lambda _: None).download(
        "https://youtube.com/watch?v=abc", output_template=str(tmp_path / "%(title).200B [%(id)s].%(ext)s"))
    assert result["filepath"] == str(final)


def test_youtube_rejects_missing_final_file(tmp_path, monkeypatch):
    install_fake_ytdlp(monkeypatch)
    monkeypatch.setattr(FakeYoutubeDL, "extract_info", lambda *a, **kw: {})
    with pytest.raises(RuntimeError, match="existing final media file"):
        YoutubeDownloader(is_canceled=lambda: False, on_progress=lambda _: None).download(
            "https://youtube.com/watch?v=abc", output_template=str(tmp_path / "video.%(ext)s"))
