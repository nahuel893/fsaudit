# Spec: Classifier Module

**Change**: phase1-classifier
**Domain**: classifier
**Date**: 2026-03-29
**PRD refs**: RF-06, RF-07, RF-08

---

## REQ-CL-01: YAML Loading and Parsing

The module MUST load `categories.yaml` from the classifier package directory and parse it into internal lookup structures. If the file is missing, it MUST raise `FileNotFoundError` with the attempted path. If the YAML is malformed or missing the `categories` key, it MUST raise `ValueError` with a descriptive message.

### Scenario CL-01.1: Successful load

> **Given** a valid `categories.yaml` exists in the classifier package directory
> **When** `classify()` is called
> **Then** the YAML is parsed without error and all categories are available for lookup

### Scenario CL-01.2: Missing YAML file

> **Given** the `categories.yaml` file does not exist at the expected path
> **When** `classify()` is called
> **Then** a `FileNotFoundError` is raised containing the file path

### Scenario CL-01.3: Malformed YAML

> **Given** a `categories.yaml` that is valid YAML but lacks the `categories` key
> **When** `classify()` is called
> **Then** a `ValueError` is raised with a message indicating the missing key

---

## REQ-CL-02: Simple Extension Mapping

The module MUST map single extensions (e.g., `.pdf`, `.py`) to their configured category. Extension matching MUST be case-insensitive: all extensions SHALL be normalized to lowercase before lookup.

### Scenario CL-02.1: Known simple extension

> **Given** a `FileRecord` with `extension=".pdf"`
> **When** `classify()` processes it
> **Then** the returned record has `category="Oficina"`

### Scenario CL-02.2: Case insensitivity

> **Given** a `FileRecord` with `extension=".PDF"` (uppercase)
> **When** `classify()` processes it
> **Then** the returned record has `category="Oficina"`

---

## REQ-CL-03: Compound Extension Handling

The module MUST support compound extensions (e.g., `.tar.gz`, `.tar.bz2`) listed under `compound_extensions` in YAML. Compound extensions MUST be checked before simple extensions using longest-suffix match against the filename.

### Scenario CL-03.1: Compound extension match

> **Given** a `FileRecord` with `name="archive.tar.gz"` and `extension=".gz"`
> **When** `classify()` processes it
> **Then** the returned record has `category="Comprimidos"` (matched via `.tar.gz`, not `.gz`)

### Scenario CL-03.2: Simple extension when no compound matches

> **Given** a `FileRecord` with `name="data.gz"` and `extension=".gz"`
> **When** `classify()` processes it
> **Then** the returned record has `category="Comprimidos"` (matched via simple `.gz`)

### Scenario CL-03.3: Multi-dot filename without compound match

> **Given** a `FileRecord` with `name="my.backup.zip"` and `extension=".zip"`
> **When** `classify()` processes it
> **Then** the returned record has `category="Comprimidos"` (no compound `.backup.zip` exists; falls through to simple `.zip`)

---

## REQ-CL-04: No-Extension Files

Files with an empty extension (`extension=""`) MUST be classified using the `match: no_extension` rule in YAML. Per current config, this maps to category `"SinExtension"`.

### Scenario CL-04.1: File without extension

> **Given** a `FileRecord` with `name="Makefile"` and `extension=""`
> **When** `classify()` processes it
> **Then** the returned record has `category="SinExtension"`

---

## REQ-CL-05: Unknown Extension Fallback

Any file whose extension does not match any YAML entry and is not empty MUST receive `category="Desconocido"`.

### Scenario CL-05.1: Unrecognized extension

> **Given** a `FileRecord` with `extension=".xyz123"`
> **When** `classify()` processes it
> **Then** the returned record has `category="Desconocido"`

---

## REQ-CL-06: Frozen FileRecord Constraint

`FileRecord` is `frozen=True`. The module MUST NOT mutate records. It MUST use `dataclasses.replace(record, category=...)` to produce new instances.

### Scenario CL-06.1: Original record unchanged

> **Given** a list containing one `FileRecord` with `category="Unclassified"`
> **When** `classify()` returns a new list
> **Then** the original record still has `category="Unclassified"` and the returned record has the resolved category

---

## REQ-CL-07: Function Signature and Statelessness

The public function MUST have the signature `classify(files: list[FileRecord]) -> list[FileRecord]`. It MUST be stateless with no side effects (no globals, no caching between calls, no I/O beyond reading `categories.yaml`).

### Scenario CL-07.1: Empty input

> **Given** an empty list `[]`
> **When** `classify([])` is called
> **Then** it returns an empty list `[]`

### Scenario CL-07.2: Mixed input

> **Given** a list with records having extensions `.py`, `.tar.gz`, `""`, and `.xyz`
> **When** `classify()` processes them
> **Then** the returned list has categories `["Codigo", "Comprimidos", "SinExtension", "Desconocido"]` respectively, preserving input order

### Scenario CL-07.3: Output length matches input

> **Given** a list of N `FileRecord` instances
> **When** `classify()` returns
> **Then** the returned list has exactly N elements
