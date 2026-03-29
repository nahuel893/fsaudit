# Spec: Scanner — Core Scanning Logic

**Domain**: scanner
**Change**: phase1-scanner
**Status**: draft

---

## REQ-SCN-01: Recursive Directory Traversal

The Scanner MUST recursively walk the entire directory tree from the given root path using `os.walk()`, producing a `FileRecord` for every accessible file.

### Scenario: Happy path — flat directory

```
Given a directory "root/" containing files ["a.txt", "b.py"]
When the Scanner scans "root/"
Then ScanResult.files MUST contain 2 FileRecord entries
And each FileRecord.depth MUST equal 0
And ScanResult.root_path MUST equal the absolute path of "root/"
```

### Scenario: Nested directories

```
Given "root/sub1/sub2/" containing "deep.txt"
When the Scanner scans "root/"
Then FileRecord for "deep.txt" MUST have depth == 2
And FileRecord.parent_dir MUST equal str(path to "root/sub1/sub2")
```

---

## REQ-SCN-02: FileRecord Field Population

Each FileRecord MUST populate all 12 fields defined in `models.py`. Fields `path`, `name`, `extension`, `size_bytes`, `mtime`, `atime`, `depth`, `parent_dir` MUST be derived from `os.stat()` and path operations. `creation_time`, `is_hidden`, `permissions` MUST be derived via platform utility functions.

### Scenario: Extension normalization

```
Given a file "REPORT.PDF" in "root/"
When the Scanner produces its FileRecord
Then FileRecord.extension MUST equal ".pdf" (lowercase)
And FileRecord.name MUST equal "REPORT.PDF" (original case)
```

### Scenario: File without extension

```
Given a file "Makefile" in "root/"
When the Scanner produces its FileRecord
Then FileRecord.extension MUST equal ""
```

---

## REQ-SCN-03: DirectoryRecord for Empty Directories

The Scanner MUST produce a `DirectoryRecord` for every directory that contains no files and no subdirectories after exclusion pruning.

### Scenario: Empty directory detected

```
Given "root/empty_dir/" exists and contains nothing
When the Scanner scans "root/"
Then ScanResult.directories MUST contain a DirectoryRecord with path == "root/empty_dir"
And DirectoryRecord.depth MUST equal 1
```

### Scenario: Non-empty directory omitted

```
Given "root/full_dir/" contains "file.txt"
When the Scanner scans "root/"
Then ScanResult.directories MUST NOT contain a DirectoryRecord for "root/full_dir/"
```

---

## REQ-SCN-04: Exclusion Patterns

The Scanner MUST support a list of exclusion patterns matched via `fnmatch` against directory and file names. Excluded directories MUST be pruned from traversal (not just filtered from results).

### Scenario: Exclude a directory by name

```
Given "root/.git/" contains 50 files and "root/src/" contains 5 files
When the Scanner scans with exclude_patterns=[".git"]
Then ScanResult.files MUST contain exactly 5 FileRecord entries
And no FileRecord.path SHALL contain ".git"
```

### Scenario: Exclude files by glob pattern

```
Given "root/" contains ["app.py", "app.pyc", "data.csv"]
When the Scanner scans with exclude_patterns=["*.pyc"]
Then ScanResult.files MUST contain 2 entries (app.py, data.csv)
```

---

## REQ-SCN-05: Depth Limiting

The Scanner MUST support an optional `max_depth` parameter. When set, directories deeper than `max_depth` (relative to root) MUST NOT be traversed.

### Scenario: Depth limit enforced

```
Given "root/a/b/c/" each containing one file
When the Scanner scans with max_depth=1
Then ScanResult.files MUST only include files at depth 0 and depth 1
And no FileRecord.depth SHALL exceed 1
```

### Scenario: No depth limit by default

```
Given a tree 10 levels deep, each level with one file
When the Scanner scans with max_depth=None
Then ScanResult.files MUST contain 10 FileRecord entries
```

---

## REQ-SCN-06: ScanResult Assembly

`ScanResult` MUST be a frozen dataclass containing `files`, `directories`, `root_path`, and `errors`. The Scanner MUST return exactly one `ScanResult` per invocation.

### Scenario: Complete result structure

```
Given "root/" with 3 files, 1 empty dir, and 1 permission-denied dir
When the Scanner completes scanning
Then ScanResult.files length MUST equal 3
And ScanResult.directories length MUST equal 1
And ScanResult.errors MUST contain at least 1 entry
And ScanResult.root_path MUST equal the scan root
```
