# Verify Report: phase1-cli

**Date**: 2026-03-29
**Verdict**: COMPLIANT (with minor observations)

---

## Test Execution

```
Platform: linux (Python 3.14.3, pytest 9.0.2)
Command: python -m pytest tests/test_cli.py -v
Result: 17 passed in 0.22s
Full suite: 159 passed in 0.67s (no regressions)
```

---

## Spec Compliance Matrix

| Requirement | Description | Status | Evidence |
|-------------|-------------|--------|----------|
| REQ-CLI-01 | Argument parsing (all flags) | COMPLIANT | `build_parser()` defines all 8 flags with correct types, defaults, and behavior. Tests: `test_defaults`, `test_all_flags`, `test_exclude_repeatable`, `test_log_level_case_insensitive`, `test_log_level_invalid_rejected` |
| REQ-CLI-02 | Input validation | COMPLIANT | `main()` validates `--path` is dir, `--output-dir` is dir, `--log-level` via argparse choices. Tests: `test_nonexistent_path_returns_1`, `test_file_as_path_returns_1`, `test_invalid_output_dir_returns_1` |
| REQ-CLI-03 | Output file naming `{folder_name}_audit_{YYYY-MM-DD}.xlsx` | COMPLIANT | Lines 141-143 of `cli.py`: `path.name` + `datetime.now().strftime("%Y-%m-%d")` + `.xlsx`. Tests: `test_output_file_created`, `test_output_naming_convention` |
| REQ-CLI-04 | Pipeline orchestration (scan -> classify -> filter -> analyze -> report) | COMPLIANT | `main()` executes steps sequentially in correct order (lines 113-147). Tests: `test_basic_run_returns_0`, `test_min_size_filters_small_files` |
| REQ-CLI-05 | Console progress messages | COMPLIANT (minor wording variance) | All 8 phase messages printed. Test: `test_progress_messages` checks substrings. See observation O-1 below. |
| REQ-CLI-06 | Logging setup | COMPLIANT | `setup_logging(level, log_file)` called at line 109 before pipeline. |
| REQ-CLI-07 | Entry point in pyproject.toml | COMPLIANT | `[project.scripts] fsaudit = "fsaudit.cli:main"` present at line 19 of `pyproject.toml`. |
| REQ-CLI-08 | Exit codes and error handling | COMPLIANT | Returns 0 on success, 1 on validation failure, 1 on pipeline exception. `try/except` wraps pipeline (lines 111-154). No raw tracebacks to stdout. |

---

## Scenario Compliance Matrix

| Scenario | Description | Status | Test Coverage |
|----------|-------------|--------|---------------|
| S-CLI-01 | Successful audit run | COMPLIANT | `test_basic_run_returns_0`, `test_output_file_created`, `test_progress_messages` |
| S-CLI-02 | Non-existent path | COMPLIANT | `test_nonexistent_path_returns_1` — returns 1, error to stderr matches spec wording |
| S-CLI-03 | Repeatable --exclude | COMPLIANT | `test_exclude_repeatable` (parser), `test_exclude_patterns_passed` (end-to-end) |
| S-CLI-04 | --min-size filtering | COMPLIANT | `test_min_size_filters_small_files` — exit 0, pipeline runs with filter |
| S-CLI-05 | Custom output directory | COMPLIANT | `test_report_written_to_custom_dir` — report written to specified dir with correct name |
| S-CLI-06 | Pipeline exception | NOT TESTED | No test simulates a pipeline exception (e.g., mocking ExcelReporter to raise OSError). Code path exists (lines 151-154) but is not exercised by tests. |
| S-CLI-07 | Testable main via argv | COMPLIANT | Every test calls `main([...])` with explicit argv — this scenario is proven by the entire test suite. |

---

## Design Coherence (ADRs)

| ADR | Implementation Match |
|-----|---------------------|
| argparse over click/typer | COMPLIANT — stdlib argparse used exclusively |
| `main(argv=None)` signature | COMPLIANT — `main(argv: list[str] \| None = None) -> int` |
| min-size filter in CLI (post-classify) | COMPLIANT — list comprehension at line 128 |
| Return int exit code (no `sys.exit()`) | COMPLIANT — `main()` returns 0 or 1, no `sys.exit()` calls |

---

## Critical Check: Output Naming Convention

**Requirement**: `{folder_name}_audit_{YYYY-MM-DD}.xlsx`

**Implementation** (cli.py lines 141-143):
```python
folder_name = path.name
date_str = datetime.now().strftime("%Y-%m-%d")
output_path = output_dir / f"{folder_name}_audit_{date_str}.xlsx"
```

**Verdict**: EXACTLY MATCHES the required convention.

---

## Observations

### O-1: Progress message wording differs from spec (LOW)

The spec prescribes exact strings like `"Scanning {path}..."` and `"Found {N} files."`. The implementation uses slightly richer wording (e.g., `"Scan complete: 12,345 files found (3 errors)."` instead of `"Found {N} files."`). The additional info (error count, commas) is an improvement. Tests verify substring presence, which is correct for this level of flexibility. **Not a blocker.**

### O-2: S-CLI-06 (pipeline exception) lacks a dedicated test (MEDIUM)

The `try/except` block at lines 151-154 handles pipeline exceptions, but no test mocks a failure to verify the behavior (DEBUG traceback, user-friendly stderr message, exit code 1). The code is correct by inspection, but it is untested.

### O-3: Design vs spec discrepancy on --inactive-days default (LOW)

- Spec REQ-CLI-01: default `365`
- Design argument table: default `180`
- Implementation: default `365`

Implementation follows the spec (authoritative). The design doc has a stale value. **No action needed for implementation; design doc could be corrected.**

### O-4: Design mentions --format flag not in spec or implementation (LOW)

The design argument table includes `--format` with `choices=["excel"]` as future-proofing. Neither the spec nor the implementation includes it. This is harmless but creates a minor inconsistency in the design doc.

---

## Task Checklist Verification

| Task | Status in tasks.md | Verified |
|------|-------------------|----------|
| A.1 console script | done | YES — pyproject.toml has entry |
| B.1 build_parser() | done | YES — all flags defined |
| B.2 input validation | done | YES — path + output-dir validated |
| C.1 logging setup | done | YES — setup_logging called |
| C.2 scan and classify | done | YES — pipeline wired |
| C.3 min-size filter | done | YES — list comprehension |
| C.4 analyze and report | done | YES — analyze + ExcelReporter |
| C.5 error handling | done | YES — try/except wraps pipeline |
| D.1-D.5 tests | done | YES — 17 tests, all passing |

---

## Summary

The phase1-cli implementation is **COMPLIANT** with the spec. All 8 requirements are met, 6 of 7 scenarios are tested and passing, and all 4 ADRs are correctly implemented. The output naming convention exactly matches `{folder_name}_audit_{YYYY-MM-DD}.xlsx`. The only gap is the absence of a dedicated test for S-CLI-06 (pipeline exception handling), and minor documentation drift in the design doc.
