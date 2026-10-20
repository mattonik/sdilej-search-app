from __future__ import annotations

import os
from http.cookiejar import MozillaCookieJar
import shutil
import tempfile
import time
from pathlib import Path
from typing import Any, Callable


class YoutubeDownloadError(RuntimeError):
    pass


def validate_youtube_cookies(path: Path) -> None:
    jar = MozillaCookieJar(str(path))
    try:
        jar.load(ignore_discard=True, ignore_expires=True)
    except (OSError, ValueError) as exc:
        raise YoutubeDownloadError("Invalid cookies export. Use Netscape cookies.txt format.") from exc
    if not any(
        (cookie.domain.lstrip(".") == "youtube.com" or cookie.domain.endswith(".youtube.com"))
        and not cookie.is_expired(time.time())
        for cookie in jar
    ):
        raise YoutubeDownloadError("Cookies export contains no unexpired YouTube cookies. Export a fresh session.")


class YoutubeDownloader:
    def __init__(
        self,
        *,
        is_canceled: Callable[[], bool],
        on_progress: Callable[[dict[str, Any]], None],
    ) -> None:
        self.is_canceled = is_canceled
        self.on_progress = on_progress

    def download(
        self,
        url: str,
        *,
        output_template: str,
        auth: dict[str, Any] | None = None,
        media_kind: str | None = None,
        download_playlist: bool = False,
    ) -> dict[str, Any]:
        try:
            import yt_dlp
        except Exception as exc:  # noqa: BLE001
            raise YoutubeDownloadError("yt-dlp is not installed in this runtime.") from exc

        final_paths: list[str] = []

        def progress_hook(payload: dict[str, Any]) -> None:
            if self.is_canceled():
                raise YoutubeDownloadError("Job canceled. Partial file kept for resume.")
            self.on_progress(payload)

        def finished_hook(filename: str) -> None:
            final_paths.append(filename)

        options = {
            "format": "bestaudio/best" if str(media_kind or "").lower() == "music" else "bestvideo+bestaudio/best",
            "outtmpl": output_template,
            "noplaylist": not download_playlist,
            "quiet": True,
            "no_warnings": True,
            "progress_hooks": [progress_hook],
            "post_hooks": [finished_hook],
            "continuedl": True,
            "retries": 3,
            "fragment_retries": 3,
        }
        if str(media_kind or "").lower() == "music":
            options["postprocessors"] = [{"key": "FFmpegExtractAudio", "preferredcodec": "m4a"}]
        else:
            options["merge_output_format"] = "mp4"
        try:
            with tempfile.TemporaryDirectory(prefix="youtube-auth-") as cookie_dir:
                self._apply_auth_options(options, auth or {}, Path(cookie_dir))
                with yt_dlp.YoutubeDL(options) as ydl:
                    info = ydl.extract_info(url, download=True)
        except YoutubeDownloadError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise YoutubeDownloadError(self._format_download_error(exc)) from exc

        if not final_paths or not all(Path(path).is_file() for path in final_paths):
            raise YoutubeDownloadError("yt-dlp did not report an existing final media file.")
        return {
            "info": info or {},
            "filepath": final_paths[-1],
        }

    def probe(self, url: str, *, auth: dict[str, Any] | None = None) -> dict[str, Any]:
        try:
            import yt_dlp
        except Exception as exc:  # noqa: BLE001
            raise YoutubeDownloadError("yt-dlp is not installed in this runtime.") from exc

        options = {"quiet": True, "no_warnings": True, "noplaylist": True, "skip_download": True}
        try:
            with tempfile.TemporaryDirectory(prefix="youtube-auth-") as cookie_dir:
                self._apply_auth_options(options, auth or {}, Path(cookie_dir))
                with yt_dlp.YoutubeDL(options) as ydl:
                    return ydl.extract_info(url, download=False) or {}
        except Exception as exc:  # noqa: BLE001
            raise YoutubeDownloadError(self._format_download_error(exc)) from exc

    def _apply_auth_options(self, options: dict[str, Any], auth: dict[str, Any], cookie_dir: Path) -> None:
        mode = str(auth.get("mode") or "none")
        if mode == "cookies_file":
            cookies_path = str(auth.get("cookies_path") or "").strip()
            if not cookies_path:
                raise YoutubeDownloadError("No YouTube cookies file configured.")
            if cookies_path:
                path = Path(cookies_path).expanduser()
                if not path.is_file():
                    raise YoutubeDownloadError(f"Configured YouTube cookies file was not found: {path}")
                if not os.access(path, os.R_OK):
                    raise YoutubeDownloadError(f"Configured YouTube cookies file is not readable: {path}")
                private_path = cookie_dir / "cookies.txt"
                shutil.copyfile(path, private_path)
                private_path.chmod(0o600)
                validate_youtube_cookies(private_path)
                options["cookiefile"] = str(private_path)
        elif mode == "cookies_from_browser":
            browser = str(auth.get("cookies_from_browser") or "").strip()
            if browser:
                options["cookiesfrombrowser"] = self._parse_cookies_from_browser(browser)

    def _parse_cookies_from_browser(self, value: str) -> tuple[str, str | None, str | None, str | None]:
        browser_spec, _, container = value.strip().partition("::")
        browser_profile, _, profile = browser_spec.partition(":")
        browser, _, keyring = browser_profile.partition("+")
        browser = browser.strip() or "firefox"
        return (
            browser,
            profile.strip() or None,
            keyring.strip() or None,
            container.strip() or None,
        )

    def _format_download_error(self, exc: Exception) -> str:
        message = str(exc) or exc.__class__.__name__
        lower = message.lower()
        auth_markers = ("private", "sign in", "login", "cookies", "confirm your age", "not available")
        if any(marker in lower for marker in auth_markers):
            return (
                f"{message} Configure YouTube cookies in Account > YouTube authentication "
                "and retry the job."
            )
        if "ffmpeg" in lower:
            return f"{message} Install ffmpeg in the application runtime and retry the job."
        return message

