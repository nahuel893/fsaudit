"""Data models for the fsaudit security scan package.

Classes
-------
Severity
    Enumeration of finding severity levels (CRITICAL → LOW).
SecurityFinding
    Immutable record for a single security finding emitted by a detector.
    ``match_context`` is automatically truncated to 60 characters in
    ``__post_init__`` — detectors MUST NOT rely on storing full secrets here.
SecurityResult
    Immutable summary of a complete security scan run.
SecurityConfigError
    Exception raised when the security configuration YAML is malformed,
    missing required fields, or points to a non-existent file.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

_MATCH_CONTEXT_MAX = 60


class Severity(str, Enum):
    """Severity levels for security findings (ordered critical → low)."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass(frozen=True)
class SecurityFinding:
    """Immutable record representing a single security finding.

    Attributes:
        path:          Absolute or relative path of the affected file.
        detector:      Detector name: ``"secrets"`` | ``"entropy"`` |
                       ``"suspicious-files"`` | ``"permissions"``.
        rule_id:       Specific rule that triggered the finding
                       (e.g. ``"aws-access-key"``).
        severity:      Finding severity.
        line_no:       1-based line number; ``None`` for metadata detectors.
        match_context: Redacted excerpt (≤ 60 chars).  Truncated automatically
                       in ``__post_init__`` if the caller passes a longer string.
        created_at:    UTC timestamp of finding creation.
    """

    path: str
    detector: str
    rule_id: str
    severity: Severity
    line_no: int | None
    match_context: str
    created_at: datetime

    def __post_init__(self) -> None:
        # Frozen dataclasses don't allow attribute assignment — use object.__setattr__
        if len(self.match_context) > _MATCH_CONTEXT_MAX:
            object.__setattr__(
                self,
                "match_context",
                self.match_context[:_MATCH_CONTEXT_MAX],
            )


@dataclass(frozen=True)
class SecurityResult:
    """Immutable summary of a complete security scan.

    Attributes:
        findings:       All emitted (and non-allowlisted) findings.
        security_score: Integer 0–100 (100 = clean).
        rules_applied:  IDs of all rules that were active during the scan.
        files_scanned:  Number of files evaluated by content detectors.
        files_skipped:  Number of files skipped (size gate, binary gate, etc.).
        duration_s:     Wall-clock time for the full scan in seconds.
    """

    findings: list[SecurityFinding]
    security_score: int
    rules_applied: list[str]
    files_scanned: int
    files_skipped: int
    duration_s: float


class SecurityConfigError(Exception):
    """Raised when the security configuration cannot be loaded or parsed.

    Common causes:
    - File not found at the specified path.
    - Malformed YAML (syntax error).
    - Missing ``version`` key.
    - Unsupported version number.
    - Missing required rule fields (``id``, ``regex``, ``severity``).
    """
