"""Tests for fsaudit.persistence package — schema, db, and repository."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Task 2D.1: Schema & Migrations
# ---------------------------------------------------------------------------

class TestSchema:
    """Tests for schema creation and migration logic."""

    def test_ensure_schema_creates_tables(self) -> None:
        """Fresh :memory: db → runs + schema_version tables exist."""
        from fsaudit.persistence.schema import apply_migrations

        conn = sqlite3.connect(":memory:")
        apply_migrations(conn)

        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        assert "runs" in tables
        assert "schema_version" in tables

    def test_ensure_schema_idempotent(self) -> None:
        """Call twice → no error, version still 1."""
        from fsaudit.persistence.schema import apply_migrations, SCHEMA_VERSION

        conn = sqlite3.connect(":memory:")
        apply_migrations(conn)
        apply_migrations(conn)  # must not raise

        from fsaudit.persistence.schema import get_schema_version
        assert get_schema_version(conn) == SCHEMA_VERSION

    def test_get_schema_version_fresh_db(self) -> None:
        """No tables → returns 0."""
        from fsaudit.persistence.schema import get_schema_version

        conn = sqlite3.connect(":memory:")
        assert get_schema_version(conn) == 0

    def test_get_schema_version_after_apply(self) -> None:
        """After migration → returns SCHEMA_VERSION."""
        from fsaudit.persistence.schema import apply_migrations, get_schema_version, SCHEMA_VERSION

        conn = sqlite3.connect(":memory:")
        apply_migrations(conn)
        assert get_schema_version(conn) == SCHEMA_VERSION

    def test_schema_version_table_has_one_row(self) -> None:
        """Version not duplicated — exactly one row after double-apply."""
        from fsaudit.persistence.schema import apply_migrations

        conn = sqlite3.connect(":memory:")
        apply_migrations(conn)
        apply_migrations(conn)

        count = conn.execute("SELECT COUNT(*) FROM schema_version").fetchone()[0]
        assert count == 1


# ---------------------------------------------------------------------------
# Task 2D.2: get_connection context manager
# ---------------------------------------------------------------------------

class TestGetConnection:
    """Tests for get_connection context manager."""

    def test_get_connection_yields_connection(self, tmp_path: Path) -> None:
        """get_connection yields a sqlite3.Connection."""
        from fsaudit.persistence.db import get_connection

        db_path = tmp_path / "test.db"
        with get_connection(db_path) as conn:
            assert isinstance(conn, sqlite3.Connection)

    def test_get_connection_creates_parent_dirs(self, tmp_path: Path) -> None:
        """Non-existent nested path → dirs created automatically."""
        from fsaudit.persistence.db import get_connection

        db_path = tmp_path / "nested" / "deep" / "test.db"
        with get_connection(db_path) as conn:
            assert isinstance(conn, sqlite3.Connection)
        assert db_path.exists()

    def test_get_connection_commits_on_clean_exit(self, tmp_path: Path) -> None:
        """Data persists after context exits cleanly."""
        from fsaudit.persistence.db import get_connection

        db_path = tmp_path / "test.db"
        with get_connection(db_path) as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS t (val TEXT)"
            )
            conn.execute("INSERT INTO t VALUES ('hello')")

        # Re-open and verify persistence
        with get_connection(db_path) as conn2:
            row = conn2.execute("SELECT val FROM t").fetchone()
            assert row is not None
            assert row[0] == "hello"

    def test_get_connection_rolls_back_on_exception(self, tmp_path: Path) -> None:
        """Data NOT persisted when context raises."""
        from fsaudit.persistence.db import get_connection

        db_path = tmp_path / "test.db"

        # First open: create table so second open can query it
        with get_connection(db_path) as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS t (val TEXT)")

        # Second open: insert then raise
        with pytest.raises(RuntimeError):
            with get_connection(db_path) as conn:
                conn.execute("INSERT INTO t VALUES ('should_not_persist')")
                raise RuntimeError("deliberate")

        # Verify row was NOT persisted
        with get_connection(db_path) as conn:
            count = conn.execute("SELECT COUNT(*) FROM t").fetchone()[0]
            assert count == 0


# ---------------------------------------------------------------------------
# Task 2D.3: Repository — save_run, get_run, list_runs, diff_runs
# ---------------------------------------------------------------------------

def _make_analysis():
    """Build a minimal AnalysisResult for repository tests."""
    from fsaudit.analyzer.metrics import AnalysisResult

    return AnalysisResult(
        total_files=10,
        total_size_bytes=1024,
        health_score=85.0,
        health_breakdown={"inactive": 5.0, "zero_byte": 2.0},
        inactive_files=[],
        zero_byte_files=[],
        permission_issues=[],
    )


class TestRepository:
    """Tests for repository CRUD operations."""

    def test_save_run_returns_integer_id(self) -> None:
        """save_run returns an integer row ID."""
        import sqlite3
        from fsaudit.persistence.schema import apply_migrations
        from fsaudit.persistence.repository import save_run

        conn = sqlite3.connect(":memory:")
        apply_migrations(conn)

        run_id = save_run(conn, "/tmp/test", _make_analysis())
        assert isinstance(run_id, int)
        assert run_id >= 1

    def test_get_run_retrieves_saved(self) -> None:
        """save then get → fields match."""
        import sqlite3
        from fsaudit.persistence.schema import apply_migrations
        from fsaudit.persistence.repository import save_run, get_run

        conn = sqlite3.connect(":memory:")
        apply_migrations(conn)

        analysis = _make_analysis()
        run_id = save_run(conn, "/tmp/mydir", analysis)
        result = get_run(conn, run_id)

        assert result is not None
        assert result["root_path"] == "/tmp/mydir"
        assert result["total_files"] == analysis.total_files
        assert result["total_size_bytes"] == analysis.total_size_bytes
        assert abs(result["health_score"] - analysis.health_score) < 0.001

    def test_get_run_returns_none_for_missing(self) -> None:
        """get_run(999) → None when no such ID."""
        import sqlite3
        from fsaudit.persistence.schema import apply_migrations
        from fsaudit.persistence.repository import get_run

        conn = sqlite3.connect(":memory:")
        apply_migrations(conn)

        assert get_run(conn, 999) is None

    def test_list_runs_ordered_desc(self) -> None:
        """3 runs saved → list_runs returns most recent first."""
        import sqlite3
        from fsaudit.persistence.schema import apply_migrations
        from fsaudit.persistence.repository import save_run, list_runs

        conn = sqlite3.connect(":memory:")
        apply_migrations(conn)

        ts_list = ["2024-01-01T00:00:00", "2024-06-01T00:00:00", "2024-12-01T00:00:00"]
        for ts in ts_list:
            save_run(conn, "/tmp/test", _make_analysis(), timestamp=ts)

        runs = list_runs(conn)
        assert len(runs) == 3
        assert runs[0]["timestamp"] == "2024-12-01T00:00:00"
        assert runs[1]["timestamp"] == "2024-06-01T00:00:00"
        assert runs[2]["timestamp"] == "2024-01-01T00:00:00"

    def test_diff_runs_computes_deltas(self) -> None:
        """Two runs → correct delta dict with 6 keys."""
        import sqlite3
        from fsaudit.persistence.schema import apply_migrations
        from fsaudit.persistence.repository import save_run, diff_runs
        from fsaudit.analyzer.metrics import AnalysisResult

        conn = sqlite3.connect(":memory:")
        apply_migrations(conn)

        a = AnalysisResult(
            total_files=10,
            total_size_bytes=1000,
            health_score=80.0,
            inactive_files=["x"] * 2,
            zero_byte_files=["y"] * 1,
            permission_issues=["z"] * 1,
        )
        b = AnalysisResult(
            total_files=15,
            total_size_bytes=2000,
            health_score=90.0,
            inactive_files=["x"] * 4,
            zero_byte_files=["y"] * 2,
            permission_issues=["z"] * 0,
        )

        id_a = save_run(conn, "/tmp/a", a)
        id_b = save_run(conn, "/tmp/b", b)

        delta = diff_runs(conn, id_a, id_b)

        assert delta is not None
        assert set(delta.keys()) == {
            "total_files_delta",
            "total_size_delta",
            "health_score_delta",
            "inactive_files_delta",
            "zero_byte_delta",
            "permission_issues_delta",
        }
        assert delta["total_files_delta"] == 5
        assert delta["total_size_delta"] == 1000
        assert abs(delta["health_score_delta"] - 10.0) < 0.001
        assert delta["inactive_files_delta"] == 2
        assert delta["zero_byte_delta"] == 1
        assert delta["permission_issues_delta"] == -1

    def test_diff_runs_nonexistent_returns_none(self) -> None:
        """diff_runs with missing run ID → None."""
        import sqlite3
        from fsaudit.persistence.schema import apply_migrations
        from fsaudit.persistence.repository import save_run, diff_runs

        conn = sqlite3.connect(":memory:")
        apply_migrations(conn)

        run_id = save_run(conn, "/tmp/test", _make_analysis())

        assert diff_runs(conn, run_id, 999) is None
        assert diff_runs(conn, 999, run_id) is None


# ---------------------------------------------------------------------------
# Task 2D.5: file_records + execute_query
# ---------------------------------------------------------------------------

class TestFileRecords:
    """Tests for save_file_records and execute_query."""

    def test_migration_v2_creates_file_records_table(self) -> None:
        """After migrations, file_records table exists."""
        import sqlite3
        from fsaudit.persistence.schema import apply_migrations

        conn = sqlite3.connect(":memory:")
        apply_migrations(conn)

        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        assert "file_records" in tables

    def test_save_file_records_inserts_rows(self, tmp_path: Path) -> None:
        """save_run with records → file_records has rows."""
        import sqlite3
        from datetime import datetime
        from fsaudit.persistence.schema import apply_migrations
        from fsaudit.persistence.repository import save_run, save_file_records
        from fsaudit.scanner.models import FileRecord

        conn = sqlite3.connect(":memory:")
        apply_migrations(conn)

        analysis = _make_analysis()
        run_id = save_run(conn, str(tmp_path), analysis)

        now = datetime.now()
        records = [
            FileRecord(
                path=tmp_path / "file1.txt",
                name="file1.txt",
                extension=".txt",
                size_bytes=100,
                mtime=now,
                creation_time=now,
                atime=now,
                depth=1,
                is_hidden=False,
                permissions="644",
                category="documents",
                parent_dir=str(tmp_path),
            ),
        ]
        save_file_records(conn, run_id, records)

        count = conn.execute("SELECT COUNT(*) FROM file_records").fetchone()[0]
        assert count == 1

    def test_query_select_returns_results(self) -> None:
        """execute_query with SELECT returns list of dicts."""
        import sqlite3
        from fsaudit.persistence.schema import apply_migrations
        from fsaudit.persistence.repository import save_run, execute_query

        conn = sqlite3.connect(":memory:")
        apply_migrations(conn)

        save_run(conn, "/tmp/q", _make_analysis())

        rows = execute_query(conn, "SELECT id, root_path FROM runs")
        assert isinstance(rows, list)
        assert len(rows) == 1
        assert rows[0]["root_path"] == "/tmp/q"

    def test_query_non_select_rejected(self) -> None:
        """execute_query with DELETE → raises ValueError."""
        import sqlite3
        from fsaudit.persistence.schema import apply_migrations
        from fsaudit.persistence.repository import execute_query

        conn = sqlite3.connect(":memory:")
        apply_migrations(conn)

        with pytest.raises(ValueError, match="[Ss]elect"):
            execute_query(conn, "DELETE FROM runs")
