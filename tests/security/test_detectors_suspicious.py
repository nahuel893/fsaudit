"""Tests for the suspicious-files metadata detector (T10)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from fsaudit.scanner.models import FileRecord
from fsaudit.security.models import Severity


def _make_record(
    name: str,
    extension: str | None = None,
    is_hidden: bool = False,
    permissions: str | None = "644",
) -> FileRecord:
    """Build a minimal FileRecord for detector tests."""
    ext = extension if extension is not None else (Path(name).suffix.lower())
    now = datetime.now(tz=timezone.utc)
    return FileRecord(
        path=Path(f"/tmp/{name}"),
        name=name,
        extension=ext,
        size_bytes=1024,
        mtime=now,
        creation_time=now,
        atime=now,
        depth=1,
        is_hidden=is_hidden,
        permissions=permissions,
        category="Unclassified",
        parent_dir="/tmp",
    )


# ---------------------------------------------------------------------------
# Double-extension
# ---------------------------------------------------------------------------

def test_double_extension_detected():
    """A file with a double extension like .pdf.exe must emit a finding."""
    from fsaudit.security.detectors.suspicious import SuspiciousFilesDetector
    from fsaudit.security.config import SecurityConfig, Allowlist
    det = SuspiciousFilesDetector()
    record = _make_record("report.pdf.exe", extension=".exe")
    cfg = SecurityConfig(version=1, rules=[], allowlist=Allowlist())
    findings = det.scan([record], cfg)
    rule_ids = [f.rule_id for f in findings]
    assert "double-extension" in rule_ids


def test_double_extension_only_one_ext_not_flagged():
    """A normal .exe file (no double extension) must NOT trigger double-extension rule."""
    from fsaudit.security.detectors.suspicious import SuspiciousFilesDetector
    from fsaudit.security.config import SecurityConfig, Allowlist
    det = SuspiciousFilesDetector()
    record = _make_record("installer.exe", extension=".exe")
    cfg = SecurityConfig(version=1, rules=[], allowlist=Allowlist())
    findings = det.scan([record], cfg)
    double_ext_findings = [f for f in findings if f.rule_id == "double-extension"]
    assert len(double_ext_findings) == 0


# ---------------------------------------------------------------------------
# Macro-enabled Office
# ---------------------------------------------------------------------------

def test_macro_office_xlsm():
    """A .xlsm file must emit a macro-enabled-office finding."""
    from fsaudit.security.detectors.suspicious import SuspiciousFilesDetector
    from fsaudit.security.config import SecurityConfig, Allowlist
    det = SuspiciousFilesDetector()
    record = _make_record("budget.xlsm", extension=".xlsm")
    cfg = SecurityConfig(version=1, rules=[], allowlist=Allowlist())
    findings = det.scan([record], cfg)
    rule_ids = [f.rule_id for f in findings]
    assert "macro-enabled-office" in rule_ids


def test_macro_office_docm():
    """A .docm file must emit a macro-enabled-office finding."""
    from fsaudit.security.detectors.suspicious import SuspiciousFilesDetector
    from fsaudit.security.config import SecurityConfig, Allowlist
    det = SuspiciousFilesDetector()
    record = _make_record("contract.docm", extension=".docm")
    cfg = SecurityConfig(version=1, rules=[], allowlist=Allowlist())
    findings = det.scan([record], cfg)
    rule_ids = [f.rule_id for f in findings]
    assert "macro-enabled-office" in rule_ids


def test_macro_office_pptm():
    """A .pptm file must emit a macro-enabled-office finding."""
    from fsaudit.security.detectors.suspicious import SuspiciousFilesDetector
    from fsaudit.security.config import SecurityConfig, Allowlist
    det = SuspiciousFilesDetector()
    record = _make_record("slides.pptm", extension=".pptm")
    cfg = SecurityConfig(version=1, rules=[], allowlist=Allowlist())
    findings = det.scan([record], cfg)
    rule_ids = [f.rule_id for f in findings]
    assert "macro-enabled-office" in rule_ids


# ---------------------------------------------------------------------------
# Hidden executable
# ---------------------------------------------------------------------------

def test_hidden_executable_detected():
    """A hidden file with an executable extension must emit a finding."""
    from fsaudit.security.detectors.suspicious import SuspiciousFilesDetector
    from fsaudit.security.config import SecurityConfig, Allowlist
    det = SuspiciousFilesDetector()
    record = _make_record(".hidden_tool.exe", extension=".exe", is_hidden=True)
    cfg = SecurityConfig(version=1, rules=[], allowlist=Allowlist())
    findings = det.scan([record], cfg)
    rule_ids = [f.rule_id for f in findings]
    assert "hidden-executable" in rule_ids


def test_hidden_pdf_not_flagged():
    """A hidden PDF (non-executable extension) must NOT trigger hidden-executable."""
    from fsaudit.security.detectors.suspicious import SuspiciousFilesDetector
    from fsaudit.security.config import SecurityConfig, Allowlist
    det = SuspiciousFilesDetector()
    record = _make_record(".hidden_doc.pdf", extension=".pdf", is_hidden=True)
    cfg = SecurityConfig(version=1, rules=[], allowlist=Allowlist())
    findings = det.scan([record], cfg)
    hidden_exe_findings = [f for f in findings if f.rule_id == "hidden-executable"]
    assert len(hidden_exe_findings) == 0


def test_non_hidden_exe_not_flagged():
    """A non-hidden .exe file must NOT trigger hidden-executable."""
    from fsaudit.security.detectors.suspicious import SuspiciousFilesDetector
    from fsaudit.security.config import SecurityConfig, Allowlist
    det = SuspiciousFilesDetector()
    record = _make_record("tool.exe", extension=".exe", is_hidden=False)
    cfg = SecurityConfig(version=1, rules=[], allowlist=Allowlist())
    findings = det.scan([record], cfg)
    hidden_exe_findings = [f for f in findings if f.rule_id == "hidden-executable"]
    assert len(hidden_exe_findings) == 0


# ---------------------------------------------------------------------------
# Regular file — no findings
# ---------------------------------------------------------------------------

def test_regular_file_not_flagged():
    """A regular .pdf file with no suspicious traits must produce zero findings."""
    from fsaudit.security.detectors.suspicious import SuspiciousFilesDetector
    from fsaudit.security.config import SecurityConfig, Allowlist
    det = SuspiciousFilesDetector()
    record = _make_record("report.pdf", extension=".pdf", is_hidden=False)
    cfg = SecurityConfig(version=1, rules=[], allowlist=Allowlist())
    findings = det.scan([record], cfg)
    assert findings == []


# ---------------------------------------------------------------------------
# Severity and detector fields
# ---------------------------------------------------------------------------

def test_returns_correct_severity():
    """Findings must carry the expected severity levels."""
    from fsaudit.security.detectors.suspicious import SuspiciousFilesDetector
    from fsaudit.security.config import SecurityConfig, Allowlist
    det = SuspiciousFilesDetector()
    records = [
        _make_record("bad.pdf.exe", extension=".exe"),       # double-extension → HIGH
        _make_record("macro.xlsm", extension=".xlsm"),       # macro office → MEDIUM
        _make_record(".hide.exe", extension=".exe", is_hidden=True),  # hidden-exe → HIGH
    ]
    cfg = SecurityConfig(version=1, rules=[], allowlist=Allowlist())
    findings = det.scan(records, cfg)
    by_rule = {f.rule_id: f.severity for f in findings}
    assert by_rule["double-extension"] == Severity.HIGH
    assert by_rule["macro-enabled-office"] == Severity.MEDIUM
    assert by_rule["hidden-executable"] == Severity.HIGH


def test_detector_name_is_suspicious_files():
    """SuspiciousFilesDetector.name must equal 'suspicious-files'."""
    from fsaudit.security.detectors.suspicious import SuspiciousFilesDetector
    det = SuspiciousFilesDetector()
    assert det.name == "suspicious-files"


def test_line_no_is_none():
    """Findings from a metadata detector must have line_no=None."""
    from fsaudit.security.detectors.suspicious import SuspiciousFilesDetector
    from fsaudit.security.config import SecurityConfig, Allowlist
    det = SuspiciousFilesDetector()
    record = _make_record("bad.pdf.exe", extension=".exe")
    cfg = SecurityConfig(version=1, rules=[], allowlist=Allowlist())
    findings = det.scan([record], cfg)
    assert all(f.line_no is None for f in findings)
