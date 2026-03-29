# Spec: Platform — Cross-Platform Abstractions

**Domain**: platform
**Change**: phase1-scanner
**Status**: draft

---

## REQ-PLT-01: Creation Time Abstraction

The system MUST provide a `get_creation_time_safe()` function that returns a `datetime` representing the best available creation time for the current OS.

- **Windows**: MUST use `st_ctime` directly (NTFS creation time).
- **Linux**: MUST use `min(st_mtime, st_ctime)` as approximation.
- **macOS**: MUST use `st_birthtime` when available.

### Scenario: Windows creation time

```
Given a stat_result with st_ctime=2025-01-15 and st_mtime=2025-06-01
When get_creation_time_safe() is called on platform "win32"
Then the result MUST equal datetime(2025, 1, 15, ...)
```

### Scenario: Linux approximation

```
Given a stat_result with st_ctime=2025-03-01 and st_mtime=2025-02-15
When get_creation_time_safe() is called on platform "linux"
Then the result MUST equal datetime(2025, 2, 15, ...) (the minimum)
```

### Scenario: macOS birthtime

```
Given a stat_result with st_birthtime=2024-12-01
When get_creation_time_safe() is called on platform "darwin"
Then the result MUST equal datetime(2024, 12, 1, ...)
```

### Scenario: macOS fallback when birthtime unavailable

```
Given a stat_result WITHOUT st_birthtime attribute on platform "darwin"
When get_creation_time_safe() is called
Then it MUST fall back to min(st_mtime, st_ctime) (Linux strategy)
```

---

## REQ-PLT-02: Hidden File Detection

The system MUST provide an `is_hidden()` function that detects hidden files in an OS-appropriate manner.

- **Linux/macOS**: A file MUST be considered hidden if its name starts with `'.'`.
- **Windows**: A file MUST be considered hidden if `stat_result.st_file_attributes` has the `FILE_ATTRIBUTE_HIDDEN` flag set.
- **Windows fallback**: If `st_file_attributes` is not available, the function MUST fall back to the dot-prefix heuristic.

### Scenario: Linux hidden file

```
Given a file named ".bashrc" on platform "linux"
When is_hidden() is called
Then the result MUST be True
```

### Scenario: Linux visible file

```
Given a file named "readme.md" on platform "linux"
When is_hidden() is called
Then the result MUST be False
```

### Scenario: Windows hidden attribute

```
Given a file with st_file_attributes containing FILE_ATTRIBUTE_HIDDEN on "win32"
When is_hidden() is called
Then the result MUST be True
```

### Scenario: Windows fallback to dot-prefix

```
Given a file named ".env" on "win32" where st_file_attributes is unavailable
When is_hidden() is called
Then the result MUST be True (dot-prefix fallback)
```

---

## REQ-PLT-03: Permissions Extraction

The system MUST provide a `get_permissions()` function that returns a human-readable permission string.

- **Linux/macOS**: MUST return an octal string (e.g., `"755"`) derived from `st_mode`.
- **Windows**: MUST return `None` (NTFS ACLs are out of scope for Phase 1).

### Scenario: Linux standard permissions

```
Given a stat_result with st_mode corresponding to rwxr-xr-x on "linux"
When get_permissions() is called
Then the result MUST equal "755"
```

### Scenario: Windows returns None

```
Given any stat_result on platform "win32"
When get_permissions() is called
Then the result MUST be None
```

---

## REQ-PLT-04: Path Encoding Safety

All platform functions MUST handle paths containing non-ASCII characters without raising exceptions. The system SHOULD use `os.fsdecode()` for byte-string paths.

### Scenario: Unicode filename

```
Given a file named "informe_2025.txt" in a path containing "documentos"
When the Scanner processes this file
Then the FileRecord MUST be created without error
And FileRecord.name MUST preserve the original characters
```

### Scenario: Byte-string path decoded

```
Given a path provided as bytes (from os.walk with bytes input)
When os.fsdecode() is applied
Then the result MUST be a valid str or raise a catchable error (never crash)
```
