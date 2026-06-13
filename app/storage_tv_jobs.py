from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any


class StorageTvJobsRepository:
    def __init__(self, storage: "Storage") -> None:
        self.storage = storage

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
        selected_seasons_json = json.dumps(selected_seasons)
        episodes_by_season_json = json.dumps(episodes_by_season)
        aliases_json = json.dumps(aliases)
        search_aliases_json = json.dumps(search_aliases)
        title_metadata_json = json.dumps(title_metadata) if title_metadata is not None else None
        show_json = json.dumps(show)

        job_id = 0

        def operation() -> None:
            nonlocal job_id
            conn = self.storage._connect()
            try:
                conn.execute("BEGIN IMMEDIATE")
                cursor = conn.execute(
                    """
                    INSERT INTO tv_search_jobs (
                        status,
                        priority,
                        show_id,
                        show_name,
                        show_json,
                        title_metadata_json,
                        aliases_json,
                        search_aliases_json,
                        selected_seasons_json,
                        episodes_by_season_json,
                        category,
                        language,
                        language_scope,
                        strict_dubbing,
                        max_results_per_variant,
                        total_episodes
                    ) VALUES ('queued', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        priority,
                        int(show.get("id")),
                        str(show.get("name") or ""),
                        show_json,
                        title_metadata_json,
                        aliases_json,
                        search_aliases_json,
                        selected_seasons_json,
                        episodes_by_season_json,
                        category,
                        language,
                        language_scope,
                        1 if strict_dubbing else 0,
                        max_results_per_variant,
                        len(episodes),
                    ),
                )
                job_id = int(cursor.lastrowid)

                for episode in episodes:
                    conn.execute(
                        """
                        INSERT INTO tv_search_job_episodes (
                            job_id,
                            season_number,
                            episode_number,
                            episode_name,
                            airdate,
                            episode_code,
                            status,
                            downloaded_files_json
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            job_id,
                            int(episode["season_number"]),
                            int(episode["episode_number"]),
                            episode.get("episode_name"),
                            episode.get("airdate"),
                            episode.get("episode_code"),
                            str(episode.get("status") or "pending"),
                            json.dumps(list(episode.get("downloaded_files") or [])),
                        ),
                    )

                self.storage._refresh_tv_search_job_counts(conn, job_id)
                pending_count = int(
                    conn.execute(
                        """
                        SELECT COUNT(*)
                        FROM tv_search_job_episodes
                        WHERE job_id = ? AND status = 'pending'
                        """,
                        (job_id,),
                    ).fetchone()[0]
                )
                if pending_count == 0:
                    conn.execute(
                        """
                        UPDATE tv_search_jobs
                        SET
                            status = 'done',
                            started_at = COALESCE(started_at, datetime('now')),
                            finished_at = datetime('now'),
                            updated_at = datetime('now')
                        WHERE id = ?
                        """,
                        (job_id,),
                    )

                conn.commit()
            finally:
                conn.close()

        self.storage._with_transaction_retry(operation)

        return self.storage.get_tv_search_job(job_id)

    def list_tv_search_jobs(self, limit: int = 50, status: str | None = None) -> list[dict[str, Any]]:
        safe_limit = max(1, min(limit, 200))
        with self.storage._connect() as conn:
            if status:
                rows = conn.execute(
                    """
                    SELECT *
                    FROM tv_search_jobs
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
                    FROM tv_search_jobs
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (safe_limit,),
                ).fetchall()
        return [self.storage._row_to_tv_search_job(row, include_episodes=False) for row in rows]

    def get_tv_search_job(self, job_id: int) -> dict[str, Any] | None:
        with self.storage._connect() as conn:
            row = conn.execute("SELECT * FROM tv_search_jobs WHERE id = ?", (job_id,)).fetchone()
            if row is None:
                return None
            episode_rows = conn.execute(
                """
                SELECT *
                FROM tv_search_job_episodes
                WHERE job_id = ?
                ORDER BY season_number ASC, episode_number ASC
                """,
                (job_id,),
            ).fetchall()
        return self.storage._row_to_tv_search_job(row, episode_rows=episode_rows, include_episodes=True)

    def claim_next_tv_search_job(self) -> dict[str, Any] | None:
        job_id: int | None = None

        def operation() -> None:
            nonlocal job_id
            conn = self.storage._connect()
            try:
                conn.execute("BEGIN IMMEDIATE")
                row = conn.execute(
                    """
                    SELECT id
                    FROM tv_search_jobs
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
                    UPDATE tv_search_jobs
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

                conn.commit()
                job_id = candidate_job_id
            finally:
                conn.close()

        self.storage._with_transaction_retry(operation)

        if job_id is None:
            return None
        return self.storage.get_tv_search_job(job_id)

    def list_pending_tv_search_episodes(self, job_id: int) -> list[dict[str, Any]]:
        with self.storage._connect() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM tv_search_job_episodes
                WHERE job_id = ? AND status = 'pending'
                ORDER BY season_number ASC, episode_number ASC
                """,
                (job_id,),
            ).fetchall()
        return [self.storage._row_to_tv_search_episode(row) for row in rows]

    def mark_tv_search_episode_running(self, job_id: int, season_number: int, episode_number: int) -> bool:
        def operation() -> bool:
            with self.storage._connect() as conn:
                cursor = conn.execute(
                    """
                    UPDATE tv_search_job_episodes
                    SET
                        status = 'running',
                        updated_at = datetime('now')
                    WHERE job_id = ? AND season_number = ? AND episode_number = ? AND status = 'pending'
                    """,
                    (job_id, season_number, episode_number),
                )
                return cursor.rowcount > 0

        return self.storage._with_write_retry(operation)

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
        def operation() -> None:
            with self.storage._connect() as conn:
                conn.execute(
                    """
                    UPDATE tv_search_job_episodes
                    SET
                        status = 'done',
                        result_count = ?,
                        query_variants_json = ?,
                        query_errors_json = ?,
                        results_json = ?,
                        updated_at = datetime('now')
                    WHERE job_id = ? AND season_number = ? AND episode_number = ?
                    """,
                    (
                        len(results),
                        json.dumps(query_variants),
                        json.dumps(query_errors),
                        json.dumps(results),
                        job_id,
                        season_number,
                        episode_number,
                    ),
                )
                self.storage._refresh_tv_search_job_counts(conn, job_id)

        self.storage._with_write_retry(operation)

    def mark_tv_search_episode_downloaded(
        self,
        job_id: int,
        *,
        season_number: int,
        episode_number: int,
        downloaded_files: list[str],
    ) -> None:
        def operation() -> None:
            with self.storage._connect() as conn:
                conn.execute(
                    """
                    UPDATE tv_search_job_episodes
                    SET
                        status = 'downloaded',
                        result_count = 0,
                        query_variants_json = '[]',
                        query_errors_json = '[]',
                        results_json = '[]',
                        downloaded_files_json = ?,
                        updated_at = datetime('now')
                    WHERE job_id = ? AND season_number = ? AND episode_number = ?
                    """,
                    (
                        json.dumps(list(downloaded_files)),
                        job_id,
                        season_number,
                        episode_number,
                    ),
                )
                self.storage._refresh_tv_search_job_counts(conn, job_id)

        self.storage._with_write_retry(operation)

    def fail_tv_search_job(self, job_id: int, *, error: str) -> None:
        def operation() -> None:
            with self.storage._connect() as conn:
                conn.execute(
                    """
                    UPDATE tv_search_jobs
                    SET
                        status = CASE WHEN status = 'canceled' THEN 'canceled' ELSE 'failed' END,
                        error = ?,
                        finished_at = CASE WHEN status = 'canceled' THEN finished_at ELSE datetime('now') END,
                        updated_at = datetime('now')
                    WHERE id = ?
                    """,
                    (error, job_id),
                )

        self.storage._with_write_retry(operation)

    def finalize_tv_search_job(self, job_id: int) -> None:
        def operation() -> None:
            with self.storage._connect() as conn:
                self.storage._refresh_tv_search_job_counts(conn, job_id)
                row = conn.execute(
                    """
                    SELECT
                        total_episodes,
                        completed_episodes,
                        status,
                        (
                            SELECT COUNT(*)
                            FROM tv_search_job_episodes
                            WHERE job_id = ? AND status = 'running'
                        ) AS running_count,
                        (
                            SELECT COUNT(*)
                            FROM tv_search_job_episodes
                            WHERE job_id = ? AND status = 'pending'
                        ) AS pending_count
                    FROM tv_search_jobs
                    WHERE id = ?
                    """,
                    (job_id, job_id, job_id),
                ).fetchone()
                if row is None:
                    return
                if row["status"] == "canceled":
                    return
                if int(row["running_count"] or 0) > 0 or int(row["pending_count"] or 0) > 0:
                    return
                conn.execute(
                    """
                    UPDATE tv_search_jobs
                    SET
                        status = 'done',
                        finished_at = datetime('now'),
                        updated_at = datetime('now')
                    WHERE id = ? AND status = 'running'
                    """,
                    (job_id,),
                )

        self.storage._with_write_retry(operation)

    def cancel_tv_search_job(self, job_id: int) -> bool:
        def operation() -> bool:
            with self.storage._connect() as conn:
                cursor = conn.execute(
                    """
                    UPDATE tv_search_jobs
                    SET
                        status = 'canceled',
                        finished_at = CASE WHEN status IN ('queued', 'running') THEN datetime('now') ELSE finished_at END,
                        updated_at = datetime('now')
                    WHERE id = ? AND status IN ('queued', 'running')
                    """,
                    (job_id,),
                )
                if cursor.rowcount < 1:
                    return False
                conn.execute(
                    """
                    UPDATE tv_search_job_episodes
                    SET
                        status = 'canceled',
                        updated_at = datetime('now')
                    WHERE job_id = ? AND status IN ('pending', 'running')
                    """,
                    (job_id,),
                )
                return True

        return self.storage._with_write_retry(operation)

    def is_tv_search_job_canceled(self, job_id: int) -> bool:
        with self.storage._connect() as conn:
            row = conn.execute("SELECT status FROM tv_search_jobs WHERE id = ?", (job_id,)).fetchone()
        if row is None:
            return True
        return row["status"] == "canceled"

    def recover_tv_search_queue_after_restart(self) -> int:
        def operation() -> int:
            with self.storage._connect() as conn:
                conn.execute(
                    """
                    UPDATE tv_search_job_episodes
                    SET
                        status = 'pending',
                        updated_at = datetime('now')
                    WHERE status = 'running'
                    """
                )
                cursor = conn.execute(
                    """
                    UPDATE tv_search_jobs
                    SET
                        status = 'queued',
                        finished_at = NULL,
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


if TYPE_CHECKING:
    from .storage import Storage
