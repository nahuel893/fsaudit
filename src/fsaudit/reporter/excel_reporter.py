"""Excel reporter — generates multi-sheet .xlsx workbooks via openpyxl."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from openpyxl import Workbook
from openpyxl.chart import LineChart, Reference
from openpyxl.styles import Font, NamedStyle, PatternFill, numbers
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from fsaudit.analyzer.metrics import AnalysisResult
from fsaudit.reporter.base import BaseReporter
from fsaudit.scanner.models import FileRecord

# Sheet names in required order (REQ-ES-01).
SHEET_NAMES: list[str] = [
    "Dashboard",
    "Por Categoria",
    "Timeline",
    "Top Archivos Pesados",
    "Archivos Inactivos",
    "Alertas",
    "Por Directorio",
    "Inventario Completo",
]


class ExcelReporter(BaseReporter):
    """Concrete reporter that writes an 8-sheet Excel workbook."""

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(
        self,
        records: list[FileRecord],
        analysis: AnalysisResult,
        output_path: Path,
    ) -> Path:
        """Create .xlsx report at *output_path*.

        Raises:
            FileNotFoundError: If the parent directory of *output_path*
                does not exist.
        """
        output_path = Path(output_path)
        if not output_path.parent.exists():
            raise FileNotFoundError(
                f"Parent directory does not exist: {output_path.parent}"
            )

        wb = Workbook()

        # Create sheets in order — first sheet is auto-created by Workbook().
        for idx, name in enumerate(SHEET_NAMES):
            if idx == 0:
                wb.active.title = name  # type: ignore[union-attr]
            else:
                wb.create_sheet(title=name)

        # Delegate writing to private methods.
        self._write_dashboard(wb[SHEET_NAMES[0]], analysis, records)
        self._write_por_categoria(wb[SHEET_NAMES[1]], analysis)
        self._write_timeline(wb[SHEET_NAMES[2]], analysis)
        self._write_top_pesados(wb[SHEET_NAMES[3]], analysis)
        self._write_inactivos(wb[SHEET_NAMES[4]], analysis)
        self._write_alertas(wb[SHEET_NAMES[5]], analysis, records)
        self._write_por_directorio(wb[SHEET_NAMES[6]], records)
        self._write_inventario(wb[SHEET_NAMES[7]], records)

        wb.save(str(output_path))
        return output_path

    # ------------------------------------------------------------------
    # Styling helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _bytes_to_mb(size_bytes: int) -> float:
        """Convert bytes to MB, rounded to 2 decimals."""
        return round(size_bytes / (1024 * 1024), 2)

    @staticmethod
    def _format_bytes(size_bytes: int) -> str:
        """Return human-readable byte string (B / KB / MB / GB)."""
        if size_bytes < 0:
            return f"{size_bytes} B"
        for unit, threshold in [("GB", 1 << 30), ("MB", 1 << 20), ("KB", 1 << 10)]:
            if size_bytes >= threshold:
                return f"{size_bytes / threshold:.2f} {unit}"
        return f"{size_bytes} B"

    @staticmethod
    def _apply_header_style(ws: Worksheet, num_cols: int) -> None:
        """Bold the first row and freeze panes at row 2."""
        bold = Font(bold=True)
        for col in range(1, num_cols + 1):
            cell = ws.cell(row=1, column=col)
            cell.font = bold
        ws.freeze_panes = "A2"

    @staticmethod
    def _apply_autofilter(ws: Worksheet, num_cols: int) -> None:
        """Apply autofilter from A1 to last data cell."""
        last_col = get_column_letter(num_cols)
        last_row = ws.max_row
        ws.auto_filter.ref = f"A1:{last_col}{last_row}"

    @staticmethod
    def _auto_column_width(
        ws: Worksheet,
        max_width: int = 50,
        sample_rows: int = 100,
    ) -> None:
        """Adjust column widths based on content (sampled)."""
        for col_cells in ws.columns:
            max_len = 0
            col_letter = get_column_letter(col_cells[0].column)
            for cell in col_cells[:sample_rows + 1]:  # +1 for header
                try:
                    length = len(str(cell.value)) if cell.value is not None else 0
                except Exception:
                    length = 0
                if length > max_len:
                    max_len = length
            adjusted = min(max_len + 2, max_width)
            ws.column_dimensions[col_letter].width = max(adjusted, 8)

    # ------------------------------------------------------------------
    # Sheet writers
    # ------------------------------------------------------------------

    def _write_dashboard(
        self,
        ws: Worksheet,
        analysis: AnalysisResult,
        records: list[FileRecord],
    ) -> None:
        """KPI overview sheet with professional layout."""
        title_font = Font(bold=True, size=14)
        section_font = Font(bold=True, size=12)
        value_font = Font(bold=True, size=14)
        label_font = Font(bold=True)

        # Row 1: Title
        ws.cell(row=1, column=1, value="Dashboard").font = title_font

        # Alert count: zero-byte + permission issues + duplicate groups
        alert_count = (
            len(analysis.zero_byte_files)
            + len(analysis.permission_issues)
            + sum(
                len(paths) for paths in analysis.duplicates_by_name.values()
            )
        )

        # KPI rows (label col A, value col B)
        kpis = [
            ("Total Archivos", analysis.total_files),
            ("Tamaño Total (MB)", self._bytes_to_mb(analysis.total_size_bytes)),
            ("Categorías", len(analysis.by_category)),
            ("Alertas Activas", alert_count),
        ]
        for i, (label, value) in enumerate(kpis, start=2):
            ws.cell(row=i, column=1, value=label).font = label_font
            ws.cell(row=i, column=2, value=value).font = value_font

        # Blank row
        current_row = len(kpis) + 2  # after KPIs + title

        # Top 5 Categorías por Tamaño section
        current_row += 1
        ws.cell(row=current_row, column=1, value="Top 5 Categorías por Tamaño").font = section_font
        current_row += 1
        ws.cell(row=current_row, column=1, value="Categoría").font = label_font
        ws.cell(row=current_row, column=2, value="Cantidad").font = label_font
        ws.cell(row=current_row, column=3, value="Tamaño (MB)").font = label_font
        current_row += 1

        # Sort categories by bytes descending, take top 5
        sorted_cats = sorted(
            analysis.by_category.items(),
            key=lambda x: x[1].get("bytes", 0),
            reverse=True,
        )[:5]
        for cat, stats in sorted_cats:
            ws.cell(row=current_row, column=1, value=cat)
            ws.cell(row=current_row, column=2, value=stats.get("count", 0))
            ws.cell(row=current_row, column=3, value=self._bytes_to_mb(stats.get("bytes", 0)))
            current_row += 1

        # Blank row
        current_row += 1

        # Top 5 Directorios por Cantidad section
        ws.cell(row=current_row, column=1, value="Top 5 Directorios por Cantidad").font = section_font
        current_row += 1
        ws.cell(row=current_row, column=1, value="Directorio").font = label_font
        ws.cell(row=current_row, column=2, value="Cantidad").font = label_font
        current_row += 1

        # Compute dir stats from records
        dir_counts: dict[str, int] = defaultdict(int)
        for rec in records:
            dir_counts[rec.parent_dir] += 1

        sorted_dirs = sorted(dir_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        for dirname, count in sorted_dirs:
            ws.cell(row=current_row, column=1, value=dirname)
            ws.cell(row=current_row, column=2, value=count)
            current_row += 1

        # Apply header style and column width
        # Style row 1 as header
        ws.freeze_panes = "A2"
        self._auto_column_width(ws)

    def _write_por_categoria(
        self, ws: Worksheet, analysis: AnalysisResult
    ) -> None:
        """Category breakdown sheet."""
        headers = [
            "Categoría",
            "Cantidad",
            "Volumen (MB)",
            "% del Total",
            "Promedio (MB)",
            "Más Reciente",
            "Más Antiguo",
        ]
        ws.append(headers)
        for cat, stats in analysis.by_category.items():
            ws.append([
                cat,
                stats.get("count", 0),
                self._bytes_to_mb(stats.get("bytes", 0)),
                round(stats.get("percent", 0.0), 2),
                self._bytes_to_mb(int(stats.get("avg_size", 0.0))),
                str(stats.get("newest", "")),
                str(stats.get("oldest", "")),
            ])

        self._apply_header_style(ws, len(headers))
        self._apply_autofilter(ws, len(headers))
        self._auto_column_width(ws)

    def _write_timeline(self, ws: Worksheet, analysis: AnalysisResult) -> None:
        """Monthly distribution sheet, sorted chronologically."""
        headers = ["Período", "Cantidad"]
        ws.append(headers)
        sorted_periods = sorted(analysis.timeline.keys())
        for period in sorted_periods:
            ws.append([period, analysis.timeline[period]])

        self._apply_header_style(ws, len(headers))
        self._apply_autofilter(ws, len(headers))
        self._auto_column_width(ws)

        # Add LineChart if we have enough data points
        num_rows = len(sorted_periods)
        if num_rows >= 2:
            chart = LineChart()
            chart.title = "Archivos por Período"
            chart.y_axis.title = "Cantidad"
            chart.x_axis.title = "Período"
            chart.style = 10

            data = Reference(ws, min_col=2, min_row=1, max_row=num_rows + 1)
            cats = Reference(ws, min_col=1, min_row=2, max_row=num_rows + 1)
            chart.add_data(data, titles_from_data=True)
            chart.set_categories(cats)
            chart.width = 20
            chart.height = 12

            ws.add_chart(chart, f"A{num_rows + 3}")

    def _write_top_pesados(
        self, ws: Worksheet, analysis: AnalysisResult
    ) -> None:
        """Top largest files sheet."""
        headers = ["Ruta", "Nombre", "Tamaño (MB)", "Categoría", "Última Modificación"]
        ws.append(headers)
        for item in analysis.top_largest:
            path = item.get("path", "")
            ws.append([
                path,
                Path(path).name,
                self._bytes_to_mb(item.get("size_bytes", 0)),
                item.get("category", ""),
                str(item.get("mtime", "")),
            ])

        self._apply_header_style(ws, len(headers))
        self._apply_autofilter(ws, len(headers))
        self._auto_column_width(ws)

    def _write_inactivos(
        self, ws: Worksheet, analysis: AnalysisResult
    ) -> None:
        """Inactive files sheet, sorted by days_inactive descending."""
        headers = [
            "Ruta",
            "Nombre",
            "Tamaño (MB)",
            "Categoría",
            "Última Modificación",
            "Días Inactivo",
        ]
        ws.append(headers)
        sorted_items = sorted(
            analysis.inactive_files,
            key=lambda x: x.get("days_inactive", 0),
            reverse=True,
        )
        for item in sorted_items:
            path = item.get("path", "")
            ws.append([
                path,
                Path(path).name,
                self._bytes_to_mb(item.get("size_bytes", 0)),
                item.get("category", ""),
                str(item.get("mtime", "")),
                item.get("days_inactive", 0),
            ])

        self._apply_header_style(ws, len(headers))
        self._apply_autofilter(ws, len(headers))
        self._auto_column_width(ws)

    def _write_alertas(
        self,
        ws: Worksheet,
        analysis: AnalysisResult,
        records: list[FileRecord],
    ) -> None:
        """Alerts sheet — aggregates 4 alert sources."""
        headers = ["Tipo Alerta", "Nombre", "Ruta", "Detalle"]
        ws.append(headers)

        # Zero-byte files
        for item in analysis.zero_byte_files:
            path = item.get("path", "")
            ws.append(["0 bytes", Path(path).name, path, "Archivo de 0 bytes"])

        # Permission issues
        for item in analysis.permission_issues:
            path = item.get("path", "")
            issue = item.get("issue", "")
            ws.append([
                f"Permisos: {issue}",
                Path(path).name,
                path,
                f"Permisos: {item.get('permissions', '')}",
            ])

        # Duplicate filenames
        for name, paths in analysis.duplicates_by_name.items():
            for dup_path in paths:
                ws.append(["Duplicado", name, dup_path, f"{len(paths)} copias"])

        # Files with empty extension
        for rec in records:
            if rec.extension == "":
                ws.append([
                    "Sin extension",
                    rec.name,
                    str(rec.path),
                    "Archivo sin extension",
                ])

        self._apply_header_style(ws, len(headers))
        self._apply_autofilter(ws, len(headers))
        self._auto_column_width(ws)

    def _write_por_directorio(
        self, ws: Worksheet, records: list[FileRecord]
    ) -> None:
        """Top directories by volume sheet."""
        headers = [
            "Directorio",
            "Cantidad Archivos",
            "Volumen Total (MB)",
            "Volumen Promedio (MB)",
        ]
        ws.append(headers)

        # Group by parent_dir
        dir_stats: dict[str, dict] = defaultdict(
            lambda: {"count": 0, "bytes": 0}
        )
        for rec in records:
            entry = dir_stats[rec.parent_dir]
            entry["count"] += 1
            entry["bytes"] += rec.size_bytes

        # Sort by volume desc, take top 50
        sorted_dirs = sorted(
            dir_stats.items(), key=lambda x: x[1]["bytes"], reverse=True
        )[:50]

        for dirname, stats in sorted_dirs:
            avg = stats["bytes"] / stats["count"] if stats["count"] else 0
            ws.append([
                dirname,
                stats["count"],
                self._bytes_to_mb(stats["bytes"]),
                self._bytes_to_mb(int(avg)),
            ])

        self._apply_header_style(ws, len(headers))
        self._apply_autofilter(ws, len(headers))
        self._auto_column_width(ws)

    def _write_inventario(
        self, ws: Worksheet, records: list[FileRecord]
    ) -> None:
        """Complete inventory sheet with autofilter."""
        headers = [
            "Ruta",
            "Nombre",
            "Extensión",
            "Tamaño (MB)",
            "Categoría",
            "Fecha Modificación",
            "Fecha Creación",
            "Último Acceso",
            "Profundidad",
            "Oculto",
            "Permisos",
            "Directorio Padre",
            "Autor",
        ]
        ws.append(headers)

        for rec in records:
            ws.append([
                str(rec.path),
                rec.name,
                rec.extension,
                self._bytes_to_mb(rec.size_bytes),
                rec.category,
                str(rec.mtime),
                str(rec.creation_time),
                str(rec.atime),
                rec.depth,
                rec.is_hidden,
                rec.permissions or "",
                rec.parent_dir,
                rec.author or "",
            ])

        # Autofilter spanning all columns
        if records:
            last_col = get_column_letter(len(headers))
            last_row = len(records) + 1  # +1 for header
            ws.auto_filter.ref = f"A1:{last_col}{last_row}"
        else:
            last_col = get_column_letter(len(headers))
            ws.auto_filter.ref = f"A1:{last_col}1"

        self._apply_header_style(ws, len(headers))
        self._auto_column_width(ws)
