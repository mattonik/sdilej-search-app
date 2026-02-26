from __future__ import annotations

import os
import re
import threading
import time
from pathlib import Path
from urllib.parse import unquote, urlparse

from .sdilej_client import SdilejClient, SdilejClientError
from .storage import Storage

DEFAULT_DOWNLOAD_DIR = "./downloads"

_FILENAME_RE = re.compile(r"filename\*=UTF-8''([^;]+)|filename=\"?([^\";]+)\"?")


class DownloadCanceledError(RuntimeError):
    pass


class DownloadWorker:
    def __init__(self, storage: Storage, poll_seconds: float = 2.0) -> None:
        self.storage = storage
        self.poll_seconds = poll_seconds
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._run_loop, name="download-worker", daemon=True)

    def start(self) -> None:
        if self._thread.is_alive():
            return
        self._thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        self._stop_event.set()
        if self._thread.is_alive():
            self._thread.join(timeout=timeout)

    def is_alive(self) -> bool:
        return self._thread.is_alive()

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            job = self.storage.claim_next_download_job()
            if not job:
                self._stop_event.wait(self.poll_seconds)
                continue

            self._process_job(job)

    def _process_job(self, job: dict) -> None:
        job_id = int(job["id"])
        detail_url = str(job["detail_url"])
        preferred_mode = str(job.get("preferred_mode") or "auto")

        client = SdilejClient(timeout_seconds=45)
        credentials = self.storage.get_account_credentials()

        if credentials:
            login_ok, login_msg = client.login(credentials[0], credentials[1])
            if not login_ok:
                if preferred_mode == "premium":
                    self.storage.fail_download_job(
                        job_id,
                        error=f"Premium login failed: {login_msg}",
                        final_url=None,
                        status_code=None,
                    )
                    return

        try:
            probe = client.probe_detail(detail_url=detail_url, run_preflight=False)
            target_url = self._pick_download_url(preferred_mode, probe.download_fast_url, probe.download_slow_url)
            if not target_url:
                raise SdilejClientError("No download URL found on detail page.")

            response = client.session.get(
                target_url,
                stream=True,
                allow_redirects=True,
                timeout=120,
            )
            status_code = response.status_code
            final_url = response.url

            content_type = (response.headers.get("Content-Type") or "").lower()
            if "text/html" in content_type:
                response.close()
                raise SdilejClientError(
                    "Download target returned HTML instead of file data. "
                    "This usually means auth/wait-page is still required."
                )

            total_header = response.headers.get("Content-Length")
            bytes_total = int(total_header) if total_header and total_header.isdigit() else None

            output_dir = self._resolve_output_dir(job.get("output_dir"))
            output_dir.mkdir(parents=True, exist_ok=True)

            filename = self._resolve_filename(
                content_disposition=response.headers.get("Content-Disposition"),
                fallback_title=probe.title,
                fallback_url=probe.detail_url,
            )
            final_path = self._resolve_unique_path(output_dir / filename)
            part_path = final_path.with_suffix(final_path.suffix + ".part")

            bytes_downloaded = 0
            started_at = time.time()
            last_progress_push = 0.0

            with open(part_path, "wb") as handle:
                for chunk in response.iter_content(chunk_size=1024 * 256):
                    if self._stop_event.is_set() or self.storage.is_job_canceled(job_id):
                        raise DownloadCanceledError("Job canceled.")

                    if not chunk:
                        continue
                    handle.write(chunk)
                    bytes_downloaded += len(chunk)

                    now = time.time()
                    if now - last_progress_push >= 1.0:
                        elapsed = max(now - started_at, 0.001)
                        speed = bytes_downloaded / elapsed
                        self.storage.update_download_progress(
                            job_id,
                            bytes_downloaded=bytes_downloaded,
                            bytes_total=bytes_total,
                            speed_bps=speed,
                            final_url=final_url,
                        )
                        last_progress_push = now

            response.close()
            os.replace(part_path, final_path)

            final_total = bytes_downloaded if bytes_total is None else bytes_total
            self.storage.complete_download_job(
                job_id,
                save_path=str(final_path),
                final_url=final_url,
                bytes_total=final_total,
                status_code=status_code,
            )

        except DownloadCanceledError as exc:
            try:
                if "part_path" in locals() and part_path.exists():
                    part_path.unlink()
            except OSError:
                pass
            self.storage.fail_download_job(
                job_id,
                error=str(exc),
                final_url=locals().get("final_url"),
                status_code=locals().get("status_code"),
            )
        except Exception as exc:  # noqa: BLE001
            try:
                if "part_path" in locals() and part_path.exists():
                    part_path.unlink()
            except OSError:
                pass
            self.storage.fail_download_job(
                job_id,
                error=str(exc),
                final_url=locals().get("final_url"),
                status_code=locals().get("status_code"),
            )

    def _pick_download_url(self, preferred_mode: str, fast_url: str | None, slow_url: str | None) -> str | None:
        if preferred_mode == "premium":
            if fast_url and not fast_url.rstrip("/").endswith("/cenik"):
                return fast_url
            return slow_url

        if preferred_mode == "free":
            return slow_url or fast_url

        # auto
        if fast_url and not fast_url.rstrip("/").endswith("/cenik"):
            return fast_url
        return slow_url or fast_url

    def _resolve_output_dir(self, configured_output_dir: str | None) -> Path:
        if configured_output_dir and configured_output_dir.strip():
            return Path(configured_output_dir).expanduser().resolve()
        env_dir = os.getenv("DOWNLOAD_DIR", DEFAULT_DOWNLOAD_DIR)
        return Path(env_dir).expanduser().resolve()

    def _resolve_filename(
        self,
        *,
        content_disposition: str | None,
        fallback_title: str | None,
        fallback_url: str,
    ) -> str:
        if content_disposition:
            match = _FILENAME_RE.search(content_disposition)
            if match:
                encoded = match.group(1)
                plain = match.group(2)
                value = unquote(encoded) if encoded else plain
                if value:
                    return self._sanitize_filename(value)

        if fallback_title:
            return self._sanitize_filename(fallback_title)

        path_name = Path(urlparse(fallback_url).path).name or "download.bin"
        return self._sanitize_filename(path_name)

    def _sanitize_filename(self, name: str) -> str:
        cleaned = re.sub(r"[\\/:*?\"<>|]+", "_", name).strip()
        cleaned = cleaned.replace("\n", " ").replace("\r", " ").strip(" .")
        return cleaned or "download.bin"

    def _resolve_unique_path(self, desired_path: Path) -> Path:
        if not desired_path.exists():
            return desired_path

        stem = desired_path.stem
        suffix = desired_path.suffix
        parent = desired_path.parent

        counter = 1
        while True:
            candidate = parent / f"{stem} ({counter}){suffix}"
            if not candidate.exists():
                return candidate
            counter += 1
