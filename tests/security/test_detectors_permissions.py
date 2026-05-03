"""Tests for the permissions metadata detector (T11)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from fsaudit.scanner.models import FileRecord
from fsaudit.security.models import Severity


def _make_record(
    name: str = "testfile.py",
    permissions: str | None = "644",
) -> FileRecord:
    """Build a minimal FileRecord for permissions detector tests."""
    now = datetime.now(tz=timezone.utc)
    return FileRecord(
        path=Path(f"/tmp/{name}"),
        name=name,
        extension=Path(name).suffix.lower(),
        size_bytes=1024,
        mtime=now,
        creation_time=now,
        atime=now,
        depth=1,
        is_hidden=False,
        permissions=permissions,
        category="Unclassified",
        parent_dir="/tmp",
    )


# ---------------------------------------------------------------------------
# World-writable
# ---------------------------------------------------------------------------


def test_world_writable_emits_finding():
    """A world-writable file (permissions ending in 2/3/6/7) must emit a finding."""
    from fsaudit.security.detectors.permissions import PermissionsDetector
    from fsaudit.security.config import SecurityConfig, Allowlist

    det = PermissionsDetector()
    record = _make_record(permissions="777")
    cfg = SecurityConfig(version=1, rules=[], allowlist=Allowlist())
    findings = det.scan([record], cfg)
    rule_ids = [f.rule_id for f in findings]
    assert any(rid in ("perm-world-writable", "perm-777") for rid in rule_ids)


def test_world_writable_finding_has_high_severity():
    """World-writable / 777 findings must have HIGH severity."""
    from fsaudit.security.detectors.permissions import PermissionsDetector
    from fsaudit.security.config import SecurityConfig, Allowlist

    det = PermissionsDetector()
    record = _make_record(permissions="777")
    cfg = SecurityConfig(version=1, rules=[], allowlist=Allowlist())
    findings = det.scan([record], cfg)
    assert findings, "Expected at least one finding for 777"
    assert all(f.severity == Severity.HIGH for f in findings if "world" in f.rule_id or f.rule_id == "perm-777")


# ---------------------------------------------------------------------------
# SUID
# ---------------------------------------------------------------------------


def test_suid_emits_finding():
    """A file with the SUID bit (4755) must emit a perm-suid finding."""
    from fsaudit.security.detectors.permissions import PermissionsDetector
    from fsaudit.security.config import SecurityConfig, Allowlist

    det = PermissionsDetector()
    record = _make_record(permissions="4755")
    cfg = SecurityConfig(version=1, rules=[], allowlist=Allowlist())
    findings = det.scan([record], cfg)
    rule_ids = [f.rule_id for f in findings]
    assert "perm-suid" in rule_ids


def test_suid_finding_has_high_severity():
    """SUID findings must have HIGH severity."""
    from fsaudit.security.detectors.permissions import PermissionsDetector
    from fsaudit.security.config import SecurityConfig, Allowlist

    det = PermissionsDetector()
    record = _make_record(permissions="4755")
    cfg = SecurityConfig(version=1, rules=[], allowlist=Allowlist())
    findings = det.scan([record], cfg)
    suid_findings = [f for f in findings if f.rule_id == "perm-suid"]
    assert suid_findings, "Expected perm-suid finding"
    assert all(f.severity == Severity.HIGH for f in suid_findings)


# ---------------------------------------------------------------------------
# SGID
# ---------------------------------------------------------------------------


def test_sgid_emits_finding():
    """A file with the SGID bit (2755) must emit a perm-sgid finding."""
    from fsaudit.security.detectors.permissions import PermissionsDetector
    from fsaudit.security.config import SecurityConfig, Allowlist

    det = PermissionsDetector()
    record = _make_record(permissions="2755")
    cfg = SecurityConfig(version=1, rules=[], allowlist=Allowlist())
    findings = det.scan([record], cfg)
    rule_ids = [f.rule_id for f in findings]
    assert "perm-sgid" in rule_ids


def test_sgid_finding_has_medium_severity():
    """SGID findings must have MEDIUM severity."""
    from fsaudit.security.detectors.permissions import PermissionsDetector
    from fsaudit.security.config import SecurityConfig, Allowlist

    det = PermissionsDetector()
    record = _make_record(permissions="2755")
    cfg = SecurityConfig(version=1, rules=[], allowlist=Allowlist())
    findings = det.scan([record], cfg)
    sgid_findings = [f for f in findings if f.rule_id == "perm-sgid"]
    assert sgid_findings, "Expected perm-sgid finding"
    assert all(f.severity == Severity.MEDIUM for f in sgid_findings)


# ---------------------------------------------------------------------------
# Windows no-op (permissions=None)
# ---------------------------------------------------------------------------


def test_permissions_none_no_findings():
    """When FileRecord.permissions is None (Windows), the detector must return empty list."""
    from fsaudit.security.detectors.permissions import PermissionsDetector
    from fsaudit.security.config import SecurityConfig, Allowlist

    det = PermissionsDetector()
    record = _make_record(permissions=None)
    cfg = SecurityConfig(version=1, rules=[], allowlist=Allowlist())
    findings = det.scan([record], cfg)
    assert findings == []


def test_permissions_none_no_exception():
    """Calling scan() on a record with permissions=None must not raise."""
    from fsaudit.security.detectors.permissions import PermissionsDetector
    from fsaudit.security.config import SecurityConfig, Allowlist

    det = PermissionsDetector()
    # Mix of None and normal records — no crash expected
    records = [
        _make_record(permissions=None),
        _make_record(name="safe.py", permissions="644"),
        _make_record(permissions=None),
    ]
    cfg = SecurityConfig(version=1, rules=[], allowlist=Allowlist())
    findings = det.scan(records, cfg)  # Must not raise
    assert isinstance(findings, list)


# ---------------------------------------------------------------------------
# Finding metadata
# ---------------------------------------------------------------------------


def test_finding_detector_field_is_permissions():
    """All findings must have detector='permissions'."""
    from fsaudit.security.detectors.permissions import PermissionsDetector
    from fsaudit.security.config import SecurityConfig, Allowlist

    det = PermissionsDetector()
    record = _make_record(permissions="4777")
    cfg = SecurityConfig(version=1, rules=[], allowlist=Allowlist())
    findings = det.scan([record], cfg)
    assert findings, "Expected findings for 4777"
    assert all(f.detector == "permissions" for f in findings)


def test_line_no_is_none():
    """Permissions detector is metadata-only; all findings must have line_no=None."""
    from fsaudit.security.detectors.permissions import PermissionsDetector
    from fsaudit.security.config import SecurityConfig, Allowlist

    det = PermissionsDetector()
    record = _make_record(permissions="777")
    cfg = SecurityConfig(version=1, rules=[], allowlist=Allowlist())
    findings = det.scan([record], cfg)
    assert findings, "Expected findings for 777"
    assert all(f.line_no is None for f in findings)


def test_normal_permissions_no_findings():
    """A file with normal 644 permissions must produce zero findings."""
    from fsaudit.security.detectors.permissions import PermissionsDetector
    from fsaudit.security.config import SecurityConfig, Allowlist

    det = PermissionsDetector()
    record = _make_record(permissions="644")
    cfg = SecurityConfig(version=1, rules=[], allowlist=Allowlist())
    findings = det.scan([record], cfg)
    assert findings == []
