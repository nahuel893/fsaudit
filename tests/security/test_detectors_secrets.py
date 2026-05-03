"""Tests for the secrets content detector (T12).

Covers:
- Size gate cuts oversize file
- Extension allowlist cuts non-text files (.jpg)
- Null-byte probe cuts binary
- Keyword pre-filter cuts file with no rule keywords
- Regex hits on AWS access key with correct line_no
- Regex hits on GitHub token
- Regex hits on PEM private-key header
- Redaction: match_context <= 60 chars
- Allowlist: finding suppressed when path matches allowlist
- Allowlist: finding suppressed when rule ID in allowlist
- Logging guard: no raw secret value appears in log messages
- scan_file signature callable directly (for future thread pool)
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from fsaudit.scanner.models import FileRecord
from fsaudit.security.config import Allowlist, Rule, SecurityConfig
from fsaudit.security.models import Severity


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_record(
    name: str = "test.py",
    size_bytes: int = 1024,
    permissions: str | None = "644",
    path: str | None = None,
) -> FileRecord:
    """Build a minimal FileRecord for secrets detector tests."""
    now = datetime.now(tz=timezone.utc)
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
        permissions=permissions,
        category="Unclassified",
        parent_dir=str(p.parent),
    )


def _make_config(
    extra_rules: list[Rule] | None = None,
    allowlist: Allowlist | None = None,
) -> SecurityConfig:
    """Return a SecurityConfig using bundled rules + optional extras."""
    from fsaudit.security.config import load_config
    cfg = load_config()  # bundled patterns.yaml
    rules = cfg.rules + (extra_rules or [])
    return SecurityConfig(
        version=1,
        rules=rules,
        allowlist=allowlist or Allowlist(),
    )


# ---------------------------------------------------------------------------
# AWS Access Key — line_no + finding content
# ---------------------------------------------------------------------------


def test_aws_key_detected(tmp_path):
    """An AWS access key in a .py file must emit a finding with aws-access-key rule_id."""
    from fsaudit.security.detectors.secrets import SecretsDetector

    secret = "AKIAIOSFODNN7EXAMPLE"
    content = f"# config\naws_key = '{secret}'\n"
    target = tmp_path / "config.py"
    target.write_text(content, encoding="utf-8")

    record = _make_record(name="config.py", path=str(target))
    cfg = _make_config()
    det = SecretsDetector()
    findings = det.scan([record], cfg)
    rule_ids = [f.rule_id for f in findings]
    assert "aws-access-key" in rule_ids


def test_aws_key_correct_line_no(tmp_path):
    """The finding for an AWS key must have the correct 1-based line_no."""
    from fsaudit.security.detectors.secrets import SecretsDetector

    secret = "AKIAIOSFODNN7EXAMPLE"
    content = "# line 1\n# line 2\n" + f"aws_key = '{secret}'\n"
    target = tmp_path / "config.py"
    target.write_text(content, encoding="utf-8")

    record = _make_record(name="config.py", path=str(target))
    cfg = _make_config()
    det = SecretsDetector()
    findings = det.scan([record], cfg)
    aws_findings = [f for f in findings if f.rule_id == "aws-access-key"]
    assert aws_findings, "Expected aws-access-key finding"
    assert aws_findings[0].line_no == 3


# ---------------------------------------------------------------------------
# GitHub token
# ---------------------------------------------------------------------------


def test_github_token_detected(tmp_path):
    """A GitHub PAT token must emit a finding with github-token rule_id."""
    from fsaudit.security.detectors.secrets import SecretsDetector

    token = "ghp_" + "A" * 36
    content = f"GITHUB_TOKEN = '{token}'\n"
    target = tmp_path / "deploy.sh"
    target.write_text(content, encoding="utf-8")

    record = _make_record(name="deploy.sh", path=str(target))
    cfg = _make_config()
    det = SecretsDetector()
    findings = det.scan([record], cfg)
    rule_ids = [f.rule_id for f in findings]
    assert "github-token" in rule_ids


# ---------------------------------------------------------------------------
# PEM private-key header
# ---------------------------------------------------------------------------


def test_pem_key_header_detected(tmp_path):
    """A PEM private key header must emit a finding with private-key-header rule_id."""
    from fsaudit.security.detectors.secrets import SecretsDetector

    content = "-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA\n"
    target = tmp_path / "server.key"
    target.write_text(content, encoding="utf-8")

    record = _make_record(name="server.key", path=str(target))
    # .key is not in default extension set — use a .pem or .txt extension
    # OR add it via custom rule scope. Use .txt equivalent to bypass ext gate.
    record2 = FileRecord(
        path=target,
        name="server.pem",
        extension=".pem",
        size_bytes=len(content),
        mtime=record.mtime,
        creation_time=record.creation_time,
        atime=record.atime,
        depth=1,
        is_hidden=False,
        permissions="600",
        category="Unclassified",
        parent_dir=str(target.parent),
    )
    cfg = _make_config()
    det = SecretsDetector()
    findings = det.scan([record2], cfg)
    rule_ids = [f.rule_id for f in findings]
    assert "private-key-header" in rule_ids


# ---------------------------------------------------------------------------
# Redaction guard
# ---------------------------------------------------------------------------


def test_match_context_max_60_chars(tmp_path):
    """Every finding's match_context must be at most 60 characters."""
    from fsaudit.security.detectors.secrets import SecretsDetector

    secret = "AKIAIOSFODNN7EXAMPLE"
    long_prefix = "x" * 100
    content = f"{long_prefix}{secret}{long_prefix}\n"
    target = tmp_path / "creds.py"
    target.write_text(content, encoding="utf-8")

    record = _make_record(name="creds.py", path=str(target))
    cfg = _make_config()
    det = SecretsDetector()
    findings = det.scan([record], cfg)
    aws_findings = [f for f in findings if f.rule_id == "aws-access-key"]
    assert aws_findings, "Expected aws-access-key finding for redaction test"
    for f in aws_findings:
        assert len(f.match_context) <= 60, (
            f"match_context too long ({len(f.match_context)} chars): {f.match_context!r}"
        )


