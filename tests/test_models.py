"""Tests for data models (FileRecord, DirectoryRecord, ScanResult, AnalysisResult)."""

import dataclasses
from datetime import datetime
from pathlib import Path

import pytest

from fsaudit.analyzer.metrics import AnalysisResult
from fsaudit.scanner.models import DirectoryRecord, FileRecord, ScanResult


# ---------------------------------------------------------------------------
# FileRecord
# ---------------------------------------------------------------------------

class TestFileRecord:
    """REQ-MOD-01: FileRecord dataclass."""

    def test_creation_happy_path(self, sample_file_record: FileRecord) -> None:
        """MOD-01a: All 12 fields accessible as typed attributes."""
        rec = sample_file_record
        assert rec.path == Path("/tmp/project/readme.md")
        assert rec.name == "readme.md"
        assert rec.extension == ".md"
        assert rec.size_bytes == 1024
        assert isinstance(rec.mtime, datetime)
        assert isinstance(rec.creation_time, datetime)
        assert isinstance(rec.atime, datetime)
        assert rec.depth == 1
        assert rec.is_hidden is False
        assert rec.permissions == "644"
        assert rec.category == "Codigo"
        assert rec.parent_dir == "/tmp/project"

    def test_immutability(self, sample_file_record: FileRecord) -> None:
        """MOD-01b: Frozen instance raises FrozenInstanceError on assignment."""
        with pytest.raises(dataclasses.FrozenInstanceError):
            sample_file_record.name = "other.txt"  # type: ignore[misc]

    def test_no_extension(self) -> None:
        """MOD-01c: File with no extension gets empty string."""
        rec = FileRecord(
            path=Path("/tmp/Makefile"),
            name="Makefile",
            extension="",
            size_bytes=0,
            mtime=datetime(2025, 1, 1),
            creation_time=datetime(2025, 1, 1),
            atime=datetime(2025, 1, 1),
            depth=0,
            is_hidden=False,
            permissions="755",
        )
        assert rec.extension == ""

    def test_none_permissions(self) -> None:
        """MOD-01d: Windows scenario — permissions is None."""
        rec = FileRecord(
            path=Path("C:/Users/test/file.txt"),
            name="file.txt",
            extension=".txt",
            size_bytes=100,
            mtime=datetime(2025, 1, 1),
            creation_time=datetime(2025, 1, 1),
            atime=datetime(2025, 1, 1),
            depth=0,
            is_hidden=False,
            permissions=None,
        )
        assert rec.permissions is None

    def test_default_category_is_unclassified(self) -> None:
        """Category defaults to 'Unclassified' when not provided."""
        rec = FileRecord(
            path=Path("/tmp/file.txt"),
            name="file.txt",
            extension=".txt",
            size_bytes=0,
            mtime=datetime(2025, 1, 1),
            creation_time=datetime(2025, 1, 1),
            atime=datetime(2025, 1, 1),
            depth=0,
            is_hidden=False,
            permissions=None,
        )
        assert rec.category == "Unclassified"


# ---------------------------------------------------------------------------
# DirectoryRecord
# ---------------------------------------------------------------------------

class TestDirectoryRecord:
    """REQ-MOD-02: DirectoryRecord dataclass."""

    def test_creation(self, sample_directory_record: DirectoryRecord) -> None:
        """MOD-02a: All three fields accessible and frozen."""
        rec = sample_directory_record
        assert rec.path == Path("/tmp/project/empty_dir")
        assert rec.depth == 1
        assert rec.is_hidden is False

    def test_immutability(self, sample_directory_record: DirectoryRecord) -> None:
        """Frozen instance raises FrozenInstanceError on assignment."""
        with pytest.raises(dataclasses.FrozenInstanceError):
            sample_directory_record.depth = 99  # type: ignore[misc]


# ---------------------------------------------------------------------------
# ScanResult
# ---------------------------------------------------------------------------

class TestScanResult:
    """REQ-MOD-03: ScanResult container."""

    def test_populated_data(self, sample_scan_result: ScanResult) -> None:
        """MOD-03a: ScanResult holds provided records."""
        assert len(sample_scan_result.files) == 1
        assert len(sample_scan_result.directories) == 1
        assert sample_scan_result.root_path == Path("/tmp/project")

    def test_empty_lists(self) -> None:
        """MOD-03b: ScanResult with empty lists (not None)."""
        result = ScanResult(
            files=[],
            directories=[],
            root_path=Path("/tmp"),
        )
        assert result.files == []
        assert result.directories == []
        assert result.errors == []

    def test_errors_default_factory(self) -> None:
        """Errors field defaults to empty list via default_factory."""
        result = ScanResult(
            files=[],
            directories=[],
            root_path=Path("/tmp"),
        )
        assert isinstance(result.errors, list)
        assert len(result.errors) == 0


# ---------------------------------------------------------------------------
# AnalysisResult
# ---------------------------------------------------------------------------

class TestAnalysisResult:
    """REQ-MOD-04: AnalysisResult dataclass."""

    def test_default_construction(self) -> None:
        """MOD-04a: All fields have sensible defaults."""
        result = AnalysisResult()
        assert result.total_files == 0
        assert result.total_size_bytes == 0
        assert result.by_category == {}
        assert result.top_largest == []
        assert result.inactive_files == []
        assert result.zero_byte_files == []
        assert result.empty_directories == []
        assert result.duplicates_by_name == {}
        assert result.timeline == {}
        assert result.permission_issues == []

    def test_is_mutable(self) -> None:
        """MOD-04b: AnalysisResult is NOT frozen — fields can be assigned."""
        result = AnalysisResult()
        result.total_files = 42
        result.total_size_bytes = 999
        result.by_category = {"Codigo": {"count": 10}}
        assert result.total_files == 42
        assert result.total_size_bytes == 999
        assert result.by_category == {"Codigo": {"count": 10}}

    def test_default_collections_are_independent(self) -> None:
        """Default empty collections must be independent across instances."""
        a = AnalysisResult()
        b = AnalysisResult()
        a.top_largest.append("file1")
        assert b.top_largest == []
        a.by_category["x"] = 1
        assert b.by_category == {}

    def test_importable(self) -> None:
        """MOD-04c: AnalysisResult is importable from fsaudit.analyzer.metrics."""
        from fsaudit.analyzer.metrics import AnalysisResult as AR
        assert AR is AnalysisResult
