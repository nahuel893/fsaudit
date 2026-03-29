"""Excel reporter — generates multi-sheet .xlsx workbooks via openpyxl."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font, NamedStyle, numbers
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
        """KPI overview sheet."""
        headers = ["KPI", "Valor"]
        ws.append(headers)

        # Alert count: zero-byte + permission issues + duplicate groups + empty dirs
        alert_count = (
            len(analysis.zero_byte_files)
            + len(analysis.permission_issues)
            + sum(
                len(paths) for paths in analysis.duplicates_by_name.values()
            )
        )

        ws.append(["Total Archivos", analysis.total_files])
        ws.append(["Volumen Total", self._format_bytes(analysis.total_size_bytes)])
        ws.append(["Alertas Activas", alert_count])
        ws.append([])  # blank row

        # Category summary sub-table
        ws.append(["Categoria", "Cantidad"])
        for cat, stats in analysis.by_category.items():
            ws.append([cat, stats.get("count", 0)])

        self._apply_header_style(ws, len(headers))
        self._auto_column_width(ws)

    def _write_por_categoria(
        self, ws: Worksheet, analysis: AnalysisResult
    ) -> None:
        """Category breakdown sheet."""
        headers = [
            "Categoria",
            "Cantidad",
            "Volumen (bytes)",
            "% del Total",
            "Promedio Tamano",
            "Mas Reciente",
            "Mas Antiguo",
        ]
        ws.append(headers)
        for cat, stats in analysis.by_category.items():
            ws.append([
                cat,
                stats.get("count", 0),
                stats.get("bytes", 0),
                round(stats.get("percent", 0.0), 2),
                round(stats.get("avg_size", 0.0), 2),
                str(stats.get("newest", "")),
                str(stats.get("oldest", "")),
            ])

        self._apply_header_style(ws, len(headers))
        self._auto_column_width(ws)

    def _write_timeline(self, ws: Worksheet, analysis: AnalysisResult) -> None:
        """Monthly distribution sheet, sorted chronologically."""
        headers = ["Periodo", "Cantidad"]
        ws.append(headers)
        for period in sorted(analysis.timeline.keys()):
            ws.append([period, analysis.timeline[period]])

        self._apply_header_style(ws, len(headers))
        self._auto_column_width(ws)

    def _write_top_pesados(
        self, ws: Worksheet, analysis: AnalysisResult
    ) -> None:
        """Top largest files sheet."""
        headers = ["Ruta", "Nombre", "Tamano", "Categoria", "Ultima Modificacion"]
        ws.append(headers)
        for item in analysis.top_largest:
            path = item.get("path", "")
            ws.append([
                path,
                Path(path).name,
                self._format_bytes(item.get("size_bytes", 0)),
                item.get("category", ""),
                str(item.get("mtime", "")),
            ])

        self._apply_header_style(ws, len(headers))
        self._auto_column_width(ws)

    def _write_inactivos(
        self, ws: Worksheet, analysis: AnalysisResult
    ) -> None:
        """Inactive files sheet, sorted by days_inactive descending."""
        headers = [
            "Ruta",
            "Nombre",
            "Tamano",
            "Categoria",
            "Ultima Modificacion",
            "Dias Inactivo",
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
                self._format_bytes(item.get("size_bytes", 0)),
                item.get("category", ""),
                str(item.get("mtime", "")),
                item.get("days_inactive", 0),
            ])

        self._apply_header_style(ws, len(headers))
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
        self._auto_column_width(ws)

    def _write_por_directorio(
        self, ws: Worksheet, records: list[FileRecord]
    ) -> None:
        """Top directories by volume sheet."""
        headers = [
            "Directorio",
            "Cantidad Archivos",
            "Volumen Total",
            "Volumen Promedio",
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
                self._format_bytes(stats["bytes"]),
                self._format_bytes(int(avg)),
            ])

        self._apply_header_style(ws, len(headers))
        self._auto_column_width(ws)

    def _write_inventario(
        self, ws: Worksheet, records: list[FileRecord]
    ) -> None:
        """Complete inventory sheet with autofilter."""
        headers = [
            "Ruta",
            "Nombre",
            "Extension",
            "Tamano",
            "Categoria",
            "Fecha Modificacion",
            "Fecha Creacion",
            "Ultimo Acceso",
            "Profundidad",
            "Oculto",
            "Permisos",
            "Directorio Padre",
        ]
        ws.append(headers)

        for rec in records:
            ws.append([
                str(rec.path),
                rec.name,
                rec.extension,
                rec.size_bytes,
                rec.category,
                str(rec.mtime),
                str(rec.creation_time),
                str(rec.atime),
                rec.depth,
                rec.is_hidden,
                rec.permissions or "",
                rec.parent_dir,
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
