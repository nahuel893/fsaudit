"""Tests for health score computation — Task 2A.3."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pytest

from fsaudit.analyzer.analyzer import _compute_health_score, _HEALTH_WEIGHTS
from fsaudit.analyzer.metrics import AnalysisResult
from fsaudit.scanner.models import DirectoryRecord, FileRecord, ScanResult
from fsaudit.analyzer.analyzer import analyze


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_NOW = datetime(2024, 6, 1)


def _make_record(
    path: str = "/tmp/file.txt",
    name: str = "file.txt",
    size_bytes: int = 100,
    mtime: datetime | None = None,
    category: str = "documents",
    permissions: str | None = "644",
) -> FileRecord:
    mt = mtime or _NOW
    return FileRecord(
        path=Path(path),
        name=name,
        extension=Path(name).suffix.lower(),
        size_bytes=size_bytes,
        mtime=mt,
        creation_time=mt,
        atime=mt,
        depth=1,
        is_hidden=False,
        permissions=permissions,
        category=category,
        parent_dir=str(Path(path).parent),
    )


def _empty_scan(dirs: list | None = None) -> ScanResult:
    return ScanResult(files=[], directories=dirs or [], root_path=Path("/tmp"))


# ---------------------------------------------------------------------------
# test_health_score_empty_dir_100
# ---------------------------------------------------------------------------


def test_health_score_empty_dir_100():
    """No files → score is 100.0 with all-zero breakdown."""
    result = AnalysisResult()
    score, breakdown = _compute_health_score(result)
    assert score == 100.0
    assert all(v == 0.0 for v in breakdown.values())


# ---------------------------------------------------------------------------
# test_health_score_all_inactive_75
# ---------------------------------------------------------------------------


def test_health_score_all_inactive_75():
    """When all files are inactive → 25-point inactive penalty.
    With Shannon entropy and 2 equal categories → 0 concentration penalty → score == 75.0."""
    result = AnalysisResult()
    result.total_files = 4
    # Two equal categories → Shannon entropy = max_entropy → concentration = 0 → no penalty
    result.by_category = {
        "documents": {"count": 2, "bytes": 200, "percent": 50.0, "avg_size": 100.0,
                      "newest": _NOW, "oldest": _NOW},
        "images": {"count": 2, "bytes": 200, "percent": 50.0, "avg_size": 100.0,
                   "newest": _NOW, "oldest": _NOW},
    }
    # All 4 files inactive
    result.inactive_files = [
        {"path": "/a", "size_bytes": 100, "category": "documents", "mtime": _NOW, "days_inactive": 400},
        {"path": "/b", "size_bytes": 100, "category": "documents", "mtime": _NOW, "days_inactive": 400},
        {"path": "/c", "size_bytes": 100, "category": "images", "mtime": _NOW, "days_inactive": 400},
        {"path": "/d", "size_bytes": 100, "category": "images", "mtime": _NOW, "days_inactive": 400},
    ]

    score, breakdown = _compute_health_score(result)

    assert breakdown["inactive_ratio"] == pytest.approx(25.0)
    assert breakdown["category_concentration"] == pytest.approx(0.0)
    assert score == pytest.approx(75.0)


# ---------------------------------------------------------------------------
# test_health_breakdown_sums_to_100_minus_score
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("inactive_count,total", [
    (0, 10),
    (5, 10),
    (10, 10),
    (1, 100),
    (0, 0),
])
def test_health_breakdown_sums_to_100_minus_score(inactive_count, total):
    """sum(breakdown.values()) == 100.0 - score for any configuration."""
    result = AnalysisResult()
    result.total_files = total
    if total > 0:
        result.by_category = {"documents": {"count": total, "bytes": total * 100,
                                             "percent": 100.0, "avg_size": 100.0,
                                             "newest": _NOW, "oldest": _NOW}}
        result.inactive_files = [
            {"path": f"/{i}", "size_bytes": 100, "category": "documents", "mtime": _NOW, "days_inactive": 400}
            for i in range(inactive_count)
        ]

    score, breakdown = _compute_health_score(result)
    assert sum(breakdown.values()) == pytest.approx(100.0 - score, abs=1e-3)


# ---------------------------------------------------------------------------
# test_health_score_each_dimension_isolation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("dimension,penalty_weight", [
    ("inactive_ratio", 25.0),
    ("name_duplicate_ratio", 20.0),
    ("zero_byte_ratio", 10.0),
    ("permission_issue_ratio", 20.0),
    ("empty_dir_ratio", 10.0),
    ("category_concentration", 15.0),
])
def test_health_score_each_dimension_isolation(dimension, penalty_weight):
    """Each dimension's weight matches _HEALTH_WEIGHTS."""
    assert _HEALTH_WEIGHTS[dimension] == pytest.approx(penalty_weight)


