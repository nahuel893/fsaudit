## Task Breakdown: excel-overflow-strategy

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~450 (code + tests) |
| 400-line budget risk | Medium |
| Chained PRs recommended | Yes |
| Suggested split | PR 1 (Shard core) → PR 2 (CSV + Plumbing + Warnings) |
| Delivery strategy | exception-ok |
| Chain strategy | feature-branch-chain |

Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: feature-branch-chain
400-line budget risk: Medium

### Suggested Work Units

| Unit | Goal | Likely PR | Notes |
|------|------|-----------|-------|
| 1 | Shard mode: constants, splitting, dashboard rows, backward compat | PR 1 | base=feature/overflow-strategy; tests included |
| 2 | CSV mode + parameter threading + CLI/TUI warnings | PR 2 | base=PR 1 branch; plumbing + UX |

---

## Phase 1: Constants & Types (foundation)

- [x] T01: Add `EXCEL_MAX_ROWS` and `MAX_INVENTORY_ROWS` constants
- [x] T02: Add `overflow_warning: str | None = None` to `AuditResult`
- [x] T03: Add `overflow_strategy: str = "shard"` to `ExcelReporter.__init__()`

## Phase 2: Shard Mode (core feature)

- [x] T04: Write tests for `_inventory_sheet_names()` — patch `MAX_INVENTORY_ROWS=50`
- [x] T05: Implement `_inventory_sheet_names(n_records: int) -> list[str]`
- [x] T06: Write tests for `_write_inventory_sheets()` — patch `MAX_INVENTORY_ROWS=50`
- [x] T07: Implement `_write_inventory_sheets(wb, records) -> int`
- [x] T08: Write tests for `_write_inventario_chunk()` per-shard structure
- [x] T09: Implement `_write_inventario_chunk(ws, records)` — extract from existing `_write_inventario()`
- [x] T10: Modify `generate()` to use `_write_inventory_sheets()` + dynamic sheet creation
- [x] T11: Write tests for dashboard overflow rows — patch `MAX_INVENTORY_ROWS=50`
- [x] T12: Implement dashboard overflow rows in `_write_dashboard()`
- [x] T13: Backward compatibility test — generate report with 30 records, verify identical output

## Phase 3: CSV Mode (second strategy)

- [x] T14: Write tests for CSV output — BOM, columns, no xlsx
- [x] T15: Write test for CSV filename format
- [x] T16: Implement `_generate_csv()` in `ExcelReporter`
- [x] T17: Modify `generate()` for CSV branch

## Phase 4: Parameter Threading (plumbing)

- [x] T18: Add `overflow_strategy` to `api.audit()`
- [x] T19: Add `overflow_warning` propagation in `api.audit()`
- [x] T20: Add `overflow_strategy` kwarg to `BaseReporter.generate()`
- [x] T21: Add `--overflow-strategy` CLI argument
- [x] T22: Wire `overflow_strategy` through `cli.py main()` → `ExcelReporter()`

## Phase 5: Warning Infrastructure (UX)

- [x] T23: CLI Rich Panel warning on overflow
- [x] T24: TUI `ScanConfig` — add `overflow_strategy` field
- [x] T25: TUI config screen — overflow strategy dropdown
- [x] T26: TUI results screen — overflow warning Label

## Phase 6: Integration & Polish

- [x] T27: Update existing tests checking `sheetnames` length (verified — already passing)
- [x] T28: End-to-end test — CLI `--overflow-strategy shard` with patched small MAX
- [x] T29: End-to-end test — CLI `--overflow-strategy csv` with patched small MAX

---

## Implementation Order

**PR 1 — Shard Core (T01–T13)**: Constants, shard splitting, dashboard rows, backward compat. Self-contained, tests verify everything. No plumbing changes needed yet.

**PR 2 — CSV + Plumbing + Warnings (T14–T29)**: CSV mode, parameter threading through CLI/API, Rich Panel + TUI warnings, integration tests. Depends on PR 1 for constants and `_write_inventario_chunk()`.

## Review Workload Forecast
- Estimated changed lines: ~450
- 400-line budget risk: Medium
- Chained PRs recommended: Yes
- Delivery strategy: exception-ok
- Decision needed before apply: No
- Suggested work-unit PR split: PR 1 (Shard core, ~200 lines) → PR 2 (CSV + Plumbing + UX, ~250 lines)

ALL TASKS COMPLETE (T01-T29).
