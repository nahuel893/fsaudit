"""Data contracts for the analyzer module."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AnalysisResult:
    """Container for all analyzer outputs.

    NOT frozen -- analyzer builds incrementally.
    """

    total_files: int = 0
    total_size_bytes: int = 0
    by_category: dict[str, Any] = field(default_factory=dict)
    top_largest: list[Any] = field(default_factory=list)
    inactive_files: list[Any] = field(default_factory=list)
    zero_byte_files: list[Any] = field(default_factory=list)
    empty_directories: list[Any] = field(default_factory=list)
    duplicates_by_name: dict[str, list[Any]] = field(default_factory=dict)
    timeline: dict[str, Any] = field(default_factory=dict)
    permission_issues: list[Any] = field(default_factory=list)
