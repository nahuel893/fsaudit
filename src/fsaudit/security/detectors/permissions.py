"""Permissions metadata detector for fsaudit.security.

This detector wraps :func:`fsaudit.common.permission_utils.find_permission_issues`
and converts the returned dicts into :class:`~fsaudit.security.models.SecurityFinding`
objects.

It is a :class:`~fsaudit.security.detectors.base.MetadataDetector` and runs
synchronously in the orchestrator thread — no file I/O is performed.

Detection rules
---------------
perm-world-writable / perm-777
    File has world-writable bit set (permissions string ends in 2, 3, 6, or 7)
    or is exactly ``777``.  The ``find_permission_issues`` utility reports
    ``777`` separately from generic world-writable; both map to severity HIGH.

perm-suid
    File has the SUID bit set (octal 4000).  Severity: HIGH.

perm-sgid
    File has the SGID bit set (octal 2000).  Severity: MEDIUM.

Windows no-op
    When ``FileRecord.permissions is None`` the record is silently skipped
    and no finding is emitted — this detector never raises on Windows paths.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from fsaudit.common.permission_utils import find_permission_issues
from fsaudit.security.detectors.base import MetadataDetector
from fsaudit.security.models import SecurityFinding, Severity

if TYPE_CHECKING:
    from fsaudit.scanner.models import FileRecord
    from fsaudit.security.config import SecurityConfig


# ---------------------------------------------------------------------------
# Rule-id → severity mapping
# ---------------------------------------------------------------------------

_ISSUE_SEVERITY: dict[str, Severity] = {
    "777": Severity.HIGH,
    "world-writable": Severity.HIGH,
    "suid": Severity.HIGH,
    "sgid": Severity.MEDIUM,
}

# Map find_permission_issues issue strings → rule_id strings used in findings
_ISSUE_RULE_ID: dict[str, str] = {
    "777": "perm-world-writable",
    "world-writable": "perm-world-writable",
    "suid": "perm-suid",
    "sgid": "perm-sgid",
}


# ---------------------------------------------------------------------------
# Detector
# ---------------------------------------------------------------------------


class PermissionsDetector(MetadataDetector):
    """Metadata-only detector for permission anomalies.

    Wraps :func:`~fsaudit.common.permission_utils.find_permission_issues` and
    normalises the returned dicts into :class:`~fsaudit.security.models.SecurityFinding`
    instances.

    All findings have ``line_no=None`` (metadata detector — no file I/O).
    When ``FileRecord.permissions`` is ``None`` (Windows), no findings are
    produced and no exception is raised.
    """

    @property
    def name(self) -> str:
        return "permissions"

    def scan(
        self,
        records: list["FileRecord"],
        config: "SecurityConfig",
    ) -> list[SecurityFinding]:
        """Inspect each record's permission metadata and return findings.

        Args:
            records: All file records from the scan.
            config:  Active security configuration (unused by this detector
                     but required by the Protocol).

        Returns:
            List of :class:`~fsaudit.security.models.SecurityFinding` instances.
            Returns an empty list when all records have ``permissions=None``.
        """
        # find_permission_issues already skips records with permissions=None
        issues = find_permission_issues(records)
        if not issues:
            return []

        ts = datetime.now(tz=timezone.utc)
        findings: list[SecurityFinding] = []

        for issue in issues:
            issue_type = issue["issue"]
            rule_id = _ISSUE_RULE_ID.get(issue_type, f"perm-{issue_type}")
            severity = _ISSUE_SEVERITY.get(issue_type, Severity.MEDIUM)
            match_context = f"permissions={issue['permissions']}"

            findings.append(
                SecurityFinding(
                    path=issue["path"],
                    detector=self.name,
                    rule_id=rule_id,
                    severity=severity,
                    line_no=None,
                    match_context=match_context,
                    created_at=ts,
                )
            )

        return findings
