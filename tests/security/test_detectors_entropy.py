"""Tests for the entropy content detector (T13).

Covers:
- High-entropy random Base64 string is detected
- Low-entropy English text is NOT detected
- Token below min length is NOT detected
- Threshold tuning: raising threshold drops detection
- Redaction: context is char-class mask (not raw token)
- Allowlist suppression works
- Content gate: oversized file skipped
- Content gate: binary file (null-byte) skipped
- scan_file callable directly (for future thread pool)
- Configurable threshold and min-length via config
- Empty file does not crash
- All-whitespace line does not crash
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from pathlib import Path

import pytest

from fsaudit.scanner.models import FileRecord
from fsaudit.security.config import Allowlist, SecurityConfig
from fsaudit.security.models import Severity


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_record(
    name: str = "test.py",
    size_bytes: int = 1024,
    path: str | None = None,
    *,
    write_content: str | None = None,
    write_binary: bytes | None = None,
    tmp_path: Path | None = None,
) -> FileRecord:
    """Build a minimal FileRecord, optionally writing a real temp file."""
    from datetime import datetime, timezone

    now = datetime.now(tz=timezone.utc)
    if tmp_path is not None and (write_content is not None or write_binary is not None):
        p = tmp_path / name
        if write_binary is not None:
            p.write_bytes(write_binary)
        else:
            p.write_text(write_content, encoding="utf-8")
        size_bytes = p.stat().st_size
    else:
        p = Path(path or f"/tmp/{name}")

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
        category="Unclassified",
        parent_dir=str(p.parent),
    )


def _make_config(
    allowlist_paths: list[str] | None = None,
    allowlist_rules: list[str] | None = None,
) -> SecurityConfig:
    """Build a minimal SecurityConfig for entropy detector tests."""
    from fsaudit.security.config import Rule

    allowlist = Allowlist(
        paths=allowlist_paths or [],
        rules=allowlist_rules or [],
        content=[],
    )
    # A placeholder rule so SecurityConfig is valid; entropy is keyword-agnostic
    rule = Rule(
        id="placeholder",
        description="placeholder",
        severity="low",
        regex=r"PLACEHOLDER",
        keywords=["PLACEHOLDER"],
    )
    return SecurityConfig(version=1, rules=[rule], allowlist=allowlist)


# A 32-char random-looking Base64 string with high entropy
_HIGH_ENTROPY_TOKEN = "aB3kR7mNpQxZ2vLwYtUoIeHsGcFdJbAK"  # > 4.5 bits/char
# A short repeated-pattern string
_LOW_ENTROPY_TOKEN = "aaaaaaaaaaaaaaaaaaaaaaaaa"  # very low entropy


# ---------------------------------------------------------------------------
# T13 Tests
# ---------------------------------------------------------------------------


class TestEntropyDetectorHighEntropy:
    """High-entropy token is detected."""

    def test_high_entropy_base64_detected(self, tmp_path: Path) -> None:
        """A line with a high-entropy token should emit a SecurityFinding."""
        from fsaudit.security.detectors.entropy import EntropyDetector

        content = f"api_secret={_HIGH_ENTROPY_TOKEN}\n"
        record = _make_record(
            tmp_path=tmp_path,
            write_content=content,
        )
        config = _make_config()
        detector = EntropyDetector()
        findings = detector.scan_file(record, None, config)
        assert len(findings) >= 1
        assert findings[0].detector == "entropy"
        assert findings[0].severity == Severity.MEDIUM

    def test_returns_list_of_findings(self, tmp_path: Path) -> None:
        """scan_file always returns a list (never None)."""
        from fsaudit.security.detectors.entropy import EntropyDetector

        record = _make_record(tmp_path=tmp_path, write_content="hello world\n")
        config = _make_config()
        detector = EntropyDetector()
        result = detector.scan_file(record, None, config)
        assert isinstance(result, list)


class TestEntropyDetectorLowEntropy:
    """Low-entropy or short tokens are NOT detected."""

    def test_low_entropy_ignored(self, tmp_path: Path) -> None:
        """Low-entropy token must not produce a finding."""
        from fsaudit.security.detectors.entropy import EntropyDetector

        content = f"api_secret={_LOW_ENTROPY_TOKEN}\n"
        record = _make_record(tmp_path=tmp_path, write_content=content)
        config = _make_config()
        detector = EntropyDetector()
        findings = detector.scan_file(record, None, config)
        assert findings == []

    def test_short_token_ignored(self, tmp_path: Path) -> None:
        """Token shorter than min_length (20 chars) must be skipped."""
        from fsaudit.security.detectors.entropy import EntropyDetector

        # 19 chars — one below min_length default of 20.
        # Use "value: <token>" so colon+space keeps the token isolated from
        # surrounding text (colon and space are not in the token regex charset).
        short_token = "aB3kR7mNpQxZ2vLwYtU"
        content = f"value: {short_token}\n"
        record = _make_record(tmp_path=tmp_path, write_content=content)
        config = _make_config()
        detector = EntropyDetector()
        findings = detector.scan_file(record, None, config)
        assert findings == []

    def test_password_changeme_no_finding(self, tmp_path: Path) -> None:
        """Low-entropy common password strings should not fire."""
        from fsaudit.security.detectors.entropy import EntropyDetector

        content = "password=changemechangemechangeme\n"
        record = _make_record(tmp_path=tmp_path, write_content=content)
        config = _make_config()
        detector = EntropyDetector()
        findings = detector.scan_file(record, None, config)
        assert findings == []


class TestEntropyDetectorThreshold:
    """Threshold tunability."""

    def test_threshold_boundary_exactly_45(self, tmp_path: Path) -> None:
        """Raising threshold above token's entropy drops the detection."""
        from fsaudit.security.detectors.entropy import EntropyDetector

        content = f"api_secret={_HIGH_ENTROPY_TOKEN}\n"
        record = _make_record(tmp_path=tmp_path, write_content=content)
        config = _make_config()
        detector = EntropyDetector()
        # With very high threshold, the same token should NOT fire
        findings = detector.scan_file(record, None, config, entropy_threshold=9.0)
        assert findings == []

    def test_low_threshold_detects_more(self, tmp_path: Path) -> None:
        """Lowering threshold should detect tokens with moderate entropy."""
        from fsaudit.security.detectors.entropy import EntropyDetector

        # A moderately entropic but >20-char token
        token = "abcdefghijklmnopqrst"  # 20 chars, uniform alphabet
        content = f"value={token}\n"
        record = _make_record(tmp_path=tmp_path, write_content=content)
        config = _make_config()
        detector = EntropyDetector()
        # At threshold=1.0 (very low), should detect
        findings = detector.scan_file(record, None, config, entropy_threshold=1.0)
        assert len(findings) >= 1


