# Design: phase1-cli

## Technical Approach

Single module `src/fsaudit/cli.py` with two functions: `build_parser()` for argument definition, `main(argv=None)` for pipeline orchestration. The CLI is a thin wiring layer — zero business logic, just argument parsing, validation, sequential pipeline calls, and progress printing. Entry point registered via `pyproject.toml` `[project.scripts]`.

## Architecture Decisions

### Decision: argparse over click/typer

| Option | Tradeoff | Decision |
|--------|----------|----------|
| argparse | stdlib, zero deps, verbose but explicit | **Chosen** |
| click | decorator-based, extra dep | Rejected |
| typer | type-hint magic, 2 transitive deps | Rejected |

**Rationale**: PRD section 6 mandates argparse. Zero new dependencies aligns with RNF-06 (portability).

### Decision: main(argv=None) signature

| Option | Tradeoff | Decision |
|--------|----------|----------|
| `main()` reads sys.argv | Simple but untestable without monkeypatch | Rejected |
| `main(argv=None)` passes to `parser.parse_args(argv)` | Testable, argv=None falls back to sys.argv | **Chosen** |

**Rationale**: Enables unit tests to call `main(["--path", "/tmp"])` without subprocess or monkeypatch.

### Decision: min-size filter location

| Option | Tradeoff | Decision |
|--------|----------|----------|
| Scanner-level filtering | Couples scanner to CLI arg | Rejected |
| Post-classify list comprehension in CLI | Simple, keeps modules pure | **Chosen** |

**Rationale**: Per proposal — `--min-size` is a post-scan filter. One-liner in CLI: `files = [f for f in files if f.size_bytes >= args.min_size]`.

### Decision: Return int exit code

| Option | Tradeoff | Decision |
|--------|----------|----------|
| `sys.exit()` inside main | Hard to test | Rejected |
| `main() -> int`, caller does `sys.exit(main())` | Testable, clean separation | **Chosen** |

**Rationale**: Entry point in pyproject calls `main()` which returns 0/1. The `[project.scripts]` shim handles exit.

## Data Flow

```
CLI (main)
  │
  ├─ 1. parse args (build_parser)
  ├─ 2. validate: Path(args.path) exists & is_dir
  ├─ 3. setup_logging(level, log_file)
  │
  ├─ 4. FileScanner(exclude, max_depth).scan(path)
  │      └─→ ScanResult { files, directories, errors }
  │
  ├─ 5. classify(scan_result.files)
  │      └─→ list[FileRecord] (with category)
  │
  ├─ 6. [optional] min-size filter
  │      └─→ filtered list[FileRecord]
  │
  ├─ 7. analyze(filtered_files, scan_result, inactive_days=N)
  │      └─→ AnalysisResult
  │
  ├─ 8. ExcelReporter().generate(filtered_files, analysis, output_path)
  │      └─→ Path (written .xlsx)
  │
  └─ 9. print summary, return 0
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `src/fsaudit/cli.py` | Create | Entry point: `build_parser()` + `main(argv=None) -> int` |
| `pyproject.toml` | Modify | Add `[project.scripts] fsaudit = "fsaudit.cli:main"` |

## Interfaces / Contracts

```python
# src/fsaudit/cli.py

def build_parser() -> argparse.ArgumentParser:
    """Define CLI arguments. Pure function, no side effects."""
    ...

def main(argv: list[str] | None = None) -> int:
    """Parse args, run pipeline, return exit code (0=ok, 1=error).

    Args:
        argv: Argument list. None = sys.argv[1:] (production).
    """
    ...
```

### Argument table

| Flag | Type | Default | Maps to |
|------|------|---------|---------|
| `--path` | `str` (required) | — | `FileScanner.scan(root=)` |
| `--output-dir` | `str` | `"."` | Output path parent |
| `--format` | `str` choices=["excel"] | `"excel"` | Reporter selection (future-proof) |
| `--depth` | `int` or None | `None` | `FileScanner(max_depth=)` |
| `--exclude` | `str` (append) | `[]` | `FileScanner(exclude_patterns=)` |
| `--min-size` | `int` | `0` | Post-classify filter (bytes) |
| `--inactive-days` | `int` | `180` | `analyze(inactive_days=)` |
| `--log-level` | `str` choices | `"INFO"` | `setup_logging(level=)` |
| `--log-file` | `str` or None | `None` | `setup_logging(log_file=)` |

### Output naming

```python
folder_name = Path(args.path).resolve().name
date_str = datetime.now().strftime("%Y-%m-%d")
output_path = Path(args.output_dir) / f"{folder_name}_audit_{date_str}.xlsx"
```

### Console progress messages

```
Scanning /home/user/docs ...
Scan complete: 12,345 files found (3 errors).
Classifying files ...
Classification complete.
Analyzing ...
Analysis complete.
Generating Excel report ...
Report saved: docs_audit_2026-03-29.xlsx
```

### Error handling

```python
def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    path = Path(args.path)
    if not path.is_dir():
        print(f"Error: '{path}' is not a valid directory.", file=sys.stderr)
        return 1
    try:
        # ... pipeline ...
        return 0
    except Exception as exc:
        logger.exception("Fatal error: %s", exc)
        print(f"Error: {exc}", file=sys.stderr)
        return 1
```

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit | `build_parser()` defaults and required args | Call parser, assert namespace values |
| Unit | `main()` with valid `tmp_path` tree | Create temp dir with files, call `main(["--path", str(tmp)])`, assert exit 0 and .xlsx exists |
| Unit | `main()` with invalid path | `main(["--path", "/nonexistent"])` returns 1 |
| Unit | `--min-size` filtering | Verify files below threshold excluded from report |
| Unit | Output naming convention | Assert filename matches `{name}_audit_{date}.xlsx` |

## Migration / Rollout

No migration required. New file + 3-line pyproject.toml addition. After `pip install -e .`, the `fsaudit` command is available.

## Open Questions

None — all interfaces are known and stable from existing modules.
