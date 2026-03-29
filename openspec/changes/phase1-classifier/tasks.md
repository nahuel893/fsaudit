# Tasks: phase1-classifier

**Change**: phase1-classifier
**Date**: 2026-03-29
**Depends on**: spec, design

---

## Phase 1 — Infrastructure

- [x] **1.1** Create `src/fsaudit/classifier/classifier.py` with module docstring and imports (`pathlib.Path`, `dataclasses.replace`, `yaml`, `FileRecord` from `fsaudit.scanner.models`)
- [x] **1.2** Update `src/fsaudit/classifier/__init__.py` to export `classify` and `load_categories`
- [x] **1.3** Create `tests/test_classifier.py` with imports, `FileRecord` factory helper, and `tmp_path` YAML fixtures (valid, missing-key, empty)

## Phase 2 — Implementation

- [x] **2.1** Implement `load_categories(path)` in `classifier.py`:
  - Default path via `Path(__file__).parent / "categories.yaml"`
  - Parse YAML, raise `FileNotFoundError` (with path) or `ValueError` (missing `categories` key)
  - Build and return `(compound_ext_map, simple_ext_map, no_ext_category)` tuple
  - Compound keys sorted by length descending for longest-match
  - Extract `no_extension` match rule -> `no_ext_category` string

- [x] **2.2** Implement `classify(records, categories_path=None)` in `classifier.py`:
  - Call `load_categories` once
  - For each record: compound `name.endswith()` check (longest first) -> simple `extension` lookup -> no-extension rule -> `"Desconocido"` fallback
  - Produce new records via `dataclasses.replace(record, category=matched)`
  - Return new list preserving input order

## Phase 3 — Testing

- [x] **3.1** Tests for `load_categories`: valid YAML produces correct dicts (CL-01.1), missing file raises `FileNotFoundError` (CL-01.2), malformed YAML raises `ValueError` (CL-01.3)
- [x] **3.2** Tests for simple extension mapping: known ext `.pdf` -> `"Oficina"` (CL-02.1), uppercase `.PDF` -> case-insensitive match (CL-02.2)
- [x] **3.3** Tests for compound extensions: `archive.tar.gz` -> `"Comprimidos"` (CL-03.1), `data.gz` falls to simple (CL-03.2), `my.backup.zip` no false compound match (CL-03.3)
- [x] **3.4** Tests for edge cases: no-extension `Makefile` -> `"SinExtension"` (CL-04.1), unknown `.xyz123` -> `"Desconocido"` (CL-05.1), empty list -> empty result (CL-07.1)
- [x] **3.5** Tests for invariants: frozen record unchanged after classify (CL-06.1), output length == input length (CL-07.3), mixed input order preserved (CL-07.2)
