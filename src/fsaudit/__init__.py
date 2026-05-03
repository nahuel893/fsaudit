"""FSAudit — Filesystem audit tool."""

__version__ = "0.10.0"

# Public API
from fsaudit.api import AuditResult, audit, scan
from fsaudit.analyzer.analyzer import analyze
from fsaudit.analyzer.metrics import AnalysisResult
from fsaudit.classifier.classifier import classify
from fsaudit.enricher import enrich_authors
from fsaudit.scanner.models import DirectoryRecord, FileRecord, ScanResult

# Security API (opt-in; imported lazily here to avoid side-effects when
# security_scan=False, but still available for programmatic use)
from fsaudit.security import (
    SecurityConfigError,
    SecurityFinding,
    SecurityResult,
    Severity,
    run_security_scan,
)

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
    # Security
    "SecurityResult",
    "SecurityFinding",
    "Severity",
    "SecurityConfigError",
    "run_security_scan",
]
