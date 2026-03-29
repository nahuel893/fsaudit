# Tasks: phase1-analyzer

**Change**: phase1-analyzer
**Status**: done

---

## Phase A: Core Analyzer Scaffold

- [x] **A1** Create `src/fsaudit/analyzer/analyzer.py` with imports, `analyze()` signature (with `_now` test seam), and empty `AnalysisResult` return.
- [x] **A2** Wire `total_files` and `total_size_bytes` computation inside `analyze()`.
- [x] **A3** Update `src/fsaudit/analyzer/__init__.py` to re-export `analyze`.

## Phase B: Metric Helpers (RF-09, RF-10, RF-15)

- [x] **B1** Implement `_compute_category_stats()` — Counter-based aggregation with count, bytes, percent, avg_size, newest, oldest per category. Handle zero total_size (percent=0.0).
- [x] **B2** Implement `_compute_timeline()` — group file counts by `mtime.strftime("%Y-%m")`.
- [x] **B3** Implement `_find_top_largest()` — sort descending by size_bytes, slice to `top_n`, return dicts with path/size_bytes/category/mtime.

## Phase C: Alert Helpers (RF-11, RF-12, RF-13, RF-14, RF-16)

- [x] **C1** Implement `_find_inactive()` — filter files where `(now - mtime).days >= inactive_days`, include days_inactive.
- [x] **C2** Implement `_find_zero_byte()` — filter `size_bytes == 0`, return path/category/mtime dicts.
- [x] **C3** Implement `_find_empty_directories()` — map `ScanResult.directories` to path/depth dicts.
- [x] **C4** Implement `_find_duplicates_by_name()` — Counter on `Path(path).name`, keep entries with count >= 2, return `dict[str, list[str]]`.
- [x] **C5** Implement `_find_permission_issues()` — parse octal string, detect 777, world-writable (last digit in {2,3,6,7}), SUID (& 0o4000), SGID (& 0o2000). Skip `None` permissions.

## Phase D: Integration in analyze()

- [x] **D1** Wire all helpers (B1-B3, C1-C5) into `analyze()`, assigning each result to the corresponding `AnalysisResult` field.

## Phase E: Tests

- [x] **E1** Create `tests/test_analyzer.py` with a `_make_record()` factory for `FileRecord` with sensible defaults.
- [x] **E2** Test REQ-A1: totals (basic + empty input).
- [x] **E3** Test REQ-A2: category stats (two categories, newest/oldest, zero-total-size).
- [x] **E4** Test REQ-A3: timeline monthly grouping.
- [x] **E5** Test REQ-A4: top_largest ranking, limit, fewer-than-N.
- [x] **E6** Test REQ-B1: inactive files (default threshold, within threshold, custom, boundary).
- [x] **E7** Test REQ-B2: zero-byte detection.
- [x] **E8** Test REQ-B3: empty directories (present + absent).
- [x] **E9** Test REQ-B4: duplicates by name (2-way, 3-way, no dupes).
- [x] **E10** Test REQ-B5: permission issues (777, safe 644, None/Windows, SUID 4755, 755 safe).
- [x] **E11** Integration test: `analyze()` with ~10 mixed records, assert all 10 AnalysisResult fields populated.

---

**Files touched**:
- `src/fsaudit/analyzer/analyzer.py` (create)
- `src/fsaudit/analyzer/__init__.py` (modify)
- `tests/test_analyzer.py` (create)
