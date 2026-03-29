# Proposal: phase1-analyzer

**Date**: 2026-03-29
**Status**: proposed
**Phase**: Phase 1, Step 4

## Intent

Implement the Analyzer module that transforms classified `List[FileRecord]` + `ScanResult` into a fully populated `AnalysisResult`. This is the computation core of the pipeline -- everything upstream (Scanner, Classifier) feeds into it, and everything downstream (Reporter) consumes its output.

## Problem

The `AnalysisResult` dataclass exists as a skeleton with 10 default-empty fields. No logic exists to compute KPIs, detect anomalies, or aggregate metrics from scanned/classified file records.

## Scope

### In Scope (PRD RF-09 through RF-16)

- **RF-09**: Category distribution -- count, bytes, percentage, avg size, newest/oldest per category
- **RF-10**: Top N largest files ranking (configurable N, default 20)
- **RF-11**: Inactive files detection (mtime > X days ago, configurable, default 180)
- **RF-12**: Zero-byte file detection
- **RF-13**: Empty directory detection (from `ScanResult.directories`)
- **RF-14**: Duplicate detection by filename (same `name` in 2+ locations)
- **RF-15**: Monthly/yearly timeline distribution by mtime
- **RF-16**: Permission anomalies on Linux (777, world-writable, SUID/SGID)

### Out of Scope

- Reporter integration (Phase 1, Step 5)
- Health score computation (Phase 2)
- Hourly distribution, depth analysis, growth rate (Phase 2/3 variables)

## Approach

Create `src/fsaudit/analyzer/analyzer.py` with a single public function:

```python
def analyze(files: list[FileRecord], scan_result: ScanResult, *, top_n: int = 20, inactive_days: int = 180) -> AnalysisResult
```

Internally, decompose into focused private functions (one per RF), each computing a slice of `AnalysisResult`. The main `analyze()` function orchestrates calls and assembles the result. Pure function -- no side effects, no I/O.

The `by_category` dict will use structured values: `{"count": int, "bytes": int, "percent": float, "avg_size": float, "newest": datetime, "oldest": datetime}`.

The `timeline` dict will use `"YYYY-MM"` string keys mapped to file counts.

## Affected Modules

| Module | Impact |
|--------|--------|
| `analyzer/analyzer.py` | **New file** -- all computation logic |
| `analyzer/metrics.py` | No changes -- `AnalysisResult` fields are sufficient |
| `analyzer/__init__.py` | Add public re-export of `analyze` function |
| `tests/test_analyzer.py` | **New file** -- unit tests for all RF-09 through RF-16 |

## Risks

- **Low**: `AnalysisResult` uses `Any` types for flexibility, but this means no compile-time safety on dict structures. Mitigated by thorough tests.
- **Low**: Permission detection is Linux-only; must gracefully skip on Windows (`permissions is None`).

## Rollback Plan

The Analyzer is a new module with no modifications to existing code. Rollback = delete `analyzer/analyzer.py` and revert `analyzer/__init__.py` to its empty state. Tests are isolated. Zero impact on Scanner or Classifier.

## Budget Estimate

~250 lines implementation + ~300 lines tests. Single-session deliverable.
