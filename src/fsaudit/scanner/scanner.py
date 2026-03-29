"""Core filesystem scanner.

Implements :class:`FileScanner` which recursively walks a directory tree
via :func:`os.walk`, collecting OS-level metadata into frozen dataclasses
defined in :mod:`fsaudit.scanner.models`.
"""

import fnmatch
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from fsaudit.scanner.models import DirectoryRecord, FileRecord, ScanResult
from fsaudit.scanner.platform_utils import (
    get_creation_time_safe,
    get_permissions,
    is_hidden,
)

logger = logging.getLogger("fsaudit.scanner")


class FileScanner:
    """Recursive filesystem scanner.

    Walks a directory tree using :func:`os.walk`, builds
    :class:`~fsaudit.scanner.models.FileRecord` for every accessible file
    and :class:`~fsaudit.scanner.models.DirectoryRecord` for empty
    directories.  Errors are collected, never raised.

    Args:
        exclude_patterns: Glob patterns matched via :func:`fnmatch.fnmatch`
            against base names.  Excluded directories are pruned from
            traversal.
        max_depth: Maximum depth relative to *root* (0 = root only).
            ``None`` means unlimited.
        follow_symlinks: Whether to follow symbolic links.  When ``True``,
            a visited-set based on :func:`os.path.realpath` prevents cycles.
    """

    def __init__(
        self,
        exclude_patterns: Optional[list[str]] = None,
        max_depth: Optional[int] = None,
        follow_symlinks: bool = False,
    ) -> None:
        self.exclude_patterns: list[str] = exclude_patterns or []
        self.max_depth: Optional[int] = max_depth
        self.follow_symlinks: bool = follow_symlinks

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def scan(self, root: Path) -> ScanResult:
        """Walk *root* and return a :class:`ScanResult`.

        Never raises — all per-file and per-directory errors are caught
        and appended to :attr:`ScanResult.errors`.
        """
        root = Path(os.path.abspath(root))
        files: list[FileRecord] = []
        dirs: list[DirectoryRecord] = []
        errors: list[str] = []
        visited: set[str] = set()

        # Seed visited set with the root's real path when following symlinks.
        if self.follow_symlinks:
            visited.add(os.path.realpath(str(root)))

        for dirpath, dirnames, filenames in os.walk(
            str(root), followlinks=self.follow_symlinks, onerror=lambda e: errors.append(f"{e.filename}: {e}"),
        ):
            depth = len(Path(dirpath).relative_to(root).parts)

            # --- Prune excluded files before processing ---
            filenames[:] = [
                f for f in filenames if not self._is_excluded(f)
            ]

            # --- Prune dirnames IN-PLACE (prevents os.walk from descending) ---
            dirnames[:] = [
                d for d in dirnames
                if not self._is_excluded(d)
                and (self.max_depth is None or depth < self.max_depth)
                and not self._is_cycle(dirpath, d, visited, errors)
            ]

            # --- Empty directory detection ---
            if not filenames and not dirnames:
                try:
                    sr = os.stat(dirpath)
                    dirs.append(
                        DirectoryRecord(
                            path=Path(dirpath),
                            depth=depth,
                            is_hidden=is_hidden(Path(dirpath).name, sr),
                        )
                    )
                except OSError as exc:
                    errors.append(f"{dirpath}: {exc}")

            # --- Per-file metadata collection ---
            for name in filenames:
                full = os.path.join(dirpath, name)
                try:
                    sr = os.stat(full, follow_symlinks=False)
                    files.append(
                        FileRecord(
                            path=Path(full),
                            name=name,
                            extension=Path(name).suffix.lower(),
                            size_bytes=sr.st_size,
                            mtime=datetime.fromtimestamp(sr.st_mtime),
                            creation_time=get_creation_time_safe(sr),
                            atime=datetime.fromtimestamp(sr.st_atime),
                            depth=depth,
                            is_hidden=is_hidden(name, sr),
                            permissions=get_permissions(sr),
                            parent_dir=str(Path(full).parent),
                        )
                    )
                except (PermissionError, OSError) as exc:
                    logger.warning("Skipping %s: %s", full, exc)
                    errors.append(f"{full}: {exc}")

        return ScanResult(
            files=files,
            directories=dirs,
            root_path=root,
            errors=errors,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _is_excluded(self, name: str) -> bool:
        """Check if *name* matches any exclusion pattern."""
        return any(fnmatch.fnmatch(name, pat) for pat in self.exclude_patterns)

    def _is_cycle(
        self,
        dirpath: str,
        name: str,
        visited: set[str],
        errors: list[str],
    ) -> bool:
        """Return ``True`` if following *name* inside *dirpath* would cycle.

        Only meaningful when :attr:`follow_symlinks` is ``True``.
        """
        if not self.follow_symlinks:
            return False
        real = os.path.realpath(os.path.join(dirpath, name))
        if real in visited:
            logger.debug("Symlink cycle detected: %s -> %s", os.path.join(dirpath, name), real)
            errors.append(f"Symlink cycle detected: {os.path.join(dirpath, name)} -> {real}")
            return True
        visited.add(real)
        return False
