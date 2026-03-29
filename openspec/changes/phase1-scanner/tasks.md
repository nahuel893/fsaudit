# Tasks: phase1-scanner

## Phase 1 — Infrastructure

- [x] **1.1** Create `src/fsaudit/scanner/platform_utils.py` with module-level `PLATFORM = sys.platform` constant and imports (`sys`, `datetime`, `stat_result`, `Optional`)
- [x] **1.2** Implement `get_creation_time_safe(sr) -> datetime` — branch on `PLATFORM`: win32→`st_ctime`, darwin→`st_birthtime` with fallback, linux→`min(st_mtime, st_ctime)`
- [x] **1.3** Implement `is_hidden(name, sr) -> bool` — dot-prefix for linux/darwin, `st_file_attributes & FILE_ATTRIBUTE_HIDDEN` for win32 with `hasattr` guard
- [x] **1.4** Implement `get_permissions(sr) -> Optional[str]` — `oct(stat.S_IMODE(sr.st_mode))` on linux/darwin, `None` on win32

## Phase 2 — Core Scanner Implementation

- [x] **2.1** Create `src/fsaudit/scanner/scanner.py` with `FileScanner.__init__(exclude_patterns, max_depth, follow_symlinks)` storing defaults
- [x] **2.2** Implement `_is_excluded(name) -> bool` using `fnmatch.fnmatch` against basename only
- [x] **2.3** Implement `_is_cycle(dirpath, name, visited) -> bool` using `os.path.realpath` set tracking
- [x] **2.4** Implement `scan(root) -> ScanResult` — `os.walk()` loop with depth computation via `len(Path(dirpath).relative_to(root).parts)`
- [x] **2.5** In `scan()`: prune `dirnames[:]` in-place for excludes, depth limit, and symlink cycles
- [x] **2.6** In `scan()`: per-file `try/except (PermissionError, OSError)` building `FileRecord` via platform utils
- [x] **2.7** In `scan()`: detect empty directories (no files + no remaining dirnames) → append `DirectoryRecord`
- [x] **2.8** In `scan()`: handle file exclusion patterns against filenames before stat

## Phase 3 — Integration & Exports

- [x] **3.1** Update `src/fsaudit/scanner/__init__.py` — export `FileScanner`, `get_creation_time_safe`, `is_hidden`, `get_permissions`

## Phase 4 — Unit Tests

- [x] **4.1** Create `tests/test_platform_utils.py` — test `get_creation_time_safe` for win32, linux, darwin using monkeypatched `PLATFORM`
- [x] **4.2** Test `is_hidden` — dot-prefix true/false on linux, `st_file_attributes` mock for win32, fallback when attr missing
- [x] **4.3** Test `get_permissions` — known `st_mode` → expected octal string on linux, `None` on win32

## Phase 5 — Integration Tests

- [x] **5.1** Create `tests/test_scanner.py` — basic flat directory scan: verify FileRecord count, fields, depth=0
- [x] **5.2** Test nested directory scan: verify depth computation and `parent_dir` field
- [x] **5.3** Test extension normalization: `.PDF` → `.pdf`, no extension → `""`
- [x] **5.4** Test exclusion patterns: excluded dir not traversed, excluded files filtered, basename-only matching
- [x] **5.5** Test depth limiting: `max_depth=1` stops at depth 1, `max_depth=0` returns only root files
- [x] **5.6** Test empty directory detection: empty dir → `DirectoryRecord`, non-empty dir → no record
- [x] **5.7** Test `PermissionError` resilience: `chmod 000` dir/file (Linux), verify error collected and scan continues
- [x] **5.8** Test symlink cycle detection: circular symlink with `follow_symlinks=True`, no infinite loop, error/warning recorded
- [x] **5.9** Test hidden file detection: `.hidden` file has `is_hidden=True`, regular file `False`
- [x] **5.10** Test `ScanResult` structure: verify all four fields populated, `root_path` correct
