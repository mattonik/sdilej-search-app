from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Any

from .models import SearchResponse

DEFAULT_DB_PATH = "./data/app.db"


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
                    strict_dubbing INTEGER NOT NULL,
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
                    notes TEXT,
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
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
                    notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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

    def delete_saved_candidate(self, file_id: int) -> bool:
        with self._connect() as conn:
            cursor = conn.execute("DELETE FROM saved_candidates WHERE file_id = ?", (file_id,))
            return cursor.rowcount > 0

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
            "notes": row["notes"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def _migrate_schema(self, conn: sqlite3.Connection) -> None:
        # Backward-compatible upgrades for existing local DBs.
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
