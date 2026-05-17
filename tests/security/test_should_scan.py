"""Tests for ContentDetector.should_scan() — cheap pre-filter contract.

should_scan(record) returns True if the detector might emit findings for the
record based on metadata alone (no file I/O). The pipeline orchestrator uses
this to skip submitting no-op futures to the ThreadPoolExecutor.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from fsaudit.scanner.models import FileRecord
from fsaudit.security.detectors.base import ContentDetector
from fsaudit.security.detectors.entropy import EntropyDetector
from fsaudit.security.detectors.secrets import (
    _DEFAULT_MAX_SIZE_BYTES,
    SecretsDetector,
)


def _make_record(
    name: str = "test.py",
    size_bytes: int = 1024,
) -> FileRecord:
    now = datetime.now(tz=timezone.utc)
    p = Path(f"/tmp/{name}")
    return FileRecord(
        path=p,
        name=name,
        extension=Path(name).suffix.lower(),
        size_bytes=size_bytes,
        mtime=now,
        creation_time=now,
        atime=now,
        depth=1,
        is_hidden=False,
        permissions="644",
        category="Codigo",
        parent_dir="/tmp",
    )


class TestContentDetectorContract:
    """should_scan exists on the ContentDetector base."""

    def test_should_scan_is_attribute_of_base(self) -> None:
        assert hasattr(ContentDetector, "should_scan")


class TestSecretsShouldScan:
    """SecretsDetector.should_scan applies size + extension gates."""

    def test_accepts_small_text_file(self) -> None:
        det = SecretsDetector()
        rec = _make_record("config.yaml", size_bytes=512)
        assert det.should_scan(rec) is True

    def test_rejects_oversize_file(self) -> None:
        det = SecretsDetector()
        rec = _make_record("huge.py", size_bytes=_DEFAULT_MAX_SIZE_BYTES + 1)
        assert det.should_scan(rec) is False

    def test_rejects_binary_extension(self) -> None:
        det = SecretsDetector()
        rec = _make_record("image.jpg", size_bytes=512)
        assert det.should_scan(rec) is False

    def test_extension_match_is_case_insensitive(self) -> None:
        det = SecretsDetector()
        rec = _make_record("README.MD", size_bytes=512)
        # Note: scanner normalizes extension to lowercase already, but
        # should_scan must not assume the caller did so.
        assert det.should_scan(rec) is True


class TestEntropyShouldScan:
    """EntropyDetector.should_scan applies size + extension gates."""

    def test_accepts_small_text_file(self) -> None:
        det = EntropyDetector()
        rec = _make_record("secrets.env", size_bytes=512)
        assert det.should_scan(rec) is True

    def test_rejects_oversize_file(self) -> None:
        det = EntropyDetector()
        rec = _make_record("huge.py", size_bytes=_DEFAULT_MAX_SIZE_BYTES + 1)
        assert det.should_scan(rec) is False

    def test_rejects_binary_extension(self) -> None:
        det = EntropyDetector()
        rec = _make_record("photo.png", size_bytes=512)
        assert det.should_scan(rec) is False