class TestEntropyDetectorRedaction:
    """match_context must be char-class mask, not raw token."""

    def test_context_redacted_as_char_class_mask(self, tmp_path: Path) -> None:
        """match_context must contain only L, D, S chars (class mask), not raw token."""
        from fsaudit.security.detectors.entropy import EntropyDetector

        content = f"key={_HIGH_ENTROPY_TOKEN}\n"
        record = _make_record(tmp_path=tmp_path, write_content=content)
        config = _make_config()
        detector = EntropyDetector()
        findings = detector.scan_file(record, None, config)
        assert len(findings) >= 1
        ctx = findings[0].match_context
        # Raw token must NOT appear in context
        assert _HIGH_ENTROPY_TOKEN not in ctx
        # match_context must only contain L, D, S chars (class mask) and = or similar
        # More specifically: no lowercase letters from the token (since token has uppercase/lowercase mixed)
        # and the context is a class-mask representation
        # Verify it's a mask: each char is L, D, or S
        allowed_mask_chars = set("LDS")
        # Allow some surrounding characters (the mask represents the token)
        for ch in ctx:
            assert ch in allowed_mask_chars, f"Unexpected char in mask context: {ch!r}"

    def test_context_max_60_chars(self, tmp_path: Path) -> None:
        """match_context must never exceed 60 characters."""
        from fsaudit.security.detectors.entropy import EntropyDetector

        # Very long high-entropy string
        long_token = "aB3kR7mNpQxZ2vLwYtUoIeHsGcFdJbAK" * 3  # 96 chars
        content = f"key={long_token}\n"
        record = _make_record(tmp_path=tmp_path, write_content=content)
        config = _make_config()
        detector = EntropyDetector()
        findings = detector.scan_file(record, None, config)
        if findings:
            assert len(findings[0].match_context) <= 60


