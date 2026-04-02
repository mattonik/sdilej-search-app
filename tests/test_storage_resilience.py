from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import sqlite3
import threading

from app.db import run_with_sqlite_retry


def test_storage_connections_enable_pragmas_and_indexes(storage) -> None:
    with storage._connect() as conn:
        journal_mode = str(conn.execute("PRAGMA journal_mode").fetchone()[0]).lower()
        foreign_keys = int(conn.execute("PRAGMA foreign_keys").fetchone()[0])
        busy_timeout = int(conn.execute("PRAGMA busy_timeout").fetchone()[0])
        index_names = {
            row["name"]
            for row in conn.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'index'
                """
            ).fetchall()
        }

    assert journal_mode == "wal"
    assert foreign_keys == 1
    assert busy_timeout >= 1000
    assert "idx_download_jobs_status_priority_id" in index_names
    assert "idx_tv_search_jobs_status_priority_id" in index_names
    assert "idx_title_metadata_cache_lookup_updated_at" in index_names


def test_run_with_sqlite_retry_retries_transient_lock_errors() -> None:
    attempts: list[int] = []

    def operation() -> str:
        attempts.append(1)
        if len(attempts) < 3:
            raise sqlite3.OperationalError("database is locked")
        return "ok"

    result = run_with_sqlite_retry(operation, attempts=4, delay_seconds=0)

    assert result == "ok"
    assert len(attempts) == 3


def test_claim_next_download_job_is_safe_under_contention(storage) -> None:
    for idx in range(2):
        storage.enqueue_download_job(
            detail_url=f"https://sdilej.cz/{idx + 1}/job-{idx + 1}.mkv",
            file_id=idx + 1,
            title=f"Job {idx + 1}",
            preferred_mode="auto",
            output_dir="/downloads",
            priority=0,
        )

    barrier = threading.Barrier(3)

    def claim_once() -> int | None:
        barrier.wait()
        job = storage.claim_next_download_job()
        return None if job is None else int(job["id"])

    with ThreadPoolExecutor(max_workers=3) as executor:
        claimed_ids = [job_id for job_id in executor.map(lambda _: claim_once(), range(3)) if job_id is not None]

    assert len(claimed_ids) == 2
    assert len(set(claimed_ids)) == 2


def test_claim_next_tv_search_job_is_safe_under_contention(storage) -> None:
    show = {"id": 321, "name": "Bluey"}
    episodes = [
        {
            "season_number": 1,
            "episode_number": 1,
            "episode_name": "Magic Xylophone",
            "airdate": "2018-10-01",
            "episode_code": "S01E01",
            "status": "pending",
        }
    ]
    for idx in range(2):
        storage.enqueue_tv_search_job(
            show=show,
            title_metadata=None,
            aliases=["Bluey"],
            search_aliases=["Bluey"],
            selected_seasons=[1],
            episodes_by_season={"1": [1]},
            category="video",
            language=None,
            language_scope="any",
            strict_dubbing=False,
            max_results_per_variant=20,
            episodes=episodes,
            priority=idx,
        )

    barrier = threading.Barrier(3)

    def claim_once() -> int | None:
        barrier.wait()
        job = storage.claim_next_tv_search_job()
        return None if job is None else int(job["id"])

    with ThreadPoolExecutor(max_workers=3) as executor:
        claimed_ids = [job_id for job_id in executor.map(lambda _: claim_once(), range(3)) if job_id is not None]

    assert len(claimed_ids) == 2
    assert len(set(claimed_ids)) == 2
