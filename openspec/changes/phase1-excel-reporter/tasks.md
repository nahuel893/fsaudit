# Tasks: phase1-excel-reporter

**Change**: phase1-excel-reporter
**Status**: done
**Date**: 2026-03-29

## Phase 1: Foundation

- [x] **1.1** Create `src/fsaudit/reporter/base.py` — `BaseReporter` ABC with abstract `generate(records, analysis, output_path) -> Path` method. Imports: `FileRecord`, `AnalysisResult`, `Path`, `abc`.
- [x] **1.2** Create `src/fsaudit/reporter/excel_reporter.py` — `ExcelReporter(BaseReporter)` class skeleton with `generate()` stub that creates a workbook, delegates to 8 empty `_write_*` methods, saves, and returns the path. Raise `FileNotFoundError` if parent dir missing.
- [x] **1.3** Update `src/fsaudit/reporter/__init__.py` — export `BaseReporter` and `ExcelReporter`.

## Phase 2: Styling Helpers

- [x] **2.1** Add `_format_bytes(size_bytes: int) -> str` static method — returns human-readable string (B/KB/MB/GB).
- [x] **2.2** Add `_apply_header_style(ws, num_cols)` — bold font, freeze panes at row 2.
- [x] **2.3** Add `_auto_column_width(ws, max_width=50, sample_rows=100)` — sample-based width adjustment capped at 50 chars.

## Phase 3: Sheet Implementations

- [x] **3.1** `_write_dashboard(ws, analysis, records)` — KPI key-value pairs: total files, total volume (formatted), alert count, category summary table. Apply header style.
- [x] **3.2** `_write_por_categoria(ws, analysis)` — 7 columns from `by_category`. Apply header + autowidth.
- [x] **3.3** `_write_timeline(ws, analysis)` — 2 columns from `timeline` dict, sorted ascending by period.
- [x] **3.4** `_write_top_pesados(ws, analysis)` — 5 columns from `top_largest`, size formatted.
- [x] **3.5** `_write_inactivos(ws, analysis)` — 6 columns from `inactive_files`, sorted by days_inactive desc.
- [x] **3.6** `_write_alertas(ws, analysis, records)` — 4 columns aggregating zero-byte, permissions, duplicates, no-extension sources.
- [x] **3.7** `_write_por_directorio(ws, records)` — 4 columns grouped by `parent_dir`, top 50 by volume desc.
- [x] **3.8** `_write_inventario(ws, records)` — 12 columns, one row per FileRecord, autofilter on header row.

## Phase 4: Integration in generate()

- [x] **4.1** Wire all `_write_*` calls in `generate()` with correct sheet names in REQ-ES-01 order. Apply styling helpers to each sheet after data is written.

## Phase 5: Tests

- [x] **5.1** Test `BaseReporter` is abstract — instantiation raises `TypeError`.
- [x] **5.2** Test `generate()` with valid fixture data — file created, loadable, returns correct path.
- [x] **5.3** Test empty input — valid xlsx with 8 sheets, headers only.
- [x] **5.4** Test invalid output path — `FileNotFoundError` raised, no partial file.
- [x] **5.5** Test sheet names and order match REQ-ES-01.
- [x] **5.6** Test Dashboard KPIs match analysis values.
- [x] **5.7** Test Por Categoria row count matches `by_category` entries.
- [x] **5.8** Test Timeline sort order is chronological ascending.
- [x] **5.9** Test Alertas aggregates all 4 sources correctly.
- [x] **5.10** Test Inventario has autofilter set.
- [x] **5.11** Test `_format_bytes` parametrized — B/KB/MB/GB boundaries.
- [x] **5.12** Test header styling — bold font, frozen panes at row 2.
