"""CLI entry point for fsaudit.

Parses arguments, validates input, orchestrates the pipeline
(scan -> classify -> analyze -> report), and provides console feedback.
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

from fsaudit.analyzer.analyzer import analyze
from fsaudit.classifier.classifier import classify
from fsaudit.logging_config import setup_logging
from fsaudit.reporter.excel_reporter import ExcelReporter
from fsaudit.scanner.scanner import FileScanner

logger = logging.getLogger("fsaudit.cli")

_VALID_LOG_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR")


def build_parser() -> argparse.ArgumentParser:
    """Define CLI arguments. Pure function, no side effects."""
    parser = argparse.ArgumentParser(
        prog="fsaudit",
        description="Audit a directory: scan, classify, analyze, and generate an Excel report.",
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
    return parser


def main(argv: list[str] | None = None) -> int:
    """Parse args, run pipeline, return exit code (0=ok, 1=error).

    Args:
        argv: Argument list. None = sys.argv[1:] (production).
    """
    parser = build_parser()
    args = parser.parse_args(argv)

    # --- Input validation ---
    path = Path(args.path).resolve()
    if not path.is_dir():
        print(
            f"Error: '{args.path}' does not exist or is not a directory.",
            file=sys.stderr,
        )
        return 1

    output_dir = Path(args.output_dir).resolve()
    if not output_dir.is_dir():
        print(
            f"Error: '{args.output_dir}' does not exist or is not a directory.",
            file=sys.stderr,
        )
        return 1

    # --- Logging setup ---
    log_file = Path(args.log_file) if args.log_file else None
    setup_logging(level=args.log_level, log_file=log_file)

    try:
        # --- 1. Scan ---
        print(f"Scanning {path} ...")
        scanner = FileScanner(
            exclude_patterns=args.exclude,
            max_depth=args.depth,
        )
        scan_result = scanner.scan(path)
        print(f"Scan complete: {len(scan_result.files):,} files found ({len(scan_result.errors)} errors).")

        # --- 2. Classify ---
        print("Classifying files ...")
        classified = classify(scan_result.files)
        print("Classification complete.")

        # --- 3. Min-size filter ---
        if args.min_size > 0:
            classified = [f for f in classified if f.size_bytes >= args.min_size]

        # --- 4. Analyze ---
        print("Analyzing ...")
        analysis = analyze(
            classified,
            scan_result,
            inactive_days=args.inactive_days,
        )
        print("Analysis complete.")

        # --- 5. Report ---
        print("Generating Excel report ...")
        folder_name = path.name
        date_str = datetime.now().strftime("%Y-%m-%d")
        output_path = output_dir / f"{folder_name}_audit_{date_str}.xlsx"

        reporter = ExcelReporter()
        reporter.generate(classified, analysis, output_path)
        print(f"Report saved: {output_path}")

        return 0

    except Exception as exc:
        logger.exception("Fatal error: %s", exc)
        print(f"Error: {exc}", file=sys.stderr)
        return 1
