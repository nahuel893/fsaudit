"""CLI entry point for fsaudit.

Parses arguments, validates input, orchestrates the pipeline
(scan -> classify -> analyze -> report), and provides console feedback.
"""

from __future__ import annotations

import argparse
import logging
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

from fsaudit.analyzer.analyzer import analyze
from fsaudit.classifier.classifier import classify
from fsaudit.logging_config import setup_logging
from fsaudit.reporter.excel_reporter import ExcelReporter
from fsaudit.scanner.scanner import FileScanner

logger = logging.getLogger("fsaudit.cli")

_DEFAULT_DB = Path.home() / ".fsaudit" / "audits.db"

_VALID_LOG_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR")


def build_parser() -> argparse.ArgumentParser:
    """Define CLI arguments. Pure function, no side effects."""
    parser = argparse.ArgumentParser(
        prog="fsaudit",
        description="Audit a directory: scan, classify, analyze, and generate a report.",
    )
    parser.add_argument(
        "--path",
        required=True,
        help="Root directory to audit.",
    )
    parser.add_argument(
        "--output-dir",
        default=".",
        help="Directory for the output report (default: current directory).",
    )
    parser.add_argument(
        "--depth",
        type=int,
        default=None,
        help="Maximum recursion depth (default: unlimited).",
    )
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        help="Directory/file patterns to exclude. May be specified multiple times.",
    )
    parser.add_argument(
        "--min-size",
        type=int,
        default=0,
        help="Minimum file size in bytes to include (default: 0).",
    )
    parser.add_argument(
        "--inactive-days",
        type=int,
        default=365,
        help="Days without modification to classify as inactive (default: 365).",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=_VALID_LOG_LEVELS,
        type=str.upper,
        help="Logging verbosity (default: INFO).",
    )
    parser.add_argument(
        "--log-file",
        default=None,
        help="Path to log file. If omitted, log to stderr only.",
    )
    parser.add_argument(
        "--hash-duplicates",
        action="store_true",
        default=False,
        help="Hash name-duplicate files to confirm true byte-level duplicates (slower).",
    )
    parser.add_argument(
        "--format",
        choices=["excel", "html"],
        default="excel",
        help="Output report format: excel (default) or html.",
    )
    # --- Persistence flags (Task 2D.4) ---
    parser.add_argument(
        "--save",
        action="store_true",
        default=False,
        help="Save analysis run to SQLite history database.",
    )
    parser.add_argument(
        "--db",
        type=str,
        default=None,
        help="Path to SQLite database file (default: ~/.fsaudit/audits.db).",
    )
    parser.add_argument(
        "--history",
        action="store_true",
        default=False,
        help="List all saved analysis runs and exit.",
    )
    parser.add_argument(
        "--diff",
        type=int,
        default=None,
        metavar="RUN_ID",
        help="Compare current run against a saved run ID.",
    )
    # --- Extended persistence flags (Task 2D.5) ---
    parser.add_argument(
        "--save-files",
        action="store_true",
        default=False,
        help="Save per-file records to the database (requires --save).",
    )
    parser.add_argument(
        "--query",
        type=str,
        default=None,
        help="Execute a SELECT query against the history database and print results.",
    )
    return parser


