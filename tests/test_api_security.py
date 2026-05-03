"""Tests for AuditResult.security field + audit() security kwargs (T17).

Covers:
- audit(security_scan=False) → result.security is None (no regression)
- audit(security_scan=True) → result.security is SecurityResult
- planted secret in fixture tree → security finding present
- privacy notice printed to stdout when security_scan=True
- privacy notice NOT printed when security_scan=False
- AuditResult has a security field
"""

from __future__ import annotations

import sys
from io import StringIO
from pathlib import Path

import pytest

from fsaudit.api import AuditResult, audit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

GOLDEN_TREE = Path(__file__).parent / "fixtures" / "golden" / "sample_tree"


def _make_secret_tree(tmp_path: Path) -> Path:
    """Create a small tree with one file containing a planted AWS key."""
    (tmp_path / "creds.py").write_text(
        "key = 'AKIAIOSFODNN7EXAMPLE12345'\n"
    )
    (tmp_path / "clean.py").write_text("x = 1\n")
    return tmp_path


# ---------------------------------------------------------------------------
# T17 — security field on AuditResult
# ---------------------------------------------------------------------------


class TestAuditResultSecurityField:
    """AuditResult must have a security field."""

    def test_audit_result_has_security_attribute(self) -> None:
        result = audit(GOLDEN_TREE, format=None)
        assert hasattr(result, "security")

    def test_security_field_is_none_when_flag_off(self) -> None:
        result = audit(GOLDEN_TREE, format=None)
        assert result.security is None

    def test_security_field_is_none_by_default(self) -> None:
        result = audit(GOLDEN_TREE, format=None, security_scan=False)
        assert result.security is None


class TestAuditSecurityScanFlagOff:
    """audit(security_scan=False) is behaviorally identical to v0.10.0."""

    def test_no_security_result_when_flag_off(self) -> None:
        result = audit(GOLDEN_TREE, format=None, security_scan=False)
        assert result.security is None

    def test_health_score_unchanged_when_flag_off(self) -> None:
        r1 = audit(GOLDEN_TREE, format=None, security_scan=False)
        r2 = audit(GOLDEN_TREE, format=None)
        assert r1.health_score == r2.health_score

    def test_total_files_unchanged_when_flag_off(self) -> None:
        result = audit(GOLDEN_TREE, format=None, security_scan=False)
        assert result.total_files == 5


class TestAuditSecurityScanFlagOn:
    """audit(security_scan=True) populates AuditResult.security."""

    def test_security_result_not_none_when_flag_on(self, tmp_path: Path) -> None:
        tree = _make_secret_tree(tmp_path)
        result = audit(tree, format=None, security_scan=True)
        assert result.security is not None

    def test_security_is_security_result_instance(self, tmp_path: Path) -> None:
        from fsaudit.security import SecurityResult
        tree = _make_secret_tree(tmp_path)
        result = audit(tree, format=None, security_scan=True)
        assert isinstance(result.security, SecurityResult)

    def test_planted_secret_found_in_findings(self, tmp_path: Path) -> None:
        tree = _make_secret_tree(tmp_path)
        result = audit(tree, format=None, security_scan=True)
        assert result.security is not None
        rule_ids = [f.rule_id for f in result.security.findings]
        assert "aws-access-key" in rule_ids

    def test_security_score_below_100_when_secret_present(self, tmp_path: Path) -> None:
        tree = _make_secret_tree(tmp_path)
        result = audit(tree, format=None, security_scan=True)
        assert result.security is not None
        assert result.security.security_score < 100


class TestAuditPrivacyNotice:
    """Privacy notice printed to stdout when security_scan=True, not otherwise."""

    def test_privacy_notice_printed_when_flag_on(self, tmp_path: Path, capsys) -> None:
        tree = _make_secret_tree(tmp_path)
        audit(tree, format=None, security_scan=True)
        captured = capsys.readouterr()
        # Privacy notice should appear in stdout
        assert "security" in captured.out.lower() or "privacy" in captured.out.lower() or "content" in captured.out.lower()

    def test_privacy_notice_not_printed_when_flag_off(self, capsys) -> None:
        audit(GOLDEN_TREE, format=None, security_scan=False)
        captured = capsys.readouterr()
        # No security-specific notice should appear
        assert "security scan" not in captured.out.lower()
