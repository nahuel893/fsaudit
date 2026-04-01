# Proposal: excel-dashboard

## Intent

Transform the existing Excel reporter from a plain data dump into a professional dashboard workbook with KPIs, interactive filters, a timeline chart, and consistent MB-based size display.

## Scope

**Single module**: `src/fsaudit/reporter/excel_reporter.py`

No new modules, no new dependencies (openpyxl already supports charts, autofilter, and styling).

### In scope

1. **Dashboard sheet redesign** — prominent KPI section (total files, total size in MB, categories count, active alerts), styled with merged cells, larger fonts, and fill colors. Category summary sub-table below KPIs with sizes in MB.
2. **Autofilter on all tabular sheets** — add `ws.auto_filter.ref` to: Por Categoria, Timeline, Top Archivos Pesados, Archivos Inactivos, Alertas, Por Directorio. Inventario Completo already has it.
3. **Line chart on Timeline sheet** — `openpyxl.chart.LineChart` with months (YYYY-MM) on X-axis and file count on Y-axis, embedded below the data table.
4. **Size normalization to MB** — all size columns across all sheets display values in MB (2 decimal places) instead of raw bytes or mixed units. Column headers updated to reflect "(MB)".

### Out of scope

- New sheets or sheet reordering
- Conditional formatting / sparklines
- PDF export or other output formats

## Approach

1. Add a `_to_mb()` static helper: `round(size_bytes / (1024 * 1024), 2)`.
2. Replace all `_format_bytes()` calls with `_to_mb()` for cell values. Keep `_format_bytes()` available but unused (backward compat).
3. Add `_apply_autofilter(ws, num_rows, num_cols)` helper — applies autofilter ref from A1 to last data cell. Call it at the end of each tabular sheet writer.
4. Rewrite `_write_dashboard()` — use merged cells for KPI title row, `Font(size=14, bold=True)` for KPI values, `PatternFill` for header background. Structure: title row, KPI grid (2x3), blank row, category table.
5. Add `_write_timeline_chart(ws, num_data_rows)` — creates a `LineChart`, sets data reference and category reference from the Timeline data range, anchors chart below the table.
6. Import `LineChart, Reference` from `openpyxl.chart` and `PatternFill, Alignment` from `openpyxl.styles`.

## Affected Modules

| Module | Change type |
|--------|-------------|
| `src/fsaudit/reporter/excel_reporter.py` | Modified — all changes here |

## Risks

- **Chart rendering**: openpyxl charts may render differently across Excel versions and LibreOffice. Mitigation: use only `LineChart` which has broad support.
- **Merged cells + autofilter**: merged cells in Dashboard could conflict if autofilter is added there. Mitigation: Dashboard is a KPI sheet, no autofilter needed.

## Rollback Plan

Single-file change. Rollback = `git checkout HEAD~1 -- src/fsaudit/reporter/excel_reporter.py`. No migrations, no schema changes, no config changes.

## Budget

Estimated 4 tasks, completable in one session.
