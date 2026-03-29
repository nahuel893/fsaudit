# Proposal: phase1-cli

**Status**: proposed
**Date**: 2026-03-29
**Author**: SDD sub-agent

---

## Intent

Create `src/fsaudit/cli.py` — the argparse entry point that orchestrates the full pipeline (scan, classify, analyze, report) and register it as a console script in `pyproject.toml`. This is the final step of Phase 1 MVP: all four pipeline modules are complete and tested; the CLI wires them together.

## Motivation

Users need a single `fsaudit` command to audit a directory. Without the CLI, the pipeline modules exist but cannot be invoked except programmatically. The CLI provides the user-facing interface described in the PRD (section 5.2, 7, 12).

## Scope

### In scope

- New file: `src/fsaudit/cli.py` with `main()` function
- argparse flags: `--path` (required), `--output-dir` (default `.`), `--format` (excel only, future-proof), `--depth`, `--exclude` (repeatable), `--min-size`, `--inactive-days` (default 180), `--log-level` (default INFO), `--log-file`
- Input validation: path exists and is a directory
- Pipeline orchestration: `FileScanner.scan()` -> `classify()` -> `analyze()` -> `ExcelReporter().generate()`
- Output naming: `{folder_name}_audit_{YYYY-MM-DD}.xlsx` where `folder_name` = scanned path's directory name
- Console progress messages: phase-level ("Scanning... done (N files)", "Classifying...", etc.)
- Entry point in `pyproject.toml`: `[project.scripts] fsaudit = "fsaudit.cli:main"`
- Logging setup via existing `setup_logging()`

### Out of scope

- HTML/JSON reporters (Phase 2)
- `--follow-symlinks` flag (not in MVP CLI spec)
- Progress bars / `tqdm` (Phase 2 enhancement)
- Any new data models or pipeline changes

## Approach

1. Add `[project.scripts]` to `pyproject.toml` mapping `fsaudit` to `fsaudit.cli:main`
2. Create `src/fsaudit/cli.py`:
   - `build_parser() -> argparse.ArgumentParser` — defines all flags
   - `main(argv=None)` — parses args, validates input, runs pipeline, prints progress, handles top-level errors with `sys.exit(1)`
3. Pipeline wiring passes scanner config (`exclude_patterns`, `max_depth`) from CLI args, threads `inactive_days` to analyzer, computes output path from `--output-dir` + naming convention
4. `--min-size` filters records between classify and analyze (post-scan filter, not scanner-level)

## Affected Modules

| Module | Change |
|--------|--------|
| `src/fsaudit/cli.py` | **NEW** — entry point |
| `pyproject.toml` | Add `[project.scripts]` section |

No changes to scanner, classifier, analyzer, or reporter.

## Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| `--min-size` semantics unclear (bytes? KB?) | Low | Default to bytes, document in help text. Accept human suffixes in Phase 2. |
| Output path conflicts (file already exists) | Low | Overwrite silently (standard CLI behavior). Log a warning. |

## Rollback Plan

1. Delete `src/fsaudit/cli.py`
2. Remove `[project.scripts]` from `pyproject.toml`
3. No other modules are touched — zero downstream impact

## Budget

Two files changed (one new, one modified). Estimated implementation: ~150 lines in `cli.py`, ~3 lines in `pyproject.toml`.
