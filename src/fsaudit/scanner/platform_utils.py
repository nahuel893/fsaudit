"""Cross-platform filesystem abstractions.

Isolates OS-dependent operations (creation time, hidden detection,
permissions) behind pure functions. The module-level ``PLATFORM`` constant
can be monkeypatched in tests to simulate cross-platform behaviour.
"""

import stat
import sys
from datetime import datetime
from os import stat_result
from typing import Optional

# Module-level constant — monkeypatch in tests to simulate other OSes.
PLATFORM: str = sys.platform

# Windows hidden-file flag (from the Windows API).
_FILE_ATTRIBUTE_HIDDEN = 0x2


def get_creation_time_safe(sr: stat_result) -> datetime:
    """Return the best-effort creation time for the current OS.

    * **Windows** (``win32``): uses ``st_ctime`` (NTFS creation time).
    * **macOS** (``darwin``): uses ``st_birthtime`` when available,
      otherwise falls back to the Linux strategy.
    * **Linux**: uses ``min(st_mtime, st_ctime)`` as approximation.

    Args:
        sr: An :class:`os.stat_result` obtained via :func:`os.stat`.

    Returns:
        A timezone-naive :class:`~datetime.datetime`.
    """
    if PLATFORM == "win32":
        return datetime.fromtimestamp(sr.st_ctime)

    if PLATFORM == "darwin":
        if hasattr(sr, "st_birthtime"):
            return datetime.fromtimestamp(sr.st_birthtime)
        # Fallback when birthtime is unavailable.
        return datetime.fromtimestamp(min(sr.st_mtime, sr.st_ctime))

    # Linux and everything else — min(mtime, ctime) as proxy.
    return datetime.fromtimestamp(min(sr.st_mtime, sr.st_ctime))


def is_hidden(name: str, sr: stat_result) -> bool:
    """Detect whether a file or directory should be considered hidden.

    * **Linux / macOS**: hidden when *name* starts with ``'.'``.
    * **Windows** (``win32``): hidden when ``st_file_attributes`` has the
      ``FILE_ATTRIBUTE_HIDDEN`` flag set.  Falls back to the dot-prefix
      heuristic when the attribute is unavailable.

    Args:
        name: The base name (not full path) of the entry.
        sr: An :class:`os.stat_result` for the entry.

    Returns:
        ``True`` if the entry is hidden for the current platform.
    """
    if PLATFORM == "win32":
        if hasattr(sr, "st_file_attributes"):
            return bool(sr.st_file_attributes & _FILE_ATTRIBUTE_HIDDEN)
        # Fallback to dot-prefix when st_file_attributes is missing.
        return name.startswith(".")

    return name.startswith(".")


def get_permissions(sr: stat_result) -> Optional[str]:
    """Return a human-readable permission string.

    * **Linux / macOS**: octal string derived from ``st_mode``
      (e.g. ``"755"``).
    * **Windows**: returns ``None`` (NTFS ACLs are out of scope).

    Args:
        sr: An :class:`os.stat_result` for the entry.

    Returns:
        An octal permission string or ``None`` on Windows.
    """
    if PLATFORM == "win32":
        return None

    return oct(stat.S_IMODE(sr.st_mode))[2:]  # strip '0o' prefix
