"""Shared pytest fixtures for FSAudit tests."""

from datetime import datetime
from pathlib import Path

import pytest

from fsaudit.scanner.models import DirectoryRecord, FileRecord, ScanResult


@pytest.fixture
def sample_file_record() -> FileRecord:
    """A valid FileRecord with realistic field values."""
    return FileRecord(
        path=Path("/tmp/project/readme.md"),
        name="readme.md",
        extension=".md",
        size_bytes=1024,
        mtime=datetime(2025, 1, 15, 10, 30, 0),
        creation_time=datetime(2025, 1, 10, 8, 0, 0),
        atime=datetime(2025, 1, 20, 14, 0, 0),
        depth=1,
        is_hidden=False,
        permissions="644",
        category="Codigo",
        parent_dir="/tmp/project",
    )


@pytest.fixture
def sample_directory_record() -> DirectoryRecord:
    """A valid DirectoryRecord."""
    return DirectoryRecord(
        path=Path("/tmp/project/empty_dir"),
        depth=1,
        is_hidden=False,
    )


@pytest.fixture
def sample_scan_result(
    sample_file_record: FileRecord,
    sample_directory_record: DirectoryRecord,
) -> ScanResult:
    """A ScanResult populated with test data."""
    return ScanResult(
        files=[sample_file_record],
        directories=[sample_directory_record],
        root_path=Path("/tmp/project"),
    )


@pytest.fixture
def tmp_tree(tmp_path: Path) -> Path:
    """Create a temporary directory tree for filesystem tests.

    Structure:
        tmp_path/
        ├── file1.txt        (10 bytes)
        ├── file2.py         (20 bytes)
        ├── .hidden_file     (5 bytes)
        ├── Makefile          (0 bytes, no extension)
        ├── subdir/
        │   └── nested.json  (15 bytes)
        └── empty_dir/
    """
    (tmp_path / "file1.txt").write_text("0123456789")
    (tmp_path / "file2.py").write_text("x" * 20)
    (tmp_path / ".hidden_file").write_text("hello")
    (tmp_path / "Makefile").write_text("")
    subdir = tmp_path / "subdir"
    subdir.mkdir()
    (subdir / "nested.json").write_text('{"key": "value"}')
    (tmp_path / "empty_dir").mkdir()
    return tmp_path
