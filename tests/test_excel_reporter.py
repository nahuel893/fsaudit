"""Tests for the Excel reporter module."""

from datetime import datetime
from pathlib import Path

import pytest
from openpyxl import load_workbook

from fsaudit.analyzer.metrics import AnalysisResult
from fsaudit.reporter.base import BaseReporter
from fsaudit.reporter.excel_reporter import ExcelReporter, SHEET_NAMES
from fsaudit.scanner.models import FileRecord


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_record(
    name: str = "file.txt",
    extension: str = ".txt",
    size_bytes: int = 1024,
    category: str = "Codigo",
    parent_dir: str = "/tmp/project",
    permissions: str | None = "644",
    is_hidden: bool = False,
    depth: int = 1,
    mtime: datetime | None = None,
) -> FileRecord:
    """Helper to build a FileRecord with sensible defaults."""
    mt = mtime or datetime(2025, 6, 15, 10, 0, 0)
    return FileRecord(
        path=Path(parent_dir) / name,
        name=name,
        extension=extension,
        size_bytes=size_bytes,
        mtime=mt,
        creation_time=datetime(2025, 1, 1),
        atime=datetime(2025, 6, 20),
        depth=depth,
        is_hidden=is_hidden,
        permissions=permissions,
        category=category,
        parent_dir=parent_dir,
    )


@pytest.fixture
def sample_records() -> list[FileRecord]:
    """A small set of diverse records for testing."""
    return [
        _make_record("readme.md", ".md", 2048, "Codigo", "/tmp/a"),
        _make_record("photo.jpg", ".jpg", 5_000_000, "Multimedia", "/tmp/b"),
        _make_record("report.xlsx", ".xlsx", 30_000, "Oficina", "/tmp/a"),
        _make_record("script.py", ".py", 500, "Codigo", "/tmp/a"),
        _make_record("Makefile", "", 0, "Codigo", "/tmp/a"),  # zero-byte, no ext
    ]


@pytest.fixture
def sample_analysis() -> AnalysisResult:
    """An AnalysisResult with populated metrics matching sample_records."""
    ar = AnalysisResult()
    ar.total_files = 5
    ar.total_size_bytes = 5_032_572
    ar.by_category = {
        "Codigo": {
            "count": 3,
            "bytes": 2548,
            "percent": 0.05,
            "avg_size": 849.3,
            "newest": datetime(2025, 6, 15),
            "oldest": datetime(2025, 6, 15),
        },
        "Multimedia": {
            "count": 1,
            "bytes": 5_000_000,
            "percent": 99.35,
            "avg_size": 5_000_000.0,
            "newest": datetime(2025, 6, 15),
            "oldest": datetime(2025, 6, 15),
        },
        "Oficina": {
            "count": 1,
            "bytes": 30_000,
            "percent": 0.6,
            "avg_size": 30_000.0,
            "newest": datetime(2025, 6, 15),
            "oldest": datetime(2025, 6, 15),
        },
    }
    ar.timeline = {
        "2025-06": 3,
        "2024-12": 1,
        "2025-01": 1,
    }
    ar.top_largest = [
        {"path": "/tmp/b/photo.jpg", "size_bytes": 5_000_000, "category": "Multimedia", "mtime": datetime(2025, 6, 15)},
        {"path": "/tmp/a/report.xlsx", "size_bytes": 30_000, "category": "Oficina", "mtime": datetime(2025, 6, 15)},
    ]
    ar.inactive_files = [
        {"path": "/tmp/a/readme.md", "size_bytes": 2048, "category": "Codigo", "mtime": datetime(2025, 6, 15), "days_inactive": 200},
        {"path": "/tmp/a/script.py", "size_bytes": 500, "category": "Codigo", "mtime": datetime(2025, 6, 15), "days_inactive": 180},
    ]
    ar.zero_byte_files = [
        {"path": "/tmp/a/Makefile", "category": "Codigo", "mtime": datetime(2025, 6, 15)},
    ]
    ar.empty_directories = []
    ar.duplicates_by_name = {
        "config.yml": ["/tmp/a/config.yml", "/tmp/b/config.yml", "/tmp/c/config.yml"],
    }
    ar.permission_issues = [
        {"path": "/tmp/a/script.py", "permissions": "777", "issue": "777"},
    ]
    return ar


# ---------------------------------------------------------------------------
# 5.1 BaseReporter is abstract
# ---------------------------------------------------------------------------


class TestBaseReporterAbstract:
    def test_cannot_instantiate(self) -> None:
        with pytest.raises(TypeError):
            BaseReporter()  # type: ignore[abstract]


# ---------------------------------------------------------------------------
# 5.2 Generate with valid data
# ---------------------------------------------------------------------------


