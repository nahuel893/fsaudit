"""Shared data models for the fsaudit TUI."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


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
    output_dir: Path = field(default_factory=Path.cwd)
