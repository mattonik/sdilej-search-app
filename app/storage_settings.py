from __future__ import annotations

from typing import Any

from .media_routing import default_library_paths


DEFAULT_LIBRARY_PATHS = default_library_paths()


class StorageSettingsRepository:
    def __init__(self, storage: "Storage") -> None:
        self.storage = storage

    def get_download_settings(self) -> dict[str, int]:
        defaults = {
            "max_concurrent_jobs": 1,
            "default_chunk_count": 1,
            "bandwidth_limit_kbps": 0,
        }
        with self.storage._connect() as conn:
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

        with self.storage._connect() as conn:
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
        with self.storage._connect() as conn:
            rows = conn.execute(
                """
                SELECT key, value
                FROM app_settings
                WHERE key IN (
                    'library_movies_dir',
                    'library_tv_dir',
                    'library_kids_movies_dir',
                    'library_kids_tv_dir',
                    'library_music_dir',
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
        if "library_music_dir" in mapping:
            result["music_dir"] = mapping["library_music_dir"]
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
        music_dir: str,
        unsorted_dir: str,
        confirm_on_uncertain: bool,
    ) -> dict[str, Any]:
        value_map = {
            "library_movies_dir": movies_dir,
            "library_tv_dir": tv_dir,
            "library_kids_movies_dir": kids_movies_dir,
            "library_kids_tv_dir": kids_tv_dir,
            "library_music_dir": music_dir,
            "library_unsorted_dir": unsorted_dir,
            "library_confirm_on_uncertain": "1" if confirm_on_uncertain else "0",
        }
        with self.storage._connect() as conn:
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

    def get_youtube_auth_settings(self) -> dict[str, Any]:
        with self.storage._connect() as conn:
            rows = conn.execute(
                """
                SELECT key, value, updated_at
                FROM app_settings
                WHERE key IN (
                    'youtube_auth_mode',
                    'youtube_cookies_path',
                    'youtube_cookies_from_browser',
                    'youtube_cookies_managed'
                )
                """
            ).fetchall()

        mapping = {row["key"]: row["value"] for row in rows}
        updated_at = next((row["updated_at"] for row in rows if row["key"] == "youtube_auth_mode"), None)
        mode = mapping.get("youtube_auth_mode") or "none"
        if mode not in {"none", "cookies_file", "cookies_from_browser"}:
            mode = "none"
        cookies_path = mapping.get("youtube_cookies_path") or None
        cookies_from_browser = mapping.get("youtube_cookies_from_browser") or None
        managed_cookies = mapping.get("youtube_cookies_managed") in {"1", "true", "yes", "on"}
        configured = mode == "cookies_file" and bool(cookies_path) or mode == "cookies_from_browser" and bool(cookies_from_browser)
        return {
            "mode": mode,
            "configured": bool(configured),
            "cookies_path": cookies_path,
            "cookies_from_browser": cookies_from_browser,
            "managed_cookies": managed_cookies,
            "updated_at": updated_at,
        }

    def set_youtube_auth_settings(
        self,
        *,
        mode: str,
        cookies_path: str | None = None,
        cookies_from_browser: str | None = None,
        managed_cookies: bool = False,
    ) -> dict[str, Any]:
        if mode not in {"none", "cookies_file", "cookies_from_browser"}:
            mode = "none"
        value_map = {
            "youtube_auth_mode": mode,
            "youtube_cookies_path": cookies_path or "",
            "youtube_cookies_from_browser": cookies_from_browser or "",
            "youtube_cookies_managed": "1" if managed_cookies else "0",
        }
        with self.storage._connect() as conn:
            for key, value in value_map.items():
                conn.execute(
                    """
                    INSERT INTO app_settings (key, value, updated_at)
                    VALUES (?, ?, datetime('now'))
                    ON CONFLICT(key) DO UPDATE SET
                        value=excluded.value,
                        updated_at=datetime('now')
                    """,
                    (key, value),
                )
        return self.get_youtube_auth_settings()

    def clear_youtube_auth_settings(self) -> None:
        with self.storage._connect() as conn:
            conn.execute(
                """
                DELETE FROM app_settings
                WHERE key IN (
                    'youtube_auth_mode',
                    'youtube_cookies_path',
                    'youtube_cookies_from_browser',
                    'youtube_cookies_managed'
                )
                """
            )


from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .storage import Storage
