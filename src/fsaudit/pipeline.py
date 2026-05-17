"""Pipeline orchestrator — composes scanner, classifier, enricher, analyzer, and reporter.

Stages in run():
  1. Scan  (FileScanner)
  2. Classify (classify())
  3. Filter by min_size
  4. Enrich with author (optional)
  5. Strip time (optional)
  6. Analyze
  7. Security scan (optional)
  8. Report generation (optional)
  9. Return AuditResult
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from datetime import datetime
from pathlib import Path

from fsaudit.analyzer.analyzer import analyze as _analyze
from fsaudit.analyzer.metrics import AnalysisResult
from fsaudit.classifier.classifier import classify
from fsaudit.scanner.models import FileRecord, ScanResult
from fsaudit.scanner.scanner import FileScanner

__all__ = ["Pipeline", "PipelineConfig"]


class PipelineConfig:
    """Configuration for a Pipeline run.

    Attributes:
        root: Root directory to audit.
        max_depth: Maximum recursion depth. ``None`` = unlimited.
        exclude: Glob patterns to exclude from traversal.
        min_size: Minimum file size in bytes (0 = include all).
        inactive_days: Days without modification to consider a file inactive.
        hash_duplicates: Enable SHA-256 hash-based duplicate detection.
        extract_author: Extract author metadata from office/PDF files.
        strip_time: Zero out the time component of mtime/atime/creation_time.
        security_scan: Enable the opt-in security scan stage.
        security_config: Path to a custom security.yaml config file.
        security_max_size: Maximum file size for content scanning (bytes).
        format: Report format: ``"excel"``, ``"html"``, or ``None`` (no report).
        output_dir: Output directory for the report.
        overflow_strategy: How to handle Excel row overflow: ``"shard"`` or ``"csv"``.
    """

    def __init__(
        self,
        root: Path,
        max_depth: int | None = None,
        exclude: list[str] | None = None,
        min_size: int = 0,
        inactive_days: int = 365,
        hash_duplicates: bool = False,
        extract_author: bool = False,
        strip_time: bool = False,
        security_scan: bool = False,
        security_config: Path | None = None,
        security_max_size: int | None = None,
        format: str | None = "excel",
        output_dir: Path | None = None,
        overflow_strategy: str = "shard",
    ) -> None:
        self.root = root
        self.max_depth = max_depth
        self.exclude = exclude or []
        self.min_size = min_size
        self.inactive_days = inactive_days
        self.hash_duplicates = hash_duplicates
        self.extract_author = extract_author
        self.strip_time = strip_time
        self.security_scan = security_scan
        self.security_config = security_config
        self.security_max_size = security_max_size
        self.format = format
        self.output_dir = output_dir
        self.overflow_strategy = overflow_strategy


class Pipeline:
    """Pipeline orchestrator for a full audit run.

    Args:
        config: PipelineConfig describing what to do.
    """

    def __init__(self, config: PipelineConfig) -> None:
        self.config = config

    def run(
        self,
        *,
        on_file: Callable[[Path], None] | None = None,
        on_phase: Callable[[str], None] | None = None,
    ) -> "AuditResult":
        """Execute the full audit pipeline.

        Args:
            on_file: Optional callback invoked with each scanned file's :class:`Path`.
            on_phase: Optional callback invoked between stages with the stage name.

        Returns:
            :class:`~fsaudit.api.AuditResult` with records, analysis, and optional report.
        """
        cfg = self.config
        root = cfg.root.resolve()

        # --- 1. Scan ---
        if on_phase is not None:
            on_phase("Scanning…")
        scanner = FileScanner(
            exclude_patterns=cfg.exclude,
            max_depth=cfg.max_depth,
        )
        scan_result = scanner.scan(root, on_file=on_file)

        # --- 2. Classify ---
        if on_phase is not None:
            on_phase("Classifying…")
        classified = classify(scan_result.files)

        # --- 3. Filter by min_size ---
        if cfg.min_size > 0:
            classified = [f for f in classified if f.size_bytes >= cfg.min_size]

        # --- 4. Enrich with author (optional) ---
        if cfg.extract_author:
            if on_phase is not None:
                on_phase("Extracting author metadata…")
            from fsaudit.enricher import enrich_authors
            classified = enrich_authors(classified)

        # --- 5. Strip time (optional) ---
        if cfg.strip_time:
            if on_phase is not None:
                on_phase("Normalizing timestamps…")
            classified = [
                replace(
                    r,
                    mtime=r.mtime.replace(hour=0, minute=0, second=0, microsecond=0),
                    creation_time=r.creation_time.replace(
                        hour=0, minute=0, second=0, microsecond=0
                    ),
                    atime=r.atime.replace(hour=0, minute=0, second=0, microsecond=0),
                )
                for r in classified
            ]

        # --- 6. Analyze ---
        if on_phase is not None:
            on_phase("Analyzing…")
        analysis = _analyze(
            classified,
            scan_result,
            inactive_days=cfg.inactive_days,
            hash_duplicates=cfg.hash_duplicates,
        )

        # --- 7. Security scan (optional) ---
        security_result = None
        if cfg.security_scan:
            if on_phase is not None:
                on_phase("Running security scan…")
            import sys as _sys

            print(  # noqa: T201
                "[Security Scan] Content scanning enabled. Files will be read to detect "
                "secrets, tokens, and anomalies. May expose sensitive file content in findings.",
                file=_sys.stdout,
            )
            from fsaudit.security import run_security_scan

            security_result = run_security_scan(
                classified,
                config_path=cfg.security_config,
                max_size=cfg.security_max_size,
            )

        # --- 8. Report generation (optional) ---
        report_path: Path | None = None
        overflow_warning: str | None = None
        if cfg.format is not None:
            if on_phase is not None:
                on_phase("Generating report…")
            import platform

            def _default_output_dir() -> Path:
                if platform.system() == "Windows":
                    desktop = Path.home() / "Desktop"
                    if not desktop.exists():
                        desktop = Path.home() / "OneDrive" / "Desktop"
                    return desktop if desktop.exists() else Path.home()
                return Path.home()

            report_dir = cfg.output_dir or _default_output_dir()
            date_str = datetime.now().strftime("%Y-%m-%d")
            folder_name = root.name

            if cfg.format == "html":
                from fsaudit.reporter.html_reporter import HtmlReporter

                reporter = HtmlReporter()
                report_path = report_dir / f"{folder_name}_audit_{date_str}.html"
            else:
                print("Generating Excel report ...")  # noqa: T201
                from fsaudit.reporter.excel_reporter import ExcelReporter

                reporter = ExcelReporter(overflow_strategy=cfg.overflow_strategy)
                report_path = report_dir / f"{folder_name}_audit_{date_str}.xlsx"

            report_path = reporter.generate(classified, analysis, report_path)
            raw_warning = getattr(reporter, "_overflow_warning", None)
            overflow_warning = raw_warning if isinstance(raw_warning, str) else None

        # --- 9. Return AuditResult ---
        # AuditResult is defined in fsaudit.api but avoiding circular import
        # by importing it here at runtime.
        from fsaudit.api import AuditResult

        return AuditResult(
            records=classified,
            analysis=analysis,
            scan_result=scan_result,
            report_path=report_path,
            security=security_result,
            overflow_warning=overflow_warning,
        )