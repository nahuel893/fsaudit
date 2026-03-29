# Proposal: phase1-excel-reporter

**Date**: 2026-03-29
**Status**: proposed

## Intent

Implement the Excel Reporter module (Phase 1, Step 5) to generate multi-sheet `.xlsx` reports from scan and analysis data. This is the primary output format of fsaudit and the last pipeline stage needed for a functional MVP.

## Problem

The pipeline produces `AnalysisResult` and `ScanResult` but has no way to present findings to the user. The PRD defines an 8-sheet Excel report as the primary deliverable.

## Approach

1. **BaseReporter ABC** (`reporter/base.py`) -- Abstract base with `generate()` method. Signature accepts `AnalysisResult`, `list[FileRecord]`, and `output_path: Path`. The file list is needed separately because `AnalysisResult` contains aggregated metrics but not the raw records required for the "Inventario Completo" sheet.

2. **ExcelReporter** (`reporter/excel_reporter.py`) -- Concrete implementation using `openpyxl`. One private method per sheet:
   - `_write_dashboard` -- KPIs: total files, total volume, files per category, top 5 dirs by volume, count of active alerts.
   - `_write_por_categoria` -- Category table from `by_category` dict.
   - `_write_timeline` -- Monthly distribution from `timeline` dict.
   - `_write_top_pesados` -- Top 20 from `top_largest`.
   - `_write_inactivos` -- Inactive files with days-inactive column.
   - `_write_alertas` -- Combines `zero_byte_files`, `permission_issues`, `duplicates_by_name`, and files with empty extension.
   - `_write_por_directorio` -- Top directories by volume/count, derived from file records.
   - `_write_inventario` -- All `FileRecord` fields as a flat table with autofilter.

3. **Styling** -- Frozen header rows, bold headers, number formatting (bytes as KB/MB/GB), auto-adjusted column widths (capped at 50 chars), alternating row colors for readability.

4. **Integration** -- Update `reporter/__init__.py` to export `BaseReporter` and `ExcelReporter`.

## Affected Modules

| Module | Change |
|--------|--------|
| `reporter/__init__.py` | Export `BaseReporter`, `ExcelReporter` |
| `reporter/base.py` | **New** -- ABC definition |
| `reporter/excel_reporter.py` | **New** -- 8-sheet implementation |

No changes to scanner, classifier, or analyzer modules.

## Risks

- **Large inventories (>100k rows)**: openpyxl write-only mode (`optimized_write=True`) may be needed. Mitigate by using `write_only` worksheets for the Inventario sheet if row count exceeds a threshold.
- **Column width calculation** on large datasets could be slow. Mitigate by sampling first N rows for width estimation.

## Rollback Plan

All changes are additive (new files only). Rollback = delete `reporter/base.py` and `reporter/excel_reporter.py`, revert `reporter/__init__.py` to empty. No existing modules are modified.

## Budget

3 new files, ~400 LOC implementation + ~300 LOC tests. One session for implementation, one for testing.
