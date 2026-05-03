"""Tests for fsaudit.common package importability (T01) and permission_utils (T02)."""

from datetime import datetime
from pathlib import Path

import pytest

from fsaudit.scanner.models import FileRecord


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_record(path: str, permissions: str | None) -> FileRecord:
    now = datetime(2025, 1, 1)
    return FileRecord(
        path=Path(path),
        name=Path(path).name,
        extension=Path(path).suffix,
        size_bytes=100,
        mtime=now,
        creation_time=now,
        atime=now,
        depth=1,
        is_hidden=False,
        permissions=permissions,
        category="Unclassified",
        parent_dir=str(Path(path).parent),
    )


# ---------------------------------------------------------------------------
# T01 — Common package importable
# ---------------------------------------------------------------------------


def test_common_package_importable():
    """fsaudit.common must be importable as a package."""
    import fsaudit.common  # noqa: F401


# ---------------------------------------------------------------------------
# T02 — permission_utils tests
# ---------------------------------------------------------------------------


def test_find_permission_issues_world_writable():
    """World-writable file (777) is detected."""
    from fsaudit.common.permission_utils import find_permission_issues

    records = [_make_record("/tmp/bad.txt", "777")]
    issues = find_permission_issues(records)
    assert len(issues) >= 1
    assert any(i["issue"] in ("777", "world-writable") for i in issues)


def test_no_issues_returns_empty():
    """Normal permissions produce no issues."""
    from fsaudit.common.permission_utils import find_permission_issues

    records = [_make_record("/tmp/ok.txt", "644")]
    issues = find_permission_issues(records)
    assert issues == []


def test_permissions_none_no_crash():
    """Records with permissions=None are silently skipped."""
    from fsaudit.common.permission_utils import find_permission_issues

    records = [_make_record("/tmp/win.txt", None)]
    issues = find_permission_issues(records)
    assert issues == []


def test_suid_detected():
    """SUID bit (4000 | 755 = 4755) is detected."""
    from fsaudit.common.permission_utils import find_permission_issues

    records = [_make_record("/tmp/suid", "4755")]
    issues = find_permission_issues(records)
    assert any(i["issue"] == "suid" for i in issues)


def test_orphan_uid_detected():
    """SGID bit (2755) is detected as sgid issue."""
    from fsaudit.common.permission_utils import find_permission_issues

    records = [_make_record("/tmp/sgid", "2755")]
    issues = find_permission_issues(records)
    assert any(i["issue"] == "sgid" for i in issues)


def test_analyzer_does_not_define_private_fn():
    """After T02, analyzer.py MUST NOT define _find_permission_issues locally."""
    import inspect
    import fsaudit.analyzer.analyzer as mod

    members = dict(inspect.getmembers(mod, inspect.isfunction))
    assert "_find_permission_issues" not in members, (
        "analyzer.py still defines _find_permission_issues; it must be removed "
        "and imported from fsaudit.common.permission_utils instead"
    )
