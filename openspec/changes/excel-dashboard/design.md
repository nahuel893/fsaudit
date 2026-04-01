# Design: Excel Dashboard

## Technical Approach

Enhance `ExcelReporter` with four capabilities — all within the single existing module. No new files, no new dependencies. openpyxl already provides `LineChart`, `Reference`, `PatternFill`, `Alignment`, and autofilter support.

## Architecture Decisions

### Decision: MB conversion as static method returning float

| Option | Tradeoff | Decision |
|--------|----------|----------|
| `_bytes_to_mb()` returning `float` | Numeric cell values, sortable in Excel | **Chosen** |
| Keep `_format_bytes()` returning `str` | Human-readable but not sortable/filterable | Rejected |
| Both: numeric + formatted column | Extra columns, cluttered | Rejected |

**Rationale**: Autofilter and chart references require numeric cells. A float in MB (2 decimals) is both readable and machine-friendly. Column headers change to include "(MB)".

### Decision: Row-based KPI layout (no merged cells)

| Option | Tradeoff | Decision |
|--------|----------|----------|
| Simple row layout (label col A, value col B) | Clean, no merge conflicts, testable | **Chosen** |
| Merged cells grid (2x3 KPI cards) | Visual appeal but breaks autofilter, harder to test | Rejected |

**Rationale**: Proposal mentioned merged cells, but they add complexity and conflict with freeze panes. Row layout keeps the sheet testable and avoids openpyxl merge edge cases.

### Decision: Autofilter helper method

| Option | Tradeoff | Decision |
|--------|----------|----------|
| `_apply_autofilter(ws, num_cols)` helper | DRY, reuses pattern from Inventario | **Chosen** |
| Inline autofilter in each method | Duplicated logic | Rejected |

## Data Flow

```
AnalysisResult ──→ ExcelReporter.generate()
                        │
                        ├─ _bytes_to_mb(val)     ← new static helper
                        ├─ _apply_autofilter(ws)  ← new helper
                        │
                        ├─ _write_dashboard()     ← KPI rewrite
                        ├─ _write_por_categoria() ← autofilter + MB
                        ├─ _write_timeline()      ← autofilter + LineChart
                        ├─ _write_top_pesados()   ← autofilter + MB
                        ├─ _write_inactivos()     ← autofilter + MB
                        ├─ _write_alertas()       ← autofilter
                        ├─ _write_por_directorio()← autofilter + MB
                        └─ _write_inventario()    ← MB (autofilter exists)
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `src/fsaudit/reporter/excel_reporter.py` | Modify | All changes — new helpers, method rewrites |
| `tests/test_excel_reporter.py` | Modify | Update assertions for MB values, add chart/autofilter tests |

## Key Implementation Details

### 1. `_bytes_to_mb` helper

```python
@staticmethod
def _bytes_to_mb(size_bytes: int) -> float:
    """Convert bytes to MB, rounded to 2 decimals."""
    return round(size_bytes / (1024 * 1024), 2)
```

### 2. `_apply_autofilter` helper

```python
@staticmethod
def _apply_autofilter(ws: Worksheet, num_cols: int) -> None:
    """Apply autofilter from A1 to last data cell."""
    last_col = get_column_letter(num_cols)
    last_row = ws.max_row
    ws.auto_filter.ref = f"A1:{last_col}{last_row}"
```

Called at end of: `_write_por_categoria`, `_write_timeline`, `_write_top_pesados`, `_write_inactivos`, `_write_alertas`, `_write_por_directorio`. Inventario already has its own autofilter logic (keep as-is).

### 3. Dashboard KPI layout

```
Row 1: "Dashboard"          (bold, Font(size=14))          ← section header
Row 2: "Total Archivos"     | {int}
Row 3: "Tamano Total (MB)"  | {float MB}
Row 4: "Categorias"         | {int: len(by_category)}
Row 5: "Alertas"            | {int: zero_byte + dupes + perm_issues}
Row 6: (blank)
Row 7: "Top 5 Categorias por Tamano"  (bold, Font(size=12)) ← section header
Row 8: "Categoria" | "Tamano (MB)"     ← sub-header
Row 9+: sorted by_category top 5 by bytes, converted to MB
Row N:  (blank)
Row N+1: "Top 5 Directorios por Cantidad" (bold, Font(size=12))
Row N+2: "Directorio" | "Cantidad"
Row N+3+: top 5 dirs by file count (computed from records)
```

Section headers use `Font(size=14, bold=True)` or `Font(size=12, bold=True)`. KPI values use `Font(size=12)`. No `PatternFill` needed — keeps it clean.

### 4. Timeline LineChart

New imports at module top:

```python
from openpyxl.chart import LineChart, Reference
```

Added at end of `_write_timeline`, after data rows:

```python
if len(analysis.timeline) >= 2:
    chart = LineChart()
    chart.title = "Archivos por Periodo"
    chart.y_axis.title = "Cantidad"
    chart.x_axis.title = "Periodo"
    chart.style = 10

    num_rows = len(analysis.timeline)
    data = Reference(ws, min_col=2, min_row=1, max_row=num_rows + 1)
    cats = Reference(ws, min_col=1, min_row=2, max_row=num_rows + 1)
    chart.add_data(data, titles_from_data=True)
    chart.set_categories(cats)
    chart.width = 20
    chart.height = 12

    ws.add_chart(chart, f"A{num_rows + 3}")
```

Guard `>= 2` prevents degenerate single-point chart.

### 5. Column header renames

| Sheet | Old header | New header |
|-------|-----------|------------|
| Por Categoria | "Volumen (bytes)" | "Volumen (MB)" |
| Por Categoria | "Promedio Tamano" | "Promedio (MB)" |
| Top Archivos Pesados | "Tamano" | "Tamano (MB)" |
| Archivos Inactivos | "Tamano" | "Tamano (MB)" |
| Por Directorio | "Volumen Total" | "Volumen Total (MB)" |
| Por Directorio | "Volumen Promedio" | "Volumen Promedio (MB)" |
| Inventario Completo | "Tamano" | "Tamano (MB)" |

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit | `_bytes_to_mb` parametrized | `@pytest.mark.parametrize` with edge cases (0, small, large) |
| Unit | Dashboard KPI values | Assert row/col values are numeric, correct count |
| Unit | Autofilter on 6 sheets | Load workbook, check `ws.auto_filter.ref is not None` for each |
| Unit | Timeline chart exists | Check `ws._charts` has length 1 when timeline has >= 2 periods |
| Unit | MB values are float | Assert `isinstance(cell.value, float)` for size columns |
| Regression | Existing tests | Update assertions that expect `_format_bytes` strings to expect floats |

## Migration / Rollout

No migration required. Single-file change, backward compatible output format.

## Open Questions

None — all decisions resolved.
