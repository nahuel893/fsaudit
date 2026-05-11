# Design: excel-overflow-strategy

## Technical Approach

Thread `overflow_strategy` through CLI → API → ExcelReporter. In `ExcelReporter.generate()`, detect overflow BEFORE writing the inventory sheet and branch into shard or CSV mode. Shard mode replaces the single "Inventario Completo" sheet with N dynamically-named sheets. CSV mode skips xlsx entirely and returns a `.csv` Path. Both modes propagate warnings through `AuditResult.overflow_warning`, CLI Rich Panel, TUI Label, and Dashboard KPI rows.

## Architecture Decisions

### Decision 1: Constants Location

**Choice**: Define `EXCEL_MAX_ROWS` and `MAX_INVENTORY_ROWS` as module-level constants in `excel_reporter.py`.

| Option | Tradeoff | Decision |
|--------|----------|----------|
| `excel_reporter.py` module scope | Constants co-located with consumer; no cross-module import needed | ✅ Chosen |
| New `reporter/constants.py` | Extra file for 2 constants; over-engineered | ❌ Rejected |
| `api.py` or `cli.py` | Wrong layer — reporter owns Excel limits | ❌ Rejected |

**Rationale**: These constants describe Excel sheet constraints. The reporter is the only consumer. Keep them close to `_write_inventario()`.

### Decision 2: OverflowStrategy Type

**Choice**: String literal `"shard" | "csv"` with `choices` validation in argparse. No enum.

| Option | Tradeoff | Decision |
|--------|----------|----------|
| String literal + argparse `choices` | Consistent with existing `--format` pattern (line 113 of cli.py); simple; no new import | ✅ Chosen |
| `enum.Enum` | Type-safe but adds import + conversion at every layer; existing code uses strings for `format` | ❌ Rejected |

**Rationale**: The project uses `str` for `--format` with `choices=["excel", "html"]`. Follow the established pattern. An enum adds ceremony for zero benefit — argparse already validates.

### Decision 3: SHEET_NAMES Dynamic Architecture

**Choice**: Keep `SHEET_NAMES` as a fixed list for the 7 non-inventory sheets. Build the inventory sheet name(s) dynamically at generation time.

| Option | Tradeoff | Decision |
|--------|----------|----------|
| Fixed list + dynamic inventory | Minimal change to existing code; `SHEET_NAMES[7]` access becomes a method call | ✅ Chosen |
| Fully dynamic SHEET_NAMES | Requires refactoring all `wb[SHEET_NAMES[i]]` references; high risk | ❌ Rejected |
| Replace SHEET_NAMES with a function | Over-engineered; 8 sheets is a stable contract | ❌ Rejected |

**Implementation**:
- `SHEET_NAMES` becomes 7 items (remove "Inventario Completo")
- New method `_inventory_sheet_names(n_records: int) -> list[str]` returns `["Inventario Completo"]` or `["Inventario 1/3", "Inventario 2/3", "Inventario 3/3"]`
- `generate()` creates sheets: 7 fixed + dynamic inventory names
- `_write_inventory_sheets(wb, records)` handles both cases

### Decision 4: Shard Splitting Algorithm

**Choice**: Pure Python slicing in `_write_inventory_sheets()`.

```
N = ceil(len(records) / MAX_INVENTORY_ROWS)  # math.ceil
chunks = [records[i*MAX : (i+1)*MAX] for i in range(N)]
for i, chunk in enumerate(chunks, 1):
    name = f"Inventario {i}/{N}" if N > 1 else "Inventario Completo"
    ws = wb.create_sheet(title=name)
    self._write_inventario_chunk(ws, chunk)  # headers + data + styling
```

**Per-shard**: Same 13 headers, `ws.append()`, autofilter, freeze panes at A2, `_auto_column_width()`. Identical to current `_write_inventario()` but operating on a chunk.

### Decision 5: CSV Writer Architecture

**Choice**: New method `ExcelReporter._generate_csv()` inside `ExcelReporter`. No separate module.

| Option | Tradeoff | Decision |
|--------|----------|----------|
| Method in ExcelReporter | Minimal new code; CSV is only used when Excel overflow triggers | ✅ Chosen |
| New `CsvReporter(BaseReporter)` | Clean separation but CSV is not a standalone format choice — it's an overflow escape hatch | ❌ Rejected |
| Separate `reporter/csv_writer.py` | Over-engineered for ~30 lines of csv.writer code | ❌ Rejected |

**Implementation**:
- `_generate_csv(records, output_path) -> Path`: opens file with UTF-8 BOM prefix (`\xef\xbb\xbf`), writes 13-column header + data rows using `csv.writer`
- `generate()` checks `self.overflow_strategy == "csv"` at entry; if so, delegates to `_generate_csv()` and returns early (no xlsx created)
- Output filename: `{folder}_inventory_{YYYY-MM-DD}.csv` (stem changes from `_audit_` to `_inventory_`)

### Decision 6: Warning Plumbing

**Flow**:
1. `ExcelReporter.generate()` detects overflow → sets `self._overflow_warning: str | None`
2. `generate()` returns `Path` as before; warning stored as instance attribute
3. `api.audit()` reads `reporter._overflow_warning` after `generate()` → sets `AuditResult.overflow_warning`
4. `cli.py` checks `result.overflow_warning` → prints `Panel(warning, style="yellow")`
5. `tui/screens/results.py` checks `results["overflow_warning"]` → renders `Label`
6. Dashboard: `_write_dashboard()` receives `overflow_warning` + `n_shards` as kwargs → writes rows 2-3 conditionally

