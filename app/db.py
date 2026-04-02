from __future__ import annotations

import os
import sqlite3
import time
from pathlib import Path
from typing import Callable, TypeVar


DEFAULT_SQLITE_BUSY_TIMEOUT_MS = 5_000
DEFAULT_SQLITE_RETRY_ATTEMPTS = 3
DEFAULT_SQLITE_RETRY_DELAY_SECONDS = 0.05

T = TypeVar("T")


def connect_sqlite(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute(f"PRAGMA busy_timeout = {_sqlite_busy_timeout_ms()}")
    return conn


def run_with_sqlite_retry(
    operation: Callable[[], T],
    *,
    attempts: int = DEFAULT_SQLITE_RETRY_ATTEMPTS,
    delay_seconds: float = DEFAULT_SQLITE_RETRY_DELAY_SECONDS,
) -> T:
    last_error: sqlite3.OperationalError | None = None
    safe_attempts = max(1, int(attempts))

    for attempt in range(safe_attempts):
        try:
            return operation()
        except sqlite3.OperationalError as exc:
            if not is_transient_sqlite_error(exc):
                raise
            last_error = exc
            if attempt >= safe_attempts - 1:
                break
            time.sleep(delay_seconds * (attempt + 1))

    if last_error is not None:
        raise last_error
    raise RuntimeError("SQLite retry wrapper exited without returning or raising.")


def is_transient_sqlite_error(exc: sqlite3.OperationalError) -> bool:
    message = str(exc).lower()
    return "database is locked" in message or "database table is locked" in message


def _sqlite_busy_timeout_ms() -> int:
    raw = os.getenv("SQLITE_BUSY_TIMEOUT_MS", "").strip()
    if not raw:
        return DEFAULT_SQLITE_BUSY_TIMEOUT_MS
    try:
        value = int(raw)
    except ValueError:
        return DEFAULT_SQLITE_BUSY_TIMEOUT_MS
    return max(1_000, value)
