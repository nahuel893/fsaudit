"""Tests for SHA-256 hash helpers, _find_duplicates_by_hash, and Task 2A.2 integration."""

import hashlib
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

import pytest

from fsaudit.analyzer.analyzer import _find_duplicates_by_hash, _sha256_file, analyze
from fsaudit.analyzer.metrics import AnalysisResult
from fsaudit.scanner.models import FileRecord, ScanResult


# ---------------------------------------------------------------------------
# _sha256_file
# ---------------------------------------------------------------------------


def test_sha256_file_known_content(tmp_path):
    """Write a temp file with known bytes; digest must match hashlib directly."""
    content = b"hello, fsaudit!"
    f = tmp_path / "known.bin"
    f.write_bytes(content)

    expected = hashlib.sha256(content).hexdigest()
    assert _sha256_file(str(f)) == expected


def test_sha256_file_empty(tmp_path):
    """Empty file produces sha256(b'').hexdigest()."""
    f = tmp_path / "empty.bin"
    f.write_bytes(b"")

    expected = hashlib.sha256(b"").hexdigest()
    assert _sha256_file(str(f)) == expected


def test_sha256_file_unreadable_returns_none(tmp_path):
    """When open raises OSError, _sha256_file returns None (no exception raised)."""
    f = tmp_path / "unreadable.bin"
    f.write_bytes(b"data")

    with patch("builtins.open", side_effect=OSError("permission denied")):
        result = _sha256_file(str(f))

    assert result is None


# ---------------------------------------------------------------------------
# _find_duplicates_by_hash
# ---------------------------------------------------------------------------


def test_find_duplicates_by_hash_identical_files(tmp_path):
    """Two files with same content are grouped under one hash key."""
    content = b"duplicate content"
    a = tmp_path / "a" / "report.txt"
    b = tmp_path / "b" / "report.txt"
    a.parent.mkdir()
    b.parent.mkdir()
    a.write_bytes(content)
    b.write_bytes(content)

    candidates = {"report.txt": [str(a), str(b)]}
    result = _find_duplicates_by_hash(candidates)

    assert len(result) == 1
    digest = hashlib.sha256(content).hexdigest()
    assert digest in result
    assert sorted(result[digest]) == sorted([str(a), str(b)])


def test_find_duplicates_by_hash_different_content_not_grouped(tmp_path):
    """Two files sharing a name but different content produce an empty result."""
    a = tmp_path / "a" / "report.txt"
    b = tmp_path / "b" / "report.txt"
    a.parent.mkdir()
    b.parent.mkdir()
    a.write_bytes(b"content A")
    b.write_bytes(b"content B")

    candidates = {"report.txt": [str(a), str(b)]}
    result = _find_duplicates_by_hash(candidates)

    assert result == {}


def test_find_duplicates_by_hash_empty_candidates():
    """Empty candidates dict returns empty dict."""
    result = _find_duplicates_by_hash({})
    assert result == {}


def test_find_duplicates_by_hash_unreadable_file_skipped(tmp_path):
    """Unreadable file is skipped; the other two identical files are still grouped."""
    content = b"shared content"
    a = tmp_path / "a" / "data.bin"
    b = tmp_path / "b" / "data.bin"
    c = tmp_path / "c" / "data.bin"
    for d in (a.parent, b.parent, c.parent):
        d.mkdir()
    a.write_bytes(content)
    b.write_bytes(content)
    c.write_bytes(b"unreadable placeholder")  # actual bytes don't matter — we'll mock it

    original_open = open

    def selective_open(path, *args, **kwargs):
        if str(path) == str(c):
            raise OSError("permission denied")
        return original_open(path, *args, **kwargs)

    candidates = {"data.bin": [str(a), str(b), str(c)]}

    with patch("builtins.open", side_effect=selective_open):
        result = _find_duplicates_by_hash(candidates)

    assert len(result) == 1
    digest = hashlib.sha256(content).hexdigest()
    assert digest in result
    assert sorted(result[digest]) == sorted([str(a), str(b)])