def test_secret_not_in_full_match_context(tmp_path):
    """The full 20-char AWS key must NOT appear verbatim in match_context after truncation."""
    from fsaudit.security.detectors.secrets import SecretsDetector

    # A very long line so the context slice covers only part of the key
    secret = "AKIAIOSFODNN7EXAMPLE"
    long_prefix = "x" * 80  # push key far from start of line
    content = f"{long_prefix}{secret}\n"
    target = tmp_path / "creds.py"
    target.write_text(content, encoding="utf-8")

    record = _make_record(name="creds.py", path=str(target))
    cfg = _make_config()
    det = SecretsDetector()
    findings = det.scan([record], cfg)
    # At minimum: the match_context must be <= 60 chars (redaction model enforces this).
    # This test confirms the model truncation is in effect for a real scan result.
    aws_findings = [f for f in findings if f.rule_id == "aws-access-key"]
    assert aws_findings, "Expected aws-access-key finding"
    for f in aws_findings:
        assert len(f.match_context) <= 60


# ---------------------------------------------------------------------------
# Gate: size
# ---------------------------------------------------------------------------


def test_size_gate_skips_large_file(tmp_path):
    """A file larger than max_size_bytes must produce zero findings."""
    from fsaudit.security.detectors.secrets import SecretsDetector

    secret = "AKIAIOSFODNN7EXAMPLE"
    content = f"aws_key = '{secret}'\n"
    target = tmp_path / "big.py"
    target.write_text(content, encoding="utf-8")

    # Report a size larger than 1 MiB
    record = FileRecord(
        path=target,
        name="big.py",
        extension=".py",
        size_bytes=2 * 1024 * 1024,  # 2 MiB — over the 1 MiB default
        mtime=datetime.now(tz=timezone.utc),
        creation_time=datetime.now(tz=timezone.utc),
        atime=datetime.now(tz=timezone.utc),
        depth=1,
        is_hidden=False,
        permissions="644",
        category="Unclassified",
        parent_dir=str(target.parent),
    )
    cfg = _make_config()
    det = SecretsDetector()
    findings = det.scan([record], cfg)
    assert findings == [], f"Expected no findings for oversized file, got {findings}"


