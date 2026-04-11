"""Repository functions for fsaudit SQLite persistence."""

from __future__ import annotations

import dataclasses
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from fsaudit.analyzer.metrics import AnalysisResult


def _json_default(obj: Any) -> Any:
    """Custom JSON serialiser for types not handled by the standard encoder."""
    if isinstance(obj, Path):
        return str(obj)
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, set):
        return list(obj)
    raise TypeError(f"Object of type {type(obj)} is not JSON serialisable")


def _serialize_analysis(analysis: AnalysisResult) -> str:
    """Serialize AnalysisResult to JSON string."""
    return json.dumps(dataclasses.asdict(analysis), default=_json_default)


def save_run(
    conn: sqlite3.Connection,
    root_path: str,
    analysis: AnalysisResult,
    *,
    timestamp: str | None = None,
) -> int:
    """Insert a run record and return its row ID."""
    ts = timestamp or datetime.now().isoformat()
    cursor = conn.execute(
        """INSERT INTO runs
               (root_path, timestamp, total_files, total_size_bytes, health_score, analysis_json)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (
            root_path,
            ts,
            analysis.total_files,
            analysis.total_size_bytes,
            analysis.health_score,
            _serialize_analysis(analysis),
        ),
    )
    conn.commit()
    return cursor.lastrowid  # type: ignore[return-value]


def _row_to_dict(cursor: sqlite3.Cursor, row: Any) -> dict:
    """Convert a cursor row to a dict using column names from description."""
    return {col[0]: row[i] for i, col in enumerate(cursor.description)}


def _fetchone_as_dict(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> dict | None:
    """Execute a query and return the first row as a dict, or None."""
    cursor = conn.execute(sql, params)
    row = cursor.fetchone()
    if row is None:
        return None
    return _row_to_dict(cursor, row)


def _fetchall_as_dicts(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> list[dict]:
    """Execute a query and return all rows as a list of dicts."""
    cursor = conn.execute(sql, params)
    rows = cursor.fetchall()
    return [_row_to_dict(cursor, row) for row in rows]


def get_run(conn: sqlite3.Connection, run_id: int) -> dict | None:
    """Retrieve a run by ID, or None if not found."""
    return _fetchone_as_dict(
        conn,
        "SELECT id, root_path, timestamp, total_files, total_size_bytes, health_score, analysis_json "
        "FROM runs WHERE id = ?",
        (run_id,),
    )


def list_runs(conn: sqlite3.Connection) -> list[dict]:
    """List all runs ordered by timestamp DESC."""
    return _fetchall_as_dicts(
        conn,
        "SELECT id, root_path, timestamp, total_files, total_size_bytes, health_score "
        "FROM runs ORDER BY timestamp DESC",
    )


def diff_runs(
    conn: sqlite3.Connection, run_id_a: int, run_id_b: int
) -> dict | None:
    """Compare two runs and return a delta dict with 6 keys, or None if either is missing."""
    row_a = _fetchone_as_dict(
        conn,
        "SELECT total_files, total_size_bytes, health_score, analysis_json FROM runs WHERE id = ?",
        (run_id_a,),
    )
    row_b = _fetchone_as_dict(
        conn,
        "SELECT total_files, total_size_bytes, health_score, analysis_json FROM runs WHERE id = ?",
        (run_id_b,),
    )

    if row_a is None or row_b is None:
        return None

    data_a = json.loads(row_a["analysis_json"])
    data_b = json.loads(row_b["analysis_json"])

    return {
        "total_files_delta": row_b["total_files"] - row_a["total_files"],
        "total_size_delta": row_b["total_size_bytes"] - row_a["total_size_bytes"],
        "health_score_delta": row_b["health_score"] - row_a["health_score"],
        "inactive_files_delta": len(data_b.get("inactive_files", [])) - len(data_a.get("inactive_files", [])),
        "zero_byte_delta": len(data_b.get("zero_byte_files", [])) - len(data_a.get("zero_byte_files", [])),
        "permission_issues_delta": len(data_b.get("permission_issues", [])) - len(data_a.get("permission_issues", [])),
    }


def save_file_records(
    conn: sqlite3.Connection,
    run_id: int,
    records: list[Any],
) -> None:
    """Batch-insert file records linked to a run."""
    rows = [
        (
            run_id,
            str(r.path),
            r.name,
            r.extension,
            r.size_bytes,
            r.mtime.timestamp() if isinstance(r.mtime, datetime) else float(r.mtime),
            r.category,
            getattr(r, "sha256", None),
        )
        for r in records
    ]
    conn.executemany(
        """INSERT INTO file_records (run_id, path, name, extension, size_bytes, mtime, category, sha256)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        rows,
    )
    conn.commit()


def execute_query(conn: sqlite3.Connection, sql: str) -> list[dict]:
    """Execute a SELECT query and return results as list of dicts.

    Raises ValueError if the SQL does not start with SELECT.
    """
    stripped = sql.strip()
    if not stripped.upper().startswith("SELECT"):
        raise ValueError(f"Only Select queries are allowed, got: {stripped[:20]!r}")
    return _fetchall_as_dicts(conn, sql)
