"""Tests for the analyzer module — RF-09 through RF-16."""

from datetime import datetime, timedelta
from pathlib import Path

import pytest

from fsaudit.analyzer import AnalysisResult, analyze
from fsaudit.scanner.models import DirectoryRecord, FileRecord, ScanResult


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def _make_record(
    path: str = "/tmp/file.txt",
    name: str = "file.txt",
    extension: str = ".txt",
    size_bytes: int = 100,
    mtime: datetime | None = None,
    category: str = "Unclassified",
    permissions: str | None = "644",
    depth: int = 1,
    parent_dir: str = "/tmp",
) -> FileRecord:
    """Build a FileRecord with sensible defaults."""
    mt = mtime or datetime(2025, 6, 1, 12, 0, 0)
    return FileRecord(
        path=Path(path),
        name=name,
        extension=extension,
        size_bytes=size_bytes,
        mtime=mt,
        creation_time=mt,
        atime=mt,
        depth=depth,
        is_hidden=False,
        permissions=permissions,
        category=category,
        parent_dir=parent_dir,
    )


def _empty_scan() -> ScanResult:
    return ScanResult(files=[], directories=[], root_path=Path("/tmp"))


def _scan_with_dirs(dirs: list[DirectoryRecord]) -> ScanResult:
    return ScanResult(files=[], directories=dirs, root_path=Path("/tmp"))


NOW = datetime(2026, 1, 1, 0, 0, 0)


# ---------------------------------------------------------------------------
# E2: REQ-A1 — Totals
# ---------------------------------------------------------------------------


class TestTotals:
    def test_basic_totals(self) -> None:
        files = [
            _make_record(size_bytes=100),
            _make_record(size_bytes=200),
            _make_record(size_bytes=300),
        ]
        result = analyze(files, _empty_scan(), _now=NOW)
        assert result.total_files == 3
        assert result.total_size_bytes == 600

    def test_empty_input(self) -> None:
        result = analyze([], _empty_scan(), _now=NOW)
        assert result.total_files == 0
        assert result.total_size_bytes == 0


# ---------------------------------------------------------------------------
# E3: REQ-A2 — Category stats
# ---------------------------------------------------------------------------


class TestCategoryStats:
    def test_two_categories(self) -> None:
        files = [
            _make_record(size_bytes=500, category="Code"),
            _make_record(size_bytes=1000, category="Code"),
            _make_record(size_bytes=200, category="Office"),
        ]
        result = analyze(files, _empty_scan(), _now=NOW)
        cat = result.by_category

        assert cat["Code"]["count"] == 2
        assert cat["Code"]["bytes"] == 1500
        assert cat["Code"]["percent"] == pytest.approx(88.235, abs=0.01)
        assert cat["Code"]["avg_size"] == 750.0
        assert cat["Office"]["count"] == 1

    def test_newest_oldest(self) -> None:
        files = [
            _make_record(category="Code", mtime=datetime(2024, 1, 15)),
            _make_record(category="Code", mtime=datetime(2024, 6, 1)),
            _make_record(category="Code", mtime=datetime(2023, 3, 10)),
        ]
        result = analyze(files, _empty_scan(), _now=NOW)
        assert result.by_category["Code"]["newest"] == datetime(2024, 6, 1)
        assert result.by_category["Code"]["oldest"] == datetime(2023, 3, 10)

    def test_zero_total_size(self) -> None:
        files = [_make_record(size_bytes=0, category="Empty")]
        result = analyze(files, _empty_scan(), _now=NOW)
        assert result.by_category["Empty"]["percent"] == 0.0


# ---------------------------------------------------------------------------
# E4: REQ-A3 — Timeline
# ---------------------------------------------------------------------------


class TestTimeline:
    def test_monthly_grouping(self) -> None:
        files = [
            _make_record(mtime=datetime(2024, 1, 5)),
            _make_record(mtime=datetime(2024, 1, 20)),
            _make_record(mtime=datetime(2024, 3, 10)),
        ]
        result = analyze(files, _empty_scan(), _now=NOW)
        assert result.timeline["2024-01-01"] == 2
        assert result.timeline["2024-03-01"] == 1
        assert "2024-02-01" not in result.timeline


# ---------------------------------------------------------------------------
# E5: REQ-A4 — Top largest
# ---------------------------------------------------------------------------


class TestTopLargest:
    def test_ranking_and_limit(self) -> None:
        files = [
            _make_record(path=f"/tmp/f{i}.txt", name=f"f{i}.txt", size_bytes=s)
            for i, s in enumerate([10, 50, 30, 20, 40])
        ]
        result = analyze(files, _empty_scan(), top_n=3, _now=NOW)
        assert len(result.top_largest) == 3
        sizes = [e["size_bytes"] for e in result.top_largest]
        assert sizes == [50, 40, 30]

    def test_fewer_than_n(self) -> None:
        files = [_make_record(size_bytes=10), _make_record(size_bytes=20)]
        result = analyze(files, _empty_scan(), top_n=20, _now=NOW)
        assert len(result.top_largest) == 2


