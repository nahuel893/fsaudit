# Spec: Error Handling — Scanner Resilience

**Domain**: error-handling
**Change**: phase1-scanner
**Status**: draft

---

## REQ-ERR-01: PermissionError Resilience

The Scanner MUST NOT halt or raise when encountering a `PermissionError` on any file or directory. The inaccessible path MUST be recorded in `ScanResult.errors` and scanning MUST continue.

### Scenario: Permission denied on a file

```
Given "root/" contains ["ok.txt", "secret.txt"] where "secret.txt" raises PermissionError on stat()
When the Scanner scans "root/"
Then ScanResult.files MUST contain 1 FileRecord (ok.txt)
And ScanResult.errors MUST contain a string referencing "secret.txt"
```

### Scenario: Permission denied on a directory

```
Given "root/restricted/" is a directory that raises PermissionError on listdir
When the Scanner scans "root/"
Then ScanResult.errors MUST contain a string referencing "restricted"
And scanning of sibling directories MUST continue normally
```

---

## REQ-ERR-02: OSError Resilience

The Scanner MUST catch `OSError` (and subclasses) per-file and per-directory. Any OS-level error during `stat()` or traversal MUST be logged in `ScanResult.errors` without halting.

### Scenario: Corrupted filesystem entry

```
Given a file entry that raises OSError during os.stat()
When the Scanner encounters this file
Then it MUST skip the file
And ScanResult.errors MUST contain the path and error description
And the scan MUST continue with remaining files
```

---

## REQ-ERR-03: Symlink Handling

The Scanner MUST default to `followlinks=False`. When `follow_symlinks=True` is set, the Scanner MUST track visited real paths to detect and break cycles.

### Scenario: Symlinks not followed by default

```
Given "root/link" is a symlink pointing to "root/target/"
When the Scanner scans with follow_symlinks=False (default)
Then the contents of "root/target/" through "root/link" MUST NOT be traversed
```

### Scenario: Symlink following with cycle detection

```
Given "root/a/" contains a symlink "loop" pointing back to "root/"
When the Scanner scans with follow_symlinks=True
Then the Scanner MUST detect the cycle via realpath comparison
And MUST NOT re-traverse "root/"
And ScanResult.errors SHOULD contain a cycle warning
```

### Scenario: Valid symlink followed

```
Given "root/link" points to "root/data/" containing "file.txt"
When the Scanner scans with follow_symlinks=True and no cycle exists
Then ScanResult.files MUST include a FileRecord for "file.txt" reached via the symlink
```

---

## REQ-ERR-04: Non-UTF8 Filename Handling

The Scanner MUST handle files whose names cannot be decoded as UTF-8. Such files MUST be either processed using `os.fsdecode()` surrogate escaping or skipped with an error recorded.

### Scenario: Surrogate-escaped filename on Linux

```
Given a file with a name containing invalid UTF-8 bytes (e.g., 0xFF)
When the Scanner encounters this file
Then it MUST either produce a FileRecord with surrogate-escaped name
Or skip the file and append an error to ScanResult.errors
And the scan MUST NOT crash
```

---

## REQ-ERR-05: Depth Limit Boundary

When `max_depth` is set, the Scanner MUST correctly compute depth as `len(dirpath.relative_to(root).parts)` and MUST prune directories exceeding the limit. Off-by-one errors MUST be avoided: depth 0 is the root itself.

### Scenario: Root directory is depth 0

```
Given "root/" contains "file.txt"
When the Scanner scans "root/" with max_depth=0
Then ScanResult.files MUST contain FileRecord for "file.txt" with depth == 0
And subdirectories of "root/" MUST NOT be traversed
```

### Scenario: Boundary at max_depth

```
Given "root/a/" (depth 1) and "root/a/b/" (depth 2) each with one file
When the Scanner scans with max_depth=1
Then files at depth 0 and 1 MUST be included
And "root/a/b/" MUST NOT be traversed
```

---

## REQ-ERR-06: Exclusion Edge Cases

Exclusion patterns MUST be matched against the base name (not the full path). Exclusions MUST apply to both files and directories.

### Scenario: Pattern matches directory name only

```
Given "root/node_modules/" and "root/src/node_modules_info.txt"
When exclude_patterns=["node_modules"]
Then "root/node_modules/" MUST be pruned
And "node_modules_info.txt" MUST NOT be excluded (fnmatch against basename)
```

### Scenario: Wildcard pattern on files

```
Given "root/" contains ["test.log", "app.log", "app.py"]
When exclude_patterns=["*.log"]
Then ScanResult.files MUST contain only "app.py"
```
