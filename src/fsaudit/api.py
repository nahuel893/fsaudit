"""Public API for fsaudit — import and use programmatically.

Usage::

    import fsaudit
    result = fsaudit.audit("/path/to/dir")
    print(result.health_score)
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from fsaudit.analyzer.metrics import AnalysisResult
from fsaudit.pipeline import Pipeline, PipelineConfig
from fsaudit.scanner.models import FileRecord, ScanResult

_VALID_FORMATS = {"excel", "html"}


@dataclass
class AuditResult:
    """Result of a full audit pipeline run."""

    records: list[FileRecord]
    analysis: AnalysisResult
    scan_result: ScanResult
    report_path: Path | None = None
    security: "SecurityResult | None" = None
    overflow_warning: str | None = None

    @property
    def health_score(self) -> float:
        """Filesystem health score in [0, 100]."""
        return self.analysis.health_score

    @property
    def total_files(self) -> int:
        """Total number of files included after all filters."""
        return self.analysis.total_files

    @property
    def total_size_bytes(self) -> int:
        """Total size in bytes of all included files."""
        return self.analysis.total_size_bytes

    @property
    def categories(self) -> dict[str, dict]:
        """Category distribution: name → stats dict."""
        return self.analysis.by_category


def scan(
    path: str | Path,
    *,
    max_depth: int | None = None,
    exclude: list[str] | None = None,
    on_file: Callable[[Path], None] | None = None,
) -> ScanResult:
    """Scan a directory and return raw scan results.

    Args:
        path: Directory to scan.
        max_depth: Max directory depth. ``None`` = unlimited.
        exclude: Glob patterns to exclude from traversal.
        on_file: Optional callback invoked with each scanned file's :class:`Path`.

    Returns:
        :class:`~fsaudit.scanner.models.ScanResult` with all discovered files.

    Raises:
        FileNotFoundError: If *path* does not exist or is not a directory.
    """
    from fsaudit.scanner.scanner import FileScanner

    root = Path(path).resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"'{path}' does not exist or is not a directory")

    scanner = FileScanner(
        exclude_patterns=exclude or [],
        max_depth=max_depth,
    )
    return scanner.scan(root, on_file=on_file)


def audit(
    path: str | Path,
    *,
    output_dir: str | Path | None = None,
    format: str | None = "excel",
    max_depth: int | None = None,
    exclude: list[str] | None = None,
    min_size: int = 0,
    inactive_days: int = 365,
    hash_duplicates: bool = False,
    extract_author: bool = False,
    strip_time: bool = False,
    on_file: Callable[[Path], None] | None = None,
    security_scan: bool = False,
    security_config: Path | None = None,
    security_max_size: int | None = None,
    overflow_strategy: str = "shard",
) -> AuditResult:
    """Run the full audit pipeline on *path*.

    Args:
        path: Directory to audit.
        output_dir: Where to save the report. ``None`` = platform default
            (Desktop on Windows, home directory on Linux/macOS).
        format: ``"excel"``, ``"html"``, or ``None`` (no report generated).
        max_depth: Max directory depth. ``None`` = unlimited.
        exclude: Glob patterns to exclude.
        min_size: Minimum file size in bytes to include (0 = include all).
        inactive_days: Days without modification to consider inactive.
        hash_duplicates: Enable SHA-256 duplicate detection (slower).
        extract_author: Extract author metadata from office/PDF files.
        strip_time: Zero out time component of mtime/atime/creation_time.
        on_file: Callback invoked with :class:`Path` per scanned file.
        overflow_strategy: How to handle Excel row overflow. ``"shard"``
            splits inventory into multiple sheets; ``"csv"`` writes a CSV
            file instead.  Default ``"shard"``.

    Returns:
        :class:`AuditResult` with records, analysis, and optional report path.

    Raises:
        FileNotFoundError: If *path* or *output_dir* does not exist.
        ValueError: If *format* is not ``"excel"``, ``"html"``, or ``None``.
    """
    # Validate format before any I/O
    if format is not None and format not in _VALID_FORMATS:
        raise ValueError(
            f"Invalid format '{format}'. Must be one of: {sorted(_VALID_FORMATS)} or None"
        )

    # Validate input path
    root = Path(path).resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"'{path}' does not exist or is not a directory")

    # Resolve and validate output directory (only when generating a report)
    report_dir: Path | None = None
    if format is not None:
        import platform

        def _default_output_dir() -> Path:
            if platform.system() == "Windows":
                desktop = Path.home() / "Desktop"
                if not desktop.exists():
                    desktop = Path.home() / "OneDrive" / "Desktop"
                return desktop if desktop.exists() else Path.home()
            return Path.home()

        report_dir = Path(output_dir).resolve() if output_dir else _default_output_dir()
        if not report_dir.is_dir():
            raise FileNotFoundError(
                f"Output directory '{output_dir}' does not exist"
            )

    config = PipelineConfig(
        root=root,
        max_depth=max_depth,
        exclude=exclude or [],
        min_size=min_size,
        inactive_days=inactive_days,
        hash_duplicates=hash_duplicates,
        extract_author=extract_author,
        strip_time=strip_time,
        security_scan=security_scan,
        security_config=security_config,
        security_max_size=security_max_size,
        format=format,
        output_dir=report_dir,
        overflow_strategy=overflow_strategy,
    )

    return Pipeline(config).run(on_file=on_file)