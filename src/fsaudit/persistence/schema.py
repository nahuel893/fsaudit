"""SQLite schema definitions and migration runner for fsaudit persistence."""

from __future__ import annotations

import sqlite3

SCHEMA_VERSION = 3

MIGRATIONS: dict[int, list[str]] = {
    1: [
        """CREATE TABLE IF NOT EXISTS schema_version (
            version INTEGER NOT NULL
        )""",
        """CREATE TABLE IF NOT EXISTS runs (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            root_path        TEXT    NOT NULL,
            timestamp        TEXT    NOT NULL,
            total_files      INTEGER NOT NULL,
            total_size_bytes INTEGER NOT NULL,
            health_score     REAL    NOT NULL,
            analysis_json    TEXT    NOT NULL
        )""",
        """CREATE INDEX IF NOT EXISTS idx_runs_timestamp ON runs(timestamp)""",
        """CREATE INDEX IF NOT EXISTS idx_runs_root_path ON runs(root_path)""",
    ],
    2: [
        """CREATE TABLE IF NOT EXISTS file_records (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id      INTEGER NOT NULL REFERENCES runs(id),
            path        TEXT    NOT NULL,
            name        TEXT    NOT NULL,
            extension   TEXT    NOT NULL,
            size_bytes  INTEGER NOT NULL,
            mtime       REAL    NOT NULL,
            category    TEXT    NOT NULL,
            sha256      TEXT
        )""",
        """CREATE INDEX IF NOT EXISTS idx_file_records_run_id ON file_records(run_id)""",
    ],
    3: [
        """ALTER TABLE file_records ADD COLUMN author TEXT""",
    ],
}


def get_schema_version(conn: sqlite3.Connection) -> int:
    """Return the current schema version, or 0 if no tables exist yet."""
    # Check if schema_version table exists
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_version'"
    ).fetchone()
    if row is None:
        return 0
    row = conn.execute("SELECT version FROM schema_version").fetchone()
    if row is None:
        return 0
    return row[0]


def ensure_schema(conn: sqlite3.Connection) -> None:
    """Run all pending migrations in order, update schema_version atomically."""
    current = get_schema_version(conn)

    for version in sorted(MIGRATIONS.keys()):
        if version <= current:
            continue
        for statement in MIGRATIONS[version]:
            conn.execute(statement)

    new_version = max(MIGRATIONS.keys())
    if current == 0:
        conn.execute("INSERT INTO schema_version (version) VALUES (?)", (new_version,))
    elif new_version > current:
        conn.execute("UPDATE schema_version SET version = ?", (new_version,))

    conn.commit()


# Backward-compatible alias — db.py and existing tests import apply_migrations
apply_migrations = ensure_schema
