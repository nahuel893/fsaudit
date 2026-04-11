"""Data contracts for the scanner module."""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class FileRecord:
    """Immutable record representing a single scanned file.

    All 12 fields match PRD section 8.1.
    """

    path: Path
    name: str
    extension: str  # lowercase, empty string if none
    size_bytes: int
    mtime: datetime
    creation_time: datetime  # OS-aware via get_creation_time_safe()
    atime: datetime
    depth: int  # relative to scan root
    is_hidden: bool
    permissions: Optional[str]  # octal string e.g. "755", None on Windows
    category: str = "Unclassified"  # set by Classifier
    parent_dir: str = ""  # str(path.parent)
    author: str | None = None  # extracted by enricher


@dataclass(frozen=True)
class DirectoryRecord:
    """Immutable record representing a scanned directory (typically empty ones)."""

    path: Path
    depth: int
    is_hidden: bool


@dataclass(frozen=True)
class ScanResult:
    """Container holding the complete output of a filesystem scan."""

    files: list[FileRecord]
    directories: list[DirectoryRecord]
    root_path: Path  # scan root for reference
    errors: list[str] = field(default_factory=list)  # PermissionError paths
