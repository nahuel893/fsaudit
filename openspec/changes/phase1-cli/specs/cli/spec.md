# Spec: CLI — phase1-cli

**Status**: draft
**Date**: 2026-03-29
**Domain**: cli

---

## Overview

The CLI module (`src/fsaudit/cli.py`) is the user-facing entry point. It parses arguments, validates input, orchestrates the pipeline (scan -> classify -> analyze -> report), and provides console feedback. Registered as a console script via `pyproject.toml`.

---

## Requirements

### REQ-CLI-01: Argument Parsing

The CLI MUST accept the following flags via `argparse`:

| Flag | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `--path` | `str` | Yes | — | Root directory to audit |
| `--output-dir` | `str` | No | `.` (cwd) | Directory for the output report |
| `--depth` | `int` | No | unlimited | Maximum recursion depth |
| `--exclude` | `str` | No (repeatable) | `[]` | Directory patterns to exclude; may be specified multiple times |
| `--min-size` | `int` | No | `0` | Minimum file size in bytes to include |
| `--inactive-days` | `int` | No | `365` | Days without modification to classify as inactive |
| `--log-level` | `str` | No | `INFO` | Logging verbosity: DEBUG, INFO, WARNING, ERROR |
| `--log-file` | `str` | No | `None` | Path to log file; if omitted, log to stderr only |

### REQ-CLI-02: Input Validation

- The CLI MUST verify `--path` exists and is a directory.
- If validation fails, the CLI MUST print a user-friendly error to stderr and exit with code 1.
- The CLI MUST verify `--output-dir` exists and is a directory when provided.
- The CLI MUST reject `--log-level` values outside the allowed set (case-insensitive).

### REQ-CLI-03: Output File Naming

The output filename MUST follow the pattern:

```
{folder_name}_audit_{YYYY-MM-DD}.xlsx
```

Where:
- `folder_name` = `Path(path).name` (the scanned directory's basename)
- `YYYY-MM-DD` = current date at execution time

Example: `--path /home/nh/Documents` on 2026-03-29 produces `Documents_audit_2026-03-29.xlsx`.

The full output path is `Path(output_dir) / filename`.

### REQ-CLI-04: Pipeline Orchestration

The CLI MUST execute the pipeline in strict order:

1. **Scan** — `FileScanner.scan()` with `exclude_patterns` and `max_depth` from args
2. **Classify** — `classify()` on scan results
3. **Filter** — if `--min-size > 0`, exclude records with `size_bytes < min_size`
4. **Analyze** — `analyze()` with `inactive_days` from args
5. **Report** — `ExcelReporter().generate()` with computed output path

Each step MUST complete before the next begins.

### REQ-CLI-05: Console Progress

The CLI MUST print phase-level progress messages to stdout:

- `"Scanning {path}..."` before scan
- `"Found {N} files."` after scan
- `"Classifying..."` before classify
- `"Analyzing..."` before analyze
- `"Generating report..."` before report
- `"Report saved to {output_path}"` on completion

### REQ-CLI-06: Logging Setup

The CLI MUST call `setup_logging(level, log_file)` before pipeline execution, configuring the root logger per `--log-level` and `--log-file` arguments.

### REQ-CLI-07: Entry Point

`pyproject.toml` MUST declare:

```toml
[project.scripts]
fsaudit = "fsaudit.cli:main"
```

`main(argv=None)` MUST accept an optional argv for testability.

### REQ-CLI-08: Exit Codes and Error Handling

- Exit code `0` on successful completion.
- Exit code `1` on any error (validation failure, pipeline exception, I/O error).
- Unhandled exceptions MUST be caught at the top level, logged, and presented as a user-friendly message (no raw tracebacks to stdout).

---

## Scenarios

### S-CLI-01: Successful audit run

**Given** a valid directory at `--path` containing files
**When** the user runs `fsaudit --path /tmp/testdir`
**Then** the CLI prints all progress messages in order
**And** produces `testdir_audit_{today}.xlsx` in the current directory
**And** exits with code 0.

### S-CLI-02: Non-existent path

**Given** `--path /nonexistent`
**When** the user runs the command
**Then** the CLI prints `"Error: '/nonexistent' does not exist or is not a directory."` to stderr
**And** exits with code 1.

### S-CLI-03: Repeatable --exclude

**Given** `--path /tmp/testdir --exclude .git --exclude node_modules`
**When** the scanner runs
**Then** both `.git` and `node_modules` directories are excluded from scan results.

### S-CLI-04: --min-size filtering

**Given** a directory with files of 0, 500, and 2000 bytes
**When** `--min-size 1000` is specified
**Then** only the 2000-byte file is passed to the analyzer.

### S-CLI-05: Custom output directory

**Given** `--output-dir /tmp/reports` exists
**When** the user runs `fsaudit --path /tmp/testdir --output-dir /tmp/reports`
**Then** the report is written to `/tmp/reports/testdir_audit_{today}.xlsx`.

### S-CLI-06: Pipeline exception

**Given** the reporter raises an `OSError` (e.g., disk full)
**When** the pipeline executes
**Then** the CLI logs the full traceback at DEBUG level
**And** prints a user-friendly error message to stderr
**And** exits with code 1.

### S-CLI-07: Testable main via argv

**Given** a test calling `main(["--path", "/tmp/testdir"])`
**When** main executes
**Then** it parses the provided argv instead of `sys.argv`.

---

## Acceptance Criteria

- All scenarios above pass.
- `fsaudit --help` prints usage with all flags documented.
- No raw tracebacks reach stdout under any error condition.
- Output filename strictly matches `{folder_name}_audit_{YYYY-MM-DD}.xlsx`.
