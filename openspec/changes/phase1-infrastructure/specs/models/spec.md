# Spec: Models — Data Contracts

**Change**: phase1-infrastructure
**Domain**: models
**Type**: NEW

---

## REQ-MOD-01: FileRecord dataclass

The system MUST provide a `FileRecord` frozen dataclass in `src/fsaudit/scanner/models.py` with exactly these fields and types:

| Field | Type | Description |
|-------|------|-------------|
| `path` | `Path` | Absolute path to the file |
| `name` | `str` | Filename with extension |
| `extension` | `str` | Lowercase extension (empty string if none) |
| `size_bytes` | `int` | File size in bytes |
| `mtime` | `datetime` | Last content modification time |
| `creation_time` | `datetime` | OS-aware creation time |
| `atime` | `datetime` | Last access time |
| `depth` | `int` | Depth relative to scan root |
| `is_hidden` | `bool` | Whether the file is hidden (OS-aware) |
| `permissions` | `str \| None` | Octal permission string or None on Windows |
| `category` | `str` | Category assigned by Classifier |
| `parent_dir` | `str` | Immediate parent directory path |

### Scenario MOD-01a: FileRecord creation (happy path)

- **Given** valid values for all 12 fields
- **When** a `FileRecord` is instantiated
- **Then** all fields MUST be accessible as typed attributes
- **And** the instance MUST be frozen (immutable)

### Scenario MOD-01b: FileRecord immutability

- **Given** an existing `FileRecord` instance
- **When** any field assignment is attempted
- **Then** a `FrozenInstanceError` MUST be raised

### Scenario MOD-01c: FileRecord with no extension

- **Given** a file with no extension (e.g., `Makefile`)
- **When** a `FileRecord` is created
- **Then** the `extension` field MUST be an empty string `""`

### Scenario MOD-01d: FileRecord with None permissions

- **Given** a file scanned on Windows (no POSIX permissions)
- **When** a `FileRecord` is created with `permissions=None`
- **Then** the instance MUST be valid and `permissions` MUST be `None`

---

## REQ-MOD-02: DirectoryRecord dataclass

The system MUST provide a `DirectoryRecord` frozen dataclass with these fields:

| Field | Type | Description |
|-------|------|-------------|
| `path` | `Path` | Absolute path to the directory |
| `depth` | `int` | Depth relative to scan root |
| `is_hidden` | `bool` | Whether the directory is hidden |

### Scenario MOD-02a: DirectoryRecord creation

- **Given** a path, depth, and hidden flag
- **When** a `DirectoryRecord` is instantiated
- **Then** all three fields MUST be accessible and the instance MUST be frozen

---

## REQ-MOD-03: ScanResult container

The system MUST provide a `ScanResult` dataclass that holds scan output:

| Field | Type |
|-------|------|
| `files` | `list[FileRecord]` |
| `directories` | `list[DirectoryRecord]` |

### Scenario MOD-03a: ScanResult with populated data

- **Given** a list of `FileRecord` and a list of `DirectoryRecord`
- **When** a `ScanResult` is created
- **Then** `files` and `directories` MUST contain the provided records

### Scenario MOD-03b: ScanResult with empty lists

- **Given** empty lists for both files and directories
- **When** a `ScanResult` is created
- **Then** both fields MUST be empty lists (not None)

---

## REQ-MOD-04: AnalysisResult dataclass

The system MUST provide an `AnalysisResult` dataclass in `src/fsaudit/analyzer/metrics.py`. It SHALL NOT be frozen (the analyzer builds it incrementally). It MUST have these 10 fields with defaults:

| Field | Type | Default |
|-------|------|---------|
| `total_files` | `int` | `0` |
| `total_size_bytes` | `int` | `0` |
| `by_category` | `dict[str, Any]` | `{}` (via `field(default_factory=dict)`) |
| `top_largest` | `list[Any]` | `[]` (via `field(default_factory=list)`) |
| `inactive_files` | `list[Any]` | `[]` (via `field(default_factory=list)`) |
| `zero_byte_files` | `list[Any]` | `[]` (via `field(default_factory=list)`) |
| `empty_directories` | `list[Any]` | `[]` (via `field(default_factory=list)`) |
| `duplicates_by_name` | `dict[str, list[Any]]` | `{}` (via `field(default_factory=dict)`) |
| `timeline` | `dict[str, Any]` | `{}` (via `field(default_factory=dict)`) |
| `permission_issues` | `list[Any]` | `[]` (via `field(default_factory=list)`) |

### Scenario MOD-04a: AnalysisResult default construction

- **Given** no arguments
- **When** an `AnalysisResult` is instantiated with defaults
- **Then** `total_files` MUST be `0`, `total_size_bytes` MUST be `0`, and all collection fields MUST be empty (not None)

### Scenario MOD-04b: AnalysisResult is mutable

- **Given** an existing `AnalysisResult` instance
- **When** a field assignment is attempted (e.g., `result.total_files = 42`)
- **Then** the assignment MUST succeed (NOT frozen)

### Scenario MOD-04c: AnalysisResult importable

- **Given** the fsaudit package is installed
- **When** `from fsaudit.analyzer.metrics import AnalysisResult` is executed
- **Then** no `ImportError` SHALL be raised
