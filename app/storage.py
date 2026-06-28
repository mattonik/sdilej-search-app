from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Any

from .db import connect_sqlite, run_with_sqlite_retry
from .models import SearchResponse
from .storage_downloads import StorageDownloadsRepository
from .storage_metadata import StorageMetadataRepository
from .storage_schema import StorageSchemaRepository
from .storage_rows import StorageRowsRepository
from .storage_saved import StorageSavedRepository
from .storage_search import StorageSearchRepository
from .storage_settings import StorageSettingsRepository
from .storage_tv_jobs import StorageTvJobsRepository

DEFAULT_DB_PATH = "./data/app.db"


class Storage:
    def __init__(self, db_path: str | None = None) -> None:
        configured_path = db_path or os.getenv("APP_DB_PATH", DEFAULT_DB_PATH)
        self.db_path = Path(configured_path).expanduser().resolve()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.rows = StorageRowsRepository(self)
        self.search = StorageSearchRepository(self)
        self.saved = StorageSavedRepository(self)
        self.schema = StorageSchemaRepository(self)
        self.metadata = StorageMetadataRepository(self)
        self.settings = StorageSettingsRepository(self)
        self.downloads = StorageDownloadsRepository(self)
        self.tv_jobs = StorageTvJobsRepository(self)

    def _connect(self) -> sqlite3.Connection:
        return connect_sqlite(self.db_path)

    def _with_write_retry(self, operation):
        return run_with_sqlite_retry(operation)

    def _with_transaction_retry(self, operation):
        return run_with_sqlite_retry(operation)

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
                    source_type TEXT NOT NULL DEFAULT 'sdilej',
                    source_metadata_json TEXT NOT NULL DEFAULT '{}',
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

                CREATE TABLE IF NOT EXISTS title_metadata_cache (
                    lookup_kind TEXT NOT NULL,
                    lookup_key TEXT NOT NULL,
                    lookup_year_key TEXT NOT NULL DEFAULT '',
                    lookup_year INTEGER,
                    payload_json TEXT NOT NULL,
                    source TEXT NOT NULL DEFAULT 'fallback',
                    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
                    PRIMARY KEY (lookup_kind, lookup_key, lookup_year_key)
                );

                CREATE TABLE IF NOT EXISTS tv_search_jobs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
                    started_at TEXT,
                    finished_at TEXT,
                    status TEXT NOT NULL DEFAULT 'queued',
                    priority INTEGER NOT NULL DEFAULT 0,
                    attempt_count INTEGER NOT NULL DEFAULT 0,
                    show_id INTEGER NOT NULL,
                    show_name TEXT NOT NULL,
                    show_json TEXT NOT NULL,
                    title_metadata_json TEXT,
                    aliases_json TEXT NOT NULL DEFAULT '[]',
                    search_aliases_json TEXT NOT NULL DEFAULT '[]',
                    selected_seasons_json TEXT NOT NULL DEFAULT '[]',
                    episodes_by_season_json TEXT NOT NULL DEFAULT '{}',
                    category TEXT NOT NULL DEFAULT 'video',
                    language TEXT,
                    language_scope TEXT NOT NULL DEFAULT 'any',
                    strict_dubbing INTEGER NOT NULL DEFAULT 0,
                    max_results_per_variant INTEGER NOT NULL DEFAULT 120,
                    total_episodes INTEGER NOT NULL DEFAULT 0,
                    completed_episodes INTEGER NOT NULL DEFAULT 0,
                    result_count INTEGER NOT NULL DEFAULT 0,
                    error TEXT
                );

                CREATE TABLE IF NOT EXISTS tv_search_job_episodes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id INTEGER NOT NULL,
                    season_number INTEGER NOT NULL,
                    episode_number INTEGER NOT NULL,
                    episode_name TEXT,
                    airdate TEXT,
                    episode_code TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    result_count INTEGER NOT NULL DEFAULT 0,
                    query_variants_json TEXT NOT NULL DEFAULT '[]',
                    query_errors_json TEXT NOT NULL DEFAULT '[]',
                    results_json TEXT NOT NULL DEFAULT '[]',
                    downloaded_files_json TEXT NOT NULL DEFAULT '[]',
                    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
                    UNIQUE(job_id, season_number, episode_number),
                    FOREIGN KEY(job_id) REFERENCES tv_search_jobs(id)
                );
                """
            )
            self.schema.apply_schema(conn)

    def record_search(self, search: SearchResponse) -> None:
        self.search.record_search(search)

    def list_search_history(self, limit: int = 50) -> list[dict[str, Any]]:
        return self.search.list_search_history(limit=limit)

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
        return self.saved.upsert_saved_candidate(
            file_id=file_id,
            title=title,
            detail_url=detail_url,
            download_url=download_url,
            size=size,
            duration=duration,
            extension=extension,
            primary_year=primary_year,
            detected_languages=detected_languages,
            has_dub_hint=has_dub_hint,
            has_subtitle_hint=has_subtitle_hint,
            media_kind=media_kind,
            is_kids=is_kids,
            series_name=series_name,
            season_number=season_number,
            episode_number=episode_number,
            classification_confidence=classification_confidence,
            notes=notes,
        )

    def list_saved_candidates(self, limit: int = 200) -> list[dict[str, Any]]:
        return self.saved.list_saved_candidates(limit=limit)

    def get_saved_candidate(self, file_id: int) -> dict[str, Any] | None:
        return self.saved.get_saved_candidate(file_id)

    def delete_saved_candidate(self, file_id: int) -> bool:
        return self.saved.delete_saved_candidate(file_id)

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

    def get_title_metadata_cache_entry(
        self,
        lookup_kind: str,
        lookup_key: str,
        lookup_year: int | None,
    ) -> dict[str, Any] | None:
        return self.metadata.get_title_metadata_cache_entry(lookup_kind, lookup_key, lookup_year)

    def get_title_metadata_cache(
        self,
        lookup_kind: str,
        lookup_key: str,
        lookup_year: int | None,
    ) -> dict[str, Any] | None:
        entry = self.get_title_metadata_cache_entry(lookup_kind, lookup_key, lookup_year)
        if entry is None:
            return None
        return dict(entry["payload"])

    def set_title_metadata_cache(
        self,
        lookup_kind: str,
        lookup_key: str,
        lookup_year: int | None,
        payload: dict[str, Any],
        source: str,
    ) -> None:
        self.metadata.set_title_metadata_cache(lookup_kind, lookup_key, lookup_year, payload, source)

    def enqueue_tv_search_job(
        self,
        *,
        show: dict[str, Any],
        title_metadata: dict[str, Any] | None,
        aliases: list[str],
        search_aliases: list[str],
        selected_seasons: list[int],
        episodes_by_season: dict[str, list[int]],
        category: str,
        language: str | None,
        language_scope: str,
        strict_dubbing: bool,
        max_results_per_variant: int,
        episodes: list[dict[str, Any]],
        priority: int = 0,
    ) -> dict[str, Any]:
        return self.tv_jobs.enqueue_tv_search_job(
            show=show,
            title_metadata=title_metadata,
            aliases=aliases,
            search_aliases=search_aliases,
            selected_seasons=selected_seasons,
            episodes_by_season=episodes_by_season,
            category=category,
            language=language,
            language_scope=language_scope,
            strict_dubbing=strict_dubbing,
            max_results_per_variant=max_results_per_variant,
            episodes=episodes,
            priority=priority,
        )

    def list_tv_search_jobs(self, limit: int = 50, status: str | None = None) -> list[dict[str, Any]]:
        return self.tv_jobs.list_tv_search_jobs(limit=limit, status=status)

    def get_tv_search_job(self, job_id: int) -> dict[str, Any] | None:
        return self.tv_jobs.get_tv_search_job(job_id)

    def claim_next_tv_search_job(self) -> dict[str, Any] | None:
        return self.tv_jobs.claim_next_tv_search_job()

    def list_pending_tv_search_episodes(self, job_id: int) -> list[dict[str, Any]]:
        return self.tv_jobs.list_pending_tv_search_episodes(job_id)

    def mark_tv_search_episode_running(self, job_id: int, season_number: int, episode_number: int) -> bool:
        return self.tv_jobs.mark_tv_search_episode_running(job_id, season_number, episode_number)

    def complete_tv_search_episode(
        self,
        job_id: int,
        *,
        season_number: int,
        episode_number: int,
        query_variants: list[str],
        query_errors: list[str],
        results: list[dict[str, Any]],
    ) -> None:
        self.tv_jobs.complete_tv_search_episode(
            job_id,
            season_number=season_number,
            episode_number=episode_number,
            query_variants=query_variants,
            query_errors=query_errors,
            results=results,
        )

    def mark_tv_search_episode_downloaded(
        self,
        job_id: int,
        *,
        season_number: int,
        episode_number: int,
        downloaded_files: list[str],
    ) -> None:
        self.tv_jobs.mark_tv_search_episode_downloaded(
            job_id,
            season_number=season_number,
            episode_number=episode_number,
            downloaded_files=downloaded_files,
        )

    def fail_tv_search_job(self, job_id: int, *, error: str) -> None:
        self.tv_jobs.fail_tv_search_job(job_id, error=error)

    def finalize_tv_search_job(self, job_id: int) -> None:
        self.tv_jobs.finalize_tv_search_job(job_id)

    def cancel_tv_search_job(self, job_id: int) -> bool:
        return self.tv_jobs.cancel_tv_search_job(job_id)

    def is_tv_search_job_canceled(self, job_id: int) -> bool:
        return self.tv_jobs.is_tv_search_job_canceled(job_id)

    def recover_tv_search_queue_after_restart(self) -> int:
        return self.tv_jobs.recover_tv_search_queue_after_restart()

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
        return self.downloads.enqueue_download_job(
            detail_url=detail_url,
            file_id=file_id,
            title=title,
            preferred_mode=preferred_mode,
            source_type=source_type,
            source_metadata=source_metadata,
            output_dir=output_dir,
            priority=priority,
            chunk_count=chunk_count,
            media_kind=media_kind,
            is_kids=is_kids,
            series_name=series_name,
            season_number=season_number,
            episode_number=episode_number,
            destination_subpath=destination_subpath,
            source_saved_file_id=source_saved_file_id,
            delete_saved_on_complete=delete_saved_on_complete,
        )

    def find_duplicate_download(
        self,
        *,
        detail_url: str,
        file_id: int | None,
    ) -> dict[str, Any] | None:
        return self.downloads.find_duplicate_download(detail_url=detail_url, file_id=file_id)

    def list_download_jobs(self, limit: int = 200, status: str | None = None) -> list[dict[str, Any]]:
        return self.downloads.list_download_jobs(limit=limit, status=status)

    def get_download_job(self, job_id: int) -> dict[str, Any] | None:
        return self.downloads.get_download_job(job_id)

    def claim_next_download_job(self) -> dict[str, Any] | None:
        return self.downloads.claim_next_download_job()

    def update_download_progress(
        self,
        job_id: int,
        *,
        bytes_downloaded: int,
        bytes_total: int | None,
        speed_bps: float | None,
        final_url: str | None,
    ) -> None:
        self.downloads.update_download_progress(
            job_id,
            bytes_downloaded=bytes_downloaded,
            bytes_total=bytes_total,
            speed_bps=speed_bps,
            final_url=final_url,
        )

    def set_download_working_path(self, job_id: int, working_path: str | None) -> None:
        self.downloads.set_download_working_path(job_id, working_path)

    def complete_download_job(
        self,
        job_id: int,
        *,
        save_path: str,
        final_url: str | None,
        bytes_total: int,
        status_code: int | None,
    ) -> None:
        self.downloads.complete_download_job(
            job_id,
            save_path=save_path,
            final_url=final_url,
            bytes_total=bytes_total,
            status_code=status_code,
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
        self.downloads.fail_download_job(
            job_id,
            error=error,
            final_url=final_url,
            status_code=status_code,
            clear_working_path=clear_working_path,
        )

    def cancel_download_job(self, job_id: int, *, complete: bool = False) -> bool:
        return self.downloads.cancel_download_job(job_id, complete=complete)

    def retry_download_job(self, job_id: int) -> bool:
        return self.downloads.retry_download_job(job_id)

    def recover_download_queue_after_restart(self) -> int:
        return self.downloads.recover_download_queue_after_restart()

    def should_delete_partial_on_cancel(self, job_id: int) -> bool:
        return self.downloads.should_delete_partial_on_cancel(job_id)

    def set_download_priority(self, job_id: int, priority: int) -> bool:
        return self.downloads.set_download_priority(job_id, priority)

    def move_download_job_to_top(self, job_id: int) -> bool:
        return self.downloads.move_download_job_to_top(job_id)

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
        return self.downloads.update_download_job_classification(
            job_id,
            media_kind=media_kind,
            is_kids=is_kids,
            series_name=series_name,
            season_number=season_number,
            episode_number=episode_number,
            output_dir=output_dir,
            destination_subpath=destination_subpath,
        )

    def delete_download_jobs(self, statuses: list[str]) -> int:
        return self.downloads.delete_download_jobs(statuses)

    def delete_download_job(self, job_id: int, *, with_data: bool = False) -> dict[str, Any] | None:
        return self.downloads.delete_download_job(job_id, with_data=with_data)

    def is_job_canceled(self, job_id: int) -> bool:
        return self.downloads.is_job_canceled(job_id)

    def get_download_summary(self) -> dict[str, int]:
        return self.downloads.get_download_summary()

    def get_download_settings(self) -> dict[str, int]:
        return self.settings.get_download_settings()

    def set_download_settings(
        self,
        *,
        max_concurrent_jobs: int,
        default_chunk_count: int,
        bandwidth_limit_kbps: int,
    ) -> dict[str, int]:
        return self.settings.set_download_settings(
            max_concurrent_jobs=max_concurrent_jobs,
            default_chunk_count=default_chunk_count,
            bandwidth_limit_kbps=bandwidth_limit_kbps,
        )

    def get_library_paths(self) -> dict[str, Any]:
        return self.settings.get_library_paths()

    def set_library_paths(
        self,
        *,
        movies_dir: str,
        tv_dir: str,
        kids_movies_dir: str,
        kids_tv_dir: str,
        music_dir: str,
        unsorted_dir: str,
        confirm_on_uncertain: bool,
    ) -> dict[str, Any]:
        return self.settings.set_library_paths(
            movies_dir=movies_dir,
            tv_dir=tv_dir,
            kids_movies_dir=kids_movies_dir,
            kids_tv_dir=kids_tv_dir,
            music_dir=music_dir,
            unsorted_dir=unsorted_dir,
            confirm_on_uncertain=confirm_on_uncertain,
        )

    def row_to_saved_candidate(self, row):
        return self.rows.row_to_saved_candidate(row)

    def row_to_download_job(self, row):
        return self.rows.row_to_download_job(row)

    def row_to_tv_search_episode(self, row):
        return self.rows.row_to_tv_search_episode(row)

    def row_to_tv_search_job(self, row, *, episode_rows=None, include_episodes: bool = True):
        return self.rows.row_to_tv_search_job(row, episode_rows=episode_rows, include_episodes=include_episodes)

    def refresh_tv_search_job_counts(self, conn, job_id: int) -> None:
        self.tv_jobs.refresh_tv_search_job_counts(conn, job_id)