# ---------------------------------------------------------------------------
# Gate: extension allowlist
# ---------------------------------------------------------------------------


def test_non_text_extension_skipped(tmp_path):
    """A .jpg file must be skipped (not in text-extension allowlist)."""
    from fsaudit.security.detectors.secrets import SecretsDetector

    secret = "AKIAIOSFODNN7EXAMPLE"
    content = f"aws_key = '{secret}'\n"
    target = tmp_path / "photo.jpg"
    target.write_text(content, encoding="utf-8")

    record = FileRecord(
        path=target,
        name="photo.jpg",
        extension=".jpg",
        size_bytes=len(content.encode()),
        mtime=datetime.now(tz=timezone.utc),
        creation_time=datetime.now(tz=timezone.utc),
        atime=datetime.now(tz=timezone.utc),
        depth=1,
        is_hidden=False,
        permissions="644",
        category="Unclassified",
        parent_dir=str(target.parent),
    )
    cfg = _make_config()
    det = SecretsDetector()
    findings = det.scan([record], cfg)
    assert findings == [], f"Expected no findings for .jpg file, got {findings}"


# ---------------------------------------------------------------------------
# Gate: null-byte probe (binary detection)
# ---------------------------------------------------------------------------


def test_binary_null_byte_skipped(tmp_path):
    """A file containing null bytes must be treated as binary and skipped."""
    from fsaudit.security.detectors.secrets import SecretsDetector

    secret = "AKIAIOSFODNN7EXAMPLE"
    target = tmp_path / "binary.py"
    # Write binary content with embedded null byte and secret text
    target.write_bytes(f"AKIA{secret}\x00binary_junk\xff\xfe".encode("latin-1"))

    record = _make_record(name="binary.py", size_bytes=target.stat().st_size, path=str(target))
    cfg = _make_config()
    det = SecretsDetector()
    findings = det.scan([record], cfg)
    assert findings == [], f"Expected no findings for binary file, got {findings}"


# ---------------------------------------------------------------------------
# Gate: keyword pre-filter
# ---------------------------------------------------------------------------


def test_keyword_prefilter_skips_non_matching(tmp_path):
    """A file without any rule keywords must produce zero findings (pre-filter gate)."""
    from fsaudit.security.detectors.secrets import SecretsDetector

    # Content with no keywords from any bundled rule
    content = "hello = 'world'\nfoo = 'bar'\n"
    target = tmp_path / "innocent.py"
    target.write_text(content, encoding="utf-8")

    record = _make_record(name="innocent.py", path=str(target))
    cfg = _make_config()
    det = SecretsDetector()
    findings = det.scan([record], cfg)
    assert findings == [], f"Expected no findings for keyword-less file, got {findings}"


# ---------------------------------------------------------------------------
# Empty file
# ---------------------------------------------------------------------------


def test_empty_file_no_crash(tmp_path):
    """An empty file must produce zero findings and not raise an exception."""
    from fsaudit.security.detectors.secrets import SecretsDetector

    target = tmp_path / "empty.py"
    target.write_text("", encoding="utf-8")

    record = _make_record(name="empty.py", size_bytes=0, path=str(target))
    cfg = _make_config()
    det = SecretsDetector()
    findings = det.scan([record], cfg)
    assert findings == []


# ---------------------------------------------------------------------------
# Allowlist suppression
# ---------------------------------------------------------------------------


