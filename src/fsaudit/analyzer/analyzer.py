"""Analyzer module — transforms classified FileRecords into AnalysisResult.

Pure computation: no I/O, no side effects. One public function `analyze()`
delegates to 8 private helpers, one per metric group (RF-09 through RF-16).
"""

from __future__ import annotations

import hashlib
import math
import os
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
    hash_duplicates: bool = False,
    hash_size_threshold: int = 0,
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
    if hash_duplicates and result.duplicates_by_name:
        result.duplicates_by_hash = _find_duplicates_by_hash(
            result.duplicates_by_name, size_threshold=hash_size_threshold
        )
    result.health_score, result.health_breakdown = _compute_health_score(result)
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
        key = r.mtime.strftime("%Y-%m-01")
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


def _sha256_file(path: str, chunk_size: int = 8192) -> str | None:
    """Return SHA-256 hex digest of file at path, or None on I/O error."""
    try:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            while chunk := f.read(chunk_size):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


def _find_duplicates_by_hash(
    candidates: dict[str, list[str]],
    *,
    size_threshold: int = 0,
) -> dict[str, list[str]]:
    """Hash-verify name-duplicate candidates. Returns digest → [paths] for true duplicates."""
    result: dict[str, list[str]] = {}
    for name, paths in candidates.items():
        by_hash: dict[str, list[str]] = {}
        for p in paths:
            if size_threshold > 0:
                try:
                    if os.path.getsize(p) < size_threshold:
                        continue
                except OSError:
                    pass
            digest = _sha256_file(p)
            if digest is not None:
                by_hash.setdefault(digest, []).append(p)
        for digest, group in by_hash.items():
            if len(group) >= 2:
                result[digest] = group
    return result


_HEALTH_WEIGHTS: dict[str, float] = {
    "inactive_ratio": 25.0,
    "name_duplicate_ratio": 20.0,
    "zero_byte_ratio": 10.0,
    "permission_issue_ratio": 20.0,
    "empty_dir_ratio": 10.0,
    "category_concentration": 15.0,
}


def _compute_health_score(result: "AnalysisResult") -> tuple[float, dict[str, float]]:
    """Compute health score 0-100 with penalty breakdown.

    Each dimension contributes a penalty (0 to its weight). Score = 100 - sum(penalties).
    Clamped to [0, 100].
    """
    breakdown: dict[str, float] = {}
    total = result.total_files

    # inactive_ratio: penalty proportional to fraction of inactive files
    if total > 0:
        inactive_ratio = len(result.inactive_files) / total
        breakdown["inactive_ratio"] = round(inactive_ratio * _HEALTH_WEIGHTS["inactive_ratio"], 4)
    else:
        breakdown["inactive_ratio"] = 0.0

    # name_duplicate_ratio: fraction of files involved in name duplicates
    if total > 0:
        dup_file_count = sum(len(v) for v in result.duplicates_by_name.values())
        dup_ratio = min(dup_file_count / total, 1.0)
        breakdown["name_duplicate_ratio"] = round(dup_ratio * _HEALTH_WEIGHTS["name_duplicate_ratio"], 4)
    else:
        breakdown["name_duplicate_ratio"] = 0.0

    # zero_byte_ratio
    if total > 0:
        zb_ratio = len(result.zero_byte_files) / total
        breakdown["zero_byte_ratio"] = round(zb_ratio * _HEALTH_WEIGHTS["zero_byte_ratio"], 4)
    else:
        breakdown["zero_byte_ratio"] = 0.0

    # permission_issue_ratio
    if total > 0:
        perm_ratio = min(len(result.permission_issues) / total, 1.0)
        breakdown["permission_issue_ratio"] = round(perm_ratio * _HEALTH_WEIGHTS["permission_issue_ratio"], 4)
    else:
        breakdown["permission_issue_ratio"] = 0.0

    # empty_dir_ratio: penalise based on empty directories relative to total files
    # Max penalty when empty dirs >= total files; cap at 1.0
    if total > 0:
        ed_ratio = min(len(result.empty_directories) / max(total, 1), 1.0)
        breakdown["empty_dir_ratio"] = round(ed_ratio * _HEALTH_WEIGHTS["empty_dir_ratio"], 4)
    else:
        # No files at all: no penalty (nothing to compare against)
        breakdown["empty_dir_ratio"] = 0.0

    # category_concentration: Shannon entropy measure
    # concentration = 1 - (entropy / max_entropy)
    # Full penalty (15 pts) when all files are in one category (entropy=0).
    # Zero penalty when perfectly uniform (entropy=max_entropy).
    if total > 0 and result.by_category:
        category_counts = {k: v["count"] for k, v in result.by_category.items()}
        proportions = [count / total for count in category_counts.values()]
        entropy = -sum(p * math.log2(p) for p in proportions if p > 0)
        n_cats = len(proportions)
        max_entropy = math.log2(n_cats) if n_cats > 1 else 1.0
        concentration = 1.0 - (entropy / max_entropy)
        breakdown["category_concentration"] = round(
            concentration * _HEALTH_WEIGHTS["category_concentration"], 4
        )
    else:
        breakdown["category_concentration"] = 0.0

    penalty = sum(breakdown.values())
    score = max(0.0, min(100.0, 100.0 - penalty))
    return round(score, 4), breakdown


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
