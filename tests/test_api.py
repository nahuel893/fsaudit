"""Tests for the public API (fsaudit.api and fsaudit top-level re-exports).

SC-01  audit returns AuditResult with report
SC-02  format=None skips report
SC-03  format="html" creates html
SC-05  health_score accessor
SC-06  scan function
SC-08  types importable from fsaudit
SC-09  invalid path raises FileNotFoundError
SC-10  functions importable
SC-11  invalid format raises ValueError
SC-12  min_size filter
SC-13  output_dir controls report location
SC-14  on_file callback
"""

from __future__ import annotations

import pytest
from pathlib import Path

from fsaudit.api import audit, scan, AuditResult


# ---------------------------------------------------------------------------
# SC-01: audit returns AuditResult with Excel report by default
# ---------------------------------------------------------------------------

def test_audit_returns_audit_result(tmp_path):
    (tmp_path / "test.txt").write_text("hello")
    result = audit(str(tmp_path))
    assert isinstance(result, AuditResult)
    assert result.report_path is not None
    assert result.report_path.exists()
    assert result.report_path.suffix == ".xlsx"


# ---------------------------------------------------------------------------
# SC-02: format=None skips report generation
# ---------------------------------------------------------------------------

def test_audit_format_none_no_report(tmp_path):
    (tmp_path / "test.txt").write_text("hello")
    result = audit(str(tmp_path), format=None)
    assert result.report_path is None


# ---------------------------------------------------------------------------
# SC-03: format="html" creates HTML report
# ---------------------------------------------------------------------------

def test_audit_format_html(tmp_path):
    (tmp_path / "test.txt").write_text("hello")
    result = audit(str(tmp_path), format="html")
    assert result.report_path is not None
    assert result.report_path.suffix == ".html"
    assert result.report_path.exists()


# ---------------------------------------------------------------------------
# SC-05: health_score accessor returns float in [0, 100]
# ---------------------------------------------------------------------------

def test_audit_result_health_score(tmp_path):
    (tmp_path / "test.txt").write_text("hello")
    result = audit(str(tmp_path), format=None)
    assert 0.0 <= result.health_score <= 100.0


# ---------------------------------------------------------------------------
# SC-06: scan function returns ScanResult
# ---------------------------------------------------------------------------

def test_scan_returns_scan_result(tmp_path):
    (tmp_path / "test.txt").write_text("hello")
    from fsaudit.scanner.models import ScanResult
    result = scan(str(tmp_path))
    assert isinstance(result, ScanResult)


# ---------------------------------------------------------------------------
# SC-08: types importable from top-level fsaudit package
# ---------------------------------------------------------------------------

def test_types_importable():
    from fsaudit import FileRecord, ScanResult, AnalysisResult, AuditResult
    assert FileRecord is not None
    assert AuditResult is not None
    assert ScanResult is not None
    assert AnalysisResult is not None


# ---------------------------------------------------------------------------
# SC-09: invalid path raises FileNotFoundError
# ---------------------------------------------------------------------------

def test_audit_invalid_path():
    with pytest.raises(FileNotFoundError):
        audit("/nonexistent/path/abc123")


# ---------------------------------------------------------------------------
# SC-10: all public functions importable and callable
# ---------------------------------------------------------------------------

def test_functions_importable():
    from fsaudit import audit, scan, classify, analyze, enrich_authors
    assert callable(audit)
    assert callable(scan)
    assert callable(classify)
    assert callable(analyze)
    assert callable(enrich_authors)


# ---------------------------------------------------------------------------
# SC-11: invalid format raises ValueError
# ---------------------------------------------------------------------------

def test_audit_invalid_format(tmp_path):
    (tmp_path / "test.txt").write_text("hello")
    with pytest.raises(ValueError):
        audit(str(tmp_path), format="pdf")


# ---------------------------------------------------------------------------
# SC-12: min_size filter excludes small files
# ---------------------------------------------------------------------------

def test_audit_min_size_filter(tmp_path):
    (tmp_path / "small.txt").write_text("hi")
    (tmp_path / "big.txt").write_text("x" * 2000)
    result = audit(str(tmp_path), format=None, min_size=1000)
    assert result.total_files == 1  # only big.txt


# ---------------------------------------------------------------------------
# SC-13: output_dir controls report location
# ---------------------------------------------------------------------------

def test_audit_output_dir(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "test.txt").write_text("hello")
    out = tmp_path / "reports"
    out.mkdir()
    result = audit(str(src), output_dir=str(out))
    assert result.report_path is not None
    assert str(out) in str(result.report_path)


# ---------------------------------------------------------------------------
# SC-14: on_file callback is invoked for each scanned file
# ---------------------------------------------------------------------------

def test_audit_on_file_callback(tmp_path):
    (tmp_path / "a.txt").write_text("a")
    (tmp_path / "b.txt").write_text("b")
    found = []
    result = audit(str(tmp_path), format=None, on_file=lambda p: found.append(p))
    assert len(found) == 2


# ---------------------------------------------------------------------------
# Additional: AuditResult convenience accessors
# ---------------------------------------------------------------------------

def test_audit_result_accessors(tmp_path):
    (tmp_path / "test.txt").write_text("hello world")
    result = audit(str(tmp_path), format=None)
    assert result.total_files >= 1
    assert result.total_size_bytes > 0
    assert isinstance(result.categories, dict)


# ---------------------------------------------------------------------------
# scan: invalid path raises FileNotFoundError
# ---------------------------------------------------------------------------

def test_scan_invalid_path():
    with pytest.raises(FileNotFoundError):
        scan("/nonexistent/path/xyz999")
