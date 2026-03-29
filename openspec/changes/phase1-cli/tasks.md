# Tasks: phase1-cli

**Status**: done
**Date**: 2026-03-29

---

## Phase A: Entry Point Registration

### A.1 Add console script to pyproject.toml
- [x] **File**: `pyproject.toml`
- **Action**: Add `[project.scripts]` section with `fsaudit = "fsaudit.cli:main"`
- **Depends**: none
- **Spec**: REQ-CLI-07

---

## Phase B: Argument Parsing

### B.1 Create cli.py with build_parser()
- [x] **File**: `src/fsaudit/cli.py` (new)
- **Action**: Create module with `build_parser() -> ArgumentParser` defining all flags: `--path` (required), `--output-dir`, `--depth`, `--exclude` (append), `--min-size`, `--inactive-days`, `--log-level` (choices), `--log-file`
- **Depends**: none
- **Spec**: REQ-CLI-01

### B.2 Input validation in main()
- [x] **File**: `src/fsaudit/cli.py`
- **Action**: Add `main(argv=None) -> int` skeleton. Validate `--path` is existing directory, `--output-dir` is existing directory. Print error to stderr and return 1 on failure.
- **Depends**: B.1
- **Spec**: REQ-CLI-02, REQ-CLI-08

---

## Phase C: Pipeline Orchestration

### C.1 Logging setup
- [x] **File**: `src/fsaudit/cli.py`
- **Action**: Call `setup_logging(level, log_file)` after validation, before pipeline.
- **Depends**: B.2
- **Spec**: REQ-CLI-06

### C.2 Scan and classify steps
- [x] **File**: `src/fsaudit/cli.py`
- **Action**: Wire `FileScanner(exclude_patterns, max_depth).scan(path)` then `classify(scan_result.files)`. Print progress messages before/after each step.
- **Depends**: C.1
- **Spec**: REQ-CLI-04 (steps 1-2), REQ-CLI-05

### C.3 Min-size filter
- [x] **File**: `src/fsaudit/cli.py`
- **Action**: If `args.min_size > 0`, filter classified files with `size_bytes >= min_size`.
- **Depends**: C.2
- **Spec**: REQ-CLI-04 (step 3), S-CLI-04

### C.4 Analyze and report steps
- [x] **File**: `src/fsaudit/cli.py`
- **Action**: Call `analyze(filtered, scan_result, inactive_days)` then `ExcelReporter().generate(filtered, analysis, output_path)`. Print progress messages. Compute output path per naming convention.
- **Depends**: C.3
- **Spec**: REQ-CLI-03, REQ-CLI-04 (steps 4-5), REQ-CLI-05

### C.5 Top-level error handling
- [x] **File**: `src/fsaudit/cli.py`
- **Action**: Wrap pipeline in try/except. Log traceback at DEBUG, print user-friendly message to stderr, return 1.
- **Depends**: C.4
- **Spec**: REQ-CLI-08, S-CLI-06

---

## Phase D: Tests

### D.1 Test build_parser defaults and required args
- [x] **File**: `tests/test_cli.py` (new)
- **Action**: Verify parser defaults, required `--path`, repeatable `--exclude`.
- **Depends**: B.1

### D.2 Test main() happy path
- [x] **File**: `tests/test_cli.py`
- **Action**: Create tmp dir with files, call `main(["--path", str(tmp)])`, assert returns 0 and .xlsx exists with correct name.
- **Depends**: C.5
- **Spec**: S-CLI-01

### D.3 Test main() invalid path
- [x] **File**: `tests/test_cli.py`
- **Action**: Call `main(["--path", "/nonexistent"])`, assert returns 1.
- **Depends**: B.2
- **Spec**: S-CLI-02

### D.4 Test min-size filtering
- [x] **File**: `tests/test_cli.py`
- **Action**: Create files of varying sizes, run with `--min-size`, verify only large files in report.
- **Depends**: C.3
- **Spec**: S-CLI-04

### D.5 Test custom output directory
- [x] **File**: `tests/test_cli.py`
- **Action**: Run with `--output-dir` pointing to tmp dir, assert report written there.
- **Depends**: C.4
- **Spec**: S-CLI-05
