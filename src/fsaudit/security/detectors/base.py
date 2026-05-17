"""Detector interface and abstract base classes for fsaudit.security.

Classes
-------
Detector
    Runtime-checkable Protocol defining the minimal contract every detector
    must satisfy: a ``name`` attribute and a ``scan()`` method.

MetadataDetector
    Abstract base class for detectors that operate on ``FileRecord`` metadata
    only (no file I/O).  These are run synchronously in the caller thread.

ContentDetector
    Abstract base class for detectors that read file contents.  Subclasses
    must implement ``scan_file()`` for per-file evaluation; the orchestrator
    dispatches these via ``ThreadPoolExecutor``.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from fsaudit.scanner.models import FileRecord
    from fsaudit.security.models import SecurityConfig, SecurityFinding


@runtime_checkable
class Detector(Protocol):
    """Minimal contract for all security detectors.

    Attributes:
        name: Unique detector identifier (used in ``SecurityFinding.detector``).

    Methods:
        scan: Run the detector over all ``records`` and return findings.
    """

    name: str

    def scan(
        self,
        records: list[FileRecord],
        config: SecurityConfig,
    ) -> list[SecurityFinding]:
        """Scan all records and return a list of findings."""
        ...


class MetadataDetector(ABC):
    """Abstract base class for metadata-only (no I/O) detectors.

    Subclasses must implement ``scan()``.  These detectors run synchronously
    in the orchestrator thread because they perform no blocking I/O.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique detector name."""
        ...

    @abstractmethod
    def scan(
        self,
        records: list[FileRecord],
        config: SecurityConfig,
    ) -> list[SecurityFinding]:
        """Inspect metadata fields of each record and return findings."""
        ...


class ContentDetector(ABC):
    """Abstract base class for content-reading detectors.

    Subclasses must implement ``scan_file()`` (called per eligible file) and
    ``scan()`` (the full-list entry-point used by the orchestrator).  Content
    detectors are dispatched via ``ThreadPoolExecutor`` by ``run_all()``.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique detector name."""
        ...

    def should_scan(self, record: FileRecord) -> bool:
        """Cheap metadata pre-filter for ``record``.

        Returns ``True`` if the detector may emit findings for ``record`` based
        on metadata alone (size, extension, etc.).  The pipeline orchestrator
        calls this BEFORE submitting a future to the executor, avoiding
        millions of no-op task submissions on large scans.

        Default implementation returns ``True`` (no pre-filter).  Subclasses
        should override to mirror their internal metadata gates so the work is
        skipped at submission time instead of inside the worker.
        """
        return True

    @abstractmethod
    def scan_file(
        self,
        record: FileRecord,
        compiled_rules: object,
        config: SecurityConfig,
    ) -> list[SecurityFinding]:
        """Evaluate a single eligible file and return findings.

        Args:
            record:         The file record to inspect.
            compiled_rules: Pre-compiled rule objects (detector-specific shape).
            config:         Active ``SecurityConfig`` for this scan.

        Returns:
            Zero or more ``SecurityFinding`` instances.
        """
        ...

    @abstractmethod
    def scan(
        self,
        records: list[FileRecord],
        config: SecurityConfig,
    ) -> list[SecurityFinding]:
        """Scan all eligible records and return findings."""
        ...
