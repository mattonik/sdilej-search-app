from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import requests

from app.downloader import DownloadWorker, DownloadCanceledError


def enqueue(storage, tmp_path, mode="free"):
    storage.enqueue_download_job(
        detail_url="https://sdilej.cz/123/clip.mp4", file_id=123, title="Clip",
        preferred_mode=mode, output_dir=str(tmp_path), priority=0,
    )
    return storage.claim_next_download_job()


def fake_client(monkeypatch, response):
    client = Mock()
    client.probe_detail.return_value = SimpleNamespace(
        download_fast_url=None, download_slow_url="https://example.test/file",
        title="Clip", detail_url="https://sdilej.cz/123/clip.mp4",
    )
    client.session.get.return_value = response
    monkeypatch.setattr("app.downloader.SdilejClient", lambda **kw: client)
    return client


def test_login_timeout_fails_job_instead_of_escaping(storage, tmp_path, monkeypatch):
    job = enqueue(storage, tmp_path, "premium")
    storage.set_account_credentials("fixture", "fixture")
    client = fake_client(monkeypatch, None)
    client.login.side_effect = requests.Timeout("login timed out")
    DownloadWorker(storage)._process_job(job)
    result = storage.get_download_job(job["id"])
    assert result["status"] == "failed"
    assert "login timed out" in result["error"]
    client.session.close.assert_called_once()


@pytest.mark.parametrize("resume", [False, True])
def test_http_error_does_not_create_finished_media(storage, tmp_path, monkeypatch, resume):
    job = enqueue(storage, tmp_path)
    error = Mock(status_code=503, url="https://example.test/file", headers={"Content-Type": "text/plain"})
    error.raise_for_status.side_effect = requests.HTTPError("503 unavailable")
    client = fake_client(monkeypatch, error)
    if resume:
        partial = tmp_path / "Clip.mp4.part"
        partial.write_bytes(b"partial")
        job["working_path"] = str(partial)
        initial = Mock(status_code=200, url=error.url, headers={"Accept-Ranges": "bytes", "Content-Length": "100"})
        client.session.get.side_effect = [initial, error]
    DownloadWorker(storage)._process_job(job)
    result = storage.get_download_job(job["id"])
    assert result["status"] == "failed"
    assert result["save_path"] is None
    assert not (tmp_path / "Clip.mp4").exists()
    error.iter_content.assert_not_called()
    if resume:
        assert partial.read_bytes() == b"partial"


def test_worker_survives_claim_failure(storage, monkeypatch):
    worker = DownloadWorker(storage, poll_seconds=0)
    calls = []
    def claim():
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("temporary database failure")
        worker._stop_event.set()
    monkeypatch.setattr(storage, "claim_next_download_job", claim)
    worker._run_loop(0)
    assert len(calls) == 2


def test_bandwidth_limit_smaller_than_chunk_completes(storage, monkeypatch):
    clock = [0.0]
    monkeypatch.setattr("app.downloader.time.monotonic", lambda: clock[0])
    worker = DownloadWorker(storage)
    worker.configure(bandwidth_limit_kbps=100)
    def advance(seconds):
        clock[0] += seconds
        assert clock[0] < 10, "throttle stalled"
    monkeypatch.setattr(worker._stop_event, "wait", advance)
    worker._throttle(256 * 1024)
    assert 1.5 <= clock[0] <= 2.0


def test_throttle_observes_cancel_and_changed_limit(storage, monkeypatch):
    worker = DownloadWorker(storage)
    worker.configure(bandwidth_limit_kbps=1)
    monkeypatch.setattr(worker._stop_event, "wait", lambda _: worker.configure(bandwidth_limit_kbps=0))
    worker._throttle(256 * 1024)
    worker._stop_event.set()
    with pytest.raises(DownloadCanceledError):
        worker._throttle(256 * 1024)
