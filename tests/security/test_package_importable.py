"""Tests for fsaudit.security package importability (T03)."""


def test_security_package_importable():
    """fsaudit.security must be importable as a package."""
    import fsaudit.security  # noqa: F401


def test_security_detectors_package_importable():
    """fsaudit.security.detectors must be importable as a sub-package."""
    import fsaudit.security.detectors  # noqa: F401