**Dashboard overflow rows** (only when overflow detected):
- Row 2: `("⚠ OVERFLOW", "Inventario dividido en N hojas (X archivos totales)")`
- Row 3: `("Estrategia", "shard")`
- Standard KPIs shift down by 2 rows

### Decision 7: Parameter Threading

Complete flow:

```
cli.py build_parser()
  └─ add_argument("--overflow-strategy", choices=["shard","csv"], default="shard")

cli.py main()
  └─ ExcelReporter(overflow_strategy=args.overflow_strategy)

ExcelReporter.__init__(overflow_strategy="shard")
  └─ self.overflow_strategy = overflow_strategy

ExcelReporter.generate()
  ├─ if self.overflow_strategy == "csv":
  │     return self._generate_csv(records, output_path)
  └─ self._write_inventory_sheets(wb, records)
       └─ if len(records) > MAX_INVENTORY_ROWS:
              # shard mode: N sheets
          else:
              # single "Inventario Completo"

api.audit(overflow_strategy="shard")
  └─ ExcelReporter(overflow_strategy=overflow_strategy)
  └─ result.overflow_warning = reporter._overflow_warning
```

## Data Flow

```
CLI args ──→ ExcelReporter.__init__(overflow_strategy=)
                  │
                  ▼
            generate(records, analysis, output_path)
                  │
         ┌────────┴────────┐
         │                 │
    csv mode?          shard mode?
         │                 │
    _generate_csv()   _write_inventory_sheets()
         │                 │
         │          ┌──────┴──────┐
         │      ≤MAX_ROWS    >MAX_ROWS
         │          │            │
         │    1 sheet "Inv"   N sheets "Inv i/N"
         │          │            │
         └──────────┴────────────┘
                     │
              set self._overflow_warning
                     │
              return Path (xlsx or csv)
                     │
                     ▼
              api.audit() reads reporter._overflow_warning
                     │
                     ▼
              AuditResult.overflow_warning
                     │
            ┌────────┼────────┐
            │        │        │
         CLI Panel  TUI Label  Dashboard KPIs
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `src/fsaudit/reporter/excel_reporter.py` | Modify | Add constants, `overflow_strategy` param, shard/CSV logic, dashboard overflow rows |
| `src/fsaudit/reporter/base.py` | Modify | Add `overflow_strategy: str = "shard"` kwarg to `generate()` signature |
| `src/fsaudit/api.py` | Modify | Add `overflow_strategy` param to `audit()`, read `reporter._overflow_warning`, add `overflow_warning` field to `AuditResult` |
| `src/fsaudit/cli.py` | Modify | Add `--overflow-strategy` arg, pass to ExcelReporter, print warning Panel |
| `src/fsaudit/tui/models.py` | Modify | Add `overflow_strategy: str = "shard"` to `ScanConfig` |
| `src/fsaudit/tui/screens/results.py` | Modify | Show `overflow_warning` Label when not None |
| `tests/test_excel_overflow.py` | Create | All overflow tests (shard, CSV, dashboard, backward compat) |
| `tests/test_cli.py` | Modify | Add `--overflow-strategy` parsing tests |

## Interfaces / Contracts

```python
# excel_reporter.py
EXCEL_MAX_ROWS: int = 1_048_576
MAX_INVENTORY_ROWS: int = EXCEL_MAX_ROWS - 1  # 1,048,575 data rows

class ExcelReporter(BaseReporter):
    def __init__(self, overflow_strategy: str = "shard") -> None: ...
    def _inventory_sheet_names(self, n_records: int) -> list[str]: ...
    def _write_inventory_sheets(self, wb: Workbook, records: list[FileRecord]) -> int: ...
    def _write_inventario_chunk(self, ws: Worksheet, records: list[FileRecord]) -> None: ...
    def _generate_csv(self, records: list[FileRecord], output_path: Path) -> Path: ...

# api.py
@dataclass
class AuditResult:
    overflow_warning: str | None = None  # NEW FIELD

def audit(..., overflow_strategy: str = "shard") -> AuditResult: ...
```

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit | Shard splitting with small MAX_INVENTORY_ROWS (patch constant to 50) | Create 120 records → expect 3 sheets "Inv 1/3", "Inv 2/3", "Inv 3/3" |
| Unit | Backward compat: < MAX rows → single "Inventario Completo" | Create 30 records → expect 1 inventory sheet, sheetnames length == 8 |
| Unit | CSV output: UTF-8 BOM, 13 columns, all records present | Create 100 records, CSV mode → verify BOM bytes, column count, row count |
| Unit | CSV mode always produces CSV regardless of row count | 10 records + CSV strategy → .csv file, no .xlsx |
| Unit | Dashboard overflow rows present/absent | Patch MAX=50, 120 records → dashboard rows 2-3 populated; 30 records → rows 2-3 empty |
| Unit | Overflow warning string construction | Verify `reporter._overflow_warning` content after generate() |
| Integration | Parameter threading: CLI → api → reporter | Call `audit(path, overflow_strategy="csv")` → verify CSV output |
| E2E | CLI `--overflow-strategy shard` with large dataset | Invoke main() with patched small MAX → verify console Panel output |

**TDD order**: Write all tests in `test_excel_overflow.py` FIRST. Tests will fail. Then implement.

## Migration / Rollout

No migration required. Default `"shard"` with files under 1M rows produces byte-identical output to v0.10.0. Fully backward compatible.

## Open Questions

- [ ] Should `generate()` return `(Path, str | None)` tuple instead of storing warning as instance attribute? (Cleaner but breaks `BaseReporter.generate()` contract)
- [ ] Should CSV mode also produce the xlsx with non-inventory sheets (Dashboard, etc.)? Current spec says "ONLY a CSV file; NO xlsx workbook created"
