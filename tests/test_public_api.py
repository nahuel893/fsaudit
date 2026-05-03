"""Tests for top-level fsaudit package re-exports — security symbols (T19).

Verifies that security symbols are importable from the top-level `fsaudit`
namespace and listed in `__all__`.
"""

from __future__ import annotations

import pytest


class TestSecuritySymbolsImportable:
    """Security types importable from top-level fsaudit package."""

    def test_security_result_importable_from_fsaudit(self) -> None:
        from fsaudit import SecurityResult  # noqa: F401
        assert SecurityResult is not None

    def test_security_finding_importable_from_fsaudit(self) -> None:
        from fsaudit import SecurityFinding  # noqa: F401
        assert SecurityFinding is not None

    def test_severity_importable_from_fsaudit(self) -> None:
        from fsaudit import Severity  # noqa: F401
        assert Severity is not None

    def test_security_config_error_importable_from_fsaudit(self) -> None:
        from fsaudit import SecurityConfigError  # noqa: F401
        assert SecurityConfigError is not None

    def test_run_security_scan_importable_from_fsaudit(self) -> None:
        from fsaudit import run_security_scan  # noqa: F401
        assert callable(run_security_scan)


class TestSecuritySymbolsInAll:
    """Security symbols are listed in fsaudit.__all__."""

    def test_security_result_in_all(self) -> None:
        import fsaudit
        assert "SecurityResult" in fsaudit.__all__

    def test_security_finding_in_all(self) -> None:
        import fsaudit
        assert "SecurityFinding" in fsaudit.__all__

    def test_severity_in_all(self) -> None:
        import fsaudit
        assert "Severity" in fsaudit.__all__

    def test_run_security_scan_in_all(self) -> None:
        import fsaudit
        assert "run_security_scan" in fsaudit.__all__


class TestSecuritySymbolsCorrectTypes:
    """Imported symbols are the same objects as in fsaudit.security."""

    def test_security_result_same_class(self) -> None:
        import fsaudit
        from fsaudit.security import SecurityResult
        assert fsaudit.SecurityResult is SecurityResult

    def test_severity_same_class(self) -> None:
        import fsaudit
        from fsaudit.security import Severity
        assert fsaudit.Severity is Severity
