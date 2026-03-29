# Verify Report: phase1-analyzer

**Change**: phase1-analyzer
**Verified**: 2026-03-29
**Verdict**: COMPLIANT

---

## Test Execution

```
118 passed in 0.18s (27 analyzer-specific, 91 pre-existing)
```

All tests pass. No regressions.

---

## Spec Compliance Matrix: Analyzer Domain

| Scenario | Spec Requirement | Test | Status |
|----------|-----------------|------|--------|
| A1.1 — Basic totals | total_files=3, total_size_bytes=600 | `TestTotals::test_basic_totals` | PASS |
| A1.2 — Empty input | total_files=0, total_size_bytes=0 | `TestTotals::test_empty_input` | PASS |
| A2.1 — Two categories | count, bytes, percent, avg_size correct | `TestCategoryStats::test_two_categories` | PASS |
| A2.2 — Newest/oldest | newest=2024-06-01, oldest=2023-03-10 | `TestCategoryStats::test_newest_oldest` | PASS |
| A2 (edge) — Zero total size | percent=0.0 when total_size=0 | `TestCategoryStats::test_zero_total_size` | PASS |
| A3.1 — Monthly grouping | 2024-01=2, 2024-03=1, no 2024-02 | `TestTimeline::test_monthly_grouping` | PASS |
| A4.1 — Ranking and limit | top_n=3 yields [50,40,30] | `TestTopLargest::test_ranking_and_limit` | PASS |
| A4.2 — Fewer than top_n | 2 files with top_n=20 yields 2 | `TestTopLargest::test_fewer_than_n` | PASS |
| A5.1 — Directory aggregation | Deferred to future phase (per spec) | N/A | N/A |

## Spec Compliance Matrix: Alerts Domain

| Scenario | Spec Requirement | Test | Status |
|----------|-----------------|------|--------|
| B1.1 — Default threshold | 200-day-old file detected, days_inactive=200 | `TestInactiveFiles::test_default_threshold` | PASS |
| B1.2 — Within threshold | 30-day-old file NOT detected | `TestInactiveFiles::test_within_threshold` | PASS |
| B1.3 — Custom threshold | 400 days, inactive_days=365, detected | `TestInactiveFiles::test_custom_threshold` | PASS |
| B1.4 — Boundary exact | Exactly 180 days, >=, detected | `TestInactiveFiles::test_boundary_exact` | PASS |
| B2.1 — Zero-byte detected | 2 of 4 files with size=0 | `TestZeroByteFiles::test_detected` | PASS |
| B2.2 — No zero-byte | All files >0 yields empty list | `TestZeroByteFiles::test_none_detected` | PASS |
| B3.1 — Empty dirs present | 2 DirectoryRecords mapped | `TestEmptyDirectories::test_present` | PASS |
| B3.2 — No empty dirs | Empty dirs list yields [] | `TestEmptyDirectories::test_absent` | PASS |
| B4.1 — Two-way duplicate | report.pdf in 2 paths, unique.txt excluded | `TestDuplicatesByName::test_two_way` | PASS |
| B4.2 — No duplicates | All unique names yields empty dict | `TestDuplicatesByName::test_no_duplicates` | PASS |
| B4.3 — Three-way duplicate | readme.md in 3 paths | `TestDuplicatesByName::test_three_way` | PASS |
| B5.1 — 777 detected | permissions="777" flagged | `TestPermissionIssues::test_777` | PASS |
| B5.2 — Safe 644 skipped | permissions="644" not flagged | `TestPermissionIssues::test_safe_644` | PASS |
| B5.3 — Windows None skipped | permissions=None not flagged | `TestPermissionIssues::test_windows_none` | PASS |
| B5.4 — SUID detected | permissions="4755" flagged as suid | `TestPermissionIssues::test_suid` | PASS |
| B5.5 — 755 safe | permissions="755" not flagged | `TestPermissionIssues::test_755_safe` | PASS |
| B5 (extra) — World-writable | permissions="666" flagged | `TestPermissionIssues::test_world_writable` | PASS |
| B5 (extra) — SGID | permissions="2755" flagged as sgid | `TestPermissionIssues::test_sgid` | PASS |

## Integration

| Scenario | Test | Status |
|----------|------|--------|
| E11 — All 10 fields populated | `TestIntegration::test_all_fields_populated` | PASS |

---

## Design Coherence (6 ADRs)

| ADR | Decision | Implementation | Coherent? |
|-----|----------|---------------|-----------|
| 1 — Multi-pass | One iteration per helper | Each helper iterates `records` independently | Yes |
| 2 — Free functions, no class | No class, matches `classify()` pattern | `analyze()` + 8 private functions, no class | Yes |
| 3 — `collections.Counter` | stdlib Counter for aggregation | `Counter` used in `_compute_timeline`, `defaultdict` in `_find_duplicates_by_name`, manual dict in `_compute_category_stats` | Yes (Counter where appropriate, manual dict where richer structure needed) |
| 4 — `_now` test seam | datetime.now() injected via `_now` param | `_now: datetime | None = None` with `now = _now or datetime.now()` | Yes |
| 5 — Return `str(path)` | Serialization-friendly path strings | All helpers return `str(r.path)` in dicts | Yes |
| 6 — Octal string parsing | Parse `FileRecord.permissions` string, no os.stat | `int(perm_str, 8)` + string checks, no filesystem access | Yes |

---

## Task Completion

All 17 tasks (A1-A3, B1-B3, C1-C5, D1, E1-E11) marked done in tasks.md. Each has corresponding implementation and test coverage verified above.

---

## Constraints Verification

| Constraint | Status |
|------------|--------|
| Pure function — no I/O, no side effects | Confirmed: no filesystem access, no logging, no print |
| Timezone-naive datetimes | Confirmed: all tests use naive `datetime()` |
| Division by zero handled | Confirmed: `test_zero_total_size` passes, percent=0.0 |
| `_now` computed once at entry | Confirmed: line 37, `now = _now or datetime.now()` |

---

## Notes

- **REQ-A5 (directory aggregation by volume)**: Spec explicitly marks this as deferred to future phases ("For Phase 1, directory stats feed into the Reporter directly from the file list"). No implementation or test expected. Not a gap.
- **Permission logic**: Implementation checks 777 first, then world-writable, then SUID/SGID independently. SUID/SGID can produce additional entries for the same file (e.g., "4777" would produce both "777" and "suid" entries). This matches the design doc ("can co-exist").
- **Extra test coverage**: Tests include `test_world_writable` (666) and `test_sgid` (2755) beyond the minimum spec scenarios. Good.

---

## Summary

**27/27 tests PASSED.** All spec scenarios from both analyzer and alerts domains are covered by tests and verified passing. All 6 ADRs are faithfully implemented. All constraints are met. No issues found.
