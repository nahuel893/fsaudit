# Proposal: phase1-classifier

**Status**: proposed
**Date**: 2026-03-29
**Phase**: 1 — MVP, Step 3 of 6

---

## Intent

Implement the Classifier module that maps file extensions to semantic categories, filling the `category` field on every `FileRecord` produced by the Scanner. This is the third pipeline stage (Scanner -> **Classifier** -> Analyzer).

## Problem

Scanner outputs `FileRecord` instances with `category="Unclassified"`. The downstream Analyzer needs categorized records to compute per-category KPIs (RF-09 through RF-16). Without the Classifier, no meaningful analysis is possible.

## Approach

- **Single public function** `classify(files: list[FileRecord]) -> list[FileRecord]` — stateless, pure transform
- **YAML-driven mapping** — load `categories.yaml` (already exists) at call time; build two lookup dicts:
  - `compound_ext_map`: longest-match for `.tar.gz`, `.tar.bz2`, etc.
  - `simple_ext_map`: single-extension lookup (`.py` -> `Codigo`)
- **Lookup order**: compound extensions first (longest match), then simple extension, then `no_extension` rule, then fallback `"Desconocido"`
- **Frozen dataclass constraint**: `FileRecord` is `frozen=True`, so use `dataclasses.replace(record, category=matched)` to produce new instances
- **Case insensitive**: extensions already lowercase from Scanner; YAML entries also lowercase

## Scope

| In scope | Out of scope |
|----------|-------------|
| `classify()` public function | Sub-category support (Phase 2) |
| YAML loading + extension map building | Modifying `categories.yaml` schema |
| Compound extension longest-match | Content-based classification |
| `no_extension` and `Desconocido` fallback | Any mutation of Scanner output |
| Unit tests (pytest, >= 80% coverage) | Integration with CLI or Analyzer |

## Affected Modules

| Module | Change |
|--------|--------|
| `src/fsaudit/classifier/classifier.py` | **New** — core logic |
| `src/fsaudit/classifier/__init__.py` | Export `classify` |
| `src/fsaudit/classifier/categories.yaml` | **Read only** — no changes |
| `tests/test_classifier.py` | **New** — unit tests |

## Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Compound extension matching misses edge cases (e.g., `file.backup.tar.gz`) | Medium | Check suffixes from right, longest first; test with multi-dot filenames |
| YAML file missing or malformed at runtime | Low | Raise clear `FileNotFoundError` / `ValueError` with path context |

## Rollback Plan

The Classifier is a new, isolated module with no side effects on existing code. Rollback = delete `classifier.py` and `test_classifier.py`, revert `__init__.py` to empty. No other modules are modified.

## Budget

- Implementation: ~80 LOC (classifier.py)
- Tests: ~100 LOC (test_classifier.py)
- Estimated effort: single session
