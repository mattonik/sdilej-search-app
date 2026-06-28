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

    def download(self, url: str, *, output_template: str) -> dict[str, Any]:
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
            "format": "bestvideo+bestaudio/best",
            "merge_output_format": "mp4",
            "outtmpl": output_template,
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "progress_hooks": [progress_hook],
            "continuedl": True,
            "retries": 3,
            "fragment_retries": 3,
        }

        with yt_dlp.YoutubeDL(options) as ydl:
            info = ydl.extract_info(url, download=True)

        final_path = self._resolve_final_path(output_template, last_filename)
        return {
            "info": info or {},
            "filepath": str(final_path) if final_path else last_filename,
        }

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
