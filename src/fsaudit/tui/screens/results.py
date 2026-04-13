"""ResultsScreen — displays audit results with tabbed content."""

from __future__ import annotations

from pathlib import Path

from textual.app import ComposeResult
from textual.screen import Screen
from textual.containers import Horizontal
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    Label,
    TabbedContent,
    TabPane,
)

from fsaudit.analyzer.metrics import AnalysisResult
from fsaudit.scanner.models import FileRecord


def _fmt_bytes(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n //= 1024
    return f"{n:.1f} PB"


class ResultsScreen(Screen):
    """Displays the completed audit results in a tabbed layout."""

    BINDINGS = [
        ("escape", "new_scan", "New Scan"),
        ("q", "quit_app", "Quit"),
    ]

    def __init__(self, results: dict) -> None:
        super().__init__()
        self._results = results

    @property
    def _analysis(self) -> AnalysisResult:
        return self._results["analysis"]

    @property
    def _records(self) -> list[FileRecord]:
        return self._results.get("records", [])

    @property
    def _report_path(self) -> Path:
        return self._results.get("report_path", Path("/tmp/report.xlsx"))

    def compose(self) -> ComposeResult:
        score = self._analysis.health_score
        color = "green" if score >= 70 else "yellow" if score >= 40 else "red"
        yield Header()
        yield Label(
            f"[bold {color}]Health Score: {score:.1f}/100[/bold {color}]",
            id="lbl-health",
        )
        with TabbedContent(id="tabs"):
            with TabPane("Summary", id="tab-summary"):
                yield DataTable(id="dt-summary", zebra_stripes=True)
            with TabPane("Categories", id="tab-categories"):
                yield DataTable(id="dt-categories", zebra_stripes=True)
            with TabPane("Top Largest", id="tab-largest"):
                yield DataTable(id="dt-largest", zebra_stripes=True)
            with TabPane("Inactive", id="tab-inactive"):
                yield DataTable(id="dt-inactive", zebra_stripes=True)
            with TabPane("Duplicates", id="tab-duplicates"):
                yield DataTable(id="dt-duplicates", zebra_stripes=True)
            with TabPane("Health Breakdown", id="tab-health"):
                yield DataTable(id="dt-health", zebra_stripes=True)
        with Horizontal(id="action-bar"):
            yield Button("Export Report", id="btn-export", variant="primary")
            yield Button("New Scan", id="btn-new-scan", variant="default")
            yield Button("Salir", id="btn-quit", variant="error")

    def on_mount(self) -> None:
        self.title = "fsaudit - Results"
        self._populate_tables()

    def _populate_tables(self) -> None:
        analysis = self._analysis

        # Summary
        dt = self.query_one("#dt-summary", DataTable)
        dt.add_columns("Metric", "Value")
        dt.add_rows([
            ("Total files", f"{analysis.total_files:,}"),
            ("Total size", _fmt_bytes(analysis.total_size_bytes)),
            ("Health score", f"{analysis.health_score:.1f}/100"),
            ("Inactive files", str(len(analysis.inactive_files))),
            ("Zero-byte files", str(len(analysis.zero_byte_files))),
            ("Name duplicates (groups)", str(len(analysis.duplicates_by_name))),
            ("Hash duplicates (groups)", str(len(analysis.duplicates_by_hash))),
            ("Report path", str(self._report_path)),
        ])

        # Categories
        dt_cat = self.query_one("#dt-categories", DataTable)
        dt_cat.add_columns("Category", "Count", "Size", "% Space")
        for cat, stats in sorted(analysis.by_category.items()):
            dt_cat.add_row(
                cat,
                str(stats.get("count", 0)),
                _fmt_bytes(stats.get("bytes", 0)),
                f"{stats.get('percent', 0):.1f}%",
            )

        # Top Largest
        dt_large = self.query_one("#dt-largest", DataTable)
        dt_large.add_columns("Path", "Size", "Category")
        for entry in analysis.top_largest:
            dt_large.add_row(
                str(entry.get("path", "")),
                _fmt_bytes(entry.get("size_bytes", 0)),
                str(entry.get("category", "")),
            )

        # Inactive
        dt_inact = self.query_one("#dt-inactive", DataTable)
        dt_inact.add_columns("Path", "Days Inactive", "Size")
        for entry in analysis.inactive_files:
            dt_inact.add_row(
                str(entry.get("path", "")),
                str(entry.get("days_inactive", "")),
                _fmt_bytes(entry.get("size_bytes", 0)),
            )

        # Duplicates
        dt_dup = self.query_one("#dt-duplicates", DataTable)
        dt_dup.add_columns("Name / Hash", "Paths")
        for name, paths in analysis.duplicates_by_name.items():
            dt_dup.add_row(f"[name] {name}", "\n".join(paths))
        for digest, paths in analysis.duplicates_by_hash.items():
            dt_dup.add_row(f"[hash] {digest[:12]}…", "\n".join(paths))

        # Health Breakdown
        dt_health = self.query_one("#dt-health", DataTable)
        dt_health.add_columns("Metric", "Penalty")
        for metric, penalty in analysis.health_breakdown.items():
            dt_health.add_row(metric, f"{penalty:.4f}")

    def action_new_scan(self) -> None:
        from fsaudit.tui.screens.folder_selector import FolderSelectorScreen

        self.app.pop_screen()
        self.app.push_screen(FolderSelectorScreen())

    def action_quit_app(self) -> None:
        self.app.exit()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-new-scan":
            self.action_new_scan()
        elif event.button.id == "btn-export":
            self.notify(f"Report saved at: {self._report_path}", title="Export")
        elif event.button.id == "btn-quit":
            self.app.exit()