def main(argv: list[str] | None = None, *, _console: Console | None = None) -> int:
    """Parse args, run pipeline, return exit code (0=ok, 1=error).

    Args:
        argv: Argument list. None = sys.argv[1:] (production).
        _console: Optional rich Console for dependency injection in tests.
    """
    console = _console or Console(file=sys.stdout, highlight=False)

    parser = build_parser()
    args = parser.parse_args(argv)

    # --- Resolve db path ---
    db_path = Path(args.db) if args.db else _DEFAULT_DB

    # --- --history: list runs and exit ---
    if getattr(args, "history", False):
        return _cmd_history(console, db_path)

    # --- --query: execute SELECT and exit ---
    if getattr(args, "query", None):
        return _cmd_query(console, db_path, args.query)

    # --- Input validation ---
    path = Path(args.path).resolve()
    if not path.is_dir():
        Console(file=sys.stderr, highlight=False).print(
            f"Error: '{args.path}' does not exist or is not a directory."
        )
        return 1

    output_dir = Path(args.output_dir).resolve()
    if not output_dir.is_dir():
        Console(file=sys.stderr, highlight=False).print(
            f"Error: '{args.output_dir}' does not exist or is not a directory."
        )
        return 1

    # --- Logging setup ---
    log_file = Path(args.log_file) if args.log_file else None
    setup_logging(level=args.log_level, log_file=log_file)

    try:
        # --- 1. Scan ---
        console.print(f"Scanning {path} ...")
        scanner = FileScanner(
            exclude_patterns=args.exclude,
            max_depth=args.depth,
        )
        file_count_seen = [0]

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("{task.fields[files_found]} files"),
            TimeElapsedColumn(),
            console=console,
            transient=True,
        ) as progress:
            task = progress.add_task("Scanning...", total=None, files_found=0)

            def _on_file(p: Path) -> None:
                file_count_seen[0] += 1
                progress.update(task, files_found=file_count_seen[0])

            scan_result = scanner.scan(path, on_file=_on_file)

        console.print(
            f"Scan complete: {len(scan_result.files):,} files found"
            f" ({len(scan_result.errors)} errors)."
        )

        # --- 2. Classify ---
        console.print("Classifying files ...")
        with console.status(""):
            classified = classify(scan_result.files)
        console.print("Classification complete.")

        # --- 3. Min-size filter ---
        if args.min_size > 0:
            classified = [f for f in classified if f.size_bytes >= args.min_size]

        # --- 4. Analyze ---
        console.print("Analyzing ...")
        with console.status(""):
            analysis = analyze(
                classified,
                scan_result,
                inactive_days=args.inactive_days,
                hash_duplicates=args.hash_duplicates,
            )
        console.print("Analysis complete.")

        # --- Health panel ---
        score = analysis.health_score
        color = "green" if score >= 80 else "yellow" if score >= 60 else "red"
        breakdown_lines = "\n".join(
            f"  {k}: -{v:.2f}" for k, v in analysis.health_breakdown.items()
        )
        console.print(
            Panel(
                f"[bold {color}]Health Score: {score:.1f}/100[/bold {color}]\n\n"
                + breakdown_lines,
                title="Filesystem Health",
                expand=False,
            )
        )

        # --- 5. Report ---
        fmt = getattr(args, "format", "excel")
        if fmt == "html":
            from fsaudit.reporter.html_reporter import HtmlReporter
            console.print("Generating HTML report ...")
            folder_name = path.name
            date_str = datetime.now().strftime("%Y-%m-%d")
            output_path = output_dir / f"{folder_name}_audit_{date_str}.html"
            reporter: ExcelReporter | HtmlReporter = HtmlReporter()  # type: ignore[assignment]
        else:
            console.print("Generating Excel report ...")
            folder_name = path.name
            date_str = datetime.now().strftime("%Y-%m-%d")
            output_path = output_dir / f"{folder_name}_audit_{date_str}.xlsx"
            reporter = ExcelReporter()

        reporter.generate(classified, analysis, output_path)
        console.print(f"Report saved: {output_path}")

        # --- 6. Persist run if requested ---
        if getattr(args, "save", False):
            try:
                from fsaudit.persistence.db import get_connection
                from fsaudit.persistence.repository import save_run, save_file_records, diff_runs

                with get_connection(db_path) as conn:
                    run_id = save_run(conn, str(path), analysis)
                    if getattr(args, "save_files", False):
                        save_file_records(conn, run_id, classified)
                    console.print(f"Run saved: id={run_id} db={db_path}")

                    # --- --diff: compare against saved run ---
                    if getattr(args, "diff", None) is not None:
                        delta = diff_runs(conn, args.diff, run_id)
                        if delta is None:
                            console.print(
                                f"[yellow]Run {args.diff} not found — cannot diff.[/yellow]"
                            )
                        else:
                            console.print("[bold]Run diff:[/bold]")
                            for key, val in delta.items():
                                console.print(f"  {key}: {val:+}")

            except sqlite3.OperationalError as exc:
                logger.warning("Could not save run to database: %s", exc)
                console.print(f"[yellow]Warning: could not save run — {exc}[/yellow]")

        return 0

    except Exception as exc:
        logger.exception("Fatal error: %s", exc)
        Console(file=sys.stderr, highlight=False).print(f"Error: {exc}")
        return 1


# ---------------------------------------------------------------------------
# Sub-commands
# ---------------------------------------------------------------------------

def _cmd_history(console: Console, db_path: Path) -> int:
    """List all saved runs. Returns exit code."""
    if not db_path.exists():
        console.print("No runs recorded.")
        return 0

    try:
        from fsaudit.persistence.db import get_connection
        from fsaudit.persistence.repository import list_runs

        with get_connection(db_path) as conn:
            runs = list_runs(conn)

        if not runs:
            console.print("No runs recorded.")
            return 0

        console.print(f"{'ID':>4}  {'Timestamp':20}  {'Path':40}  {'Files':>8}  {'Score':>6}")
        console.print("-" * 90)
        for run in runs:
            console.print(
                f"{run['id']:>4}  {run['timestamp']:20}  {run['root_path']:40}  "
                f"{run['total_files']:>8}  {run['health_score']:>6.1f}"
            )
        return 0

    except sqlite3.OperationalError as exc:
        logger.warning("Could not read history: %s", exc)
        console.print(f"[yellow]Warning: could not read history — {exc}[/yellow]")
        return 0


def _cmd_query(console: Console, db_path: Path, sql: str) -> int:
    """Execute a SELECT query and print results. Returns exit code."""
    try:
        from fsaudit.persistence.db import get_connection
        from fsaudit.persistence.repository import execute_query

        with get_connection(db_path) as conn:
            rows = execute_query(conn, sql)

        if not rows:
            console.print("(no rows)")
            return 0

        headers = list(rows[0].keys())
        console.print("  ".join(f"{h:>12}" for h in headers))
        console.print("-" * (14 * len(headers)))
        for row in rows:
            console.print("  ".join(f"{str(row[h]):>12}" for h in headers))
        return 0

    except ValueError as exc:
        Console(file=sys.stderr, highlight=False).print(f"Error: {exc}")
        return 1
    except sqlite3.OperationalError as exc:
        Console(file=sys.stderr, highlight=False).print(f"Error: {exc}")
        return 1