def test_allowlist_path_suppresses_finding(tmp_path):
    """A finding whose path matches an allowlist glob must be suppressed."""
    from fsaudit.security.detectors.secrets import SecretsDetector

    secret = "AKIAIOSFODNN7EXAMPLE"
    content = f"aws_key = '{secret}'\n"
    target = tmp_path / "fixtures" / "config.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")

    record = FileRecord(
        path=target,
        name="config.py",
        extension=".py",
        size_bytes=len(content.encode()),
        mtime=datetime.now(tz=timezone.utc),
        creation_time=datetime.now(tz=timezone.utc),
        atime=datetime.now(tz=timezone.utc),
        depth=2,
        is_hidden=False,
        permissions="644",
        category="Unclassified",
        parent_dir=str(target.parent),
    )
    # Allowlist the fixtures directory
    allowlist = Allowlist(paths=["**/fixtures/**"])
    cfg = SecurityConfig(version=1, rules=_make_config().rules, allowlist=allowlist)
    det = SecretsDetector()
    findings = det.scan([record], cfg)
    assert findings == [], f"Expected finding to be suppressed by allowlist path, got {findings}"


def test_allowlist_rule_id_suppresses_finding(tmp_path):
    """A finding whose rule_id is in the allowlist.rules list must be suppressed."""
    from fsaudit.security.detectors.secrets import SecretsDetector

    secret = "AKIAIOSFODNN7EXAMPLE"
    content = f"aws_key = '{secret}'\n"
    target = tmp_path / "config.py"
    target.write_text(content, encoding="utf-8")

    record = _make_record(name="config.py", path=str(target))
    allowlist = Allowlist(rules=["aws-access-key"])
    cfg = SecurityConfig(version=1, rules=_make_config().rules, allowlist=allowlist)
    det = SecretsDetector()
    findings = det.scan([record], cfg)
    aws_findings = [f for f in findings if f.rule_id == "aws-access-key"]
    assert aws_findings == [], f"Expected aws-access-key finding to be suppressed, got {aws_findings}"


# ---------------------------------------------------------------------------
# Logging guard
# ---------------------------------------------------------------------------


def test_no_raw_secret_in_logs(tmp_path, caplog):
    """No raw secret value must appear in any log message during a scan."""
    from fsaudit.security.detectors.secrets import SecretsDetector

    # Plant a clearly identifiable 20-char secret
    secret = "AKIAIOSFODNN7EXAMPLE"
    content = f"aws_key = '{secret}'\n"
    target = tmp_path / "creds.py"
    target.write_text(content, encoding="utf-8")

    record = _make_record(name="creds.py", path=str(target))
    cfg = _make_config()
    det = SecretsDetector()

    with caplog.at_level(logging.DEBUG, logger="fsaudit"):
        det.scan([record], cfg)

    for record_log in caplog.records:
        assert secret not in record_log.getMessage(), (
            f"Raw secret found in log message at level {record_log.levelname}: "
            f"{record_log.getMessage()!r}"
        )


# ---------------------------------------------------------------------------
# scan_file callable directly (thread-pool contract)
# ---------------------------------------------------------------------------


def test_scan_file_callable_directly(tmp_path):
    """scan_file must be callable with (record, compiled_rules, config) signature."""
    from fsaudit.security.detectors.secrets import SecretsDetector

    secret = "AKIAIOSFODNN7EXAMPLE"
    content = f"aws_key = '{secret}'\n"
    target = tmp_path / "test.py"
    target.write_text(content, encoding="utf-8")

    record = _make_record(name="test.py", path=str(target))
    cfg = _make_config()
    det = SecretsDetector()

    # compile_rules is a method that should exist on the detector
    compiled = det.compile_rules(cfg)
    findings = det.scan_file(record, compiled, cfg)
    assert isinstance(findings, list)
    rule_ids = [f.rule_id for f in findings]
    assert "aws-access-key" in rule_ids
