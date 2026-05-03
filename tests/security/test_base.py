"""Tests for fsaudit.security.detectors.base (T06)."""

import pytest


# ---------------------------------------------------------------------------
# T06 — Detector protocol and ABC tests
# ---------------------------------------------------------------------------


def test_detector_protocol_runtime_checkable():
    """Detector protocol must be runtime-checkable via isinstance()."""
    from fsaudit.security.detectors.base import Detector

    class FakeDetector:
        name = "fake"

        def scan(self, records, config):
            return []

    fd = FakeDetector()
    assert isinstance(fd, Detector)


def test_metadata_detector_is_abstract():
    """MetadataDetector must be abstract — cannot be instantiated directly."""
    from fsaudit.security.detectors.base import MetadataDetector

    with pytest.raises(TypeError):
        MetadataDetector()  # type: ignore[abstract]


def test_content_detector_has_scan_file():
    """ContentDetector must expose an abstract scan_file() method."""
    from fsaudit.security.detectors.base import ContentDetector
    import inspect

    # scan_file must exist as an abstract method
    members = dict(inspect.getmembers(ContentDetector))
    assert "scan_file" in members, "ContentDetector must define scan_file()"

    # Instantiation without implementing scan_file must fail
    with pytest.raises(TypeError):
        ContentDetector()  # type: ignore[abstract]
