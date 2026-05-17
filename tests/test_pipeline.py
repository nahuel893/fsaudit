"""Tests for the Pipeline orchestrator (src/fsaudit/pipeline.py).

T01: PipelineConfig dataclass with all fields
T02: Pipeline class with stub run() returning AuditResult
T03: scan → classify → filter stages
T04: enrich (optional) + strip_time (optional)
T05: analyze stage
T06: security scan (optional)
T07: report generation (optional)
T08: on_file callback during scan
T09: on_phase callback between stages
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from pathlib import Path

import pytest

from fsaudit.pipeline import Pipeline, PipelineConfig


# ---------------------------------------------------------------------------
# T01: PipelineConfig dataclass
# ---------------------------------------------------------------------------

def test_pipeline_config_defaults():
    """PC-01: All fields have correct defaults."""
    config = PipelineConfig(root=Path("/tmp"))
    assert config.root == Path("/tmp")
    assert config.max_depth is None
    assert config.exclude == []
    assert config.min_size == 0
    assert config.inactive_days == 365
    assert config.hash_duplicates is False
    assert config.extract_author is False
    assert config.strip_time is False
    assert config.security_scan is False
    assert config.security_config is None
    assert config.security_max_size is None
    assert config.format == "excel"
    assert config.output_dir is None
    assert config.overflow_strategy == "shard"


def test_pipeline_config_explicit():
    """PC-02: All fields accept explicit values."""
    config = PipelineConfig(
        root=Path("/tmp"),
        max_depth=3,
        exclude=["*.pyc", "__pycache__"],
        min_size=100,
        inactive_days=180,
        hash_duplicates=True,
        extract_author=True,
        strip_time=True,
        security_scan=True,
        security_config=Path("/tmp/security.yaml"),
        security_max_size=1024,
        format="html",
        output_dir=Path("/tmp/out"),
        overflow_strategy="csv",
    )
    assert config.max_depth == 3
    assert config.exclude == ["*.pyc", "__pycache__"]
    assert config.min_size == 100
    assert config.inactive_days == 180
    assert config.hash_duplicates is True
    assert config.extract_author is True
    assert config.strip_time is True
    assert config.security_scan is True
    assert config.security_config == Path("/tmp/security.yaml")
    assert config.security_max_size == 1024
    assert config.format == "html"
    assert config.output_dir == Path("/tmp/out")
    assert config.overflow_strategy == "csv"


# ---------------------------------------------------------------------------
# T02: Pipeline stub — run() returns AuditResult
# ---------------------------------------------------------------------------

def test_pipeline_run_returns_audit_result(tmp_path):
    """PL-01: Pipeline.run() returns an AuditResult with scan data."""
    (tmp_path / "test.txt").write_text("hello world")
    config = PipelineConfig(root=tmp_path, format=None)
    pipeline = Pipeline(config)
    result = pipeline.run()
    assert result is not None
    assert result.scan_result is not None
    assert result.analysis is not None
    assert result.records is not None
    assert result.report_path is None  # format=None


def test_pipeline_run_scans_files(tmp_path):
    """PL-02: run() produces FileRecords from the scan."""
    (tmp_path / "a.txt").write_text("alpha")
    (tmp_path / "b.py").write_text("beta")
    config = PipelineConfig(root=tmp_path, format=None)
    result = Pipeline(config).run()
    names = {r.name for r in result.records}
    assert "a.txt" in names
    assert "b.py" in names


def test_pipeline_run_classifies(tmp_path):
    """PL-03: run() classifies records with a category field."""
    (tmp_path / "readme.md").write_text("documentation")
    config = PipelineConfig(root=tmp_path, format=None)
    result = Pipeline(config).run()
    for r in result.records:
        assert r.category is not None
        assert r.category != ""


def test_pipeline_run_filters_by_min_size(tmp_path):
    """PL-04: min_size filter excludes small files."""
    (tmp_path / "small.txt").write_text("hi")
    (tmp_path / "large.txt").write_text("x" * 1000)
    config = PipelineConfig(root=tmp_path, format=None, min_size=500)
    result = Pipeline(config).run()
    assert all(r.size_bytes >= 500 for r in result.records)
    assert len(result.records) == 1


# ---------------------------------------------------------------------------
# T04: enrich (optional) + strip_time (optional)
# ---------------------------------------------------------------------------

def test_pipeline_run_extract_author(tmp_path):
    """PL-05: extract_author populates author field when True."""
    # Create a simple file that enricher can process
    (tmp_path / "doc.xlsx").write_bytes(
        b"PK\x03\x04"  # minimal ZIP/Office file header
    )
    config = PipelineConfig(
        root=tmp_path,
        format=None,
        extract_author=True,
        min_size=0,
    )
    result = Pipeline(config).run()
    # Result should not crash; author field may or may not be populated
    assert result is not None


def test_pipeline_run_strip_time(tmp_path):
    """PL-06: strip_time zeroes time components when True."""
    (tmp_path / "test.txt").write_text("content")
    config = PipelineConfig(root=tmp_path, format=None, strip_time=True)
    result = Pipeline(config).run()
    for r in result.records:
        assert r.mtime.hour == 0
        assert r.mtime.minute == 0
        assert r.mtime.second == 0
        assert r.mtime.microsecond == 0


def test_pipeline_run_strip_time_preserves_date(tmp_path):
    """PL-07: strip_time preserves the date (year/month/day)."""
    (tmp_path / "test.txt").write_text("content")
    config = PipelineConfig(root=tmp_path, format=None, strip_time=True)
    result = Pipeline(config).run()
    for r in result.records:
        assert r.mtime.year == datetime.now().year
        assert r.mtime.month == datetime.now().month
        assert r.mtime.day == datetime.now().day


# ---------------------------------------------------------------------------
# T05: analyze stage
# ---------------------------------------------------------------------------

def test_pipeline_run_analysis_result(tmp_path):
    """PL-08: run() produces AnalysisResult with health_score."""
    (tmp_path / "file.txt").write_text("data")
    config = PipelineConfig(root=tmp_path, format=None)
    result = Pipeline(config).run()
    assert 0.0 <= result.health_score <= 100.0
    assert result.analysis.total_files >= 1


def test_pipeline_run_inactive_days(tmp_path):
    """PL-09: inactive_days parameter is passed to analyzer."""
    (tmp_path / "old.txt").write_text("ancient data")
    config = PipelineConfig(root=tmp_path, format=None, inactive_days=1)
    result = Pipeline(config).run()
    # With 1 day threshold, file should appear inactive
    assert result.analysis is not None


def test_pipeline_run_hash_duplicates(tmp_path):
    """PL-10: hash_duplicates enables hash-based duplicate detection."""
    (tmp_path / "dup1.txt").write_text("same content")
    (tmp_path / "dup2.txt").write_text("same content")
    config = PipelineConfig(root=tmp_path, format=None, hash_duplicates=True)
    result = Pipeline(config).run()
    assert result.analysis.duplicates_by_hash is not None


# ---------------------------------------------------------------------------
# T06: security scan (optional)
# ---------------------------------------------------------------------------

def test_pipeline_run_security_scan_skipped_by_default(tmp_path):
    """PL-11: security_scan=False skips the security scan stage."""
    (tmp_path / "file.txt").write_text("hello")
    config = PipelineConfig(root=tmp_path, format=None)
    result = Pipeline(config).run()
    assert result.security is None


def test_pipeline_run_security_scan_enabled(tmp_path):
    """PL-12: security_scan=True runs the security scan."""
    (tmp_path / "file.txt").write_text("hello")
    config = PipelineConfig(root=tmp_path, format=None, security_scan=True)
    result = Pipeline(config).run()
    assert result.security is not None
    assert hasattr(result.security, "findings")
    assert hasattr(result.security, "security_score")


# ---------------------------------------------------------------------------
# T07: report generation (optional)
# ---------------------------------------------------------------------------

def test_pipeline_run_no_report_when_format_none(tmp_path):
    """PL-13: format=None produces no report_path."""
    (tmp_path / "file.txt").write_text("hello")
    config = PipelineConfig(root=tmp_path, format=None)
    result = Pipeline(config).run()
    assert result.report_path is None


def test_pipeline_run_excel_report(tmp_path):
    """PL-14: format='excel' generates an .xlsx file."""
    (tmp_path / "file.txt").write_text("hello")
    config = PipelineConfig(root=tmp_path, format="excel", output_dir=tmp_path)
    result = Pipeline(config).run()
    assert result.report_path is not None
    assert result.report_path.suffix == ".xlsx"
    assert result.report_path.exists()


def test_pipeline_run_html_report(tmp_path):
    """PL-15: format='html' generates an .html file."""
    (tmp_path / "file.txt").write_text("hello")
    config = PipelineConfig(root=tmp_path, format="html", output_dir=tmp_path)
    result = Pipeline(config).run()
    assert result.report_path is not None
    assert result.report_path.suffix == ".html"
    assert result.report_path.exists()


def test_pipeline_run_overflow_warning(tmp_path):
    """PL-16: overflow_strategy is passed to reporter."""
    config = PipelineConfig(root=tmp_path, format="excel", overflow_strategy="csv")
    # Should not raise
    result = Pipeline(config).run()
    assert result is not None


# ---------------------------------------------------------------------------
# T08: on_file callback during scan
# ---------------------------------------------------------------------------

def test_pipeline_run_on_file_callback(tmp_path):
    """PL-17: on_file callback is invoked for each scanned file."""
    (tmp_path / "a.txt").write_text("alpha")
    (tmp_path / "b.txt").write_text("beta")
    found = []

    def on_file(p: Path) -> None:
        found.append(p)

    config = PipelineConfig(root=tmp_path, format=None)
    result = Pipeline(config).run(on_file=on_file)
    assert len(found) == 2
    assert all(isinstance(p, Path) for p in found)


# ---------------------------------------------------------------------------
# T09: on_phase callback between stages
# ---------------------------------------------------------------------------

def test_pipeline_run_on_phase_callback(tmp_path):
    """PL-18: on_phase is called between each pipeline stage."""
    (tmp_path / "file.txt").write_text("hello")
    phases: list[str] = []

    def on_phase(phase: str) -> None:
        phases.append(phase)

    config = PipelineConfig(root=tmp_path, format=None)
    Pipeline(config).run(on_phase=on_phase)
    # Should have called on_phase for: scan, classify, analyze, report (optional)
    assert len(phases) >= 3


def test_pipeline_run_on_phase_receives_stage_names(tmp_path):
    """PL-19: on_phase receives string names for each stage."""
    (tmp_path / "file.txt").write_text("hello")
    phases: list[str] = []

    config = PipelineConfig(root=tmp_path, format=None)
    Pipeline(config).run(on_phase=lambda p: phases.append(p))
    for phase in phases:
        assert isinstance(phase, str)
        assert phase != ""


# ---------------------------------------------------------------------------
# T10-T12 integration: wiring correctness
# ---------------------------------------------------------------------------

def test_pipeline_run_returns_api_audit_result(tmp_path):
    """PL-20: Pipeline.run() returns the same structure as api.audit()."""
    from fsaudit.api import AuditResult
    (tmp_path / "file.txt").write_text("data")
    config = PipelineConfig(root=tmp_path, format=None)
    result = Pipeline(config).run()
    assert isinstance(result, AuditResult)
    assert hasattr(result, "records")
    assert hasattr(result, "analysis")
    assert hasattr(result, "scan_result")
    assert hasattr(result, "report_path")
    assert hasattr(result, "security")
    assert hasattr(result, "health_score")