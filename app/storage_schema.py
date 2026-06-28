from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING


class StorageSchemaRepository:
    def __init__(self, storage: "Storage") -> None:
        self.storage = storage

    def apply_schema(self, conn: sqlite3.Connection) -> None:
        self._ensure_column(conn, table="search_history", column="strict_dubbing", definition="INTEGER NOT NULL DEFAULT 0")
        self._ensure_column(conn, table="saved_candidates", column="updated_at", definition="TEXT NOT NULL DEFAULT (datetime('now'))")
        self._ensure_column(conn, table="saved_candidates", column="media_kind", definition="TEXT")
        self._ensure_column(conn, table="saved_candidates", column="is_kids", definition="INTEGER NOT NULL DEFAULT 0")
        self._ensure_column(conn, table="saved_candidates", column="series_name", definition="TEXT")
        self._ensure_column(conn, table="saved_candidates", column="season_number", definition="INTEGER")
        self._ensure_column(conn, table="saved_candidates", column="episode_number", definition="INTEGER")
        self._ensure_column(conn, table="saved_candidates", column="classification_confidence", definition="TEXT")
        self._ensure_column(conn, table="download_jobs", column="working_path", definition="TEXT")
        self._ensure_column(conn, table="download_jobs", column="chunk_count", definition="INTEGER")
        self._ensure_column(conn, table="download_jobs", column="source_type", definition="TEXT NOT NULL DEFAULT 'sdilej'")
        self._ensure_column(conn, table="download_jobs", column="source_metadata_json", definition="TEXT NOT NULL DEFAULT '{}'")
        self._ensure_column(conn, table="download_jobs", column="media_kind", definition="TEXT")
        self._ensure_column(conn, table="download_jobs", column="is_kids", definition="INTEGER NOT NULL DEFAULT 0")
        self._ensure_column(conn, table="download_jobs", column="series_name", definition="TEXT")
        self._ensure_column(conn, table="download_jobs", column="season_number", definition="INTEGER")
        self._ensure_column(conn, table="download_jobs", column="episode_number", definition="INTEGER")
        self._ensure_column(conn, table="download_jobs", column="destination_subpath", definition="TEXT")
        self._ensure_column(conn, table="download_jobs", column="source_saved_file_id", definition="INTEGER")
        self._ensure_column(conn, table="download_jobs", column="delete_saved_on_complete", definition="INTEGER NOT NULL DEFAULT 0")
        self._ensure_column(conn, table="download_jobs", column="delete_partial_on_cancel", definition="INTEGER NOT NULL DEFAULT 0")
        self._ensure_column(conn, table="tv_search_jobs", column="search_aliases_json", definition="TEXT NOT NULL DEFAULT '[]'")
        self._ensure_column(conn, table="tv_search_job_episodes", column="downloaded_files_json", definition="TEXT NOT NULL DEFAULT '[]'")

        self._ensure_index(conn, name="idx_download_jobs_status_priority_id", table="download_jobs", columns="status, priority DESC, id ASC")
        self._ensure_index(conn, name="idx_download_jobs_file_status_id", table="download_jobs", columns="file_id, status, id DESC")
        self._ensure_index(conn, name="idx_download_jobs_detail_status_id", table="download_jobs", columns="detail_url, status, id DESC")
        self._ensure_index(conn, name="idx_download_attempts_job_id_id_desc", table="download_attempts", columns="job_id, id DESC")
        self._ensure_index(conn, name="idx_tv_search_jobs_status_priority_id", table="tv_search_jobs", columns="status, priority DESC, id ASC")
        self._ensure_index(conn, name="idx_tv_search_job_episodes_job_status_season_episode", table="tv_search_job_episodes", columns="job_id, status, season_number ASC, episode_number ASC")
        self._ensure_index(conn, name="idx_title_metadata_cache_lookup_updated_at", table="title_metadata_cache", columns="lookup_kind, lookup_key, lookup_year_key, updated_at DESC")
        self._ensure_index(conn, name="idx_saved_candidates_updated_at_file_id", table="saved_candidates", columns="updated_at DESC, file_id DESC")

    def year_key(self, value: int | None) -> str:
        return "" if value is None else str(int(value))

    def _ensure_column(self, conn: sqlite3.Connection, *, table: str, column: str, definition: str) -> None:
        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
        existing_columns = {row["name"] for row in rows}
        if column in existing_columns:
            return
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    def _ensure_index(self, conn: sqlite3.Connection, *, name: str, table: str, columns: str, where: str | None = None) -> None:
        statement = f"CREATE INDEX IF NOT EXISTS {name} ON {table} ({columns})"
        if where:
            statement = f"{statement} WHERE {where}"
        conn.execute(statement)


if TYPE_CHECKING:
    from .storage import Storage