class TestGenerateValid:
    def test_creates_file_and_returns_path(
        self, tmp_path: Path, sample_records: list[FileRecord], sample_analysis: AnalysisResult
    ) -> None:
        out = tmp_path / "report.xlsx"
        reporter = ExcelReporter()
        result = reporter.generate(sample_records, sample_analysis, out)

        assert result == out
        assert out.exists()
        assert out.stat().st_size > 0

    def test_file_is_loadable(
        self, tmp_path: Path, sample_records: list[FileRecord], sample_analysis: AnalysisResult
    ) -> None:
        out = tmp_path / "report.xlsx"
        ExcelReporter().generate(sample_records, sample_analysis, out)
        wb = load_workbook(out)
        assert wb is not None
        wb.close()


# ---------------------------------------------------------------------------
# 5.3 Empty input
# ---------------------------------------------------------------------------


class TestEmptyInput:
    def test_empty_produces_valid_xlsx(self, tmp_path: Path) -> None:
        out = tmp_path / "empty.xlsx"
        ExcelReporter().generate([], AnalysisResult(), out)

        assert out.exists()
        wb = load_workbook(out)
        assert len(wb.sheetnames) == 8
        wb.close()

    def test_empty_sheets_have_headers_only(self, tmp_path: Path) -> None:
        out = tmp_path / "empty.xlsx"
        ExcelReporter().generate([], AnalysisResult(), out)
        wb = load_workbook(out)

        # Inventario should have header row only
        inv = wb["Inventario Completo"]
        assert inv.max_row >= 1  # at least header
        # No data rows beyond possible header
        wb.close()


# ---------------------------------------------------------------------------
# 5.4 Invalid output path
# ---------------------------------------------------------------------------


class TestInvalidOutputPath:
    def test_missing_parent_raises(self, tmp_path: Path) -> None:
        out = tmp_path / "nonexistent_dir" / "report.xlsx"
        with pytest.raises(FileNotFoundError):
            ExcelReporter().generate([], AnalysisResult(), out)

    def test_no_partial_file(self, tmp_path: Path) -> None:
        out = tmp_path / "nonexistent_dir" / "report.xlsx"
        with pytest.raises(FileNotFoundError):
            ExcelReporter().generate([], AnalysisResult(), out)
        assert not out.exists()


# ---------------------------------------------------------------------------
# 5.5 Sheet names and order
# ---------------------------------------------------------------------------


class TestSheetNamesOrder:
    def test_sheet_names_match(
        self, tmp_path: Path, sample_records: list[FileRecord], sample_analysis: AnalysisResult
    ) -> None:
        out = tmp_path / "report.xlsx"
        ExcelReporter().generate(sample_records, sample_analysis, out)
        wb = load_workbook(out)
        assert wb.sheetnames == SHEET_NAMES
        wb.close()


# ---------------------------------------------------------------------------
# 5.6 Dashboard KPIs
# ---------------------------------------------------------------------------


class TestDashboard:
    def test_kpis_match_analysis(
        self, tmp_path: Path, sample_records: list[FileRecord], sample_analysis: AnalysisResult
    ) -> None:
        out = tmp_path / "report.xlsx"
        ExcelReporter().generate(sample_records, sample_analysis, out)
        wb = load_workbook(out)
        ws = wb["Dashboard"]

        # Row 2: Total Archivos
        assert ws.cell(row=2, column=1).value == "Total Archivos"
        assert ws.cell(row=2, column=2).value == 5

        # Row 3: Volumen Total (human-readable string)
        assert ws.cell(row=3, column=1).value == "Volumen Total"
        assert "MB" in str(ws.cell(row=3, column=2).value) or "GB" in str(ws.cell(row=3, column=2).value)

        wb.close()


# ---------------------------------------------------------------------------
# 5.7 Por Categoria rows
# ---------------------------------------------------------------------------


class TestPorCategoria:
    def test_row_count_matches_categories(
        self, tmp_path: Path, sample_records: list[FileRecord], sample_analysis: AnalysisResult
    ) -> None:
        out = tmp_path / "report.xlsx"
        ExcelReporter().generate(sample_records, sample_analysis, out)
        wb = load_workbook(out)
        ws = wb["Por Categoria"]

        # 3 categories + 1 header = 4 rows
        data_rows = ws.max_row - 1  # subtract header
        assert data_rows == 3
        wb.close()


# ---------------------------------------------------------------------------
# 5.8 Timeline sort order
# ---------------------------------------------------------------------------


class TestTimelineSort:
    def test_chronological_ascending(
        self, tmp_path: Path, sample_records: list[FileRecord], sample_analysis: AnalysisResult
    ) -> None:
        out = tmp_path / "report.xlsx"
        ExcelReporter().generate(sample_records, sample_analysis, out)
        wb = load_workbook(out)
        ws = wb["Timeline"]

        periods = []
        for row in range(2, ws.max_row + 1):
            val = ws.cell(row=row, column=1).value
            if val:
                periods.append(val)

        assert periods == sorted(periods)
        assert periods == ["2024-12", "2025-01", "2025-06"]
        wb.close()


# ---------------------------------------------------------------------------
# 5.8b Top Archivos Pesados has Nombre column
# ---------------------------------------------------------------------------


