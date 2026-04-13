"""FSAudit — Filesystem audit tool."""

__version__ = "0.9.0"

# Public API
from fsaudit.api import AuditResult, audit, scan
from fsaudit.analyzer.analyzer import analyze
from fsaudit.analyzer.metrics import AnalysisResult
from fsaudit.classifier.classifier import classify
from fsaudit.enricher import enrich_authors
from fsaudit.scanner.models import DirectoryRecord, FileRecord, ScanResult

__all__ = [
    "__version__",
    "audit",
    "scan",
    "classify",
    "analyze",
    "enrich_authors",
    "AuditResult",
    "AnalysisResult",
    "FileRecord",
    "ScanResult",
    "DirectoryRecord",
]
