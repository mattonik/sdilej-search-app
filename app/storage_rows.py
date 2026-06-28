from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any


class StorageRowsRepository:
    def __init__(self, storage: "Storage") -> None:
        self.storage = storage

    def row_to_saved_candidate(self, row) -> dict[str, Any]:
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

    def row_to_download_job(self, row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "started_at": row["started_at"],
            "finished_at": row["finished_at"],
            "file_id": row["file_id"],
            "title": row["title"],
            "detail_url": row["detail_url"],
            "source_type": row["source_type"],
            "source_metadata": json.loads(row["source_metadata_json"] or "{}"),
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

    def row_to_tv_search_episode(self, row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "job_id": row["job_id"],
            "season_number": row["season_number"],
            "episode_number": row["episode_number"],
            "episode_name": row["episode_name"],
            "airdate": row["airdate"],
            "episode_code": row["episode_code"],
            "status": row["status"],
            "result_count": row["result_count"],
            "query_variants": json.loads(row["query_variants_json"] or "[]"),
            "query_errors": json.loads(row["query_errors_json"] or "[]"),
            "results": json.loads(row["results_json"] or "[]"),
            "downloaded_files": json.loads(row["downloaded_files_json"] or "[]"),
            "updated_at": row["updated_at"],
        }

    def row_to_tv_search_job(
        self,
        row,
        *,
        episode_rows=None,
        include_episodes: bool = True,
    ) -> dict[str, Any]:
        payload = {
            "id": row["id"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "started_at": row["started_at"],
            "finished_at": row["finished_at"],
            "status": row["status"],
            "priority": row["priority"],
            "attempt_count": row["attempt_count"],
            "show": json.loads(row["show_json"] or "{}"),
            "title_metadata": json.loads(row["title_metadata_json"] or "null"),
            "aliases": json.loads(row["aliases_json"] or "[]"),
            "search_aliases": json.loads(row["search_aliases_json"] or "[]"),
            "selected_seasons": json.loads(row["selected_seasons_json"] or "[]"),
            "episodes_by_season": json.loads(row["episodes_by_season_json"] or "{}"),
            "category": row["category"],
            "language": row["language"],
            "language_scope": row["language_scope"],
            "strict_dubbing": bool(row["strict_dubbing"]),
            "max_results_per_variant": row["max_results_per_variant"],
            "total_episodes": row["total_episodes"],
            "completed_episodes": row["completed_episodes"],
            "result_count": row["result_count"],
            "error": row["error"],
        }
        if not include_episodes:
            return payload

        episode_items = [self.row_to_tv_search_episode(item) for item in (episode_rows or [])]
        seasons_map: dict[int, list[dict[str, Any]]] = {}
        for episode in episode_items:
            seasons_map.setdefault(int(episode["season_number"]), []).append(episode)

        seasons: list[dict[str, Any]] = []
        for season_number in sorted(seasons_map):
            items = sorted(seasons_map[season_number], key=lambda item: (item["episode_number"], item["id"]))
            seasons.append(
                {
                    "season_number": season_number,
                    "episode_count": len(items),
                    "completed_episodes": sum(1 for item in items if item["status"] in {"done", "downloaded"}),
                    "downloaded_episodes": sum(1 for item in items if item["status"] == "downloaded"),
                    "result_count": sum(int(item.get("result_count") or 0) for item in items),
                    "episodes": items,
                }
            )
        payload["seasons"] = seasons
        return payload


if TYPE_CHECKING:
    from .storage import Storage