# ---------------------------------------------------------------------------
# E6: REQ-B1 — Inactive files
# ---------------------------------------------------------------------------


class TestInactiveFiles:
    def test_default_threshold(self) -> None:
        mtime = NOW - timedelta(days=200)
        files = [_make_record(mtime=mtime)]
        result = analyze(files, _empty_scan(), inactive_days=180, _now=NOW)
        assert len(result.inactive_files) == 1
        assert result.inactive_files[0]["days_inactive"] == 200

    def test_within_threshold(self) -> None:
        mtime = NOW - timedelta(days=30)
        files = [_make_record(mtime=mtime)]
        result = analyze(files, _empty_scan(), inactive_days=180, _now=NOW)
        assert len(result.inactive_files) == 0

    def test_custom_threshold(self) -> None:
        mtime = NOW - timedelta(days=400)
        files = [_make_record(mtime=mtime)]
        result = analyze(files, _empty_scan(), inactive_days=365, _now=NOW)
        assert len(result.inactive_files) == 1
        assert result.inactive_files[0]["days_inactive"] == 400

    def test_boundary_exact(self) -> None:
        mtime = NOW - timedelta(days=180)
        files = [_make_record(mtime=mtime)]
        result = analyze(files, _empty_scan(), inactive_days=180, _now=NOW)
        assert len(result.inactive_files) == 1


# ---------------------------------------------------------------------------
# E7: REQ-B2 — Zero-byte files
# ---------------------------------------------------------------------------


class TestZeroByteFiles:
    def test_detected(self) -> None:
        files = [
            _make_record(size_bytes=0, path="/a", name="a"),
            _make_record(size_bytes=100, path="/b", name="b"),
            _make_record(size_bytes=0, path="/c", name="c"),
            _make_record(size_bytes=50, path="/d", name="d"),
        ]
        result = analyze(files, _empty_scan(), _now=NOW)
        assert len(result.zero_byte_files) == 2

    def test_none_detected(self) -> None:
        files = [_make_record(size_bytes=100), _make_record(size_bytes=200)]
        result = analyze(files, _empty_scan(), _now=NOW)
        assert len(result.zero_byte_files) == 0


# ---------------------------------------------------------------------------
# E8: REQ-B3 — Empty directories
# ---------------------------------------------------------------------------


class TestEmptyDirectories:
    def test_present(self) -> None:
        dirs = [
            DirectoryRecord(path=Path("/a/empty"), depth=2, is_hidden=False),
            DirectoryRecord(path=Path("/b/empty"), depth=1, is_hidden=False),
        ]
        result = analyze([], _scan_with_dirs(dirs), _now=NOW)
        assert len(result.empty_directories) == 2
        assert result.empty_directories[0]["path"] == "/a/empty"
        assert result.empty_directories[0]["depth"] == 2

    def test_absent(self) -> None:
        result = analyze([], _empty_scan(), _now=NOW)
        assert len(result.empty_directories) == 0


# ---------------------------------------------------------------------------
# E9: REQ-B4 — Duplicates by name
# ---------------------------------------------------------------------------


class TestDuplicatesByName:
    def test_two_way(self) -> None:
        files = [
            _make_record(path="/a/report.pdf", name="report.pdf"),
            _make_record(path="/b/report.pdf", name="report.pdf"),
            _make_record(path="/c/unique.txt", name="unique.txt"),
        ]
        result = analyze(files, _empty_scan(), _now=NOW)
        assert "report.pdf" in result.duplicates_by_name
        assert len(result.duplicates_by_name["report.pdf"]) == 2
        assert "unique.txt" not in result.duplicates_by_name

    def test_three_way(self) -> None:
        files = [
            _make_record(path="/a/readme.md", name="readme.md"),
            _make_record(path="/b/readme.md", name="readme.md"),
            _make_record(path="/c/readme.md", name="readme.md"),
        ]
        result = analyze(files, _empty_scan(), _now=NOW)
        assert len(result.duplicates_by_name["readme.md"]) == 3

    def test_no_duplicates(self) -> None:
        files = [
            _make_record(path="/a/one.txt", name="one.txt"),
            _make_record(path="/b/two.txt", name="two.txt"),
        ]
        result = analyze(files, _empty_scan(), _now=NOW)
        assert len(result.duplicates_by_name) == 0


# ---------------------------------------------------------------------------
# E10: REQ-B5 — Permission issues
# ---------------------------------------------------------------------------


