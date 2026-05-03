"""Suspicious-files metadata detector for fsaudit.security.

This detector inspects ``FileRecord`` metadata ONLY — no file I/O is performed.
It is a :class:`~fsaudit.security.detectors.base.MetadataDetector` and runs
synchronously in the orchestrator thread.

Detection rules
---------------
double-extension
    File name contains more than one extension where the final extension is in
    the executable set (e.g. ``invoice.pdf.exe``).  The stem of the name
    (everything before the last extension) must itself have an extension-like
    suffix, signalling an attempt to disguise an executable as a benign file.
    Severity: HIGH.

macro-enabled-office
    File extension is one of ``{.xlsm, .docm, .pptm, .xltm, .dotm, .potm,
    .ppsm}`` — Microsoft Office formats that can contain embedded macros.
    Severity: MEDIUM.

hidden-executable
    ``FileRecord.is_hidden is True`` AND the file extension is in the
    executable set.  Severity: HIGH.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from fsaudit.security.detectors.base import MetadataDetector
from fsaudit.security.models import SecurityFinding, Severity

if TYPE_CHECKING:
    from fsaudit.scanner.models import FileRecord
    from fsaudit.security.config import SecurityConfig


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_EXECUTABLE_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".exe", ".bat", ".cmd", ".com", ".scr", ".pif", ".vbs", ".vbe",
        ".js", ".jse", ".ws", ".wsf", ".wsc", ".wsh", ".ps1", ".ps2",
        ".sh", ".bash", ".zsh", ".ksh", ".csh", ".fish",
        ".msi", ".msp", ".mst", ".appx", ".msix",
        ".dll", ".so", ".dylib",
        ".jar", ".war", ".ear",
        ".app", ".ipa", ".apk",
    }
)

_MACRO_EXTENSIONS: frozenset[str] = frozenset(
    {".xlsm", ".docm", ".pptm", ".xltm", ".dotm", ".potm", ".ppsm"}
)


# ---------------------------------------------------------------------------
# Detector
# ---------------------------------------------------------------------------


class SuspiciousFilesDetector(MetadataDetector):
    """Metadata-only detector for suspicious file characteristics."""

    @property
    def name(self) -> str:
        return "suspicious-files"

    def scan(
        self,
        records: list["FileRecord"],
        config: "SecurityConfig",
    ) -> list[SecurityFinding]:
        """Inspect each record's metadata and return zero or more findings.

        No file I/O is performed.

        Args:
            records: All file records from the scan.
            config:  Active security configuration (not used by this detector
                     but required by the Protocol).

        Returns:
            List of :class:`~fsaudit.security.models.SecurityFinding` instances.
        """
        findings: list[SecurityFinding] = []
        for record in records:
            findings.extend(self._inspect(record))
        return findings

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _inspect(self, record: "FileRecord") -> list[SecurityFinding]:
        """Return all findings for a single record."""
        results: list[SecurityFinding] = []
        ts = datetime.now(tz=timezone.utc)

        # --- Rule 1: double-extension ---
        if self._is_double_extension(record):
            results.append(
                SecurityFinding(
                    path=str(record.path),
                    detector=self.name,
                    rule_id="double-extension",
                    severity=Severity.HIGH,
                    line_no=None,
                    match_context=f"name={record.name}",
                    created_at=ts,
                )
            )

        # --- Rule 2: macro-enabled office ---
        if record.extension.lower() in _MACRO_EXTENSIONS:
            results.append(
                SecurityFinding(
                    path=str(record.path),
                    detector=self.name,
                    rule_id="macro-enabled-office",
                    severity=Severity.MEDIUM,
                    line_no=None,
                    match_context=f"ext={record.extension}",
                    created_at=ts,
                )
            )

        # --- Rule 3: hidden executable ---
        if record.is_hidden and record.extension.lower() in _EXECUTABLE_EXTENSIONS:
            results.append(
                SecurityFinding(
                    path=str(record.path),
                    detector=self.name,
                    rule_id="hidden-executable",
                    severity=Severity.HIGH,
                    line_no=None,
                    match_context=f"name={record.name}",
                    created_at=ts,
                )
            )

        return results

    @staticmethod
    def _is_double_extension(record: "FileRecord") -> bool:
        """Return True when the file has a dangerous double-extension pattern.

        Criteria:
        - The last extension is in the executable set.
        - The stem (name without last extension) still has a non-empty suffix,
          meaning the name contains at least two period-separated parts after
          the initial name component (e.g. ``report.pdf.exe`` → stem is
          ``report.pdf`` which has suffix ``.pdf``).
        """
        ext = record.extension.lower()
        if ext not in _EXECUTABLE_EXTENSIONS:
            return False
        stem = Path(record.name).stem  # remove last extension
        # The stem must itself have a suffix (i.e. another extension)
        return bool(Path(stem).suffix)
