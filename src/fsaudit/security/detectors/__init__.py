"""Detector sub-package for fsaudit.security.

Public exports:
    ALL_DETECTORS — tuple of all registered Detector instances (in priority order)
    run_all(records, config) -> list[SecurityFinding]
        Orchestrates all detectors, using a ThreadPoolExecutor for ContentDetectors
        and running MetadataDetectors synchronously.

Concurrency model
-----------------
- :class:`~fsaudit.security.detectors.base.MetadataDetector` instances run in the
  calling thread (they perform no file I/O and are fast).
- :class:`~fsaudit.security.detectors.base.ContentDetector` instances dispatch
  ``scan_file(record, compiled_rules, config)`` per file via
  ``ThreadPoolExecutor(max_workers=min(32, (os.cpu_count() or 1) + 4))``.
  The ``re`` module is thread-safe, so compiled rules are shared freely.

Rules compiled once
-------------------
``SecretsDetector.compile_rules(config)`` is called ONCE per ``run_all()``
invocation.  The resulting compiled-rule list is passed to every ``scan_file``
call.  ``EntropyDetector`` ignores ``compiled_rules`` (it is keyword-agnostic).
"""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import TYPE_CHECKING

from fsaudit.security.detectors.base import ContentDetector, MetadataDetector
from fsaudit.security.detectors.entropy import EntropyDetector
from fsaudit.security.detectors.permissions import PermissionsDetector
from fsaudit.security.detectors.secrets import SecretsDetector
from fsaudit.security.detectors.suspicious import SuspiciousFilesDetector

if TYPE_CHECKING:
    from fsaudit.scanner.models import FileRecord
    from fsaudit.security.config import SecurityConfig
    from fsaudit.security.models import SecurityFinding


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

ALL_DETECTORS: tuple = (
    SuspiciousFilesDetector(),
    PermissionsDetector(),
    SecretsDetector(),
    EntropyDetector(),
)


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


def run_all(
    records: list["FileRecord"],
    config: "SecurityConfig",
    *,
    max_workers: int | None = None,
) -> list["SecurityFinding"]:
    """Run all registered detectors and return a sorted merged finding list.

    Metadata detectors execute synchronously in the calling thread.
    Content detectors execute in a ``ThreadPoolExecutor``, one future per file
    per detector.

    Rules are compiled ONCE per call and shared across all content-detector
    invocations.

    Args:
        records:     All :class:`~fsaudit.scanner.models.FileRecord` objects to scan.
        config:      Active :class:`~fsaudit.security.config.SecurityConfig`.
        max_workers: Override for thread-pool size (default:
                     ``min(32, (os.cpu_count() or 1) + 4)``).

    Returns:
        All non-allowlisted findings, sorted by ``(path, rule_id, line_no)``
        for determinism.
    """
    if not records:
        return []

    findings: list["SecurityFinding"] = []

    # Resolve worker count
    _workers = max_workers if max_workers is not None else min(32, (os.cpu_count() or 1) + 4)

    # Compile rules ONCE for all ContentDetectors
    compiled_rules_map: dict[str, object] = {}
    for detector in ALL_DETECTORS:
        if isinstance(detector, SecretsDetector):
            compiled_rules_map[detector.name] = detector.compile_rules(config)

    # Run MetadataDetectors synchronously
    for detector in ALL_DETECTORS:
        if isinstance(detector, MetadataDetector) and not isinstance(detector, ContentDetector):
            findings.extend(detector.scan(records, config))

    # Run ContentDetectors via ThreadPoolExecutor
    content_detectors = [d for d in ALL_DETECTORS if isinstance(d, ContentDetector)]
    if content_detectors and records:
        with ThreadPoolExecutor(max_workers=_workers) as executor:
            futures = []
            for detector in content_detectors:
                compiled = compiled_rules_map.get(detector.name)
                # Pre-filter: skip records that fail the detector's cheap
                # metadata gates so no future is submitted for guaranteed
                # no-op work. Saves O(n) submit/lock overhead on big scans.
                for record in records:
                    if not detector.should_scan(record):
                        continue
                    fut = executor.submit(
                        detector.scan_file,
                        record,
                        compiled,
                        config,
                    )
                    futures.append(fut)

            for fut in as_completed(futures):
                result = fut.result()
                if result:
                    findings.extend(result)

    # Sort for determinism: (path, rule_id, line_no or -1)
    findings.sort(key=lambda f: (f.path, f.rule_id, f.line_no if f.line_no is not None else -1))
    return findings