# ---------------------------------------------------------------------------
# test_health_single_category_concentration_15
# ---------------------------------------------------------------------------


def test_health_single_category_concentration_15():
    """All files in one category → maximum concentration penalty (15 pts)."""
    result = AnalysisResult()
    result.total_files = 5
    result.by_category = {
        "documents": {"count": 5, "bytes": 500, "percent": 100.0, "avg_size": 100.0,
                      "newest": _NOW, "oldest": _NOW}
    }

    score, breakdown = _compute_health_score(result)

    # With Shannon entropy: 1 category → entropy=0, max_entropy=1 (sentinel), concentration=1.0
    # → full penalty = 15.0
    assert "category_concentration" in breakdown
    assert breakdown["category_concentration"] == pytest.approx(15.0)


# ---------------------------------------------------------------------------
# test_health_uniform_categories_0
# ---------------------------------------------------------------------------


def test_health_uniform_categories_0():
    """Files evenly distributed across categories → 0 concentration penalty."""
    result = AnalysisResult()
    result.total_files = 4
    result.by_category = {
        "documents": {"count": 1, "bytes": 100, "percent": 25.0, "avg_size": 100.0,
                      "newest": _NOW, "oldest": _NOW},
        "images": {"count": 1, "bytes": 100, "percent": 25.0, "avg_size": 100.0,
                   "newest": _NOW, "oldest": _NOW},
        "audio": {"count": 1, "bytes": 100, "percent": 25.0, "avg_size": 100.0,
                  "newest": _NOW, "oldest": _NOW},
        "video": {"count": 1, "bytes": 100, "percent": 25.0, "avg_size": 100.0,
                  "newest": _NOW, "oldest": _NOW},
    }

    score, breakdown = _compute_health_score(result)

    assert breakdown["category_concentration"] == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# test_health_score_clamped_at_0
# ---------------------------------------------------------------------------


def test_health_score_clamped_at_0():
    """Extreme worst-case → score >= 0 (never negative)."""
    result = AnalysisResult()
    result.total_files = 10
    result.by_category = {
        "documents": {"count": 10, "bytes": 1000, "percent": 100.0, "avg_size": 100.0,
                      "newest": _NOW, "oldest": _NOW}
    }
    # All inactive
    result.inactive_files = [{"path": f"/{i}", "size_bytes": 100, "category": "documents",
                               "mtime": _NOW, "days_inactive": 400} for i in range(10)]
    # All zero-byte
    result.zero_byte_files = [{"path": f"/{i}", "category": "documents", "mtime": _NOW} for i in range(10)]
    # Many permission issues
    result.permission_issues = [{"path": f"/{i}", "permissions": "777", "issue": "777"} for i in range(10)]
    # Many duplicates
    result.duplicates_by_name = {f"file{i}.txt": [f"/a/file{i}.txt", f"/b/file{i}.txt"] for i in range(10)}
    # Many empty dirs
    result.empty_directories = [{"path": f"/empty{i}", "depth": 1} for i in range(10)]

    score, breakdown = _compute_health_score(result)

    assert score >= 0.0


# ---------------------------------------------------------------------------
# test_health_score_clamped_at_100
# ---------------------------------------------------------------------------


def test_health_score_clamped_at_100():
    """Pristine result (no files, no issues) → score == 100.0."""
    result = AnalysisResult()
    score, breakdown = _compute_health_score(result)
    assert score == pytest.approx(100.0)


# ---------------------------------------------------------------------------
# Integration: analyze() always computes health score
# ---------------------------------------------------------------------------


def test_analyze_always_computes_health_score():
    """analyze() populates health_score and health_breakdown unconditionally."""
    f = _make_record()
    scan = ScanResult(files=[f], directories=[], root_path=Path("/tmp"))
    result = analyze([f], scan)
    assert isinstance(result.health_score, float)
    assert 0.0 <= result.health_score <= 100.0
    assert isinstance(result.health_breakdown, dict)
    assert len(result.health_breakdown) == len(_HEALTH_WEIGHTS)
