# Design: Phase 1 — Scanner Module

## Technical Approach

Two new files implement the scanner pipeline stage: `platform_utils.py` isolates every OS-dependent operation behind pure functions, while `scanner.py` owns the `os.walk()` loop and builds `ScanResult`. The existing frozen dataclasses in `models.py` remain untouched — they are the contract.

## Architecture Decisions

| # | Decision | Alternatives | Rationale |
|---|----------|-------------|-----------|
| ADR-1 | `os.walk()` for traversal | `pathlib.rglob()`, `os.scandir()` tree | `os.walk()` yields `dirnames` in-place — enables O(1) pruning for excludes and depth. `rglob()` offers no pruning hook. |
| ADR-2 | `sys.platform` string check for OS detection | `platform.system()`, runtime duck-typing | `sys.platform` is a compile-time constant on CPython — branch predictor-friendly, zero function-call overhead. Three values cover all targets: `win32`, `linux`, `darwin`. |
| ADR-3 | `hasattr(stat_result, 'st_file_attributes')` for Windows hidden | `ctypes` + `GetFileAttributesW` | `os.stat()` already exposes `st_file_attributes` on Windows (Python 3.x). Avoids ctypes FFI complexity. Falls back to dot-prefix on non-Windows. |
| ADR-4 | `fnmatch.fnmatch()` for exclude patterns | `re.match()`, `pathlib.match()` | Matches CLI glob conventions users expect (`*.log`, `node_modules`). Simpler than regex, no compilation needed. |
| ADR-5 | Depth as `len(Path(dirpath).relative_to(root).parts)` | Counter incremented manually | Computed from path structure — correct even when `os.walk()` visits dirs out of order. Zero state to track. |
| ADR-6 | `set()` of `os.path.realpath()` for symlink cycle detection | `os.stat()` device+inode pairs | `realpath` resolves the full chain. Device+inode is more precise but platform-dependent. `realpath` set is simpler and sufficient. |
| ADR-7 | Extension via `Path(name).suffix.lower()` | Manual `rsplit('.', 1)` | `pathlib.suffix` handles edge cases (dotfiles, no ext). Compound extensions (`.tar.gz`) are classifier's concern — scanner reports raw suffix (`.gz`). |

## Data Flow

```
CLI
 │
 │  root: Path, exclude: list[str], depth: int?, follow_symlinks: bool
 ▼
┌──────────────────────────────────────────────────────┐
│ FileScanner.__init__(exclude, max_depth, follow_sym) │
└──────────────────┬───────────────────────────────────┘
                   │ .scan(root)
                   ▼
          ┌─────────────────┐
          │   os.walk(root)  │◄── followlinks param
          └────────┬────────┘
                   │ yields (dirpath, dirnames, filenames)
                   ▼
   ┌───────────────────────────────┐
   │ Per-directory processing loop │
   │                               │
   │ 1. Compute depth              │
   │ 2. Prune dirnames (exclude +  │
   │    depth + symlink cycles)    │
   │ 3. Detect empty directory     │
   └───────────┬───────────────────┘
               │ for each filename
               ▼
   ┌───────────────────────────────┐
   │ Per-file processing           │
   │                               │
   │ 1. os.stat(full_path)         │
   │ 2. platform_utils.*()         │
   │ 3. Build FileRecord           │
   │ 4. try/except → errors list   │
   └───────────┬───────────────────┘
               │
               ▼
         ┌────────────┐
         │ ScanResult  │──→ downstream pipeline
         │  .files     │
         │  .directories│
         │  .errors    │
         └────────────┘
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `src/fsaudit/scanner/platform_utils.py` | Create | Three pure functions: `get_creation_time_safe`, `is_hidden`, `get_permissions` |
| `src/fsaudit/scanner/scanner.py` | Create | `FileScanner` class with `scan(root) -> ScanResult` |
| `src/fsaudit/scanner/__init__.py` | Modify | Export `FileScanner` and platform utils |
| `tests/test_scanner.py` | Create | Integration tests for `FileScanner.scan()` |
| `tests/test_platform_utils.py` | Create | Unit tests for OS-abstraction functions |

## Interfaces / Contracts

### platform_utils.py

```python
import sys
from datetime import datetime
from os import stat_result
from pathlib import Path
from typing import Optional

PLATFORM: str = sys.platform  # testable via monkeypatch

def get_creation_time_safe(sr: stat_result) -> datetime:
    """Return best-effort creation time.
    Windows: st_ctime. macOS: st_birthtime. Linux: min(st_mtime, st_ctime).
    """

def is_hidden(name: str, sr: stat_result) -> bool:
    """Dot-prefix on Linux/macOS. FILE_ATTRIBUTE_HIDDEN on Windows."""

def get_permissions(sr: stat_result) -> Optional[str]:
    """Octal string (e.g. '755') on Linux/macOS. None on Windows."""
```

Key detail: `PLATFORM` is a module-level constant that tests can monkeypatch to simulate cross-platform behavior without actually running on Windows.

### scanner.py

```python
from pathlib import Path
from typing import Optional
from fsaudit.scanner.models import ScanResult

class FileScanner:
    def __init__(
        self,
        exclude_patterns: list[str] | None = None,
        max_depth: int | None = None,
        follow_symlinks: bool = False,
    ) -> None: ...

    def scan(self, root: Path) -> ScanResult:
        """Walk root, return ScanResult. Never raises — errors collected."""
