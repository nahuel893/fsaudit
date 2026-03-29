"""Scanner module — recursive filesystem scanning with cross-platform support."""

from fsaudit.scanner.models import DirectoryRecord, FileRecord, ScanResult
from fsaudit.scanner.platform_utils import (
    get_creation_time_safe,
    get_permissions,
    is_hidden,
)
from fsaudit.scanner.scanner import FileScanner

__all__ = [
    "DirectoryRecord",
    "FileRecord",
    "FileScanner",
    "ScanResult",
    "get_creation_time_safe",
    "get_permissions",
    "is_hidden",
]