def test_find_duplicates_by_hash_three_files_two_identical(tmp_path):
    """3 files: 2 share content, 1 differs — only the pair is in the result."""
    shared = b"i am duplicated"
    unique = b"i am unique"

    a = tmp_path / "a" / "notes.txt"
    b = tmp_path / "b" / "notes.txt"
    c = tmp_path / "c" / "notes.txt"
    for d in (a.parent, b.parent, c.parent):
        d.mkdir()
    a.write_bytes(shared)
    b.write_bytes(shared)
    c.write_bytes(unique)

    candidates = {"notes.txt": [str(a), str(b), str(c)]}
    result = _find_duplicates_by_hash(candidates)

    assert len(result) == 1
    digest = hashlib.sha256(shared).hexdigest()
    assert digest in result
    assert sorted(result[digest]) == sorted([str(a), str(b)])
    # Unique file's digest must NOT appear
    unique_digest = hashlib.sha256(unique).hexdigest()
    assert unique_digest not in result


# ---------------------------------------------------------------------------
# Task 2A.2: AnalysisResult new fields
# ---------------------------------------------------------------------------


def test_analysis_result_default_duplicates_by_hash():
    """AnalysisResult() must have duplicates_by_hash defaulting to {}."""
    r = AnalysisResult()
    assert r.duplicates_by_hash == {}


def test_analysis_result_default_health_score():
    """AnalysisResult() must have health_score defaulting to 100.0."""
    r = AnalysisResult()
    assert r.health_score == 100.0


def test_analysis_result_default_health_breakdown():
    """AnalysisResult() must have health_breakdown defaulting to {}."""
    r = AnalysisResult()
    assert r.health_breakdown == {}


# ---------------------------------------------------------------------------
# Task 2A.2: analyze() hash_duplicates kwarg
# ---------------------------------------------------------------------------


def _make_file_record(path: str, name: str, size: int = 100) -> FileRecord:
    _dt = datetime(2024, 1, 1)
    return FileRecord(
        path=Path(path),
        name=name,
        extension=Path(name).suffix.lower(),
        size_bytes=size,
        mtime=_dt,
        creation_time=_dt,
        atime=_dt,
        depth=1,
        is_hidden=False,
        permissions=None,
        category="documents",
        parent_dir=str(Path(path).parent),
    )


def _make_scan_result(files=None, root: str = "/tmp") -> ScanResult:
    return ScanResult(files=files or [], directories=[], root_path=Path(root), errors=[])


def test_analyze_hash_duplicates_false_empty(tmp_path):
    """analyze() with default (hash_duplicates=False) → duplicates_by_hash == {}."""
    f = tmp_path / "a.txt"
    f.write_bytes(b"hello")
    record = _make_file_record(str(f), "a.txt")
    scan = _make_scan_result([record], root=str(tmp_path))
    result = analyze([record], scan)
    assert result.duplicates_by_hash == {}


def test_find_duplicates_by_hash_size_threshold_skips_small_files(tmp_path):
    """Two identical small files (10 bytes) with size_threshold=100 → empty dict."""
    content = b"0123456789"  # exactly 10 bytes
    a = tmp_path / "dira" / "small.txt"
    b = tmp_path / "dirb" / "small.txt"
    a.parent.mkdir()
    b.parent.mkdir()
    a.write_bytes(content)
    b.write_bytes(content)

    candidates = {"small.txt": [str(a), str(b)]}
    result = _find_duplicates_by_hash(candidates, size_threshold=100)

    assert result == {}


def test_analyze_hash_duplicates_true_populated(tmp_path):
    """analyze() with hash_duplicates=True and real duplicate files → populated dict."""
    content = b"i am a duplicate"
    a = tmp_path / "dira" / "report.txt"
    b = tmp_path / "dirb" / "report.txt"
    a.parent.mkdir()
    b.parent.mkdir()
    a.write_bytes(content)
    b.write_bytes(content)

    rec_a = _make_file_record(str(a), "report.txt")
    rec_b = _make_file_record(str(b), "report.txt")
    scan = _make_scan_result([rec_a, rec_b], root=str(tmp_path))

    result = analyze([rec_a, rec_b], scan, hash_duplicates=True)

    assert len(result.duplicates_by_hash) == 1
    digest = hashlib.sha256(content).hexdigest()
    assert digest in result.duplicates_by_hash
    assert sorted(result.duplicates_by_hash[digest]) == sorted([str(a), str(b)])