class TestPermissionIssues:
    def test_777(self) -> None:
        files = [_make_record(permissions="777")]
        result = analyze(files, _empty_scan(), _now=NOW)
        issues = result.permission_issues
        assert any(i["issue"] == "777" for i in issues)

    def test_safe_644(self) -> None:
        files = [_make_record(permissions="644")]
        result = analyze(files, _empty_scan(), _now=NOW)
        assert len(result.permission_issues) == 0

    def test_windows_none(self) -> None:
        files = [_make_record(permissions=None)]
        result = analyze(files, _empty_scan(), _now=NOW)
        assert len(result.permission_issues) == 0

    def test_suid(self) -> None:
        files = [_make_record(permissions="4755")]
        result = analyze(files, _empty_scan(), _now=NOW)
        issues = result.permission_issues
        assert any(i["issue"] == "suid" for i in issues)

    def test_755_safe(self) -> None:
        files = [_make_record(permissions="755")]
        result = analyze(files, _empty_scan(), _now=NOW)
        assert len(result.permission_issues) == 0

    def test_world_writable(self) -> None:
        files = [_make_record(permissions="666")]
        result = analyze(files, _empty_scan(), _now=NOW)
        issues = result.permission_issues
        assert any(i["issue"] == "world-writable" for i in issues)

    def test_sgid(self) -> None:
        files = [_make_record(permissions="2755")]
        result = analyze(files, _empty_scan(), _now=NOW)
        issues = result.permission_issues
        assert any(i["issue"] == "sgid" for i in issues)


# ---------------------------------------------------------------------------
# E11: Integration test — all fields populated
# ---------------------------------------------------------------------------


class TestIntegration:
    def test_all_fields_populated(self) -> None:
        old = NOW - timedelta(days=400)
        files = [
            _make_record(
                path="/a/report.pdf",
                name="report.pdf",
                size_bytes=5000,
                category="Documents",
                mtime=datetime(2025, 3, 1),
            ),
            _make_record(
                path="/b/report.pdf",
                name="report.pdf",
                size_bytes=3000,
                category="Documents",
                mtime=datetime(2025, 5, 1),
            ),
            _make_record(
                path="/c/code.py",
                name="code.py",
                size_bytes=1200,
                category="Code",
                mtime=old,
                permissions="777",
            ),
            _make_record(
                path="/d/empty.log",
                name="empty.log",
                size_bytes=0,
                category="Logs",
                mtime=datetime(2025, 1, 10),
            ),
            _make_record(
                path="/e/photo.jpg",
                name="photo.jpg",
                size_bytes=80000,
                category="Images",
                mtime=datetime(2024, 12, 25),
                permissions="4755",
            ),
            _make_record(
                path="/f/notes.txt",
                name="notes.txt",
                size_bytes=500,
                category="Documents",
                mtime=datetime(2025, 6, 15),
            ),
            _make_record(
                path="/g/data.csv",
                name="data.csv",
                size_bytes=25000,
                category="Data",
                mtime=datetime(2024, 8, 1),
                permissions=None,
            ),
            _make_record(
                path="/h/old.bak",
                name="old.bak",
                size_bytes=200,
                category="Archives",
                mtime=old,
            ),
            _make_record(
                path="/i/script.sh",
                name="script.sh",
                size_bytes=400,
                category="Code",
                mtime=datetime(2025, 7, 1),
                permissions="755",
            ),
            _make_record(
                path="/j/readme.md",
                name="readme.md",
                size_bytes=800,
                category="Documents",
                mtime=datetime(2025, 4, 1),
            ),
        ]

        dirs = [
            DirectoryRecord(path=Path("/x/empty"), depth=2, is_hidden=False),
        ]
        scan = ScanResult(files=[], directories=dirs, root_path=Path("/"))

        result = analyze(files, scan, top_n=5, inactive_days=365, _now=NOW)

        # Totals
        assert result.total_files == 10
        assert result.total_size_bytes == sum(f.size_bytes for f in files)

        # Category
        assert "Documents" in result.by_category
        assert result.by_category["Documents"]["count"] == 4

        # Timeline
        assert len(result.timeline) > 0

        # Top largest
        assert len(result.top_largest) == 5
        assert result.top_largest[0]["size_bytes"] >= result.top_largest[-1]["size_bytes"]

        # Inactive
        assert len(result.inactive_files) >= 2  # code.py and old.bak

        # Zero-byte
        assert len(result.zero_byte_files) == 1

        # Empty dirs
        assert len(result.empty_directories) == 1

        # Duplicates
        assert "report.pdf" in result.duplicates_by_name

        # Timeline populated
        assert isinstance(result.timeline, dict)

        # Permission issues
        assert len(result.permission_issues) >= 1  # 777 and 4755
