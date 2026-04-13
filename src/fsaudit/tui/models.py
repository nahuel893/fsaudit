"""Shared data models for the fsaudit TUI."""

from __future__ import annotations

import platform
from dataclasses import dataclass, field
from pathlib import Path


def _default_output_dir() -> Path:
    """Default export directory: Desktop on Windows, Home on Linux/macOS."""
    if platform.system() == "Windows":
        desktop = Path.home() / "Desktop"
        if not desktop.exists():
            desktop = Path.home() / "OneDrive" / "Desktop"
        return desktop if desktop.exists() else Path.home()
    return Path.home()


@dataclass
class ScanConfig:
    """Configuration for a single audit run, collected from the TUI."""

    root: Path
    depth: int | None = None
    exclude: list[str] = field(default_factory=list)
    min_size: int = 0
    inactive_days: int = 365
    format: str = "excel"
    hash_duplicates: bool = False
    extract_author: bool = False
    output_dir: Path = field(default_factory=_default_output_dir)
