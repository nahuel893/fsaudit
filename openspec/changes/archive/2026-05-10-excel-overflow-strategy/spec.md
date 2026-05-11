# Specification: excel-overflow-strategy

## Purpose

Prevent silent data loss when Excel inventory rows exceed the 1,048,576-row limit. Introduce an `--overflow-strategy` CLI flag with `shard` (default) and `csv` modes, plus warning infrastructure across CLI, TUI, and Dashboard.

## Requirements

### REQ-01: Overflow Strategy Parameter

| Aspect | Detail |
|--------|--------|
| CLI flag | `--overflow-strategy` with `choices=["shard", "csv"]`, default `"shard"` |
| Invalid value | MUST raise `SystemExit` with descriptive error message |
| Constants | `EXCEL_MAX_ROWS = 1_048_576`; `MAX_INVENTORY_ROWS = EXCEL_MAX_ROWS - 1` (data rows only) |
| Threading | CLI `→` `api.audit(overflow_strategy=…) → ExcelReporter.__init__(overflow_strategy=…) → _write_inventario` |
| Default | `"shard"` at every layer |

#### Scenario: SC-05 — Invalid strategy value

- GIVEN a CLI invocation with `--overflow-strategy sqlite`
- WHEN the argument parser processes the flag
- THEN the program MUST exit with `SystemExit` and an error message containing the invalid value

### REQ-02: Shard Mode

| Aspect | Detail |
|--------|--------|
| Trigger | `len(records) > MAX_INVENTORY_ROWS` |
| Sheet naming | `"Inventario {i}/{N}"` for i in 1..N, where N = `ceil(len / MAX_INVENTORY_ROWS)` |
| Per-shard structure | Same 13-column headers, autofilter, freeze panes at A2, column widths |
| No overflow | Sheet name remains `"Inventario Completo"` — output byte-identical to v0.10.0 |
| SHEET_NAMES | MUST accommodate dynamic shard count (no longer fixed-length list) |
| Dashboard | 2 extra KPI rows after title: overflow warning + shard count |

#### Scenario: SC-01 — Sub-limit files, shard strategy (backward compat)

- GIVEN `len(records) < MAX_INVENTORY_ROWS` and `overflow_strategy="shard"`
- WHEN the Excel report is generated
- THEN the workbook MUST contain exactly one sheet named `"Inventario Completo"` with content identical to v0.10.0 output

#### Scenario: SC-02 — Overflow files, shard strategy

- GIVEN `len(records) > MAX_INVENTORY_ROWS` and `overflow_strategy="shard"`
- WHEN the Excel report is generated
- THEN the workbook MUST contain N sheets named `"Inventario 1/N"` through `"Inventario N/N"`; each shard MUST contain ≤ `MAX_INVENTORY_ROWS` data rows plus one header row

#### Scenario: SC-06 — Shard mode dashboard overflow rows

- GIVEN overflow is triggered in shard mode
- WHEN the Dashboard sheet is written
- THEN rows 2–3 MUST contain: `("⚠ OVERFLOW", "Inventario dividido en N hojas (X archivos totales)")` and `("Estrategia", "shard")`

#### Scenario: SC-07 — No overflow, no extra dashboard rows

- GIVEN `len(records) ≤ MAX_INVENTORY_ROWS`
- WHEN the Dashboard sheet is written
- THEN NO overflow or strategy rows MUST appear (backward compatible)

### REQ-03: CSV Mode

| Aspect | Detail |
|--------|--------|
| Output | ONLY a CSV file; NO xlsx workbook created |
| Filename | `{folder_name}_inventory_{YYYY-MM-DD}.csv` |
| Columns | Same 13 columns as Inventario Completo |
| Encoding | UTF-8 with BOM (prefix `\xef\xbb\xbf`) |
| Writer | Python stdlib `csv.writer` |
| api.audit() return | `AuditResult.report_path` points to the CSV file |

#### Scenario: SC-03 — Overflow files, CSV strategy

- GIVEN `len(records) > MAX_INVENTORY_ROWS` and `overflow_strategy="csv"`
- WHEN the audit completes
- THEN a CSV file MUST exist at `report_path`; NO `.xlsx` file MUST be created; the CSV MUST contain all records with UTF-8 BOM prefix

#### Scenario: SC-04 — Sub-limit files, CSV strategy

- GIVEN `len(records) < MAX_INVENTORY_ROWS` and `overflow_strategy="csv"`
- WHEN the audit completes
- THEN a CSV file MUST be generated (CSV mode always produces CSV regardless of row count)

#### Scenario: SC-10 — CSV file format validation

- GIVEN a CSV output file from any overflow strategy run
- WHEN the file is read
- THEN the first 3 bytes MUST be `\xef\xbb\xbf` (UTF-8 BOM); the header row MUST contain exactly 13 column names matching the Inventario Completo headers

### REQ-04: Warnings — CLI

| Aspect | Detail |
|--------|--------|
| Style | `rich.panel.Panel` with yellow/red styling |
| Shard message | File count, shard count, strategy name |
| CSV message | File count, output CSV path, strategy name |
| Trigger | Any overflow condition (records > MAX_INVENTORY_ROWS) OR csv mode active |

#### Scenario: SC-08 — CLI warning panel on overflow

- GIVEN records exceed `MAX_INVENTORY_ROWS` and `overflow_strategy="shard"`
- WHEN the CLI pipeline completes reporting
- THEN a `Panel` MUST be printed to console containing the shard count and total file count

### REQ-05: Warnings — TUI

| Aspect | Detail |
|--------|--------|
| `AuditResult.overflow_warning` | `str \| None` field; populated when overflow triggered |
| `ScanConfig.overflow_strategy` | `str` field; default `"shard"` |
| Config screen | Dropdown/select for overflow strategy |
| Results screen | `Label` displaying `overflow_warning` when not `None` |

#### Scenario: SC-09 — TUI results screen overflow warning

- GIVEN `AuditResult.overflow_warning` is not `None`
- WHEN `ResultsScreen` is composed
- THEN a `Label` MUST display `overflow_warning` text

### REQ-06: Warnings — Dashboard

| Aspect | Detail |
|--------|--------|
| Position | Rows 2–3 (after title row at row 1) |
| Row 2 | `⚠ OVERFLOW` label + `"Inventario dividido en N hojas (X archivos totales)"` |
| Row 3 | `Estrategia` label + strategy value (`"shard"` or `"csv"`) |
| No overflow | No extra rows — KPIs start at row 2 as in v0.10.0 |

(Covered by SC-06 and SC-07.)

### REQ-07: API Changes

| Component | Change |
|-----------|--------|
| `api.audit()` | New param `overflow_strategy: str = "shard"` |
| `AuditResult` | New field `overflow_warning: str \| None = None` |
| `api.scan()` | Unchanged |
| `BaseReporter.generate()` | New optional kwarg `overflow_strategy: str = "shard"` |
| `ExcelReporter.__init__()` | New param `overflow_strategy: str = "shard"` |

## Out of Scope

- `db` overflow strategy (separate change)
- HTML report overflow handling (already has `max_rows=500`)
- Scanner, Classifier, Analyzer module changes
- Security sheet overflow (unlikely to exceed 1M rows)
- Alertas / Archivos Inactivos sheet overflow (secondary risk, deferred)
