# Spec: excel-sheets

**Change**: phase1-excel-reporter
**Domain**: excel-sheets
**Status**: draft
**Date**: 2026-03-29

## Overview

Defines the structure, columns, and behavior of the 8 Excel sheets produced by `ExcelReporter`. Each sheet maps to a specific PRD section (Section 10) and draws from `AnalysisResult` and/or `list[FileRecord]`.

## Requirements

### REQ-ES-01: Sheet presence and order

The workbook MUST contain exactly 8 sheets in this order:
1. Dashboard, 2. Por Categoria, 3. Timeline, 4. Top Archivos Pesados, 5. Archivos Inactivos, 6. Alertas, 7. Por Directorio, 8. Inventario Completo.

All sheets MUST exist even when their data source is empty.

### REQ-ES-02: Dashboard sheet

MUST display KPI rows: Total Archivos (`total_files`), Volumen Total (`total_size_bytes` formatted as human-readable), count of active alerts (sum of zero-byte, permission issues, duplicates), and a summary table of files per category from `by_category`.

### REQ-ES-03: Por Categoria sheet

Columns: Categoria, Cantidad, Volumen (bytes), % del Total, Promedio Tamano, Mas Reciente, Mas Antiguo. One row per entry in `by_category`. Source: `AnalysisResult.by_category`.

### REQ-ES-04: Timeline sheet

Columns: Periodo (YYYY-MM), Cantidad. One row per entry in `timeline` dict, sorted chronologically ascending. Source: `AnalysisResult.timeline`.

### REQ-ES-05: Top Archivos Pesados sheet

Columns: Nombre, Ruta, Tamano, Categoria, Ultima Modificacion. Rows from `top_largest` (up to 20). Size MUST be formatted as human-readable (KB/MB/GB). Source: `AnalysisResult.top_largest`.

### REQ-ES-06: Archivos Inactivos sheet

Columns: Nombre, Ruta, Tamano, Categoria, Ultima Modificacion, Dias Inactivo. Source: `AnalysisResult.inactive_files`. Sorted by `days_inactive` descending.

### REQ-ES-07: Alertas sheet

Columns: Tipo Alerta, Nombre, Ruta, Detalle. MUST aggregate 4 alert sources:
- Zero-byte files (type: "0 bytes")
- Permission issues (type: "Permisos: {issue}")
- Duplicate filenames (type: "Duplicado")
- Files with empty extension from `records` (type: "Sin extension")

### REQ-ES-08: Por Directorio sheet

Columns: Directorio, Cantidad Archivos, Volumen Total, Volumen Promedio. Derived from `records` grouped by `parent_dir`. Sorted by Volumen Total descending. SHOULD show top 50 directories.

### REQ-ES-09: Inventario Completo sheet

One row per `FileRecord`. Columns: Ruta, Nombre, Extension, Tamano, Categoria, Fecha Modificacion, Fecha Creacion, Ultimo Acceso, Profundidad, Oculto, Permisos, Directorio Padre. MUST have autofilter enabled on the header row.

### REQ-ES-10: Basic styling

All sheets MUST have: bold header row, frozen first row (freeze panes at row 2), number formatting for byte columns (comma-separated integers or human-readable). Column widths SHOULD be auto-adjusted (capped at 50 characters).

## Scenarios

### SC-ES-01: All 8 sheets present

**Given** any valid call to `ExcelReporter.generate()`
**When** the workbook is opened
**Then** `workbook.sheetnames` equals the 8 names in REQ-ES-01 order

### SC-ES-02: Dashboard KPIs match analysis

**Given** `AnalysisResult` with `total_files=150`, `total_size_bytes=1_073_741_824`
**When** Dashboard sheet is read
**Then** the total files value is 150
**And** the total volume is displayed as human-readable (e.g., "1.00 GB")

### SC-ES-03: Por Categoria rows match by_category

**Given** `by_category` has 3 entries ("Codigo", "Oficina", "Multimedia")
**When** Por Categoria sheet is read
**Then** there are exactly 3 data rows (plus header)
**And** each row has all 7 columns populated

### SC-ES-04: Timeline sorted chronologically

**Given** `timeline` = {"2025-03": 10, "2024-12": 5, "2025-01": 8}
**When** Timeline sheet is read
**Then** rows appear in order: 2024-12, 2025-01, 2025-03

### SC-ES-05: Inventario has autofilter

**Given** a workbook generated with 10 records
**When** the Inventario Completo sheet is inspected
**Then** `sheet.auto_filter.ref` is set and covers all columns

### SC-ES-06: Empty data still produces sheets

**Given** an empty `records` list and default `AnalysisResult()`
**When** the workbook is generated
**Then** all 8 sheets exist with header rows only and zero data rows

### SC-ES-07: Alertas aggregates multiple sources

**Given** `zero_byte_files` has 2 entries, `permission_issues` has 1, `duplicates_by_name` has 1 key with 3 paths, and records contain 1 file with empty extension
**When** Alertas sheet is read
**Then** there are at least 6 data rows (2 zero-byte + 1 permission + 2 duplicate + 1 sin extension)
