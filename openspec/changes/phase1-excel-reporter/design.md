# Design: Phase 1 Excel Reporter

## Technical Approach

Implement the reporter module as the final pipeline stage. A `BaseReporter` ABC defines the contract; `ExcelReporter` is the first concrete implementation using openpyxl. Each of the 8 PRD-defined sheets maps to one private method. The reporter receives pre-computed `AnalysisResult` + raw `list[FileRecord]` and produces a `.xlsx` file. No mutation of input data.

## Architecture Decisions

### ADR-1: BaseReporter ABC with single `generate()` method

| Option | Tradeoff | Decision |
|--------|----------|----------|
| ABC with `generate()` | Clean contract, easy to add HTML/JSON reporters later | **Chosen** |
| Protocol (structural typing) | More Pythonic but less explicit for portfolio project | Rejected |
| No base class, standalone functions | Simpler but breaks PRD's Reporter subclass design | Rejected |

**Rationale**: PRD section 5.2 explicitly names `BaseReporter` with subclasses. ABC enforces the contract at instantiation time, matching the pipeline's design-by-contract approach.

### ADR-2: Signature — `generate(records, analysis, output_path) -> Path`

| Option | Tradeoff | Decision |
|--------|----------|----------|
| `generate(analysis, records, output_path)` | Analysis-first feels natural but records are the raw data | Rejected |
| `generate(records, analysis, output_path)` | Records are primary input, analysis is derived | **Chosen** |
| `generate(scan_result, analysis, output_path)` | Leaks scanner internals into reporter | Rejected |

**Rationale**: The Inventario sheet needs raw `FileRecord` fields. `AnalysisResult` lacks per-file detail by design. Passing both keeps the reporter decoupled from `ScanResult`.

### ADR-3: Standard mode vs write-only mode (openpyxl)

| Option | Tradeoff | Decision |
|--------|----------|----------|
| Always standard mode | Supports styling, autofilter, frozen panes; holds all cells in memory | **Chosen** |
| Write-only for Inventario sheet | Lower memory but no cell styling, no autofilter | Deferred |
| Write-only threshold (>100k rows) | Complexity for edge case | Deferred |

**Rationale**: MVP targets typical user home dirs (~10k-50k files). Standard mode enables frozen panes, autofilter, and styling on all sheets. Write-only optimization deferred to Phase 2 if profiling shows need.

### ADR-4: One private method per sheet

| Option | Tradeoff | Decision |
|--------|----------|----------|
| One method per sheet | Clear separation, easy to test individually | **Chosen** |
| Generic table writer + config dicts | DRY but obscures sheet-specific logic (dashboard KPIs, alert grouping) | Rejected |

**Rationale**: Each sheet has unique structure (dashboard = KPI pairs, alertas = multi-source union, inventario = flat table). A generic writer would need so many special cases it would be harder to maintain.

### ADR-5: Styling strategy

| Option | Tradeoff | Decision |
|--------|----------|----------|
| Helper functions + NamedStyle objects | Reusable, clean separation of content vs presentation | **Chosen** |
| Inline styling per cell | Quick but duplicated, hard to change theme | Rejected |

**Rationale**: `NamedStyle` objects are created once per workbook and applied by name. Helpers for header row, number format, and column width keep sheet methods focused on data.

## Data Flow

```
list[FileRecord]  ──┐
                     ├──→ ExcelReporter.generate() ──→ .xlsx file
AnalysisResult    ──┘           │
                                ├── _write_dashboard(ws, analysis)
                                ├── _write_por_categoria(ws, analysis)
                                ├── _write_timeline(ws, analysis)
                                ├── _write_top_pesados(ws, analysis)
                                ├── _write_inactivos(ws, analysis)
                                ├── _write_alertas(ws, analysis)
                                ├── _write_por_directorio(ws, records)
                                └── _write_inventario(ws, records)
```

Each `_write_*` method receives the worksheet (already created by `generate()`) and the relevant data source. After all sheets are written, `generate()` calls `wb.save(output_path)` and returns the `Path`.

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `src/fsaudit/reporter/base.py` | Create | `BaseReporter` ABC with abstract `generate()` |
| `src/fsaudit/reporter/excel_reporter.py` | Create | `ExcelReporter` with 8 sheet methods + styling helpers |
| `src/fsaudit/reporter/__init__.py` | Modify | Export `BaseReporter`, `ExcelReporter` |

## Interfaces / Contracts

```python
# reporter/base.py
from abc import ABC, abstractmethod
from pathlib import Path
from fsaudit.analyzer.metrics import AnalysisResult
from fsaudit.scanner.models import FileRecord

class BaseReporter(ABC):
    @abstractmethod
    def generate(
        self,
        records: list[FileRecord],
        analysis: AnalysisResult,
        output_path: Path,
    ) -> Path:
        """Generate report file. Returns path to created file."""
        ...
```

```python
# reporter/excel_reporter.py  (public surface only)
class ExcelReporter(BaseReporter):
    def generate(self, records, analysis, output_path) -> Path: ...

    # Private sheet writers — each takes (ws: Worksheet, data)
    # Private helpers:
    #   _apply_header_style(ws: Worksheet, row: int, num_cols: int)
    #   _auto_column_width(ws: Worksheet, max_width: int = 50, sample_rows: int = 100)
    #   _format_bytes(size_bytes: int) -> str  (returns "1.23 MB" etc.)
```

**Sheet column specs** (from PRD section 10):

| Sheet | Columns |
|-------|---------|
| Dashboard | KPI name, Value (key-value pairs, not tabular) |
| Por Categoria | Categoria, Cantidad, Bytes, % Total, Promedio, Mas Reciente, Mas Antiguo |
| Timeline | Mes (YYYY-MM), Cantidad |
| Top Pesados | Nombre, Ruta, Tamano, Categoria, Ultima Modificacion |
| Inactivos | Ruta, Tamano, Categoria, Ultima Modificacion, Dias Inactivo |
| Alertas | Tipo Alerta, Ruta, Detalle |
| Por Directorio | Directorio, Cantidad Archivos, Volumen Total, Profundidad |
| Inventario | path, name, extension, size_bytes, mtime, creation_time, atime, depth, is_hidden, permissions, category, parent_dir |

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit | Each `_write_*` method produces correct rows/cols | Create ExcelReporter, call generate() with fixture data, load .xlsx with openpyxl and assert cell values |
| Unit | `_format_bytes` conversion accuracy | Parametrized test: bytes/KB/MB/GB boundaries |
| Unit | Header styling applied correctly | Assert font.bold, freeze_panes on loaded workbook |
| Unit | Empty input (0 files) produces valid .xlsx | generate() with empty list should not raise |
| Integration | Full pipeline scan -> analyze -> report | End-to-end with tmp_path fixture filesystem |

## Migration / Rollout

No migration required. All changes are additive (new files + one import update). Rollback = delete two new files, revert `__init__.py`.

## Open Questions

None -- all data structures and sheet specs are fully defined by the existing codebase and PRD.
