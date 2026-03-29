# Spec: Alerts Domain

**Change**: phase1-analyzer
**Domain**: alerts
**Status**: draft
**Covers**: RF-11, RF-12, RF-13, RF-14, RF-16

---

## Overview

Detection of anomalies within scanned files. All alert logic runs inside `analyze()` and populates `AnalysisResult` fields. Each detection is a pure filter over input data.

---

## REQ-B1: Inactive File Detection (RF-11)

The analyzer MUST populate `inactive_files` with files whose `mtime` exceeds `inactive_days` from now. Each entry: `path` (str), `size_bytes` (int), `category` (str), `mtime` (datetime), `days_inactive` (int).

### Scenario B1.1: Detection with default threshold

**Given** a file with mtime 200 days ago and `inactive_days=180`
**When** `analyze()` is called
**Then** `inactive_files` MUST contain that file
**And** `days_inactive` MUST equal 200

### Scenario B1.2: File within threshold

**Given** a file with mtime 30 days ago and `inactive_days=180`
**When** `analyze()` is called
**Then** `inactive_files` MUST NOT contain that file

### Scenario B1.3: Custom threshold

**Given** a file with mtime 400 days ago and `inactive_days=365`
**When** `analyze()` is called
**Then** `inactive_files` MUST contain that file with `days_inactive` equal to 400

### Scenario B1.4: Boundary — exact threshold

**Given** a file with mtime exactly 180 days ago and `inactive_days=180`
**When** `analyze()` is called
**Then** `inactive_files` MUST contain that file (greater-than-or-equal)

---

## REQ-B2: Zero-Byte File Detection (RF-12)

The analyzer MUST populate `zero_byte_files` where `size_bytes == 0`. Each entry: `path` (str), `category` (str), `mtime` (datetime).

### Scenario B2.1: Zero-byte detected

**Given** files with sizes [0, 100, 0, 50]
**When** `analyze()` is called
**Then** `zero_byte_files` MUST have length 2

### Scenario B2.2: No zero-byte files

**Given** files with sizes [100, 200]
**When** `analyze()` is called
**Then** `zero_byte_files` MUST be empty

---

## REQ-B3: Empty Directory Detection (RF-13)

The analyzer MUST populate `empty_directories` from `ScanResult.directories`. Each entry: `path` (str), `depth` (int).

### Scenario B3.1: Empty directories present

**Given** a ScanResult with 2 DirectoryRecords
**When** `analyze()` is called
**Then** `empty_directories` MUST have length 2
**And** each entry MUST contain `path` and `depth`

### Scenario B3.2: No empty directories

**Given** a ScanResult with an empty `directories` list
**When** `analyze()` is called
**Then** `empty_directories` MUST be empty

---

## REQ-B4: Duplicate Detection by Filename (RF-14)

The analyzer MUST populate `duplicates_by_name` as `dict[str, list[str]]` — keys are filenames in 2+ locations, values are path lists. Unique names MUST NOT appear.

### Scenario B4.1: Duplicates detected

**Given** files: "/a/report.pdf", "/b/report.pdf", "/c/unique.txt"
**When** `analyze()` is called
**Then** `duplicates_by_name` MUST contain key "report.pdf" with 2 paths
**And** "unique.txt" MUST NOT be a key

### Scenario B4.2: No duplicates

**Given** files with all unique names
**When** `analyze()` is called
**Then** `duplicates_by_name` MUST be empty

### Scenario B4.3: Three-way duplicate

**Given** 3 files all named "readme.md" in different directories
**When** `analyze()` is called
**Then** `duplicates_by_name["readme.md"]` MUST contain exactly 3 paths

---

## REQ-B5: Permission Issues (RF-16)

The analyzer MUST flag files with unusual Linux permissions: "7" in the other-users octal position (world-accessible) or SUID/SGID bits set. Files with `permissions is None` (Windows) MUST be skipped.

### Scenario B5.1: World-writable detected

**Given** a file with `permissions="777"`
**When** `analyze()` is called
**Then** `permission_issues` MUST contain that file

### Scenario B5.2: Safe permissions skipped

**Given** a file with `permissions="644"`
**When** `analyze()` is called
**Then** `permission_issues` MUST NOT contain that file

### Scenario B5.3: Windows files skipped

**Given** a file with `permissions=None`
**When** `analyze()` is called
**Then** `permission_issues` MUST NOT contain that file

### Scenario B5.4: SUID bit detected

**Given** a file with `permissions="4755"`
**When** `analyze()` is called
**Then** `permission_issues` MUST contain that file

### Scenario B5.5: World-readable but not writable

**Given** a file with `permissions="755"`
**When** `analyze()` is called
**Then** `permission_issues` MUST NOT contain that file (read+execute is common)

---

## Constraints

- All detection MUST be pure — no filesystem access.
- `days_inactive` computed as `(now - mtime).days`.
- The `now` reference SHOULD be computed once at `analyze()` entry for consistency and testability.
