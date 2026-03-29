"""Analyzer module — transforms classified FileRecords into AnalysisResult.

Pure computation: no I/O, no side effects. One public function `analyze()`
delegates to 8 private helpers, one per metric group (RF-09 through RF-16).
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

from fsaudit.analyzer.metrics import AnalysisResult
from fsaudit.scanner.models import FileRecord, ScanResult


def analyze(
    files: list[FileRecord],
    scan_result: ScanResult,
    *,
    top_n: int = 20,
    inactive_days: int = 180,
    _now: datetime | None = None,
) -> AnalysisResult:
    """Analyze scanned files and produce a complete AnalysisResult.

    Args:
        files: Classified file records to analyze.
        scan_result: Full scan output (used for empty directories).
        top_n: How many entries in top_largest ranking.
        inactive_days: Threshold for inactive file detection.
        _now: Override for "now" (test seam). Defaults to datetime.now().

    Returns:
        Fully populated AnalysisResult.
    """
    now = _now or datetime.now()
    total_size = sum(r.size_bytes for r in files)

    result = AnalysisResult()
    result.total_files = len(files)
    result.total_size_bytes = total_size
    result.by_category = _compute_category_stats(files, total_size)
    result.timeline = _compute_timeline(files)
    result.top_largest = _find_top_largest(files, top_n)
    result.inactive_files = _find_inactive(files, inactive_days, now)
    result.zero_byte_files = _find_zero_byte(files)
    result.empty_directories = _find_empty_directories(scan_result)
    result.duplicates_by_name = _find_duplicates_by_name(files)
    result.permission_issues = _find_permission_issues(files)
    return result


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _compute_category_stats(
    records: list[FileRecord], total_size: int
) -> dict[str, dict]:
    """RF-09: Category distribution with count, bytes, percent, avg, newest, oldest."""
    cats: dict[str, dict] = {}
    for r in records:
        cat = r.category
        if cat not in cats:
            cats[cat] = {
                "count": 0,
                "bytes": 0,
                "newest": r.mtime,
                "oldest": r.mtime,
            }
        entry = cats[cat]
        entry["count"] += 1
        entry["bytes"] += r.size_bytes
        if r.mtime > entry["newest"]:
            entry["newest"] = r.mtime
        if r.mtime < entry["oldest"]:
            entry["oldest"] = r.mtime

    for entry in cats.values():
        count = entry["count"]
        cat_bytes = entry["bytes"]
        entry["percent"] = (cat_bytes / total_size * 100) if total_size else 0.0
        entry["avg_size"] = cat_bytes / count if count else 0.0

    return cats


def _compute_timeline(records: list[FileRecord]) -> dict[str, int]:
    """RF-15: Monthly file count distribution by mtime."""
    counter: Counter[str] = Counter()
    for r in records:
        key = r.mtime.strftime("%Y-%m")
        counter[key] += 1
    return dict(counter)


def _find_top_largest(records: list[FileRecord], n: int) -> list[dict]:
    """RF-10: Top N largest files sorted descending by size."""
    sorted_recs = sorted(records, key=lambda r: r.size_bytes, reverse=True)
    return [
        {
            "path": str(r.path),
            "size_bytes": r.size_bytes,
            "category": r.category,
            "mtime": r.mtime,
        }
        for r in sorted_recs[:n]
    ]


def _find_inactive(
    records: list[FileRecord], days: int, now: datetime
) -> list[dict]:
    """RF-11: Files inactive for >= `days` days."""
    result: list[dict] = []
    for r in records:
        delta = (now - r.mtime).days
        if delta >= days:
            result.append(
                {
                    "path": str(r.path),
                    "size_bytes": r.size_bytes,
                    "category": r.category,
                    "mtime": r.mtime,
                    "days_inactive": delta,
                }
            )
    return result


def _find_zero_byte(records: list[FileRecord]) -> list[dict]:
    """RF-12: Files with size_bytes == 0."""
    return [
        {"path": str(r.path), "category": r.category, "mtime": r.mtime}
        for r in records
        if r.size_bytes == 0
    ]


def _find_empty_directories(scan_result: ScanResult) -> list[dict]:
    """RF-13: Empty directories from ScanResult.directories."""
    return [
        {"path": str(d.path), "depth": d.depth}
        for d in scan_result.directories
    ]


def _find_duplicates_by_name(records: list[FileRecord]) -> dict[str, list[str]]:
    """RF-14: Files sharing the same name in 2+ locations."""
    by_name: defaultdict[str, list[str]] = defaultdict(list)
    for r in records:
        by_name[r.name].append(str(r.path))
    return {name: paths for name, paths in by_name.items() if len(paths) >= 2}


def _find_permission_issues(records: list[FileRecord]) -> list[dict]:
    """RF-16: Detect 777, world-writable, SUID, SGID permissions."""
    issues: list[dict] = []
    for r in records:
        if r.permissions is None:
            continue
        perm_str = r.permissions
        try:
            perm_int = int(perm_str, 8)
        except ValueError:
            continue

        # Check each issue type; report the most specific match
        if perm_str == "777":
            issues.append(
                {"path": str(r.path), "permissions": perm_str, "issue": "777"}
            )
        elif perm_str[-1] in ("2", "3", "6", "7"):
            issues.append(
                {
                    "path": str(r.path),
                    "permissions": perm_str,
                    "issue": "world-writable",
                }
            )

        # SUID / SGID (can co-exist with above, but spec shows separate entries)
        if perm_int & 0o4000:
            issues.append(
                {"path": str(r.path), "permissions": perm_str, "issue": "suid"}
            )
        if perm_int & 0o2000:
            issues.append(
                {"path": str(r.path), "permissions": perm_str, "issue": "sgid"}
            )

    return issues
