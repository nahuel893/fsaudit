"""Tests for fsaudit.security.models (T05)."""

import pytest
from datetime import datetime


# ---------------------------------------------------------------------------
# T05 — Security models tests
# ---------------------------------------------------------------------------


def test_severity_enum_values():
    """Severity enum must have critical, high, medium, low values."""
    from fsaudit.security.models import Severity

    assert Severity.CRITICAL == "critical"
    assert Severity.HIGH == "high"
    assert Severity.MEDIUM == "medium"
    assert Severity.LOW == "low"


def test_security_finding_frozen():
    """SecurityFinding must be a frozen dataclass (immutable)."""
    from fsaudit.security.models import SecurityFinding, Severity

    finding = SecurityFinding(
        path="/tmp/test.py",
        detector="secrets",
        rule_id="aws-access-key",
        severity=Severity.CRITICAL,
        line_no=42,
        match_context="AKIA_TEST_0000",
        created_at=datetime(2025, 1, 1),
    )
    with pytest.raises((AttributeError, TypeError)):
        finding.path = "/other"  # type: ignore[misc]


def test_match_context_truncated_at_60():
    """match_context longer than 60 chars must be truncated to 60 chars."""
    from fsaudit.security.models import SecurityFinding, Severity

    long_context = "A" * 80
    finding = SecurityFinding(
        path="/tmp/test.py",
        detector="secrets",
        rule_id="test",
        severity=Severity.LOW,
        line_no=1,
        match_context=long_context,
        created_at=datetime(2025, 1, 1),
    )
    assert len(finding.match_context) <= 60


def test_security_result_frozen():
    """SecurityResult must be a frozen dataclass (immutable)."""
    from fsaudit.security.models import SecurityResult

    result = SecurityResult(
        findings=[],
        security_score=100,
        rules_applied=[],
        files_scanned=0,
        files_skipped=0,
        duration_s=0.0,
    )
    with pytest.raises((AttributeError, TypeError)):
        result.security_score = 50  # type: ignore[misc]


def test_security_config_error_is_exception():
    """SecurityConfigError must be a subclass of Exception."""
    from fsaudit.security.models import SecurityConfigError

    err = SecurityConfigError("bad config")
    assert isinstance(err, Exception)
    assert "bad config" in str(err)
