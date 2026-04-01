# Spec: excel-dashboard (DELTA)

**Domain**: excel-dashboard
**Module**: `src/fsaudit/reporter/excel_reporter.py`
**Type**: Delta — modifies existing ExcelReporter behavior

---

## MODIFIED: Dashboard sheet redesign

The Dashboard sheet MUST display a KPI section with four metrics followed by a category summary table.

### Requirements

- **KPI-1**: Dashboard MUST display "Total Archivos" with `analysis.total_files` as value.
- **KPI-2**: Dashboard MUST display "Tamaño Total (MB)" with `analysis.total_size_bytes` converted to MB (2 decimal places).
- **KPI-3**: Dashboard MUST display "Categorías" with the count of keys in `analysis.by_category`.
- **KPI-4**: Dashboard MUST display "Alertas Activas" with the sum of zero-byte files, permission issues, and duplicate groups.
- **KPI-STYLE**: KPI values MUST use `Font(bold=True, size=14)`. KPI labels MUST use `Font(bold=True)`. A `PatternFill` SHOULD be applied to the KPI header row.
- **CAT-TABLE**: Below the KPI section, a category summary sub-table MUST list each category with its count and size in MB.

### Scenario: Dashboard KPIs render correctly

```
GIVEN an AnalysisResult with total_files=150, total_size_bytes=10485760,
      by_category={"docs": {...}, "images": {...}}, zero_byte_files=[x],
      permission_issues=[], duplicates_by_name={"a.txt": ["p1","p2"]}
WHEN  the Dashboard sheet is written
THEN  cell values MUST include:
      - "Total Archivos" → 150
      - "Tamaño Total (MB)" → 10.00
      - "Categorías" → 2
      - "Alertas Activas" → 3
```

---

## MODIFIED: Size values displayed in MB across all sheets

All size columns across every sheet MUST display numeric MB values (2 decimal places) instead of the current `_format_bytes()` string output.

### Requirements

- **MB-CONVERT**: A `_to_mb(size_bytes: int) -> float` static method MUST return `round(size_bytes / (1024 * 1024), 2)`.
- **MB-HEADER**: Column headers containing size references MUST read "Tamaño (MB)" — not "Tamano", "Volumen (bytes)", or "Tamano" without tilde. Applies to: Por Categoría, Top Archivos Pesados, Archivos Inactivos, Por Directorio, Inventario Completo.
- **MB-CELLS**: Cell values for size columns MUST be numeric floats (not strings), enabling Excel sorting and formulas.

### Scenario: Size columns contain numeric MB values

```
GIVEN a file record with size_bytes=2097152
WHEN  written to any sheet with a size column
THEN  the cell value MUST be 2.0 (float), not "2.00 MB" (string)
AND   the column header MUST contain "Tamaño (MB)"
```

---

## ADDED: Autofilter on all tabular sheets

Every sheet that contains a header row and tabular data MUST have autofilter enabled, except Dashboard (KPI layout, not tabular).

### Requirements

- **AF-SHEETS**: Autofilter MUST be applied to: Por Categoría, Timeline, Top Archivos Pesados, Archivos Inactivos, Alertas, Por Directorio. Inventario Completo already has autofilter (no change).
- **AF-RANGE**: Autofilter ref MUST span from `A1` to the last column letter + last data row (e.g., `A1:G25`).
- **AF-EMPTY**: When a sheet has zero data rows, autofilter MUST still cover the header row (e.g., `A1:D1`).
- **AF-HELPER**: A reusable `_apply_autofilter(ws, num_rows, num_cols)` helper SHOULD be extracted to avoid duplication.

### Scenario: Autofilter is set on Por Categoría

```
GIVEN an AnalysisResult with 5 categories
WHEN  the "Por Categoría" sheet is written
THEN  ws.auto_filter.ref MUST equal "A1:G6"
```

### Scenario: Autofilter on empty Alertas sheet

```
GIVEN an AnalysisResult with no alerts and records with no extensionless files
WHEN  the "Alertas" sheet is written
THEN  ws.auto_filter.ref MUST equal "A1:D1"
```

---

## ADDED: Line chart on Timeline sheet

The Timeline sheet MUST include an openpyxl `LineChart` visualizing file count per period.

### Requirements

- **CHART-TYPE**: The chart MUST be a `LineChart` from `openpyxl.chart`.
- **CHART-X**: X-axis categories MUST be the period labels (YYYY-MM format) from column A.
- **CHART-Y**: Y-axis data MUST be the file counts from column B.
- **CHART-TITLE**: Chart title MUST be "Archivos por Período".
- **CHART-POS**: The chart MUST be anchored below the last data row (e.g., cell `A{last_row + 2}`), not overlapping data.
- **CHART-EMPTY**: When timeline has zero entries, no chart MUST be added.

### Scenario: Timeline chart renders with data

```
GIVEN an AnalysisResult with timeline={"2025-01": 10, "2025-02": 20, "2025-03": 15}
WHEN  the Timeline sheet is written
THEN  a LineChart MUST exist on the sheet
AND   chart.title MUST equal "Archivos por Período"
AND   the chart anchor row MUST be >= last_data_row + 2
```

### Scenario: No chart on empty timeline

```
GIVEN an AnalysisResult with timeline={}
WHEN  the Timeline sheet is written
THEN  no chart object MUST be present on the sheet
```
