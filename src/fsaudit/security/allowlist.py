"""Allowlist suppression logic for fsaudit security findings.

Functions
---------
is_allowed(path, rule_id, match_context, allowlist) -> bool
    Return ``True`` if the finding should be suppressed, ``False`` if it
    should be included in ``SecurityResult.findings``.

Suppression gates (any one match → suppress):
1. **Path gate**: normalise path to forward slashes, then check each glob in
   ``allowlist.paths`` using ``PurePosixPath.match()``.  Globs containing
   ``**`` fall back to ``fnmatch.fnmatchcase`` for cross-platform ``**``
   handling.
2. **Rule gate**: ``rule_id in allowlist.rules``.
3. **Content gate**: ``re.search(pattern, match_context)`` for each pattern in
   ``allowlist.content``.
"""

from __future__ import annotations

import fnmatch
import re
from pathlib import PurePosixPath
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fsaudit.security.config import Allowlist


def is_allowed(
    path: str,
    rule_id: str,
    match_context: str,
    allowlist: "Allowlist",
) -> bool:
    """Return ``True`` if this finding should be suppressed by the allowlist.

    Args:
        path:          File path string (may use OS-native separators).
        rule_id:       Rule identifier that produced the finding.
        match_context: Redacted context string (≤ 60 chars).
        allowlist:     Active :class:`~fsaudit.security.config.Allowlist`.

    Returns:
        ``True``  → finding is allowlisted, exclude from results.
        ``False`` → finding is not suppressed, include in results.
    """
    # Normalise to forward slashes for consistent glob matching
    normalised_path = path.replace("\\", "/")

    # --- Gate 1: path globs ---
    for glob in allowlist.paths:
        if _path_matches_glob(normalised_path, glob):
            return True

    # --- Gate 2: rule ID list ---
    if rule_id in allowlist.rules:
        return True

    # --- Gate 3: content regex ---
    for pattern in allowlist.content:
        try:
            if re.search(pattern, match_context):
                return True
        except re.error:
            # Bad pattern in config — skip silently to avoid crashing the scan
            pass

    return False


def _path_matches_glob(normalised_path: str, glob: str) -> bool:
    """Return ``True`` if *normalised_path* matches *glob*.

    Uses ``PurePosixPath.match()`` for simple patterns; falls back to
    ``fnmatch.fnmatchcase()`` for globs containing ``**``, which
    ``PurePosixPath.match`` handles from Python 3.12+ but not on 3.10/3.11.
    """
    if "**" in glob:
        # fnmatch with ** support via direct string matching
        return fnmatch.fnmatchcase(normalised_path, glob)
    try:
        return PurePosixPath(normalised_path).match(glob)
    except Exception:  # noqa: BLE001
        return False
