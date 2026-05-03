"""Security scan package for fsaudit.

Opt-in content and metadata security scan that consumes the already-walked
``list[FileRecord]`` produced by the scanner pipeline and produces a
``SecurityResult`` alongside the existing ``AnalysisResult``.

This package is NEVER imported unless ``security_scan=True`` is passed to
``api.audit()``, keeping the default pipeline fully opt-out.

Public API:
    run_security_scan(records, config_path=None, *, max_size=None, max_workers=None)
        -> SecurityResult
    SecurityResult
    SecurityFinding
    Severity
    SecurityConfigError
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from fsaudit.security.config import load_config
from fsaudit.security.detectors import run_all
from fsaudit.security.models import (
    SecurityConfigError,
    SecurityFinding,
    SecurityResult,
    Severity,
)
from fsaudit.security.scorer import compute_security_score

if TYPE_CHECKING:
    from pathlib import Path

    from fsaudit.scanner.models import FileRecord

__all__ = [
    "run_security_scan",
    "SecurityResult",
    "SecurityFinding",
    "Severity",
    "SecurityConfigError",
]

_DEFAULT_MAX_SIZE_BYTES: int = 1_048_576  # 1 MiB


def run_security_scan(
    records: list["FileRecord"],
    config_path: "str | Path | None" = None,
    *,
    max_size: int | None = None,
    max_workers: int | None = None,
) -> SecurityResult:
    """Run the full security scan pipeline and return a :class:`SecurityResult`.

    Loads the active :class:`~fsaudit.security.config.SecurityConfig` (from
    *config_path*, the user's ``~/.fsaudit/security.yaml``, or the bundled
    ``patterns.yaml`` — in that resolution order), runs all registered
    detectors via :func:`~fsaudit.security.detectors.run_all`, computes a
    :func:`~fsaudit.security.scorer.compute_security_score`, and packages the
    result.

    Args:
        records:     All :class:`~fsaudit.scanner.models.FileRecord` objects
                     from the scan pipeline.
        config_path: Optional explicit path to a ``security.yaml`` config file.
                     Overrides the user default and bundled config.
        max_size:    Max file size (bytes) passed to content detectors.
                     Defaults to 1 MiB when ``None``.
        max_workers: Thread-pool size override. ``None`` = auto.

    Returns:
        :class:`SecurityResult` with findings, score, timing, and counts.

    Raises:
        SecurityConfigError: If the config file is malformed or missing
            required fields.
    """
    start = time.monotonic()

    # Load config
    config = load_config(path=str(config_path) if config_path is not None else None)

    # Track rules_applied (IDs of all active rules)
    rules_applied = [rule.id for rule in config.rules]

    # Run detectors
    findings = run_all(records, config, max_workers=max_workers)

    # Count files_scanned and files_skipped
    # Content detectors apply gates; approximation: count non-empty text-extension records
    # that fit within max_size as "scanned", others as "skipped".
    _max = max_size if max_size is not None else _DEFAULT_MAX_SIZE_BYTES

    from fsaudit.security.detectors.secrets import _TEXT_EXTENSIONS  # local import OK

    files_scanned = 0
    files_skipped = 0
    for record in records:
        if record.size_bytes > _max:
            files_skipped += 1
        elif record.extension.lower() not in _TEXT_EXTENSIONS:
            files_skipped += 1
        else:
            files_scanned += 1

    # Compute score
    security_score = compute_security_score(findings)

    duration_s = time.monotonic() - start

    return SecurityResult(
        findings=findings,
        security_score=security_score,
        rules_applied=rules_applied,
        files_scanned=files_scanned,
        files_skipped=files_skipped,
        duration_s=duration_s,
    )
