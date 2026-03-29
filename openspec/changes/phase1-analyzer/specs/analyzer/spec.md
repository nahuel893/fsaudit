# Spec: Analyzer Domain

**Change**: phase1-analyzer
**Domain**: analyzer
**Status**: draft
**Covers**: RF-09, RF-10, RF-11, RF-12, RF-13

---

## Overview

Core analysis logic that transforms `List[FileRecord]` + `ScanResult` into a populated `AnalysisResult`. Pure computation — no I/O, no side effects.

## Public Interface

```python
def analyze(
    files: list[FileRecord],
    scan_result: ScanResult,
    *,
    top_n: int = 20,
    inactive_days: int = 180,
) -> AnalysisResult
```

---

## REQ-A1: Total Aggregation (RF-09)

The analyzer MUST compute `total_files` as `len(files)` and `total_size_bytes` as the sum of all `file.size_bytes`.

### Scenario A1.1: Basic totals

**Given** a list of 3 FileRecords with sizes [100, 200, 300]
**When** `analyze()` is called
**Then** `result.total_files` MUST equal 3
**And** `result.total_size_bytes` MUST equal 600

### Scenario A1.2: Empty input

**Given** an empty file list
**When** `analyze()` is called
**Then** `result.total_files` MUST equal 0
**And** `result.total_size_bytes` MUST equal 0

---

## REQ-A2: Category Breakdown (RF-09)

The analyzer MUST populate `by_category` as `dict[str, dict]` where each key is a category name and each value contains: `count` (int), `bytes` (int), `percent` (float, 0-100), `avg_size` (float), `newest` (datetime), `oldest` (datetime).

### Scenario A2.1: Two categories

**Given** 2 files categorized "Code" (500B, 1000B) and 1 file "Office" (200B)
**When** `analyze()` is called
**Then** `by_category["Code"]["count"]` MUST equal 2
**And** `by_category["Code"]["bytes"]` MUST equal 1500
**And** `by_category["Code"]["percent"]` MUST be approximately 88.24 (1500/1700*100)
**And** `by_category["Code"]["avg_size"]` MUST equal 750.0
**And** `by_category["Office"]["count"]` MUST equal 1

### Scenario A2.2: Newest and oldest per category

**Given** 3 "Code" files with mtimes [2024-01-15, 2024-06-01, 2023-03-10]
**When** `analyze()` is called
**Then** `by_category["Code"]["newest"]` MUST equal 2024-06-01
**And** `by_category["Code"]["oldest"]` MUST equal 2023-03-10

---

## REQ-A3: Timeline Distribution (RF-15)

The analyzer MUST populate `timeline` as `dict[str, int]` with keys in `"YYYY-MM"` format, values being file counts per month based on `mtime`.

### Scenario A3.1: Monthly grouping

**Given** files with mtimes [2024-01-05, 2024-01-20, 2024-03-10]
**When** `analyze()` is called
**Then** `timeline["2024-01"]` MUST equal 2
**And** `timeline["2024-03"]` MUST equal 1
**And** `"2024-02"` SHOULD NOT appear in timeline

---

## REQ-A4: Top N Largest Files (RF-10)

The analyzer MUST populate `top_largest` as a list of dicts with keys: `path` (str), `size_bytes` (int), `category` (str), `mtime` (datetime). The list MUST be sorted descending by `size_bytes` and limited to `top_n` entries.

### Scenario A4.1: Ranking and limit

**Given** 5 files with sizes [10, 50, 30, 20, 40] and `top_n=3`
**When** `analyze()` is called
**Then** `top_largest` MUST have length 3
**And** sizes MUST be [50, 40, 30] in order

### Scenario A4.2: Fewer files than top_n

**Given** 2 files and `top_n=20`
**When** `analyze()` is called
**Then** `top_largest` MUST have length 2

---

## REQ-A5: By-Directory Stats (RF-13 — directory volume)

The analyzer MUST compute top directories by volume and count using `FileRecord.parent_dir`. The result SHOULD be available via `by_category` or a dedicated structure in future phases. For Phase 1, directory stats feed into the Reporter directly from the file list.

### Scenario A5.1: Directory aggregation

**Given** 3 files in "/home/docs" (100B each) and 1 file in "/home/pics" (500B)
**When** the analyzer groups by `parent_dir`
**Then** "/home/pics" MUST rank first by volume (500B)
**And** "/home/docs" MUST rank first by count (3)

---

## Constraints

- The function MUST be pure — no filesystem access, no logging side effects.
- All datetime comparisons MUST use timezone-naive datetimes (matching FileRecord contract).
- Division by zero MUST be handled: if `total_size_bytes` is 0, all `percent` values MUST be 0.0.
