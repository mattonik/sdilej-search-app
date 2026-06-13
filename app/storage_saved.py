from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any


class StorageSavedRepository:
    def __init__(self, storage: "Storage") -> None:
        self.storage = storage

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

        with self.storage._connect() as conn:
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

        return self.storage.rows.row_to_saved_candidate(row)

    def list_saved_candidates(self, limit: int = 200) -> list[dict[str, Any]]:
        safe_limit = max(1, min(limit, 1000))
        with self.storage._connect() as conn:
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
        return [self.storage.rows.row_to_saved_candidate(row) for row in rows]

    def get_saved_candidate(self, file_id: int) -> dict[str, Any] | None:
        with self.storage._connect() as conn:
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
        return self.storage.rows.row_to_saved_candidate(row)

    def delete_saved_candidate(self, file_id: int) -> bool:
        with self.storage._connect() as conn:
            cursor = conn.execute("DELETE FROM saved_candidates WHERE file_id = ?", (file_id,))
            return cursor.rowcount > 0


if TYPE_CHECKING:
    from .storage import Storage
