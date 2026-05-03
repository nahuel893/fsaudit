"""Tests for the security scorer (T14).

Covers:
- Empty findings → score 100
- Single low-severity finding → 99
- Multiple low (10 findings) → 90 (10×1, no cap hit)
- Many low (20 findings) → 90 (cap at 10 — flood-resistance)
- Single critical → 75 (100 − 25)
- Critical bucket cap (3 critical = 75 capped at 40) → 60 (100 − 40)
- Mixed severities respect each cap independently
- Score never goes below 0

Weights:  {critical: 25, high: 10, medium: 4, low: 1}
Caps:     {critical: 40, high: 30, medium: 20, low: 10}
Formula:  score = max(0, 100 - sum(capped_penalty_per_severity))
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from fsaudit.security.models import SecurityFinding, Severity


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_finding(severity: Severity, rule_id: str = "test-rule") -> SecurityFinding:
    """Build a minimal SecurityFinding with the given severity."""
    now = datetime.now(tz=timezone.utc)
    return SecurityFinding(
        path="/tmp/test.py",
        detector="test",
        rule_id=rule_id,
        severity=severity,
        line_no=1,
        match_context="placeholder",
        created_at=now,
    )


def _low(n: int = 1) -> list[SecurityFinding]:
    return [_make_finding(Severity.LOW) for _ in range(n)]


def _medium(n: int = 1) -> list[SecurityFinding]:
    return [_make_finding(Severity.MEDIUM) for _ in range(n)]


def _high(n: int = 1) -> list[SecurityFinding]:
    return [_make_finding(Severity.HIGH) for _ in range(n)]


def _critical(n: int = 1) -> list[SecurityFinding]:
    return [_make_finding(Severity.CRITICAL) for _ in range(n)]


# ---------------------------------------------------------------------------
# T14 Tests
# ---------------------------------------------------------------------------


class TestScorerBaseline:
    """Baseline cases."""

    def test_no_findings_scores_100(self) -> None:
        """Empty finding list must return score of 100."""
        from fsaudit.security.scorer import compute_security_score

        score = compute_security_score([])
        assert score == 100

    def test_returns_int(self) -> None:
        """Return type must be int."""
        from fsaudit.security.scorer import compute_security_score

        score = compute_security_score([])
        assert isinstance(score, int)


class TestScorerLowSeverity:
    """Low-severity findings and flood resistance."""

    def test_single_low_severity_finding(self) -> None:
        """One LOW finding reduces score by 1 → 99."""
        from fsaudit.security.scorer import compute_security_score

        score = compute_security_score(_low(1))
        assert score == 99

    def test_ten_low_findings_no_cap(self) -> None:
        """10 LOW findings × 1 = 10 penalty, no cap hit → score 90."""
        from fsaudit.security.scorer import compute_security_score

        score = compute_security_score(_low(10))
        assert score == 90

    def test_twenty_low_findings_capped_at_10(self) -> None:
        """20 LOW findings would be 20 penalty but cap is 10 → score still 90."""
        from fsaudit.security.scorer import compute_security_score

        score = compute_security_score(_low(20))
        assert score == 90  # cap kicks in at 10 total penalty for LOW

    def test_hundred_low_findings_still_capped(self) -> None:
        """100 LOW findings still capped at 10 → score 90."""
        from fsaudit.security.scorer import compute_security_score

        score = compute_security_score(_low(100))
        assert score == 90


class TestScorerHighSeverity:
    """HIGH severity findings and cap."""

    def test_single_high_finding(self) -> None:
        """One HIGH finding reduces score by 10 → 90."""
        from fsaudit.security.scorer import compute_security_score

        score = compute_security_score(_high(1))
        assert score == 90

    def test_three_high_findings(self) -> None:
        """3 HIGH findings × 10 = 30 penalty, at the cap → score 70."""
        from fsaudit.security.scorer import compute_security_score

        score = compute_security_score(_high(3))
        assert score == 70

    def test_high_cap_at_30(self) -> None:
        """4 HIGH findings would be 40 but cap is 30 → score still 70."""
        from fsaudit.security.scorer import compute_security_score

        score = compute_security_score(_high(4))
        assert score == 70  # capped at 30


class TestScorerMediumSeverity:
    """MEDIUM severity findings and cap."""

    def test_single_medium_finding(self) -> None:
        """One MEDIUM finding reduces score by 4 → 96."""
        from fsaudit.security.scorer import compute_security_score

        score = compute_security_score(_medium(1))
        assert score == 96

    def test_five_medium_findings(self) -> None:
        """5 MEDIUM findings × 4 = 20 penalty, at the cap → score 80."""
        from fsaudit.security.scorer import compute_security_score

        score = compute_security_score(_medium(5))
        assert score == 80

    def test_medium_cap_at_20(self) -> None:
        """6 MEDIUM findings would be 24 but cap is 20 → score still 80."""
        from fsaudit.security.scorer import compute_security_score

        score = compute_security_score(_medium(6))
        assert score == 80  # capped at 20


class TestScorerCriticalSeverity:
    """CRITICAL severity findings and cap."""

    def test_single_critical_finding(self) -> None:
        """One CRITICAL finding reduces score by 25 → 75."""
        from fsaudit.security.scorer import compute_security_score

        score = compute_security_score(_critical(1))
        assert score == 75

    def test_two_critical_findings(self) -> None:
        """2 CRITICAL findings × 25 = 50, but cap is 40 → penalty capped at 40 → score 60."""
        from fsaudit.security.scorer import compute_security_score

        score = compute_security_score(_critical(2))
        assert score == 60  # min(2×25, 40) = 40 penalty

    def test_critical_cap_at_40(self) -> None:
        """3 CRITICAL findings × 25 = 75, but cap is 40 → score 60."""
        from fsaudit.security.scorer import compute_security_score

        score = compute_security_score(_critical(3))
        assert score == 60  # capped at 40


class TestScorerFloorAndMixed:
    """Score floor and mixed severity independence."""

    def test_score_never_below_zero(self) -> None:
        """Combined penalty cannot push score below 0."""
        from fsaudit.security.scorer import compute_security_score

        # Max possible penalty: 40+30+20+10 = 100 (capped)
        findings = _critical(10) + _high(10) + _medium(10) + _low(100)
        score = compute_security_score(findings)
        assert score == 0

    def test_mixed_severities_each_cap_independent(self) -> None:
        """Each severity bucket cap is applied independently.

        1 CRITICAL (25) + 1 HIGH (10) + 1 MEDIUM (4) + 1 LOW (1) = 40 penalty → 60.
        No cap is hit since each is below its bucket cap.
        """
        from fsaudit.security.scorer import compute_security_score

        findings = _critical(1) + _high(1) + _medium(1) + _low(1)
        score = compute_security_score(findings)
        assert score == 60  # 100 - (25 + 10 + 4 + 1)

    def test_mixed_with_caps(self) -> None:
        """Critical cap + high cap fired simultaneously: 40 + 30 = 70 penalty → 30."""
        from fsaudit.security.scorer import compute_security_score

        # critical: 3×25=75 → capped 40; high: 4×10=40 → capped 30
        findings = _critical(3) + _high(4)
        score = compute_security_score(findings)
        assert score == 30  # 100 - (40 + 30)
