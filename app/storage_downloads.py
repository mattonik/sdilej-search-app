from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any


class StorageDownloadsRepository:
    def __init__(self, storage: "Storage") -> None:
        self.storage = storage

    def enqueue_download_job(
        self,
        *,
        detail_url: str,
        file_id: int | None,
        title: str | None,
        preferred_mode: str,
        output_dir: str | None,
        priority: int,
        source_type: str = "sdilej",
        source_metadata: dict[str, Any] | None = None,
        chunk_count: int | None = None,
        media_kind: str | None = None,
        is_kids: bool = False,
        series_name: str | None = None,
        season_number: int | None = None,
        episode_number: int | None = None,
        destination_subpath: str | None = None,
        source_saved_file_id: int | None = None,
        delete_saved_on_complete: bool = False,
    ) -> dict[str, Any]:
        job_id = 0

        def operation() -> None:
            nonlocal job_id
            with self.storage._connect() as conn:
                cursor = conn.execute(
                    """
                    INSERT INTO download_jobs (
                        file_id,
                        title,
                        detail_url,
                        source_type,
                        source_metadata_json,
                        preferred_mode,
                        output_dir,
                        priority,
                        chunk_count,
                        media_kind,
                        is_kids,
                        series_name,
                        season_number,
                        episode_number,
                        destination_subpath,
                        source_saved_file_id,
                        delete_saved_on_complete,
                        status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'queued')
                    """,
                    (
                        file_id,
                        title,
                        detail_url,
                        source_type,
                        json.dumps(source_metadata or {}, ensure_ascii=False),
                        preferred_mode,
                        output_dir,
                        priority,
                        chunk_count,
                        media_kind,
                        1 if is_kids else 0,
                        series_name,
                        season_number,
                        episode_number,
                        destination_subpath,
                        source_saved_file_id,
                        1 if delete_saved_on_complete else 0,
                    ),
                )
                job_id = int(cursor.lastrowid)

        self.storage._with_write_retry(operation)
        return self.storage.get_download_job(job_id)

    def find_duplicate_download(
        self,
        *,
        detail_url: str,
        file_id: int | None,
    ) -> dict[str, Any] | None:
        with self.storage._connect() as conn:
            if file_id is not None:
                row = conn.execute(
                    """
                    SELECT *
                    FROM download_jobs
                    WHERE file_id = ?
                      AND status IN ('queued', 'running', 'done')
                    ORDER BY id DESC
                    LIMIT 1
                    """,
                    (file_id,),
                ).fetchone()
                if row is not None:
                    return self.storage.row_to_download_job(row)

            row = conn.execute(
                """
                SELECT *
                FROM download_jobs
                WHERE detail_url = ?
                  AND status IN ('queued', 'running', 'done')
                ORDER BY id DESC
                LIMIT 1
                """,
                (detail_url,),
            ).fetchone()
            if row is None:
                return None
            return self.storage.row_to_download_job(row)

    def list_download_jobs(self, limit: int = 200, status: str | None = None) -> list[dict[str, Any]]:
        safe_limit = max(1, min(limit, 1000))
        with self.storage._connect() as conn:
            if status:
                rows = conn.execute(
                    """
                    SELECT *
                    FROM download_jobs
                    WHERE status = ?
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (status, safe_limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT *
                    FROM download_jobs
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (safe_limit,),
                ).fetchall()

        return [self.storage.row_to_download_job(row) for row in rows]

    def get_download_job(self, job_id: int) -> dict[str, Any] | None:
        with self.storage._connect() as conn:
            row = conn.execute("SELECT * FROM download_jobs WHERE id = ?", (job_id,)).fetchone()
        if row is None:
            return None
        return self.storage.row_to_download_job(row)

    def claim_next_download_job(self) -> dict[str, Any] | None:
        job_id: int | None = None

        def operation() -> None:
            nonlocal job_id
            conn = self.storage._connect()
            try:
                conn.execute("BEGIN IMMEDIATE")
                row = conn.execute(
                    """
                    SELECT id
                    FROM download_jobs
                    WHERE status = 'queued'
                    ORDER BY priority DESC, id ASC
                    LIMIT 1
                    """
                ).fetchone()

                if row is None:
                    conn.commit()
                    job_id = None
                    return

                candidate_job_id = int(row["id"])
                updated = conn.execute(
                    """
                    UPDATE download_jobs
                    SET
                        status = 'running',
                        started_at = COALESCE(started_at, datetime('now')),
                        updated_at = datetime('now'),
                        attempt_count = attempt_count + 1,
                        error = NULL
                    WHERE id = ? AND status = 'queued'
                    """,
                    (candidate_job_id,),
                )
                if updated.rowcount != 1:
                    conn.rollback()
                    job_id = None
                    return

                conn.execute(
                    "INSERT INTO download_attempts (job_id) VALUES (?)",
                    (candidate_job_id,),
                )
                conn.commit()
                job_id = candidate_job_id
            finally:
                conn.close()

        self.storage._with_transaction_retry(operation)
        if job_id is None:
            return None
        return self.storage.get_download_job(job_id)

    def update_download_progress(
        self,
        job_id: int,
        *,
        bytes_downloaded: int,
        bytes_total: int | None,
        speed_bps: float | None,
        final_url: str | None,
    ) -> None:
        with self.storage._connect() as conn:
            conn.execute(
                """
                UPDATE download_jobs
                SET
                    bytes_downloaded = ?,
                    bytes_total = ?,
                    speed_bps = ?,
                    final_url = COALESCE(?, final_url),
                    updated_at = datetime('now')
                WHERE id = ? AND status = 'running'
                """,
                (
                    bytes_downloaded,
                    bytes_total,
                    speed_bps,
                    final_url,
                    job_id,
                ),
            )

    def set_download_working_path(self, job_id: int, working_path: str | None) -> None:
        with self.storage._connect() as conn:
            conn.execute(
                """
                UPDATE download_jobs
                SET
                    working_path = ?,
                    updated_at = datetime('now')
                WHERE id = ?
                """,
                (working_path, job_id),
            )

    def complete_download_job(
        self,
        job_id: int,
        *,
        save_path: str,
        final_url: str | None,
        bytes_total: int,
        status_code: int | None,
    ) -> None:
        def operation() -> None:
            with self.storage._connect() as conn:
                conn.execute(
                    """
                    UPDATE download_jobs
                    SET
                        status = 'done',
                        save_path = ?,
                        working_path = NULL,
                        final_url = COALESCE(?, final_url),
                        bytes_total = ?,
                        bytes_downloaded = ?,
                        speed_bps = NULL,
                        delete_partial_on_cancel = 0,
                        finished_at = datetime('now'),
                        updated_at = datetime('now')
                    WHERE id = ?
                    """,
                    (save_path, final_url, bytes_total, bytes_total, job_id),
                )
                conn.execute(
                    """
                    UPDATE download_attempts
                    SET
                        finished_at = datetime('now'),
                        status_code = ?,
                        final_url = ?,
                        error = NULL
                    WHERE id = (
                        SELECT id
                        FROM download_attempts
                        WHERE job_id = ?
                        ORDER BY id DESC
                        LIMIT 1
                    )
                    """,
                    (status_code, final_url, job_id),
                )

        self.storage._with_write_retry(operation)

    def fail_download_job(
        self,
        job_id: int,
        *,
        error: str,
        final_url: str | None,
        status_code: int | None,
        clear_working_path: bool = False,
    ) -> None:
        def operation() -> None:
            with self.storage._connect() as conn:
                conn.execute(
                    """
                    UPDATE download_jobs
                    SET
                        status = CASE WHEN status = 'canceled' THEN 'canceled' ELSE 'failed' END,
                        error = ?,
                        final_url = COALESCE(?, final_url),
                        working_path = CASE WHEN ? THEN NULL ELSE working_path END,
                        speed_bps = NULL,
                        delete_partial_on_cancel = CASE WHEN ? THEN 0 ELSE delete_partial_on_cancel END,
                        finished_at = CASE WHEN status = 'canceled' THEN finished_at ELSE datetime('now') END,
                        updated_at = datetime('now')
                    WHERE id = ?
                    """,
                    (
                        error,
                        final_url,
                        1 if clear_working_path else 0,
                        1 if clear_working_path else 0,
                        job_id,
                    ),
                )
                conn.execute(
                    """
                    UPDATE download_attempts
                    SET
                        finished_at = datetime('now'),
                        status_code = ?,
                        final_url = ?,
                        error = ?
                    WHERE id = (
                        SELECT id
                        FROM download_attempts
                        WHERE job_id = ?
                        ORDER BY id DESC
                        LIMIT 1
                    )
                    """,
                    (status_code, final_url, error, job_id),
                )

        self.storage._with_write_retry(operation)

    def cancel_download_job(self, job_id: int, *, complete: bool = False) -> bool:
        def operation() -> bool:
            with self.storage._connect() as conn:
                cursor = conn.execute(
                    """
                    UPDATE download_jobs
                    SET
                        status = 'canceled',
                        delete_partial_on_cancel = CASE WHEN ? THEN 1 ELSE delete_partial_on_cancel END,
                        updated_at = datetime('now'),
                        finished_at = CASE WHEN status IN ('queued', 'running') THEN datetime('now') ELSE finished_at END
                    WHERE id = ? AND status IN ('queued', 'running')
                    """,
                    (1 if complete else 0, job_id),
                )
                return cursor.rowcount > 0

        return self.storage._with_write_retry(operation)

    def retry_download_job(self, job_id: int) -> bool:
        def operation() -> bool:
            with self.storage._connect() as conn:
                cursor = conn.execute(
                    """
                    UPDATE download_jobs
                    SET
                        status = 'queued',
                        updated_at = datetime('now'),
                        started_at = NULL,
                        finished_at = NULL,
                        save_path = NULL,
                        final_url = NULL,
                        bytes_total = NULL,
                        speed_bps = NULL,
                        delete_partial_on_cancel = 0,
                        error = NULL
                    WHERE id = ? AND status IN ('failed', 'canceled')
                    """,
                    (job_id,),
                )
                return cursor.rowcount > 0

        return self.storage._with_write_retry(operation)

    def recover_download_queue_after_restart(self) -> int:
        def operation() -> int:
            with self.storage._connect() as conn:
                cursor = conn.execute(
                    """
                    UPDATE download_jobs
                    SET
                        status = 'queued',
                        finished_at = NULL,
                        speed_bps = NULL,
                        delete_partial_on_cancel = 0,
                        error = CASE
                            WHEN error IS NULL OR error = '' THEN 'Recovered after app restart; queued again.'
                            ELSE error || ' | Recovered after app restart; queued again.'
                        END,
                        updated_at = datetime('now')
                    WHERE status = 'running'
                    """
                )
                return cursor.rowcount

        return self.storage._with_write_retry(operation)

    def should_delete_partial_on_cancel(self, job_id: int) -> bool:
        with self.storage._connect() as conn:
            row = conn.execute(
                "SELECT delete_partial_on_cancel FROM download_jobs WHERE id = ?",
                (job_id,),
            ).fetchone()
        if row is None:
            return False
        return bool(row["delete_partial_on_cancel"])

    def set_download_priority(self, job_id: int, priority: int) -> bool:
        def operation() -> bool:
            with self.storage._connect() as conn:
                cursor = conn.execute(
                    """
                    UPDATE download_jobs
                    SET
                        priority = ?,
                        updated_at = datetime('now')
                    WHERE id = ? AND status IN ('queued', 'running')
                    """,
                    (priority, job_id),
                )
                return cursor.rowcount > 0

        return self.storage._with_write_retry(operation)

    def move_download_job_to_top(self, job_id: int) -> bool:
        def operation() -> bool:
            with self.storage._connect() as conn:
                row = conn.execute(
                    "SELECT id, status FROM download_jobs WHERE id = ?",
                    (job_id,),
                ).fetchone()
                if row is None or row["status"] != "queued":
                    return False

                max_row = conn.execute(
                    "SELECT COALESCE(MAX(priority), 0) AS max_priority FROM download_jobs WHERE status = 'queued'"
                ).fetchone()
                max_priority = int(max_row["max_priority"]) if max_row else 0

                cursor = conn.execute(
                    """
                    UPDATE download_jobs
                    SET
                        priority = ?,
                        updated_at = datetime('now')
                    WHERE id = ? AND status = 'queued'
                    """,
                    (max_priority + 1, job_id),
                )
                return cursor.rowcount > 0

        return self.storage._with_write_retry(operation)

    def update_download_job_classification(
        self,
        job_id: int,
        *,
        media_kind: str,
        is_kids: bool,
        series_name: str | None,
        season_number: int | None,
        episode_number: int | None,
        output_dir: str,
        destination_subpath: str,
    ) -> bool:
        def operation() -> bool:
            with self.storage._connect() as conn:
                cursor = conn.execute(
                    """
                    UPDATE download_jobs
                    SET
                        media_kind = ?,
                        is_kids = ?,
                        series_name = ?,
                        season_number = ?,
                        episode_number = ?,
                        output_dir = ?,
                        destination_subpath = ?,
                        updated_at = datetime('now')
                    WHERE id = ? AND status = 'queued'
                    """,
                    (
                        media_kind,
                        1 if is_kids else 0,
                        series_name,
                        season_number,
                        episode_number,
                        output_dir,
                        destination_subpath,
                        job_id,
                    ),
                )
                return cursor.rowcount > 0

        return self.storage._with_write_retry(operation)

    def delete_download_jobs(self, statuses: list[str]) -> int:
        valid_statuses = [status for status in statuses if status in {"done", "failed", "canceled"}]
        if not valid_statuses:
            return 0

        placeholders = ",".join(["?"] * len(valid_statuses))
        with self.storage._connect() as conn:
            conn.execute(
                f"DELETE FROM download_attempts WHERE job_id IN (SELECT id FROM download_jobs WHERE status IN ({placeholders}))",
                tuple(valid_statuses),
            )
            cursor = conn.execute(
                f"DELETE FROM download_jobs WHERE status IN ({placeholders})",
                tuple(valid_statuses),
            )
            return cursor.rowcount

    def delete_download_job(self, job_id: int, *, with_data: bool = False) -> dict[str, Any] | None:
        with self.storage._connect() as conn:
            row = conn.execute("SELECT * FROM download_jobs WHERE id = ?", (job_id,)).fetchone()
            if row is None:
                return None

            if row["status"] == "running":
                raise ValueError("Cannot remove a running job. Cancel it first.")

            conn.execute("DELETE FROM download_attempts WHERE job_id = ?", (job_id,))
            conn.execute("DELETE FROM download_jobs WHERE id = ?", (job_id,))

        deleted_paths: list[str] = []
        missing_paths: list[str] = []
        path_errors: list[str] = []

        if with_data:
            seen: set[str] = set()
            for candidate in (row["save_path"], row["working_path"]):
                if not candidate:
                    continue
                path_value = str(candidate)
                if path_value in seen:
                    continue
                seen.add(path_value)

                try:
                    file_path = Path(path_value)
                    if file_path.exists():
                        file_path.unlink()
                        deleted_paths.append(path_value)
                    else:
                        missing_paths.append(path_value)
                except Exception as exc:  # noqa: BLE001
                    path_errors.append(f"{path_value}: {exc}")

        return {
            "deleted": True,
            "job_id": job_id,
            "with_data": with_data,
            "deleted_paths": deleted_paths,
            "missing_paths": missing_paths,
            "path_errors": path_errors,
        }

    def is_job_canceled(self, job_id: int) -> bool:
        with self.storage._connect() as conn:
            row = conn.execute("SELECT status FROM download_jobs WHERE id = ?", (job_id,)).fetchone()
        if row is None:
            return True
        return row["status"] == "canceled"

    def get_download_summary(self) -> dict[str, int]:
        with self.storage._connect() as conn:
            rows = conn.execute(
                "SELECT status, COUNT(*) AS count FROM download_jobs GROUP BY status"
            ).fetchall()
        summary = {
            "queued": 0,
            "running": 0,
            "done": 0,
            "failed": 0,
            "canceled": 0,
        }
        for row in rows:
            summary[row["status"]] = row["count"]
        return summary


if TYPE_CHECKING:
    from .storage import Storage
