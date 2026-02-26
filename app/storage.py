from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Any

from .media_routing import default_library_paths
from .models import SearchResponse

DEFAULT_DB_PATH = "./data/app.db"
DEFAULT_LIBRARY_PATHS = default_library_paths()


class Storage:
    def __init__(self, db_path: str | None = None) -> None:
        configured_path = db_path or os.getenv("APP_DB_PATH", DEFAULT_DB_PATH)
        self.db_path = Path(configured_path).expanduser().resolve()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS search_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    query TEXT NOT NULL,
                    effective_query TEXT NOT NULL,
                    category TEXT NOT NULL,
                    sort TEXT NOT NULL,
                    language TEXT,
                    language_scope TEXT NOT NULL,
                    strict_dubbing INTEGER NOT NULL DEFAULT 0,
                    release_year INTEGER,
                    search_url TEXT NOT NULL,
                    result_count INTEGER NOT NULL,
                    unfiltered_result_count INTEGER NOT NULL
                );

                CREATE TABLE IF NOT EXISTS saved_candidates (
                    file_id INTEGER PRIMARY KEY,
                    title TEXT NOT NULL,
                    detail_url TEXT NOT NULL,
                    download_url TEXT,
                    size TEXT,
                    duration TEXT,
                    extension TEXT,
                    primary_year INTEGER,
                    detected_languages_json TEXT NOT NULL DEFAULT '[]',
                    has_dub_hint INTEGER NOT NULL DEFAULT 0,
                    has_subtitle_hint INTEGER NOT NULL DEFAULT 0,
                    media_kind TEXT,
                    is_kids INTEGER NOT NULL DEFAULT 0,
                    series_name TEXT,
                    season_number INTEGER,
                    episode_number INTEGER,
                    classification_confidence TEXT,
                    notes TEXT,
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS app_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS download_jobs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
                    started_at TEXT,
                    finished_at TEXT,
                    file_id INTEGER,
                    title TEXT,
                    detail_url TEXT NOT NULL,
                    preferred_mode TEXT NOT NULL DEFAULT 'auto',
                    output_dir TEXT,
                    status TEXT NOT NULL DEFAULT 'queued',
                    priority INTEGER NOT NULL DEFAULT 0,
                    attempt_count INTEGER NOT NULL DEFAULT 0,
                    chunk_count INTEGER,
                    media_kind TEXT,
                    is_kids INTEGER NOT NULL DEFAULT 0,
                    series_name TEXT,
                    season_number INTEGER,
                    episode_number INTEGER,
                    destination_subpath TEXT,
                    source_saved_file_id INTEGER,
                    delete_saved_on_complete INTEGER NOT NULL DEFAULT 0,
                    save_path TEXT,
                    working_path TEXT,
                    final_url TEXT,
                    bytes_total INTEGER,
                    bytes_downloaded INTEGER NOT NULL DEFAULT 0,
                    speed_bps REAL,
                    delete_partial_on_cancel INTEGER NOT NULL DEFAULT 0,
                    error TEXT
                );

                CREATE TABLE IF NOT EXISTS download_attempts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id INTEGER NOT NULL,
                    started_at TEXT NOT NULL DEFAULT (datetime('now')),
                    finished_at TEXT,
                    status_code INTEGER,
                    final_url TEXT,
                    error TEXT,
                    FOREIGN KEY(job_id) REFERENCES download_jobs(id)
                );
                """
            )
            self._migrate_schema(conn)

    def record_search(self, search: SearchResponse) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO search_history (
                    query,
                    effective_query,
                    category,
                    sort,
                    language,
                    language_scope,
                    strict_dubbing,
                    release_year,
                    search_url,
                    result_count,
                    unfiltered_result_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    search.query,
                    search.effective_query,
                    search.category,
                    search.sort,
                    search.language,
                    search.language_scope,
                    1 if search.strict_dubbing else 0,
                    search.release_year,
                    search.search_url,
                    search.result_count,
                    search.unfiltered_result_count,
                ),
            )

    def list_search_history(self, limit: int = 50) -> list[dict[str, Any]]:
        safe_limit = max(1, min(limit, 500))
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    id,
                    created_at,
                    query,
                    effective_query,
                    category,
                    sort,
                    language,
                    language_scope,
                    strict_dubbing,
                    release_year,
                    search_url,
                    result_count,
                    unfiltered_result_count
                FROM search_history
                ORDER BY id DESC
                LIMIT ?
                """,
                (safe_limit,),
            ).fetchall()

        return [
            {
                "id": row["id"],
                "created_at": row["created_at"],
                "query": row["query"],
                "effective_query": row["effective_query"],
                "category": row["category"],
                "sort": row["sort"],
                "language": row["language"],
                "language_scope": row["language_scope"],
                "strict_dubbing": bool(row["strict_dubbing"]),
                "release_year": row["release_year"],
                "search_url": row["search_url"],
                "result_count": row["result_count"],
                "unfiltered_result_count": row["unfiltered_result_count"],
            }
            for row in rows
        ]

    def upsert_saved_candidate(
        self,
        *,
        file_id: int,
        title: str,
        detail_url: str,
        download_url: str | None,
        size: str | None,
        duration: str | None,
        extension: str | None,
        primary_year: int | None,
        detected_languages: list[str],
        has_dub_hint: bool,
        has_subtitle_hint: bool,
        media_kind: str | None,
        is_kids: bool,
        series_name: str | None,
        season_number: int | None,
        episode_number: int | None,
        classification_confidence: str | None,
        notes: str | None,
    ) -> dict[str, Any]:
        detected_json = json.dumps(detected_languages)

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO saved_candidates (
                    file_id,
                    title,
                    detail_url,
                    download_url,
                    size,
                    duration,
                    extension,
                    primary_year,
                    detected_languages_json,
                    has_dub_hint,
                    has_subtitle_hint,
                    media_kind,
                    is_kids,
                    series_name,
                    season_number,
                    episode_number,
                    classification_confidence,
                    notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(file_id) DO UPDATE SET
                    title=excluded.title,
                    detail_url=excluded.detail_url,
                    download_url=excluded.download_url,
                    size=excluded.size,
                    duration=excluded.duration,
                    extension=excluded.extension,
                    primary_year=excluded.primary_year,
                    detected_languages_json=excluded.detected_languages_json,
                    has_dub_hint=excluded.has_dub_hint,
                    has_subtitle_hint=excluded.has_subtitle_hint,
                    media_kind=excluded.media_kind,
                    is_kids=excluded.is_kids,
                    series_name=excluded.series_name,
                    season_number=excluded.season_number,
                    episode_number=excluded.episode_number,
                    classification_confidence=excluded.classification_confidence,
                    notes=excluded.notes,
                    updated_at=datetime('now')
                """,
                (
                    file_id,
                    title,
                    detail_url,
                    download_url,
                    size,
                    duration,
                    extension,
                    primary_year,
                    detected_json,
                    1 if has_dub_hint else 0,
                    1 if has_subtitle_hint else 0,
                    media_kind,
                    1 if is_kids else 0,
                    series_name,
                    season_number,
                    episode_number,
                    classification_confidence,
                    notes,
                ),
            )

            row = conn.execute(
                """
                SELECT
                    file_id,
                    title,
                    detail_url,
                    download_url,
                    size,
                    duration,
                    extension,
                    primary_year,
                    detected_languages_json,
                    has_dub_hint,
                    has_subtitle_hint,
                    media_kind,
                    is_kids,
                    series_name,
                    season_number,
                    episode_number,
                    classification_confidence,
                    notes,
                    created_at,
                    updated_at
                FROM saved_candidates
                WHERE file_id = ?
                """,
                (file_id,),
            ).fetchone()

        return self._row_to_saved_candidate(row)

    def list_saved_candidates(self, limit: int = 200) -> list[dict[str, Any]]:
        safe_limit = max(1, min(limit, 1000))
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    file_id,
                    title,
                    detail_url,
                    download_url,
                    size,
                    duration,
                    extension,
                    primary_year,
                    detected_languages_json,
                    has_dub_hint,
                    has_subtitle_hint,
                    media_kind,
                    is_kids,
                    series_name,
                    season_number,
                    episode_number,
                    classification_confidence,
                    notes,
                    created_at,
                    updated_at
                FROM saved_candidates
                ORDER BY updated_at DESC, file_id DESC
                LIMIT ?
                """,
                (safe_limit,),
            ).fetchall()

        return [self._row_to_saved_candidate(row) for row in rows]

    def get_saved_candidate(self, file_id: int) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT
                    file_id,
                    title,
                    detail_url,
                    download_url,
                    size,
                    duration,
                    extension,
                    primary_year,
                    detected_languages_json,
                    has_dub_hint,
                    has_subtitle_hint,
                    media_kind,
                    is_kids,
                    series_name,
                    season_number,
                    episode_number,
                    classification_confidence,
                    notes,
                    created_at,
                    updated_at
                FROM saved_candidates
                WHERE file_id = ?
                """,
                (file_id,),
            ).fetchone()
        if row is None:
            return None
        return self._row_to_saved_candidate(row)

    def delete_saved_candidate(self, file_id: int) -> bool:
        with self._connect() as conn:
            cursor = conn.execute("DELETE FROM saved_candidates WHERE file_id = ?", (file_id,))
            return cursor.rowcount > 0

    def set_account_credentials(self, login: str, password: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO app_settings (key, value, updated_at)
                VALUES ('account_login', ?, datetime('now'))
                ON CONFLICT(key) DO UPDATE SET
                    value=excluded.value,
                    updated_at=datetime('now')
                """,
                (login,),
            )
            conn.execute(
                """
                INSERT INTO app_settings (key, value, updated_at)
                VALUES ('account_password', ?, datetime('now'))
                ON CONFLICT(key) DO UPDATE SET
                    value=excluded.value,
                    updated_at=datetime('now')
                """,
                (password,),
            )

    def clear_account_credentials(self) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM app_settings WHERE key IN ('account_login', 'account_password')")

    def get_account_credentials(self) -> tuple[str, str] | None:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT key, value FROM app_settings WHERE key IN ('account_login', 'account_password')"
            ).fetchall()

        values = {row["key"]: row["value"] for row in rows}
        login = values.get("account_login")
        password = values.get("account_password")
        if not login or not password:
            return None
        return login, password

    def enqueue_download_job(
        self,
        *,
        detail_url: str,
        file_id: int | None,
        title: str | None,
        preferred_mode: str,
        output_dir: str | None,
        priority: int,
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
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO download_jobs (
                    file_id,
                    title,
                    detail_url,
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
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'queued')
                """,
                (
                    file_id,
                    title,
                    detail_url,
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
            job_id = cursor.lastrowid

        return self.get_download_job(job_id)

    def find_duplicate_download(
        self,
        *,
        detail_url: str,
        file_id: int | None,
    ) -> dict[str, Any] | None:
        with self._connect() as conn:
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
                    return self._row_to_download_job(row)

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
            return self._row_to_download_job(row)

    def list_download_jobs(self, limit: int = 200, status: str | None = None) -> list[dict[str, Any]]:
        safe_limit = max(1, min(limit, 1000))
        with self._connect() as conn:
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

        return [self._row_to_download_job(row) for row in rows]

    def get_download_job(self, job_id: int) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM download_jobs WHERE id = ?", (job_id,)).fetchone()
        if row is None:
            return None
        return self._row_to_download_job(row)

    def claim_next_download_job(self) -> dict[str, Any] | None:
        conn = self._connect()
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
                return None

            job_id = row["id"]
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
                (job_id,),
            )
            if updated.rowcount != 1:
                conn.rollback()
                return None

            conn.execute(
                "INSERT INTO download_attempts (job_id) VALUES (?)",
                (job_id,),
            )
            conn.commit()
        finally:
            conn.close()

        return self.get_download_job(job_id)

    def update_download_progress(
        self,
        job_id: int,
        *,
        bytes_downloaded: int,
        bytes_total: int | None,
        speed_bps: float | None,
        final_url: str | None,
    ) -> None:
        with self._connect() as conn:
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
        with self._connect() as conn:
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
        with self._connect() as conn:
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

    def fail_download_job(
        self,
        job_id: int,
        *,
        error: str,
        final_url: str | None,
        status_code: int | None,
        clear_working_path: bool = False,
    ) -> None:
        with self._connect() as conn:
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

    def cancel_download_job(self, job_id: int, *, complete: bool = False) -> bool:
        with self._connect() as conn:
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

    def retry_download_job(self, job_id: int) -> bool:
        with self._connect() as conn:
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

    def recover_download_queue_after_restart(self) -> int:
        with self._connect() as conn:
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

    def should_delete_partial_on_cancel(self, job_id: int) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT delete_partial_on_cancel FROM download_jobs WHERE id = ?",
                (job_id,),
            ).fetchone()
        if row is None:
            return False
        return bool(row["delete_partial_on_cancel"])

    def set_download_priority(self, job_id: int, priority: int) -> bool:
        with self._connect() as conn:
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

    def move_download_job_to_top(self, job_id: int) -> bool:
        with self._connect() as conn:
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
        with self._connect() as conn:
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

    def delete_download_jobs(self, statuses: list[str]) -> int:
        valid_statuses = [status for status in statuses if status in {"done", "failed", "canceled"}]
        if not valid_statuses:
            return 0

        placeholders = ",".join(["?"] * len(valid_statuses))
        with self._connect() as conn:
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
        with self._connect() as conn:
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
        with self._connect() as conn:
            row = conn.execute("SELECT status FROM download_jobs WHERE id = ?", (job_id,)).fetchone()
        if row is None:
            return True
        return row["status"] == "canceled"

    def get_download_summary(self) -> dict[str, int]:
        with self._connect() as conn:
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

    def get_download_settings(self) -> dict[str, int]:
        defaults = {
            "max_concurrent_jobs": 1,
            "default_chunk_count": 1,
            "bandwidth_limit_kbps": 0,
        }
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT key, value
                FROM app_settings
                WHERE key IN ('download_max_concurrent_jobs', 'download_default_chunk_count', 'download_bandwidth_limit_kbps')
                """
            ).fetchall()

        mapping = {row["key"]: row["value"] for row in rows}
        settings = dict(defaults)
        try:
            if "download_max_concurrent_jobs" in mapping:
                settings["max_concurrent_jobs"] = int(mapping["download_max_concurrent_jobs"])
            if "download_default_chunk_count" in mapping:
                settings["default_chunk_count"] = int(mapping["download_default_chunk_count"])
            if "download_bandwidth_limit_kbps" in mapping:
                settings["bandwidth_limit_kbps"] = int(mapping["download_bandwidth_limit_kbps"])
        except ValueError:
            return defaults

        settings["max_concurrent_jobs"] = max(1, min(settings["max_concurrent_jobs"], 8))
        settings["default_chunk_count"] = max(1, min(settings["default_chunk_count"], 8))
        settings["bandwidth_limit_kbps"] = max(0, settings["bandwidth_limit_kbps"])
        return settings

    def set_download_settings(
        self,
        *,
        max_concurrent_jobs: int,
        default_chunk_count: int,
        bandwidth_limit_kbps: int,
    ) -> dict[str, int]:
        max_concurrent_jobs = max(1, min(int(max_concurrent_jobs), 8))
        default_chunk_count = max(1, min(int(default_chunk_count), 8))
        bandwidth_limit_kbps = max(0, int(bandwidth_limit_kbps))

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO app_settings (key, value, updated_at)
                VALUES ('download_max_concurrent_jobs', ?, datetime('now'))
                ON CONFLICT(key) DO UPDATE SET
                    value=excluded.value,
                    updated_at=datetime('now')
                """,
                (str(max_concurrent_jobs),),
            )
            conn.execute(
                """
                INSERT INTO app_settings (key, value, updated_at)
                VALUES ('download_default_chunk_count', ?, datetime('now'))
                ON CONFLICT(key) DO UPDATE SET
                    value=excluded.value,
                    updated_at=datetime('now')
                """,
                (str(default_chunk_count),),
            )
            conn.execute(
                """
                INSERT INTO app_settings (key, value, updated_at)
                VALUES ('download_bandwidth_limit_kbps', ?, datetime('now'))
                ON CONFLICT(key) DO UPDATE SET
                    value=excluded.value,
                    updated_at=datetime('now')
                """,
                (str(bandwidth_limit_kbps),),
            )
        return {
            "max_concurrent_jobs": max_concurrent_jobs,
            "default_chunk_count": default_chunk_count,
            "bandwidth_limit_kbps": bandwidth_limit_kbps,
        }

    def get_library_paths(self) -> dict[str, Any]:
        defaults: dict[str, Any] = {
            **DEFAULT_LIBRARY_PATHS,
            "confirm_on_uncertain": True,
        }
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT key, value
                FROM app_settings
                WHERE key IN (
                    'library_movies_dir',
                    'library_tv_dir',
                    'library_kids_movies_dir',
                    'library_kids_tv_dir',
                    'library_unsorted_dir',
                    'library_confirm_on_uncertain'
                )
                """
            ).fetchall()

        mapping = {row["key"]: row["value"] for row in rows}
        result = dict(defaults)
        if "library_movies_dir" in mapping:
            result["movies_dir"] = mapping["library_movies_dir"]
        if "library_tv_dir" in mapping:
            result["tv_dir"] = mapping["library_tv_dir"]
        if "library_kids_movies_dir" in mapping:
            result["kids_movies_dir"] = mapping["library_kids_movies_dir"]
        if "library_kids_tv_dir" in mapping:
            result["kids_tv_dir"] = mapping["library_kids_tv_dir"]
        if "library_unsorted_dir" in mapping:
            result["unsorted_dir"] = mapping["library_unsorted_dir"]
        if "library_confirm_on_uncertain" in mapping:
            result["confirm_on_uncertain"] = mapping["library_confirm_on_uncertain"] in {"1", "true", "yes", "on"}

        return result

    def set_library_paths(
        self,
        *,
        movies_dir: str,
        tv_dir: str,
        kids_movies_dir: str,
        kids_tv_dir: str,
        unsorted_dir: str,
        confirm_on_uncertain: bool,
    ) -> dict[str, Any]:
        value_map = {
            "library_movies_dir": movies_dir,
            "library_tv_dir": tv_dir,
            "library_kids_movies_dir": kids_movies_dir,
            "library_kids_tv_dir": kids_tv_dir,
            "library_unsorted_dir": unsorted_dir,
            "library_confirm_on_uncertain": "1" if confirm_on_uncertain else "0",
        }
        with self._connect() as conn:
            for key, value in value_map.items():
                conn.execute(
                    """
                    INSERT INTO app_settings (key, value, updated_at)
                    VALUES (?, ?, datetime('now'))
                    ON CONFLICT(key) DO UPDATE SET
                        value=excluded.value,
                        updated_at=datetime('now')
                    """,
                    (key, str(value)),
                )

        return self.get_library_paths()

    def _row_to_saved_candidate(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "file_id": row["file_id"],
            "title": row["title"],
            "detail_url": row["detail_url"],
            "download_url": row["download_url"],
            "size": row["size"],
            "duration": row["duration"],
            "extension": row["extension"],
            "primary_year": row["primary_year"],
            "detected_languages": json.loads(row["detected_languages_json"] or "[]"),
            "has_dub_hint": bool(row["has_dub_hint"]),
            "has_subtitle_hint": bool(row["has_subtitle_hint"]),
            "media_kind": row["media_kind"],
            "is_kids": bool(row["is_kids"]),
            "series_name": row["series_name"],
            "season_number": row["season_number"],
            "episode_number": row["episode_number"],
            "classification_confidence": row["classification_confidence"],
            "notes": row["notes"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def _row_to_download_job(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "started_at": row["started_at"],
            "finished_at": row["finished_at"],
            "file_id": row["file_id"],
            "title": row["title"],
            "detail_url": row["detail_url"],
            "preferred_mode": row["preferred_mode"],
            "output_dir": row["output_dir"],
            "status": row["status"],
            "priority": row["priority"],
            "attempt_count": row["attempt_count"],
            "chunk_count": row["chunk_count"],
            "media_kind": row["media_kind"],
            "is_kids": bool(row["is_kids"]),
            "series_name": row["series_name"],
            "season_number": row["season_number"],
            "episode_number": row["episode_number"],
            "destination_subpath": row["destination_subpath"],
            "source_saved_file_id": row["source_saved_file_id"],
            "delete_saved_on_complete": bool(row["delete_saved_on_complete"]),
            "save_path": row["save_path"],
            "working_path": row["working_path"],
            "final_url": row["final_url"],
            "bytes_total": row["bytes_total"],
            "bytes_downloaded": row["bytes_downloaded"],
            "speed_bps": row["speed_bps"],
            "delete_partial_on_cancel": bool(row["delete_partial_on_cancel"]),
            "error": row["error"],
        }

    def _migrate_schema(self, conn: sqlite3.Connection) -> None:
        self._ensure_column(
            conn,
            table="search_history",
            column="strict_dubbing",
            definition="INTEGER NOT NULL DEFAULT 0",
        )

        self._ensure_column(
            conn,
            table="saved_candidates",
            column="updated_at",
            definition="TEXT NOT NULL DEFAULT (datetime('now'))",
        )
        self._ensure_column(
            conn,
            table="saved_candidates",
            column="media_kind",
            definition="TEXT",
        )
        self._ensure_column(
            conn,
            table="saved_candidates",
            column="is_kids",
            definition="INTEGER NOT NULL DEFAULT 0",
        )
        self._ensure_column(
            conn,
            table="saved_candidates",
            column="series_name",
            definition="TEXT",
        )
        self._ensure_column(
            conn,
            table="saved_candidates",
            column="season_number",
            definition="INTEGER",
        )
        self._ensure_column(
            conn,
            table="saved_candidates",
            column="episode_number",
            definition="INTEGER",
        )
        self._ensure_column(
            conn,
            table="saved_candidates",
            column="classification_confidence",
            definition="TEXT",
        )

        self._ensure_column(
            conn,
            table="download_jobs",
            column="working_path",
            definition="TEXT",
        )

        self._ensure_column(
            conn,
            table="download_jobs",
            column="chunk_count",
            definition="INTEGER",
        )
        self._ensure_column(
            conn,
            table="download_jobs",
            column="media_kind",
            definition="TEXT",
        )
        self._ensure_column(
            conn,
            table="download_jobs",
            column="is_kids",
            definition="INTEGER NOT NULL DEFAULT 0",
        )
        self._ensure_column(
            conn,
            table="download_jobs",
            column="series_name",
            definition="TEXT",
        )
        self._ensure_column(
            conn,
            table="download_jobs",
            column="season_number",
            definition="INTEGER",
        )
        self._ensure_column(
            conn,
            table="download_jobs",
            column="episode_number",
            definition="INTEGER",
        )
        self._ensure_column(
            conn,
            table="download_jobs",
            column="destination_subpath",
            definition="TEXT",
        )

        self._ensure_column(
            conn,
            table="download_jobs",
            column="source_saved_file_id",
            definition="INTEGER",
        )

        self._ensure_column(
            conn,
            table="download_jobs",
            column="delete_saved_on_complete",
            definition="INTEGER NOT NULL DEFAULT 0",
        )

        self._ensure_column(
            conn,
            table="download_jobs",
            column="delete_partial_on_cancel",
            definition="INTEGER NOT NULL DEFAULT 0",
        )

    def _ensure_column(
        self,
        conn: sqlite3.Connection,
        *,
        table: str,
        column: str,
        definition: str,
    ) -> None:
        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
        existing_columns = {row["name"] for row in rows}
        if column in existing_columns:
            return
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
