# Design: phase1-analyzer

## Technical Approach

Single module `analyzer.py` with one public function `analyze()` and 8 private helpers, one per RF metric group. Follows the same pattern as `classifier.py`: top-level pure function, no classes, functional style. Multi-pass over `records` (one per helper) for clarity over premature optimization — N is filesystem-bound and always fits in memory.

## Architecture Decisions

| # | Decision | Alternatives | Rationale |
|---|----------|-------------|-----------|
| 1 | **Multi-pass** (one iteration per helper) | Single-pass accumulating all metrics | Helpers are independent and testable in isolation. File counts are <1M in practice; CPU cost is negligible vs. I/O. |
| 2 | **Free functions, no class** | `FileAnalyzer` class (PRD mentions one) | Codebase convention: `classify()` is a free function. No state to encapsulate. Matches existing pattern. |
| 3 | **`collections.Counter`** for category/timeline aggregation | Manual dict accumulation | stdlib, concise, purpose-built for frequency counting. |
| 4 | **`datetime.now()` injected via `_now` param** (test seam) | Freeze time / mock | Simpler, no external deps, explicit. Hidden param with underscore prefix. |
| 5 | **Return `str(path)` in list items** (top_largest, inactive, etc.) | Return full `FileRecord` refs | Keeps `AnalysisResult` serialization-friendly. Reporter needs paths + sizes, not full records. |
| 6 | **Permission check via octal string parsing** | `os.stat` / `stat` module | `FileRecord.permissions` is already an octal string. No filesystem access needed. |

## Data Flow

```
List[FileRecord] ──┬──→ _compute_category_stats() ──→ by_category
                   ├──→ _compute_timeline()        ──→ timeline
                   ├──→ _find_top_largest(n)       ──→ top_largest
                   ├──→ _find_inactive(days)       ──→ inactive_files
                   ├──→ _find_zero_byte()          ──→ zero_byte_files
                   ├──→ _find_duplicates_by_name() ──→ duplicates_by_name
                   └──→ _find_permission_issues()  ──→ permission_issues

ScanResult ────────────→ _find_empty_directories()  ──→ empty_directories

analyze() assembles AnalysisResult:
  total_files      = len(records)
  total_size_bytes = sum(r.size_bytes for r in records)
  + all fields above
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `src/fsaudit/analyzer/analyzer.py` | Create | All computation logic: `analyze()` + 8 private helpers |
| `src/fsaudit/analyzer/__init__.py` | Modify | Re-export `analyze` (like classifier exports `classify`) |
| `tests/test_analyzer.py` | Create | Unit tests covering RF-09 through RF-16 |

## Interfaces / Contracts

```python
def analyze(
    files: list[FileRecord],
    scan_result: ScanResult,
    *,
    top_n: int = 20,
    inactive_days: int = 180,
    _now: datetime | None = None,  # test seam
) -> AnalysisResult: ...
```

### Helper signatures

```python
def _compute_category_stats(records: list[FileRecord]) -> dict[str, dict]:
    # Returns: {"Documents": {"count": 5, "bytes": 10240,
    #   "percent": 33.2, "avg_size": 2048.0,
    #   "newest": datetime, "oldest": datetime}, ...}

def _compute_timeline(records: list[FileRecord]) -> dict[str, int]:
    # Returns: {"2024-01": 42, "2024-02": 17, ...}

def _find_top_largest(records: list[FileRecord], n: int) -> list[dict]:
    # Returns: [{"path": str, "size_bytes": int, "category": str}, ...]

def _find_inactive(records: list[FileRecord], days: int, now: datetime) -> list[dict]:
    # Returns: [{"path": str, "size_bytes": int, "mtime": datetime, "category": str}, ...]

def _find_zero_byte(records: list[FileRecord]) -> list[dict]:
    # Returns: [{"path": str, "category": str}, ...]

def _find_empty_directories(scan_result: ScanResult) -> list[dict]:
    # Returns: [{"path": str, "depth": int}, ...]

def _find_duplicates_by_name(records: list[FileRecord]) -> dict[str, list[str]]:
    # Returns: {"report.pdf": ["/a/report.pdf", "/b/report.pdf"], ...}
    # Only entries with 2+ paths included.

def _find_permission_issues(records: list[FileRecord]) -> list[dict]:
    # Returns: [{"path": str, "permissions": str, "issue": str}, ...]
    # issue: "777" | "world-writable" | "suid" | "sgid"
    # Skips records where permissions is None (Windows).
```

### Permission detection logic

| Octal pattern | Issue label |
|---------------|-------------|
| `"777"` | `"777"` |
| `o+w` (last digit in `{2,3,6,7}`) | `"world-writable"` |
| SUID (`int(octal) & 0o4000`) | `"suid"` |
| SGID (`int(octal) & 0o2000`) | `"sgid"` |

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit | Each `_helper` in isolation | Factory function for `FileRecord` with sensible defaults. Parametrize edge cases. |
| Unit | `analyze()` integration of helpers | Small fixture list (~10 records), assert all 10 `AnalysisResult` fields populated. |
| Unit | Empty input | `analyze([], scan_result)` returns zeroed `AnalysisResult`. |
| Unit | Windows compat | Records with `permissions=None` produce no permission issues. |

## Migration / Rollout

No migration required. New file, additive change to `__init__.py`.

## Open Questions

None -- all contracts are defined by existing dataclasses and the PRD.
