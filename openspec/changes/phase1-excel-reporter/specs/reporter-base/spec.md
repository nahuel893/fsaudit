# Spec: reporter-base

**Change**: phase1-excel-reporter
**Domain**: reporter-base
**Status**: draft
**Date**: 2026-03-29

## Overview

Defines the `BaseReporter` abstract contract and the `ExcelReporter` concrete class that generates valid `.xlsx` files from scan and analysis data.

## Requirements

### REQ-RB-01: BaseReporter ABC

The module MUST define `BaseReporter` as an abstract base class in `reporter/base.py` with a single abstract method:

```python
def generate(
    self,
    records: list[FileRecord],
    analysis: AnalysisResult,
    output_path: Path,
) -> Path:
```

The method MUST return the `Path` of the generated file. Subclasses MUST implement this method.

### REQ-RB-02: ExcelReporter class

`ExcelReporter` MUST extend `BaseReporter` and be defined in `reporter/excel_reporter.py`. It MUST use `openpyxl` as the only Excel engine.

### REQ-RB-03: Output file creation

`ExcelReporter.generate()` MUST create a valid `.xlsx` file at the specified `output_path`. If parent directories do not exist, the method MUST raise `FileNotFoundError` (no implicit mkdir).

### REQ-RB-04: Valid xlsx output

The generated file MUST be loadable by `openpyxl.load_workbook()` without errors. The file MUST NOT be empty (zero bytes).

### REQ-RB-05: Module exports

`reporter/__init__.py` MUST export `BaseReporter` and `ExcelReporter`.

## Scenarios

### SC-RB-01: Generate report with valid data

**Given** a list of `FileRecord` and an `AnalysisResult` with populated metrics
**When** `ExcelReporter.generate(records, analysis, output_path)` is called
**Then** a `.xlsx` file is created at `output_path`
**And** the file is loadable by `openpyxl.load_workbook()`
**And** the returned `Path` equals `output_path`

### SC-RB-02: Generate report with empty data

**Given** an empty list of `FileRecord` and a default `AnalysisResult()`
**When** `ExcelReporter.generate([], analysis, output_path)` is called
**Then** a valid `.xlsx` file is still created at `output_path`
**And** all 8 sheets are present (headers only, no data rows)

### SC-RB-03: Invalid output path

**Given** an `output_path` whose parent directory does not exist
**When** `ExcelReporter.generate()` is called
**Then** `FileNotFoundError` is raised
**And** no partial file is left on disk

### SC-RB-04: BaseReporter is abstract

**Given** a direct instantiation of `BaseReporter`
**When** the caller tries to call `generate()`
**Then** `TypeError` is raised because the ABC cannot be instantiated without implementing `generate()`
