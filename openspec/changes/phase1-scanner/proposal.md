# Proposal: phase1-scanner

## Intent

Implement the Scanner module — the first functional stage of the fsaudit pipeline. The Scanner recursively walks a directory tree, collects OS-level metadata via `os.stat()`, and produces a `ScanResult` containing `List[FileRecord]` and `List[DirectoryRecord]`. This is the data source for every downstream module (Classifier, Analyzer, Reporter).

## Scope

### In scope

| Area | Detail |
|------|--------|
| `scanner.py` | `FileScanner` class with `scan(root) -> ScanResult` using `os.walk()` |
| `platform_utils.py` | `get_creation_time_safe()`, `is_hidden()`, `get_permissions()` — OS-aware abstractions |
| Error handling | Per-file `try/except` for `PermissionError` and `OSError`; logged, never halts scan |
| Exclusion patterns | `--exclude` support via fnmatch against directory/file names |
| Depth limiting | `--depth N` caps recursion depth relative to scan root |
| Symlink handling | `followlinks=False` by default; `--follow-symlinks` opt-in with visited-set cycle detection |
| Edge cases | Non-UTF8 filenames (`os.fsdecode()`), long paths (Windows >260), zero-byte files |
| Tests | pytest with `tmp_path` fixtures covering RF-01 through RF-05 and edge cases |

### Out of scope

- Classifier logic (RF-06 to RF-08) — separate phase
- Parallelized scanning (`ThreadPoolExecutor`) — Fase 2 per PRD
- Progress bar (`tqdm`) — deferred to CLI integration phase
- `statx()` / `crtime` on Linux — Fase 3 per PRD

## Approach

1. **`platform_utils.py`** — implement three pure functions:
   - `get_creation_time_safe(stat_result, platform) -> datetime`: Windows uses `st_ctime`, Linux uses `min(st_mtime, st_ctime)`, macOS uses `st_birthtime`
   - `is_hidden(path, name, platform) -> bool`: Linux checks `'.'` prefix, Windows checks `FILE_ATTRIBUTE_HIDDEN` via `stat_result.st_file_attributes`
   - `get_permissions(stat_result, platform) -> Optional[str]`: octal string on Linux, `None` on Windows

2. **`scanner.py`** — `FileScanner` class:
   - Constructor accepts `exclude_patterns: list[str]`, `max_depth: Optional[int]`, `follow_symlinks: bool`
   - `scan(root: Path) -> ScanResult` drives `os.walk()`, computes `depth` as `len(dirpath.relative_to(root).parts)`
   - Prunes excluded dirs in-place on `os.walk()`'s `dirnames` list (standard os.walk pattern)
   - Tracks `visited_real_paths: set` when `follow_symlinks=True` to break cycles
   - Catches `PermissionError`/`OSError` per-file and per-directory, appends to `ScanResult.errors`
   - Empty directories (no files, no subdirs after pruning) produce `DirectoryRecord`

3. **Tests** — `tests/test_scanner.py` and `tests/test_platform_utils.py`:
   - Fixtures create temp trees with nested dirs, hidden files, symlinks, empty dirs
   - Test cases map 1:1 to RF-01 through RF-05 plus edge cases (circular symlinks, permission denied)

## Affected Modules

| Module | Change |
|--------|--------|
| `src/fsaudit/scanner/platform_utils.py` | **New file** — OS abstractions |
| `src/fsaudit/scanner/scanner.py` | **New file** — FileScanner class |
| `src/fsaudit/scanner/__init__.py` | Update — export `FileScanner`, `scan` |
| `tests/test_scanner.py` | **New file** — scanner integration tests |
| `tests/test_platform_utils.py` | **New file** — unit tests for platform functions |

## Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Windows `FILE_ATTRIBUTE_HIDDEN` requires `stat_result.st_file_attributes` (only on Windows) | Medium | Guard with `hasattr()` check; fall back to dot-prefix heuristic |
| `os.fsdecode()` can raise `UnicodeDecodeError` on corrupted filenames | Low | Wrap in try/except, log and skip file |
| Symlink cycle detection adds memory overhead for very large trees | Low | Only enabled with `--follow-symlinks`; uses `os.path.realpath()` set |

## Rollback Plan

All changes are **additive** (new files only). Rollback = delete `platform_utils.py`, `scanner.py`, and test files; revert `__init__.py` to empty. Zero impact on existing infrastructure.

## Performance Target

100,000 files scanned in <60 seconds (SSD, 8GB RAM) per RNF-01. Single-threaded `os.walk()` + `os.stat()` is expected to meet this — each iteration is one syscall pair. Benchmark test included in test suite.

## Decision Log

| Decision | Rationale |
|----------|-----------|
| `os.walk()` over `pathlib.rglob()` | `os.walk()` gives in-place dir pruning for excludes and depth control; `rglob()` does not |
| Platform detection via `sys.platform` | Simpler than runtime duck-typing; matches PRD's explicit Windows/Linux/macOS matrix |
| Frozen dataclasses (already in models.py) | Immutability guarantees pipeline integrity; no module can mutate another's output |
