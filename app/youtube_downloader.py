from __future__ import annotations

from pathlib import Path
from typing import Any, Callable


class YoutubeDownloadError(RuntimeError):
    pass


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
    ) -> dict[str, Any]:
        try:
            import yt_dlp
        except Exception as exc:  # noqa: BLE001
            raise YoutubeDownloadError("yt-dlp is not installed in this runtime.") from exc

        last_filename: str | None = None

        def progress_hook(payload: dict[str, Any]) -> None:
            nonlocal last_filename
            if self.is_canceled():
                raise YoutubeDownloadError("Job canceled. Partial file kept for resume.")
            filename = payload.get("filename") or payload.get("tmpfilename")
            if filename:
                last_filename = str(filename)
            self.on_progress(payload)

        options = {
            "format": "bestaudio/best" if str(media_kind or "").lower() == "music" else "bestvideo+bestaudio/best",
            "outtmpl": output_template,
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "progress_hooks": [progress_hook],
            "continuedl": True,
            "retries": 3,
            "fragment_retries": 3,
        }
        if str(media_kind or "").lower() == "music":
            options["postprocessors"] = [{"key": "FFmpegExtractAudio", "preferredcodec": "m4a"}]
        else:
            options["merge_output_format"] = "mp4"
        self._apply_auth_options(options, auth or {})

        try:
            with yt_dlp.YoutubeDL(options) as ydl:
                info = ydl.extract_info(url, download=True)
        except YoutubeDownloadError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise YoutubeDownloadError(self._format_download_error(exc)) from exc

        final_path = self._resolve_final_path(output_template, last_filename)
        return {
            "info": info or {},
            "filepath": str(final_path) if final_path else last_filename,
        }

    def probe(self, url: str, *, auth: dict[str, Any] | None = None) -> dict[str, Any]:
        try:
            import yt_dlp
        except Exception as exc:  # noqa: BLE001
            raise YoutubeDownloadError("yt-dlp is not installed in this runtime.") from exc

        options = {"quiet": True, "no_warnings": True, "noplaylist": True, "skip_download": True}
        self._apply_auth_options(options, auth or {})
        try:
            with yt_dlp.YoutubeDL(options) as ydl:
                return ydl.extract_info(url, download=False) or {}
        except Exception as exc:  # noqa: BLE001
            raise YoutubeDownloadError(self._format_download_error(exc)) from exc

    def _apply_auth_options(self, options: dict[str, Any], auth: dict[str, Any]) -> None:
        mode = str(auth.get("mode") or "none")
        if mode == "cookies_file":
            cookies_path = str(auth.get("cookies_path") or "").strip()
            if cookies_path:
                options["cookiefile"] = cookies_path
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
        return message

    def _resolve_final_path(self, output_template: str, last_filename: str | None) -> Path | None:
        if last_filename:
            candidate = Path(last_filename)
            if candidate.exists() and not candidate.name.endswith(".part"):
                return candidate

        template = Path(output_template)
        parent = template.parent
        pattern = template.name.replace("%(ext)s", "*")
        matches = [
            item
            for item in parent.glob(pattern)
            if item.is_file() and not item.name.endswith((".part", ".ytdl"))
        ]
        if not matches:
            return None
        return max(matches, key=lambda item: item.stat().st_mtime)
