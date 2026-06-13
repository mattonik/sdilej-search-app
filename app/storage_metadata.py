from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any


class StorageMetadataRepository:
    def __init__(self, storage: "Storage") -> None:
        self.storage = storage

    def get_title_metadata_cache_entry(
        self,
        lookup_kind: str,
        lookup_key: str,
        year: int | None = None,
    ) -> dict[str, Any] | None:
        with self.storage._connect() as conn:
            row = conn.execute(
                """
                SELECT
                    lookup_kind,
                    lookup_key,
                    lookup_year_key,
                    lookup_year,
                    payload_json,
                    source,
                    updated_at
                FROM title_metadata_cache
                WHERE lookup_kind = ?
                  AND lookup_key = ?
                  AND lookup_year_key = ?
                """,
                (lookup_kind, lookup_key, self.storage.schema.year_key(year)),
            ).fetchone()

        if row is None:
            return None
        return {
            "lookup_kind": row["lookup_kind"],
            "lookup_key": row["lookup_key"],
            "lookup_year_key": row["lookup_year_key"],
            "lookup_year": row["lookup_year"],
            "payload": json.loads(row["payload_json"] or "{}"),
            "source": row["source"],
            "updated_at": row["updated_at"],
        }

    def get_title_metadata(
        self,
        lookup_kind: str,
        lookup_key: str,
        year: int | None = None,
    ) -> dict[str, Any] | None:
        entry = self.get_title_metadata_cache_entry(lookup_kind, lookup_key, year)
        return None if entry is None else entry["payload"]

    def set_title_metadata_cache(
        self,
        lookup_kind: str,
        lookup_key: str,
        lookup_year: int | None,
        payload: dict[str, Any],
        source: str,
    ) -> None:
        with self.storage._connect() as conn:
            conn.execute(
                """
                INSERT INTO title_metadata_cache (
                    lookup_kind,
                    lookup_key,
                    lookup_year_key,
                    lookup_year,
                    payload_json,
                    source,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
                ON CONFLICT(lookup_kind, lookup_key, lookup_year_key) DO UPDATE SET
                    lookup_year=excluded.lookup_year,
                    payload_json=excluded.payload_json,
                    source=excluded.source,
                    updated_at=datetime('now')
                """,
                (
                    lookup_kind,
                    lookup_key,
                    self.storage.schema.year_key(lookup_year),
                    lookup_year,
                    json.dumps(payload, ensure_ascii=False),
                    source,
                ),
            )


if TYPE_CHECKING:
    from .storage import Storage