class TestEntropyDetectorAllowlist:
    """Allowlist suppression."""

    def test_allowlist_path_suppresses_finding(self, tmp_path: Path) -> None:
        """Finding for an allowlisted path must be suppressed."""
        from fsaudit.security.detectors.entropy import EntropyDetector

        content = f"api_secret={_HIGH_ENTROPY_TOKEN}\n"
        record = _make_record(
            name="secret.py",
            tmp_path=tmp_path,
            write_content=content,
        )
        config = _make_config(allowlist_paths=["**/tmp/**"])
        detector = EntropyDetector()
        findings = detector.scan_file(record, None, config)
        assert findings == []

    def test_allowlist_rule_suppresses_finding(self, tmp_path: Path) -> None:
        """Finding suppressed when rule_id in allowlist.rules."""
        from fsaudit.security.detectors.entropy import EntropyDetector

        content = f"api_secret={_HIGH_ENTROPY_TOKEN}\n"
        record = _make_record(tmp_path=tmp_path, write_content=content)
        config = _make_config(allowlist_rules=["entropy-high"])
        detector = EntropyDetector()
        findings = detector.scan_file(record, None, config)
        assert findings == []


class TestEntropyDetectorContentGate:
    """Content gates: size and binary."""

    def test_oversized_file_skipped(self, tmp_path: Path) -> None:
        """File larger than max_size_bytes must be skipped (zero findings)."""
        from fsaudit.security.detectors.entropy import EntropyDetector

        content = f"api_secret={_HIGH_ENTROPY_TOKEN}\n"
        record = _make_record(tmp_path=tmp_path, write_content=content)
        # Override size_bytes to simulate an oversized file
        import dataclasses

        oversized_record = dataclasses.replace(record, size_bytes=2_000_000)
        config = _make_config()
        detector = EntropyDetector()
        findings = detector.scan_file(oversized_record, None, config, max_size_bytes=1_048_576)
        assert findings == []

    def test_binary_file_skipped(self, tmp_path: Path) -> None:
        """File with null bytes (binary) must be skipped."""
        from fsaudit.security.detectors.entropy import EntropyDetector

        binary_content = b"aB3kR7mNpQxZ2vLwYtUoIeHsGcFdJbAK\x00some binary data"
        record = _make_record(
            tmp_path=tmp_path,
            write_binary=binary_content,
        )
        config = _make_config()
        detector = EntropyDetector()
        findings = detector.scan_file(record, None, config)
        assert findings == []


class TestEntropyDetectorEdgeCases:
    """Edge cases."""

    def test_empty_file_no_crash(self, tmp_path: Path) -> None:
        """Empty file must return empty findings without raising."""
        from fsaudit.security.detectors.entropy import EntropyDetector

        record = _make_record(tmp_path=tmp_path, write_content="")
        config = _make_config()
        detector = EntropyDetector()
        findings = detector.scan_file(record, None, config)
        assert findings == []

    def test_all_whitespace_line_no_crash(self, tmp_path: Path) -> None:
        """Line with only whitespace must not crash."""
        from fsaudit.security.detectors.entropy import EntropyDetector

        record = _make_record(tmp_path=tmp_path, write_content="   \t  \n   \n")
        config = _make_config()
        detector = EntropyDetector()
        findings = detector.scan_file(record, None, config)
        assert findings == []

    def test_scan_file_callable_directly(self, tmp_path: Path) -> None:
        """scan_file is directly callable (for future ThreadPoolExecutor)."""
        from fsaudit.security.detectors.entropy import EntropyDetector

        content = f"api_secret={_HIGH_ENTROPY_TOKEN}\n"
        record = _make_record(tmp_path=tmp_path, write_content=content)
        config = _make_config()
        detector = EntropyDetector()
        # Call directly (not via scan) — must work
        result = detector.scan_file(record, None, config)
        assert isinstance(result, list)

    def test_line_no_populated(self, tmp_path: Path) -> None:
        """line_no on findings must be a positive integer (1-based)."""
        from fsaudit.security.detectors.entropy import EntropyDetector

        content = "first line\n" + f"api_secret={_HIGH_ENTROPY_TOKEN}\n"
        record = _make_record(tmp_path=tmp_path, write_content=content)
        config = _make_config()
        detector = EntropyDetector()
        findings = detector.scan_file(record, None, config)
        assert len(findings) >= 1
        assert findings[0].line_no == 2