```

### os.walk() loop — pseudocode

```python
def scan(self, root: Path) -> ScanResult:
    files, dirs, errors = [], [], []
    visited: set[str] = set()          # only used when follow_symlinks

    for dirpath, dirnames, filenames in os.walk(root, followlinks=self.follow_symlinks):
        depth = len(Path(dirpath).relative_to(root).parts)

        # --- Prune dirnames IN-PLACE (prevents os.walk from descending) ---
        dirnames[:] = [
            d for d in dirnames
            if not self._is_excluded(d)
            and (self.max_depth is None or depth < self.max_depth)
            and not self._is_cycle(dirpath, d, visited)
        ]

        # --- Empty directory detection ---
        if not filenames and not dirnames:
            try:
                sr = os.stat(dirpath)
                dirs.append(DirectoryRecord(
                    path=Path(dirpath), depth=depth,
                    is_hidden=is_hidden(Path(dirpath).name, sr),
                ))
            except OSError as e:
                errors.append(f"{dirpath}: {e}")

        # --- Per-file metadata collection ---
        for name in filenames:
            full = os.path.join(dirpath, name)
            try:
                sr = os.stat(full, follow_symlinks=False)
                files.append(FileRecord(
                    path=Path(full), name=name,
                    extension=Path(name).suffix.lower(),
                    size_bytes=sr.st_size,
                    mtime=datetime.fromtimestamp(sr.st_mtime),
                    creation_time=get_creation_time_safe(sr),
                    atime=datetime.fromtimestamp(sr.st_atime),
                    depth=depth,
                    is_hidden=is_hidden(name, sr),
                    permissions=get_permissions(sr),
                    parent_dir=str(Path(full).parent),
                ))
            except (PermissionError, OSError) as e:
                errors.append(f"{full}: {e}")

    return ScanResult(files=files, directories=dirs, root_path=root, errors=errors)
```

### Exclusion logic

```python
def _is_excluded(self, name: str) -> bool:
    """Match directory/file name against exclude patterns using fnmatch."""
    return any(fnmatch.fnmatch(name, pat) for pat in self.exclude_patterns)
```

Patterns are matched against the **name only** (not full path) — this aligns with how `--exclude` works in `find` and `rsync`.

### Symlink cycle detection

```python
def _is_cycle(self, dirpath: str, name: str, visited: set[str]) -> bool:
    """Return True if following this symlink would create a cycle."""
    if not self.follow_symlinks:
        return False
    real = os.path.realpath(os.path.join(dirpath, name))
    if real in visited:
        return True
    visited.add(real)
    return False
```

## Sequence Diagram — scan() call

```
CLI                FileScanner         os.walk        platform_utils
 │                     │                  │                │
 │  scan(root)         │                  │                │
 │────────────────────>│                  │                │
 │                     │  os.walk(root)   │                │
 │                     │─────────────────>│                │
 │                     │                  │                │
 │                     │  (dirpath,dirs,files)             │
 │                     │<─────────────────│                │
 │                     │                  │                │
 │                     │── prune dirnames in-place         │
 │                     │── detect empty dir                │
 │                     │                  │                │
 │                     │  for each file:  │                │
 │                     │── os.stat(file)  │                │
 │                     │                  │                │
 │                     │  get_creation_time_safe(sr)       │
 │                     │─────────────────────────────────->│
 │                     │                             datetime
 │                     │<─────────────────────────────────│
 │                     │  is_hidden(name, sr)              │
 │                     │─────────────────────────────────->│
 │                     │                              bool │
 │                     │<─────────────────────────────────│
 │                     │  get_permissions(sr)              │
 │                     │─────────────────────────────────->│
 │                     │                     Optional[str] │
 │                     │<─────────────────────────────────│
 │                     │                  │                │
 │                     │── append FileRecord               │
 │                     │                  │                │
 │   ScanResult        │  (loop until exhausted)           │
 │<────────────────────│                  │                │
```

## Testing Strategy

| Layer | What | Approach |
|-------|------|----------|
| Unit | `get_creation_time_safe` | Monkeypatch `PLATFORM`; feed mock `stat_result` with known timestamps |
| Unit | `is_hidden` | Dot-prefix names + mock `st_file_attributes` for Windows path |
| Unit | `get_permissions` | Known `st_mode` values → expected octal strings |
| Unit | `_is_excluded` | Pattern list vs name combinations |
| Integration | `FileScanner.scan()` — basic tree | `tmp_path` fixture: nested dirs, various extensions, verify FileRecord fields |
| Integration | Exclusion | Create `node_modules/` dir, exclude it, verify not in results |
| Integration | Depth limiting | 5-level deep tree, `max_depth=2`, verify depth of returned records |
| Integration | Permission errors | `tmp_path` dir with `chmod 000` (Linux only), verify error collected |
| Integration | Symlink cycles | Create circular symlink, `follow_symlinks=True`, verify no hang + error/skip |
| Integration | Empty directories | Create empty dir inside tree, verify DirectoryRecord emitted |
| Integration | Hidden files | Dot-prefix file + regular file, verify `is_hidden` flag |
| Benchmark | 100k files | Generate 100k empty files in `tmp_path`, assert `scan()` < 60s |

## Migration / Rollout

No migration required. All changes are additive new files. `__init__.py` update is backward-compatible (currently empty).

## Open Questions

- [x] Compound extensions (`.tar.gz`) — resolved: scanner uses `Path.suffix` (reports `.gz`), classifier handles compound mapping
- [ ] Should `FileScanner` accept a logger instance or use `logging.getLogger("fsaudit.scanner")`? Recommendation: module-level logger via `getLogger` (matches `logging_config.py` pattern), but flagging for confirmation.
