# Tasks: excel-dashboard

**Module**: `src/fsaudit/reporter/excel_reporter.py`
**Test file**: `tests/test_excel_reporter.py`

---

## Phase 1: Helpers and imports

### [x] 1.1 Add new imports
Add `LineChart`, `Reference` from `openpyxl.chart` and `PatternFill`, `Alignment` from `openpyxl.styles` at module top of `excel_reporter.py`.

### [x] 1.2 Add `_bytes_to_mb` static method
Static method returning `round(size_bytes / (1024 * 1024), 2)`. Place above `_format_bytes`.

### [x] 1.3 Add `_apply_autofilter` static helper
`_apply_autofilter(ws, num_cols)` — computes last column letter via `get_column_letter`, reads `ws.max_row`, sets `ws.auto_filter.ref`. Import `get_column_letter` if not already imported.

---

## Phase 2: Size normalization

### [x] 2.1 Replace `_format_bytes` calls with `_bytes_to_mb`
In each sheet-writing method, swap all `_format_bytes(val)` cell assignments to `_bytes_to_mb(val)` so cells contain numeric floats.

### [x] 2.2 Update size column headers
Rename headers per design: "Volumen (MB)", "Promedio (MB)", "Tamaño (MB)", "Volumen Total (MB)", "Volumen Promedio (MB)" across Por Categoría, Top Archivos Pesados, Archivos Inactivos, Por Directorio, Inventario Completo.

---

## Phase 3: Autofilter

### [x] 3.1 Call `_apply_autofilter` on six sheets
Add `_apply_autofilter(ws, num_cols)` at end of: `_write_por_categoria`, `_write_timeline`, `_write_top_pesados`, `_write_inactivos`, `_write_alertas`, `_write_por_directorio`. Skip Dashboard (KPI layout) and Inventario (already has autofilter).

---

## Phase 4: Dashboard rewrite

### [x] 4.1 Rewrite `_write_dashboard`
Row-based KPI layout: title row (Font size=14 bold), four KPI rows (label col A, value col B with Font size=12), blank row, "Top 5 Categorías por Tamaño" section header, sub-header row, top 5 categories sorted by bytes descending converted to MB, blank row, "Top 5 Directorios por Cantidad" section, top 5 dirs by file count.

---

## Phase 5: Timeline chart

### [x] 5.1 Add LineChart to `_write_timeline`
After writing data rows, guard with `len(timeline) >= 2`. Create `LineChart` with title "Archivos por Período", data from col B, categories from col A, anchor at `A{num_rows + 3}`, width=20, height=12.

---

## Phase 6: Tests

### [x] 6.1 Add `_bytes_to_mb` parametrized tests
Cases: 0 → 0.0, 1048576 → 1.0, 2097152 → 2.0, 500 → 0.0.

### [x] 6.2 Update existing test assertions
Replace any assertions expecting `_format_bytes` string output with float MB values.

### [x] 6.3 Add autofilter assertions
Load generated workbook, verify `ws.auto_filter.ref` is not None for the six target sheets. Verify empty-data sheet has header-only autofilter range.

### [x] 6.4 Add Dashboard KPI value assertions
Assert KPI cells contain correct numeric values matching the scenario in the spec.

### [x] 6.5 Add Timeline chart assertion
Verify `len(ws._charts) == 1` when timeline has >= 2 entries, and `len(ws._charts) == 0` when timeline is empty.
