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
DOWNLOAD_TIMEOUT_SECONDS = 120
DOWNLOAD_CHUNK_SIZE = 1024 * 256
MAX_WORKER_THREADS = 8

_FILENAME_RE = re.compile(r"filename\*=UTF-8''([^;]+)|filename=\"?([^\";]+)\"?")
_CONTENT_RANGE_TOTAL_RE = re.compile(r"^bytes\s+\d+-\d+/(\d+)$", re.IGNORECASE)


class DownloadCanceledError(RuntimeError):
    pass


class DownloadWorker:
    def __init__(self, storage: Storage, poll_seconds: float = 2.0) -> None:
        self.storage = storage
        self.poll_seconds = poll_seconds
        self._stop_event = threading.Event()
        self._threads: list[threading.Thread] = []
        self._config_lock = threading.Lock()
        self._throttle_lock = threading.Lock()

        self.max_concurrent_jobs = 1
        self.default_chunk_count = 1
        self.bandwidth_limit_kbps = 0
        self._throttle_tokens = 0.0
        self._throttle_last_refill = time.monotonic()

    def configure(
        self,
        *,
        max_concurrent_jobs: int | None = None,
        default_chunk_count: int | None = None,
        bandwidth_limit_kbps: int | None = None,
    ) -> None:
        with self._config_lock:
            if max_concurrent_jobs is not None:
                self.max_concurrent_jobs = max(1, min(int(max_concurrent_jobs), MAX_WORKER_THREADS))
            if default_chunk_count is not None:
                self.default_chunk_count = max(1, min(int(default_chunk_count), 8))
            if bandwidth_limit_kbps is not None:
                self.bandwidth_limit_kbps = max(0, int(bandwidth_limit_kbps))

        with self._throttle_lock:
            limit_bps = self._current_bandwidth_limit_bps()
            self._throttle_last_refill = time.monotonic()
            self._throttle_tokens = float(limit_bps) if limit_bps > 0 else 0.0

    def start(self) -> None:
        if any(thread.is_alive() for thread in self._threads):
            return
        self._stop_event.clear()
        self._threads = [
            threading.Thread(target=self._run_loop, args=(idx,), name=f"download-worker-{idx}", daemon=True)
            for idx in range(MAX_WORKER_THREADS)
        ]
        for thread in self._threads:
            thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        self._stop_event.set()
        for thread in self._threads:
            if thread.is_alive():
                thread.join(timeout=timeout)

    def is_alive(self) -> bool:
        return any(thread.is_alive() for thread in self._threads)

    def _run_loop(self, worker_index: int) -> None:
        while not self._stop_event.is_set():
            with self._config_lock:
                max_concurrent = self.max_concurrent_jobs
            if worker_index >= max_concurrent:
                self._stop_event.wait(self.poll_seconds)
                continue

            job = self.storage.claim_next_download_job()
            if not job:
                self._stop_event.wait(self.poll_seconds)
                continue

            self._process_job(job)

    def _process_job(self, job: dict) -> None:
        job_id = int(job["id"])
        detail_url = str(job["detail_url"])
        preferred_mode = str(job.get("preferred_mode") or "auto")
        with self._config_lock:
            default_chunk_count = self.default_chunk_count
        configured_chunk_count = int(job.get("chunk_count") or default_chunk_count or 1)
        effective_chunk_count = max(1, min(configured_chunk_count, 8))
        io_chunk_size = DOWNLOAD_CHUNK_SIZE * effective_chunk_count

        credentials = self.storage.get_account_credentials()
        if preferred_mode == "premium" and not credentials:
            self.storage.fail_download_job(
                job_id,
                error="Premium mode requested but no account credentials are configured.",
                final_url=None,
                status_code=None,
            )
            return

        client = SdilejClient(timeout_seconds=45)
        login_message = None

        if credentials:
            login_ok, login_msg = client.login(credentials[0], credentials[1])
            login_message = login_msg
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
                if preferred_mode == "premium":
                    raise SdilejClientError("Premium direct link is not available for this file.")
                raise SdilejClientError("No download URL found on detail page.")

            response = client.session.get(
                target_url,
                stream=True,
                allow_redirects=True,
                timeout=DOWNLOAD_TIMEOUT_SECONDS,
            )
            status_code = response.status_code
            final_url = response.url

            if self._is_html_response(response):
                response.close()
                # Session/link refresh path for premium-capable modes.
                if credentials and preferred_mode != "free":
                    login_ok, login_msg = client.login(credentials[0], credentials[1])
                    login_message = login_msg
                    if not login_ok and preferred_mode == "premium":
                        raise SdilejClientError(f"Premium login refresh failed: {login_msg}")

                    probe = client.probe_detail(detail_url=detail_url, run_preflight=False)
                    target_url = self._pick_download_url(preferred_mode, probe.download_fast_url, probe.download_slow_url)
                    if not target_url:
                        if preferred_mode == "premium":
                            raise SdilejClientError("Premium direct link is not available after login refresh.")
                        raise SdilejClientError("No download URL found on detail page after refresh.")

                    response = client.session.get(
                        target_url,
                        stream=True,
                        allow_redirects=True,
                        timeout=DOWNLOAD_TIMEOUT_SECONDS,
                    )
                    status_code = response.status_code
                    final_url = response.url

            if self._is_html_response(response):
                response.close()
                hint = (
                    "Download target returned HTML instead of file data. "
                    "The premium session/link may be invalid or temporarily blocked."
                )
                if login_message:
                    hint = f"{hint} Login: {login_message}"
                raise SdilejClientError(hint)

            output_dir = self._resolve_output_dir(job.get("output_dir"))
            output_dir.mkdir(parents=True, exist_ok=True)

            filename = self._resolve_filename(
                content_disposition=response.headers.get("Content-Disposition"),
                fallback_title=probe.title,
                fallback_url=probe.detail_url,
                job=job,
            )
            working_path = str(job.get("working_path") or "").strip()
            if working_path:
                part_path = Path(working_path).expanduser()
                final_path = part_path.with_suffix("")
            else:
                final_path = self._resolve_unique_path(output_dir / filename)
                part_path = final_path.with_suffix(final_path.suffix + ".part")
            self.storage.set_download_working_path(job_id, str(part_path))

            bytes_total = self._parse_content_length(response.headers.get("Content-Length"))
            bytes_downloaded = 0
            append_mode = "wb"

            existing_size = part_path.stat().st_size if part_path.exists() else 0
            if existing_size > 0:
                if bytes_total is not None and existing_size >= bytes_total:
                    response.close()
                    os.replace(part_path, final_path)
                    self.storage.complete_download_job(
                        job_id,
                        save_path=str(final_path),
                        final_url=final_url,
                        bytes_total=existing_size,
                        status_code=status_code,
                    )
                    self._run_post_complete_actions(job_id)
                    return

                if self._supports_resume(response):
                    response.close()
                    response = client.session.get(
                        target_url,
                        headers={"Range": f"bytes={existing_size}-"},
                        stream=True,
                        allow_redirects=True,
                        timeout=DOWNLOAD_TIMEOUT_SECONDS,
                    )
                    status_code = response.status_code
                    final_url = response.url

                    if self._is_html_response(response):
                        response.close()
                        raise SdilejClientError("Resume request returned HTML; premium link is no longer valid.")

                    if response.status_code == 206:
                        append_mode = "ab"
                        bytes_downloaded = existing_size
                        total_from_range = self._extract_total_from_content_range(response.headers.get("Content-Range"))
                        if total_from_range is not None:
                            bytes_total = total_from_range
                        elif bytes_total is None:
                            remaining = self._parse_content_length(response.headers.get("Content-Length"))
                            if remaining is not None:
                                bytes_total = existing_size + remaining
                    else:
                        if part_path.exists():
                            part_path.unlink()
                        bytes_total = self._parse_content_length(response.headers.get("Content-Length"))
                        bytes_downloaded = 0
                        append_mode = "wb"
                else:
                    response.close()
                    if part_path.exists():
                        part_path.unlink()
                    response = client.session.get(
                        target_url,
                        stream=True,
                        allow_redirects=True,
                        timeout=DOWNLOAD_TIMEOUT_SECONDS,
                    )
                    status_code = response.status_code
                    final_url = response.url
                    if self._is_html_response(response):
                        response.close()
                        raise SdilejClientError("Restart download request returned HTML instead of file data.")
                    bytes_total = self._parse_content_length(response.headers.get("Content-Length"))
                    bytes_downloaded = 0
                    append_mode = "wb"

            started_at = time.time()
            base_downloaded = bytes_downloaded
            last_progress_push = 0.0

            with open(part_path, append_mode) as handle:
                for chunk in response.iter_content(chunk_size=io_chunk_size):
                    if self._stop_event.is_set() or self.storage.is_job_canceled(job_id):
                        raise DownloadCanceledError("Job canceled. Partial file kept for resume.")

                    if not chunk:
                        continue
                    self._throttle(len(chunk))
                    handle.write(chunk)
                    bytes_downloaded += len(chunk)

                    now = time.time()
                    if now - last_progress_push >= 1.0:
                        elapsed = max(now - started_at, 0.001)
                        speed = max(bytes_downloaded - base_downloaded, 0) / elapsed
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

            final_total = bytes_downloaded if bytes_total is None else max(bytes_total, bytes_downloaded)
            self.storage.complete_download_job(
                job_id,
                save_path=str(final_path),
                final_url=final_url,
                bytes_total=final_total,
                status_code=status_code,
            )
            self._run_post_complete_actions(job_id)

        except DownloadCanceledError as exc:
            clear_working_path = False
            if self.storage.should_delete_partial_on_cancel(job_id):
                if "part_path" in locals() and part_path.exists():
                    try:
                        part_path.unlink()
                    except OSError:
                        pass
                clear_working_path = True
                error_text = "Job canceled completely; partial data removed."
            else:
                error_text = str(exc)

            self.storage.fail_download_job(
                job_id,
                error=error_text,
                final_url=locals().get("final_url"),
                status_code=locals().get("status_code"),
                clear_working_path=clear_working_path,
            )
        except Exception as exc:  # noqa: BLE001
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
            return None

        if preferred_mode == "free":
            return slow_url or fast_url

        # auto
        if fast_url and not fast_url.rstrip("/").endswith("/cenik"):
            return fast_url
        return slow_url or fast_url

    def _run_post_complete_actions(self, job_id: int) -> None:
        job = self.storage.get_download_job(job_id)
        if not job:
            return
        if not job.get("delete_saved_on_complete"):
            return
        source_saved_file_id = job.get("source_saved_file_id")
        if source_saved_file_id is None:
            return
        self.storage.delete_saved_candidate(int(source_saved_file_id))

    def _current_bandwidth_limit_bps(self) -> int:
        return int(self.bandwidth_limit_kbps * 1024)

    def _throttle(self, byte_count: int) -> None:
        if byte_count <= 0:
            return
        limit_bps = self._current_bandwidth_limit_bps()
        if limit_bps <= 0:
            return

        while not self._stop_event.is_set():
            with self._throttle_lock:
                now = time.monotonic()
                elapsed = max(0.0, now - self._throttle_last_refill)
                if elapsed > 0:
                    burst_cap = float(limit_bps)
                    self._throttle_tokens = min(burst_cap, self._throttle_tokens + elapsed * limit_bps)
                    self._throttle_last_refill = now

                if self._throttle_tokens >= byte_count:
                    self._throttle_tokens -= byte_count
                    return

                deficit = byte_count - self._throttle_tokens

            sleep_seconds = max(deficit / limit_bps, 0.002)
            time.sleep(min(sleep_seconds, 0.2))

    def _is_html_response(self, response) -> bool:
        content_type = (response.headers.get("Content-Type") or "").lower()
        return "text/html" in content_type

    def _parse_content_length(self, value: str | None) -> int | None:
        if not value:
            return None
        if not value.isdigit():
            return None
        return int(value)

    def _supports_resume(self, response) -> bool:
        accept_ranges = (response.headers.get("Accept-Ranges") or "").lower()
        return "bytes" in accept_ranges

    def _extract_total_from_content_range(self, value: str | None) -> int | None:
        if not value:
            return None
        match = _CONTENT_RANGE_TOTAL_RE.match(value.strip())
        if not match:
            return None
        return int(match.group(1))

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
        job: dict | None = None,
    ) -> str:
        raw_filename: str
        if content_disposition:
            match = _FILENAME_RE.search(content_disposition)
            if match:
                encoded = match.group(1)
                plain = match.group(2)
                value = unquote(encoded) if encoded else plain
                if value:
                    raw_filename = self._sanitize_filename(value)
                    return self._normalize_tv_filename(raw_filename, fallback_title=fallback_title, job=job)

        if fallback_title:
            raw_filename = self._sanitize_filename(fallback_title)
            return self._normalize_tv_filename(raw_filename, fallback_title=fallback_title, job=job)

        path_name = Path(urlparse(fallback_url).path).name or "download.bin"
        raw_filename = self._sanitize_filename(path_name)
        return self._normalize_tv_filename(raw_filename, fallback_title=fallback_title, job=job)

    def _normalize_tv_filename(self, raw_filename: str, *, fallback_title: str | None, job: dict | None) -> str:
        if not job:
            return raw_filename

        media_kind = str(job.get("media_kind") or "").lower().strip()
        if media_kind != "tv":
            return raw_filename

        series_name = str(job.get("series_name") or "").strip()
        if not series_name:
            return raw_filename

        season_raw = job.get("season_number")
        episode_raw = job.get("episode_number")
        try:
            season_number = int(season_raw) if season_raw is not None else None
        except (TypeError, ValueError):
            season_number = None
        try:
            episode_number = int(episode_raw) if episode_raw is not None else None
        except (TypeError, ValueError):
            episode_number = None

        if season_number is None or season_number < 1:
            return raw_filename

        ext = Path(raw_filename).suffix
        if not ext and fallback_title:
            ext = Path(self._sanitize_filename(fallback_title)).suffix
        if not ext:
            ext = ".bin"

        safe_series = self._sanitize_filename(series_name)
        if episode_number is not None and episode_number > 0:
            normalized = f"{safe_series} - S{season_number:02d}E{episode_number:02d}{ext}"
        else:
            normalized = f"{safe_series} - S{season_number:02d}{ext}"
        return self._sanitize_filename(normalized)

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
