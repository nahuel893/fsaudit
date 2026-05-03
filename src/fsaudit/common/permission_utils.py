"""Shared permission-issue detection for fsaudit.

Public API
----------
find_permission_issues(records: list[FileRecord]) -> list[dict]
    Detect world-writable (777 / o+w), SUID, and SGID permission anomalies
    from a list of FileRecords.  Returns an empty list when no issues are found
    or when all records have ``permissions=None`` (Windows).
"""

from __future__ import annotations

from fsaudit.scanner.models import FileRecord


def find_permission_issues(records: list[FileRecord]) -> list[dict]:
    """RF-16: Detect 777, world-writable, SUID, SGID permissions.

    Args:
        records: Classified file records to inspect.

    Returns:
        List of dicts, each with keys ``path``, ``permissions``, ``issue``.
        One dict per issue type per file (a file may contribute multiple dicts
        when it has both a world-writable bit and a SUID bit, for example).
    """
    issues: list[dict] = []
    for r in records:
        if r.permissions is None:
            continue
        perm_str = r.permissions
        try:
            perm_int = int(perm_str, 8)
        except ValueError:
            continue

        # Check each issue type; report the most specific match
        if perm_str == "777":
            issues.append(
                {"path": str(r.path), "permissions": perm_str, "issue": "777"}
            )
        elif perm_str[-1] in ("2", "3", "6", "7"):
            issues.append(
                {
                    "path": str(r.path),
                    "permissions": perm_str,
                    "issue": "world-writable",
                }
            )

        # SUID / SGID (can co-exist with above, so checked independently)
        if perm_int & 0o4000:
            issues.append(
                {"path": str(r.path), "permissions": perm_str, "issue": "suid"}
            )
        if perm_int & 0o2000:
            issues.append(
                {"path": str(r.path), "permissions": perm_str, "issue": "sgid"}
            )

    return issues
