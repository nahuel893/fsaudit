"""ProgressScreen — runs the audit pipeline in a background thread."""

from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path

from textual.app import ComposeResult
from textual.screen import Screen
from textual.containers import Horizontal
from textual.widgets import Button, Header, Label, ProgressBar, RichLog

from fsaudit.analyzer.analyzer import analyze
from fsaudit.classifier.classifier import classify
from fsaudit.reporter.excel_reporter import ExcelReporter
from fsaudit.scanner.scanner import FileScanner
from fsaudit.tui.models import ScanConfig


_THROTTLE_INTERVAL = 0.1  # seconds between UI updates


class ProgressScreen(Screen):
    """Shows live scan progress and runs the full pipeline in a worker thread."""

    BINDINGS = [("escape", "go_back", "Back")]

    def __init__(self, config: ScanConfig) -> None:
        super().__init__()
        self._config = config
        self._file_count = 0
        self._last_update: float = 0.0
        self._last_path: str = ""
        self._finished = False
        self._worker_result: dict | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        yield Label("Starting audit…", id="lbl-phase")
        with Horizontal(id="action-bar"):
            yield Button("Back", id="btn-back", variant="default", disabled=True)
            yield Button("Ver Resultados ↵", id="btn-continue", variant="primary", disabled=True)
            yield Button("Salir", id="btn-quit", variant="error", disabled=True)
        yield Label("", id="lbl-file-count")
        yield ProgressBar(id="progress", total=100, show_eta=False)
        yield RichLog(id="log", highlight=True, markup=True, max_lines=50)
        yield Label("", id="lbl-error", classes="error")

    def on_mount(self) -> None:
        self.title = "fsaudit - Running Audit"
        self.run_worker(self._run_audit, thread=True, exclusive=True)

    def action_go_back(self) -> None:
        self.app.pop_screen()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-back":
            self.app.pop_screen()
        elif event.button.id == "btn-continue":
            self.dismiss(self._worker_result)
        elif event.button.id == "btn-quit":
            self.app.exit()

    # ------------------------------------------------------------------
    # Worker
    # ------------------------------------------------------------------

    def _update_phase(self, text: str) -> None:
        """Safe cross-thread label update."""
        self.app.call_from_thread(self._set_phase, text)

    def _set_phase(self, text: str) -> None:
        self.query_one("#lbl-phase", Label).update(text)

    def _on_file_found(self, path: Path) -> None:
        """Callback invoked by FileScanner for each file — runs in the worker thread.

        Throttles UI updates to avoid flooding the Textual event loop.
        """
        self._file_count += 1
        self._last_path = str(path)

        now = time.monotonic()
        if now - self._last_update >= _THROTTLE_INTERVAL:
            self._last_update = now
            count = self._file_count
            display_path = self._last_path
            if len(display_path) > 70:
                display_path = "…" + display_path[-67:]

            def _update() -> None:
                try:
                    self.query_one("#lbl-file-count", Label).update(
                        f"Files found: [bold]{count:,}[/bold]"
                    )
                    log = self.query_one("#log", RichLog)
                    log.write(f"[dim]{display_path}[/dim]")
                except Exception:
                    pass  # screen may have been unmounted

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

        # Final scan count update
        count = self._file_count

        def _final_scan_update() -> None:
            try:
                self.query_one("#lbl-file-count", Label).update(
                    f"Files found: [bold]{count:,}[/bold] ✓"
                )
                bar = self.query_one("#progress", ProgressBar)
                bar.update(progress=33)
            except Exception:
                pass

        self.app.call_from_thread(_final_scan_update)

        # 2. Classify
        self._update_phase(f"Classifying {count:,} files…")
        classified = classify(scan_result.files)

        # 3. Min-size filter
        if cfg.min_size > 0:
            classified = [f for f in classified if f.size_bytes >= cfg.min_size]

        # 4. Author extraction (if configured)
        if getattr(cfg, "extract_author", False):
            self._update_phase("Extracting author metadata…")
            from fsaudit.enricher import enrich_authors
            classified = enrich_authors(classified)

        # 5. Strip time from dates (if configured)
        if getattr(cfg, "strip_time", False):
            from dataclasses import replace
            classified = [
                replace(
                    r,
                    mtime=r.mtime.replace(hour=0, minute=0, second=0, microsecond=0),
                    creation_time=r.creation_time.replace(hour=0, minute=0, second=0, microsecond=0),
                    atime=r.atime.replace(hour=0, minute=0, second=0, microsecond=0),
                )
                for r in classified
            ]

        def _classify_done() -> None:
            try:
                bar = self.query_one("#progress", ProgressBar)
                bar.update(progress=50)
            except Exception:
                pass

        self.app.call_from_thread(_classify_done)

        # 5. Analyze
        self._update_phase("Analyzing…")
        analysis = analyze(
            classified,
            scan_result,
            inactive_days=cfg.inactive_days,
            hash_duplicates=cfg.hash_duplicates,
        )

        def _analyze_done() -> None:
            try:
                bar = self.query_one("#progress", ProgressBar)
                bar.update(progress=75)
            except Exception:
                pass

        self.app.call_from_thread(_analyze_done)

        # 6. Generate report
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

        def _report_done() -> None:
            try:
                bar = self.query_one("#progress", ProgressBar)
                bar.update(progress=100)
                self.query_one("#lbl-phase", Label).update(
                    "[bold green]Audit complete![/bold green]"
                )
            except Exception:
                pass

        self.app.call_from_thread(_report_done)
        self._finished = True

        return {
            "records": classified,
            "analysis": analysis,
            "scan_result": scan_result,
            "report_path": output_path,
        }

    def on_worker_state_changed(self, event) -> None:
        """Handle worker state transitions."""
        from textual.worker import WorkerState

        if event.state == WorkerState.SUCCESS:
            self._on_success(event.worker)
        elif event.state == WorkerState.ERROR:
            self._on_error(event.worker)

    def _on_success(self, worker) -> None:
        """Worker completed — enable buttons and show results."""
        try:
            self._worker_result = worker.result
        except Exception:
            self._worker_result = None

        # Enable buttons
        self.query_one("#btn-continue", Button).disabled = False
        self.query_one("#btn-quit", Button).disabled = False

        # Update labels
        try:
            result = self._worker_result or {}
            analysis = result.get("analysis")
            report_path = result.get("report_path", "")
            if analysis:
                self.query_one("#lbl-phase", Label).update(
                    f"[bold green]Audit complete![/bold green]  "
                    f"Files: {analysis.total_files:,} | Health: {analysis.health_score:.1f}/100"
                )
            self.query_one("#log", RichLog).write(
                f"\n[bold]Report saved:[/bold] {report_path}"
            )
        except Exception:
            pass

    def _on_error(self, worker) -> None:
        """Worker failed — show error and enable back button."""
        self.query_one("#lbl-phase", Label).update("[bold red]Audit failed[/bold red]")
        error_msg = str(worker.error) if worker.error else "Unknown error"
        self.query_one("#lbl-error", Label).update(error_msg)
        self.query_one("#btn-back", Button).disabled = False
