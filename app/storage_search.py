from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .models import SearchResponse


class StorageSearchRepository:
    def __init__(self, storage: "Storage") -> None:
        self.storage = storage

    def record_search(self, search: SearchResponse) -> None:
        with self.storage._connect() as conn:
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
        with self.storage._connect() as conn:
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


if TYPE_CHECKING:
    from .storage import Storage
