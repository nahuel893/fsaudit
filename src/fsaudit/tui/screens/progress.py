"""ProgressScreen — runs the audit pipeline in a background thread."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Label, ProgressBar, RichLog

from fsaudit.analyzer.analyzer import analyze
from fsaudit.classifier.classifier import classify
from fsaudit.reporter.excel_reporter import ExcelReporter
from fsaudit.scanner.scanner import FileScanner
from fsaudit.tui.models import ScanConfig


class ProgressScreen(Screen):
    """Shows live scan progress and runs the full pipeline in a worker thread."""

    BINDINGS = [("escape", "go_back", "Back")]

    def __init__(self, config: ScanConfig) -> None:
        super().__init__()
        self._config = config
        self._file_count = 0

    def compose(self) -> ComposeResult:
        yield Header()
        yield Label("Starting audit…", id="lbl-phase")
        yield ProgressBar(id="progress", total=None, show_eta=False)
        yield RichLog(id="log", highlight=True, markup=True, max_lines=100)
        yield Label("", id="lbl-error", classes="error")
        yield Button("Back", id="btn-back", variant="default", disabled=True)
        yield Footer()

    def on_mount(self) -> None:
        self.title = "fsaudit - Running Audit"
        self.run_worker(self._run_audit, thread=True, exclusive=True)

    def action_go_back(self) -> None:
        self.app.pop_screen()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-back":
            self.app.pop_screen()

    # ------------------------------------------------------------------
    # Worker
    # ------------------------------------------------------------------

    def _update_phase(self, text: str) -> None:
        """Safe cross-thread label update."""
        self.app.call_from_thread(self._set_phase, text)

    def _set_phase(self, text: str) -> None:
        self.query_one("#lbl-phase", Label).update(text)

    def _on_file_found(self, path: Path) -> None:
        """Callback invoked by FileScanner for each file — runs in the worker thread."""
        self._file_count += 1

        def _update() -> None:
            log = self.query_one("#log", RichLog)
            log.write(f"[dim]{path}[/dim]")
            bar = self.query_one("#progress", ProgressBar)
            bar.advance(1)
            self.query_one("#lbl-phase", Label).update(
                f"Scanning… {self._file_count:,} files found"
            )

        self.app.call_from_thread(_update)

    def _run_audit(self) -> dict:
        """Full pipeline — runs in a background thread via self.run_worker."""
        cfg = self._config

        # 1. Scan
        self._update_phase("Scanning…")
        scanner = FileScanner(
            exclude_patterns=cfg.exclude,
            max_depth=cfg.depth,
        )
        scan_result = scanner.scan(cfg.root, on_file=self._on_file_found)

        # 2. Classify
        self._update_phase("Classifying…")
        classified = classify(scan_result.files)

        # 3. Min-size filter
        if cfg.min_size > 0:
            classified = [f for f in classified if f.size_bytes >= cfg.min_size]

        # 4. Analyze
        self._update_phase("Analyzing…")
        analysis = analyze(
            classified,
            scan_result,
            inactive_days=cfg.inactive_days,
            hash_duplicates=cfg.hash_duplicates,
        )

        # 5. Generate report
        self._update_phase("Generating report…")
        date_str = datetime.now().strftime("%Y-%m-%d")
        folder_name = cfg.root.name

        if cfg.format == "html":
            from fsaudit.reporter.html_reporter import HtmlReporter

            reporter = HtmlReporter()
            output_path = cfg.output_dir / f"{folder_name}_audit_{date_str}.html"
        else:
            reporter = ExcelReporter()
            output_path = cfg.output_dir / f"{folder_name}_audit_{date_str}.xlsx"

        reporter.generate(classified, analysis, output_path)

        return {
            "records": classified,
            "analysis": analysis,
            "scan_result": scan_result,
            "report_path": output_path,
        }

    def on_worker_success(self, event) -> None:
        """Worker completed successfully — push ResultsScreen."""
        self.dismiss(event.worker.result)

    def on_worker_error(self, event) -> None:
        """Worker failed — show error and enable back button."""
        self.query_one("#lbl-phase", Label).update("[bold red]Audit failed[/bold red]")
        self.query_one("#lbl-error", Label).update(str(event.worker.error))
        self.query_one("#btn-back", Button).disabled = False
