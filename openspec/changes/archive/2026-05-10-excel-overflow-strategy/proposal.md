# Proposal: excel-overflow-strategy

## Intent

Prevent silent data loss when scanning large filesystems. The "Inventario Completo" sheet in Excel reports uses `ws.append()` which openpyxl does NOT validate — rows beyond Excel's 1,048,576 hard limit are written, file saves successfully, but Excel/LibreOffice silently truncates them. Users scanning 1M+ files get truncated reports with no warning. This change adds two overflow strategies so users can choose between automatic sharding or CSV output.

## Scope

### In Scope
- `--overflow-strategy` CLI arg: `shard` (default) | `csv`
- Shard mode: split "Inventario Completo" into "Inventario 1/N"…"Inventario N/N" when rows > MAX_INVENTORY_ROWS (1,048,575)
- CSV mode: generate only a CSV file with full inventory, no xlsx at all
- Dashboard overflow notice (2 extra KPI rows per shard warning)
- CLI Rich console warning when overflow is triggered
- TUI results-screen notification when overflow was triggered
- Constants: `EXCEL_MAX_ROWS = 1_048_576`, `MAX_INVENTORY_ROWS = EXCEL_MAX_ROWS - 1`
- Thread parameter through: CLI → api.audit() → ExcelReporter
- Strict TDD: all tests written FIRST

### Out of Scope
- `db` strategy (separate change)
- HTML report overflow handling (already has `max_rows=500`)
- Scanner, Classifier, Analyzer modules (no changes needed)
- Security sheet overflow (deferred — unlikely to hit 1M rows)

## Capabilities

### New Capabilities
- `excel-overflow-strategy`: CLI flag and parameter threading through audit pipeline; warning infrastructure (CLI console + TUI + dashboard)
- `excel-shard-mode`: sheet splitting with N-shard naming convention, per-shard headers/autofilter/freeze-panes/column-widths, dashboard overflow KPI rows
- `excel-csv-mode`: CSV-only output with UTF-8 BOM, naming `{folder}_inventory_{YYYY-MM-DD}.csv`, 13-column inventory fields

### Modified Capabilities
- None — no existing specs to modify

## Approach

**Parameter threading**: `--overflow-strategy` parsed in `cli.py` → passed to `api.audit(overflow_strategy=…)` → stored in `RepoConfig` → `ExcelReporter.__init__()` receives it. Default: `"shard"`.

**Shard logic** (`ExcelReporter._write_inventario`):
1. Check `len(records) > MAX_INVENTORY_ROWS` BEFORE writing
2. If overflow: calculate shard count = `ceil(len(records) / MAX_INVENTORY_ROWS)`
3. Replace single "Inventario Completo" sheet with N sheets named "Inventario 1/N", "Inventario 2/N", etc.
4. Dashboard gets 2 extra rows: total files + shard count
5. Each shard: same headers (row 1), autofilter, freeze panes (A2), column widths
6. If no overflow: sheet stays "Inventario Completo" — backward compatible

**CSV logic**: `ExcelReporter.generate()` skips xlsx entirely. Uses `csv.writer` with UTF-8-BOM, writes 13-column inventory. Returns `Path` to CSV file. Output path stem changed to `{folder}_inventory_{date}`.

**Warnings** (all modes on overflow):
- CLI: `console.print(rich.warning panel)` with file count + strategy
- TUI: set `overflow_warning` in `AuditResult`, `ResultsScreen` renders a Label
- Dashboard: 2 KPI rows at top of sheet (row 2-3) with warning message + shard info

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `src/fsaudit/cli.py` | Modified | Add `--overflow-strategy` arg, console warning logic |
| `src/fsaudit/api.py` | Modified | Add param to `audit()`, `AuditResult.overflow_warning` field |
| `src/fsaudit/reporter/excel_reporter.py` | Modified | Accept strategy, shard logic, CSV fallback, dashboard KPI |
| `src/fsaudit/reporter/base.py` | Modified | Optional `overflow_strategy` param on `generate()` |
| `src/fsaudit/tui/models.py` | Modified | `ScanConfig.overflow_strategy` field |
| `src/fsaudit/tui/screens/config.py` | Modified | UI for strategy selection |
| `src/fsaudit/tui/screens/results.py` | Modified | Overflow warning display |
| `tests/test_excel_reporter.py` | Modified | Test shard splitting, CSV output, backward compat |
| `tests/test_cli.py` | Modified | Test `--overflow-strategy` parsing |
| `tests/test_tui.py` | New | TUI overflow strategy tests |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Existing test assertions on `sheetnames` length break | High | Update tests to handle 8+N-1 sheets; backward compat when no overflow |
| CSV mode changes output file extension breaks downstream tooling | Low | Document naming convention; separate `output_path` stem logic |
| Shard performance degrades with 10+ shards | Low | Python slicing is O(n); Excel write is the bottleneck, not split logic |
| TUI Textual widget sizing for overflow warning label | Med | Use `Label` with auto-wrapping; test with long messages |

## Rollback Plan

Revert `--overflow-strategy` default to `"shard"` (always backward-compatible — files under 1M rows produce identical output). If CSV mode causes issues, deprecate flag. All logic is additive behind the strategy guard; removing the parameter removes all new behavior.

## Dependencies

- openpyxl >= 3.1 (already installed)
- No new packages needed

## Success Criteria

- [ ] `--overflow-strategy shard` splits 2M records into 2+ sheets with identical structure
- [ ] `--overflow-strategy csv` produces a valid CSV with UTF-8-BOM, 13 columns, no xlsx
- [ ] Files under 1M rows produce identical output (backward compatible)
- [ ] CLI warning displayed on overflow in both modes
- [ ] 175 existing tests remain green; new tests pass first
- [ ] TUI shows overflow warning in results screen
