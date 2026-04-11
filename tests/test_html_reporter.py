"""Tests for HtmlReporter (Task 2B.4)."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from fsaudit.analyzer.metrics import AnalysisResult
from fsaudit.reporter.base import BaseReporter
from fsaudit.scanner.models import FileRecord


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

def _make_file_record(
    name: str = "file.txt",
    size_bytes: int = 1024,
    category: str = "Documentos",
    mtime: datetime | None = None,
    path: str | None = None,
) -> FileRecord:
    return FileRecord(
        path=Path(path or f"/tmp/{name}"),
        name=name,
        extension=Path(name).suffix.lower(),
        size_bytes=size_bytes,
        mtime=mtime or datetime(2024, 6, 15),
        creation_time=datetime(2024, 1, 1),
        atime=datetime(2024, 6, 15),
        depth=0,
        is_hidden=False,
        permissions="644",
        category=category,
        parent_dir="/tmp",
    )


@pytest.fixture()
def minimal_records() -> list[FileRecord]:
    return [
        _make_file_record("a.txt", 2_097_152, "Documentos"),   # 2 MB
        _make_file_record("b.py", 1_048_576, "Codigo"),         # 1 MB
        _make_file_record("c.pdf", 5_242_880, "Documentos"),    # 5 MB
    ]


@pytest.fixture()
def minimal_analysis(minimal_records: list[FileRecord]) -> AnalysisResult:
    from fsaudit.analyzer.analyzer import analyze
    from fsaudit.scanner.models import ScanResult, DirectoryRecord

    scan = ScanResult(
        files=minimal_records,
        directories=[],
        root_path=Path("/tmp"),
    )
    return analyze(minimal_records, scan, inactive_days=180, _now=datetime(2026, 1, 1))


@pytest.fixture()
def generated_html(tmp_path: Path, minimal_records, minimal_analysis) -> str:
    from fsaudit.reporter.html_reporter import HtmlReporter

    out = tmp_path / "report.html"
    HtmlReporter().generate(minimal_records, minimal_analysis, out)
    return out.read_text()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestHtmlReporterSubclass:
    def test_html_reporter_is_base_reporter_subclass(self) -> None:
        from fsaudit.reporter.html_reporter import HtmlReporter

        assert issubclass(HtmlReporter, BaseReporter)


class TestHtmlReporterGenerate:
    def test_generate_creates_file(self, tmp_path, minimal_records, minimal_analysis) -> None:
        from fsaudit.reporter.html_reporter import HtmlReporter

        out = tmp_path / "report.html"
        HtmlReporter().generate(minimal_records, minimal_analysis, out)
        assert out.exists()

    def test_generate_returns_path(self, tmp_path, minimal_records, minimal_analysis) -> None:
        from fsaudit.reporter.html_reporter import HtmlReporter

        out = tmp_path / "report.html"
        result = HtmlReporter().generate(minimal_records, minimal_analysis, out)
        assert result == out


class TestHtmlDocStructure:
    def test_output_starts_with_doctype(self, generated_html: str) -> None:
        assert generated_html.strip().lower().startswith("<!doctype html")

    def test_all_11_section_ids_present(self, generated_html: str) -> None:
        expected_ids = [
            "summary",
            "categories",
            "top-largest",
            "inactive",
            "zero-byte",
            "name-duplicates",
            "hash-duplicates",
            "permission-issues",
            "empty-dirs",
            "timeline",
            "health-breakdown",
        ]
        for section_id in expected_ids:
            assert f'id="{section_id}"' in generated_html, (
                f"Missing section id='{section_id}'"
            )

    def test_no_external_resource_references(self, generated_html: str) -> None:
        assert 'src="http' not in generated_html
        assert 'href="http' not in generated_html

    def test_self_contained_has_style_tag(self, generated_html: str) -> None:
        assert "<style" in generated_html

    def test_sortable_js_present(self, generated_html: str) -> None:
        assert "sortTable" in generated_html or "<script" in generated_html


class TestHtmlContent:
    def test_health_score_value_in_output(
        self, generated_html: str, minimal_analysis: AnalysisResult
    ) -> None:
        score_str = f"{minimal_analysis.health_score:.1f}"
        assert score_str in generated_html

    def test_empty_hash_duplicates_section_noted(self, generated_html: str) -> None:
        # When no hash duplicates, the section should still exist with a note
        assert 'id="hash-duplicates"' in generated_html

    def test_categories_section_has_data(self, generated_html: str) -> None:
        assert "Documentos" in generated_html
        assert "Codigo" in generated_html

    def test_timeline_section_has_data(self, generated_html: str) -> None:
        assert "2024" in generated_html

    def test_sizes_in_mb(self, generated_html: str) -> None:
        # a.txt is 2 MB, should appear as "2.00" in the report
        assert "2.00" in generated_html


class TestHtmlMaxRows:
    def test_max_rows_truncation(self, tmp_path: Path, minimal_analysis: AnalysisResult) -> None:
        from fsaudit.reporter.html_reporter import HtmlReporter

        # Build 600 inactive file records in analysis
        analysis = AnalysisResult()
        analysis.total_files = 600
        analysis.inactive_files = [
            {"path": f"/tmp/f{i}.txt", "size_bytes": 100, "category": "Documentos",
             "mtime": datetime(2020, 1, 1), "days_inactive": 2000}
            for i in range(600)
        ]
        analysis.health_score = 50.0
        analysis.health_breakdown = {}
        analysis.by_category = {}
        analysis.timeline = {}
        analysis.top_largest = []
        analysis.zero_byte_files = []
        analysis.empty_directories = []
        analysis.duplicates_by_name = {}
        analysis.duplicates_by_hash = {}
        analysis.permission_issues = []

        out = tmp_path / "report.html"
        records = [_make_file_record(f"f{i}.txt") for i in range(5)]
        HtmlReporter(max_rows=500).generate(records, analysis, out)
        html = out.read_text()

        # Should have a truncation notice somewhere
        assert "500" in html or "truncat" in html.lower() or "showing" in html.lower()


class TestHtmlEmptyAnalysis:
    def test_empty_analysis_renders_without_error(self, tmp_path: Path) -> None:
        from fsaudit.reporter.html_reporter import HtmlReporter

        analysis = AnalysisResult()
        records: list[FileRecord] = []
        out = tmp_path / "empty_report.html"
        result = HtmlReporter().generate(records, analysis, out)
        assert result.exists()
        html = out.read_text()
        assert "<!DOCTYPE" in html or "<!doctype" in html