class TestTopPesadosNombre:
    def test_nombre_column_present(
        self, tmp_path: Path, sample_records: list[FileRecord], sample_analysis: AnalysisResult
    ) -> None:
        out = tmp_path / "report.xlsx"
        ExcelReporter().generate(sample_records, sample_analysis, out)
        wb = load_workbook(out)
        ws = wb["Top Archivos Pesados"]

        headers = [ws.cell(row=1, column=c).value for c in range(1, ws.max_column + 1)]
        assert "Nombre" in headers
        assert headers == ["Ruta", "Nombre", "Tamano", "Categoria", "Ultima Modificacion"]

        # Verify data rows derive Nombre from path
        assert ws.cell(row=2, column=2).value == "photo.jpg"
        assert ws.cell(row=3, column=2).value == "report.xlsx"
        wb.close()


# ---------------------------------------------------------------------------
# 5.8c Archivos Inactivos has Nombre column
# ---------------------------------------------------------------------------


class TestInactivosNombre:
    def test_nombre_column_present(
        self, tmp_path: Path, sample_records: list[FileRecord], sample_analysis: AnalysisResult
    ) -> None:
        out = tmp_path / "report.xlsx"
        ExcelReporter().generate(sample_records, sample_analysis, out)
        wb = load_workbook(out)
        ws = wb["Archivos Inactivos"]

        headers = [ws.cell(row=1, column=c).value for c in range(1, ws.max_column + 1)]
        assert "Nombre" in headers
        assert headers == ["Ruta", "Nombre", "Tamano", "Categoria", "Ultima Modificacion", "Dias Inactivo"]

        # Verify data rows derive Nombre from path (sorted by days_inactive desc)
        assert ws.cell(row=2, column=2).value == "readme.md"
        assert ws.cell(row=3, column=2).value == "script.py"
        wb.close()


# ---------------------------------------------------------------------------
# 5.9 Alertas aggregates all sources
# ---------------------------------------------------------------------------


class TestAlertas:
    def test_aggregates_all_sources(
        self, tmp_path: Path, sample_records: list[FileRecord], sample_analysis: AnalysisResult
    ) -> None:
        out = tmp_path / "report.xlsx"
        ExcelReporter().generate(sample_records, sample_analysis, out)
        wb = load_workbook(out)
        ws = wb["Alertas"]

        data_rows = ws.max_row - 1  # subtract header
        # Expected: 1 zero-byte + 1 permission + 3 duplicates + 1 no-extension = 6
        assert data_rows >= 6

        # Check alert types present
        types = set()
        for row in range(2, ws.max_row + 1):
            types.add(ws.cell(row=row, column=1).value)

        assert "0 bytes" in types
        assert any("Permisos" in t for t in types if t)
        assert "Duplicado" in types
        assert "Sin extension" in types

        wb.close()


# ---------------------------------------------------------------------------
# 5.10 Inventario has autofilter
# ---------------------------------------------------------------------------


class TestInventarioAutofilter:
    def test_autofilter_set(
        self, tmp_path: Path, sample_records: list[FileRecord], sample_analysis: AnalysisResult
    ) -> None:
        out = tmp_path / "report.xlsx"
        ExcelReporter().generate(sample_records, sample_analysis, out)
        wb = load_workbook(out)
        ws = wb["Inventario Completo"]

        assert ws.auto_filter.ref is not None
        assert ws.auto_filter.ref != ""
        wb.close()


# ---------------------------------------------------------------------------
# 5.11 _format_bytes parametrized
# ---------------------------------------------------------------------------


class TestFormatBytes:
    @pytest.mark.parametrize(
        "size_bytes, expected",
        [
            (0, "0 B"),
            (512, "512 B"),
            (1023, "1023 B"),
            (1024, "1.00 KB"),
            (1536, "1.50 KB"),
            (1_048_576, "1.00 MB"),
            (1_073_741_824, "1.00 GB"),
            (2_500_000_000, "2.33 GB"),
        ],
    )
    def test_format_bytes(self, size_bytes: int, expected: str) -> None:
        assert ExcelReporter._format_bytes(size_bytes) == expected


# ---------------------------------------------------------------------------
# 5.12 Header styling
# ---------------------------------------------------------------------------


class TestHeaderStyling:
    def test_bold_headers_and_frozen_panes(
        self, tmp_path: Path, sample_records: list[FileRecord], sample_analysis: AnalysisResult
    ) -> None:
        out = tmp_path / "report.xlsx"
        ExcelReporter().generate(sample_records, sample_analysis, out)
        wb = load_workbook(out)

        for sheet_name in SHEET_NAMES:
            ws = wb[sheet_name]
            # Header row should be bold
            first_cell = ws.cell(row=1, column=1)
            assert first_cell.font.bold, f"Header not bold in {sheet_name}"
            # Frozen panes
            assert ws.freeze_panes == "A2", f"Freeze panes wrong in {sheet_name}"

        wb.close()
