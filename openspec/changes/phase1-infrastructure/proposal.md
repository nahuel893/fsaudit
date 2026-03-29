# Proposal: Phase 1 Infrastructure — Project Foundation

## Intent

FSAudit has no code yet — only a PRD. Every subsequent module (Scanner, Classifier, Analyzer, Reporter) depends on a well-defined project skeleton, shared data contracts, and a category mapping file. This change bootstraps the repository so that all Phase 1 implementation work can proceed against a stable foundation with clear interfaces.

## Scope

### In Scope

- `pyproject.toml` with src layout, Python 3.10+ requirement, and all MVP dependencies (openpyxl, Jinja2, PyYAML, pytest)
- `src/fsaudit/` package with `__init__.py` and sub-packages: `scanner/`, `classifier/`, `analyzer/`, `reporter/`
- `FileRecord` dataclass in `src/fsaudit/scanner/models.py` matching PRD section 8.1 (all 12 fields)
- `DirectoryRecord` dataclass for tracking empty directories (path, depth, is_hidden)
- `ScanResult` container type holding `List[FileRecord]` + `List[DirectoryRecord]`
- `AnalysisResult` dataclass stub in `src/fsaudit/analyzer/metrics.py`
- `categories.yaml` in `src/fsaudit/classifier/` with all 8 PRD categories including compound extensions (.tar.gz, .tar.bz2)
- Basic logging configuration in `src/fsaudit/logging_config.py` (configurable level, file + console handlers)
- `tests/` directory with `conftest.py` (shared fixtures)
- Empty `__init__.py` files in every package for proper imports

### Out of Scope

- Scanner, Classifier, Analyzer, Reporter implementation logic
- CLI entry point (`argparse` setup)
- Any report generation (Excel, HTML, JSON)
- Platform-specific utilities (`get_creation_time_safe`, `is_hidden`)
- Test implementations beyond conftest scaffolding

## Approach

Use a PEP 621 `pyproject.toml` with src layout (`src/fsaudit/`). Define all data contracts as frozen dataclasses with full type hints. The `categories.yaml` follows the PRD mapping exactly, with compound extensions listed before single extensions to support longest-match lookup. Logging uses stdlib `logging` with a `setup_logging()` function accepting level and output path. No framework dependencies — pure Python foundation.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `pyproject.toml` | New | Project metadata, dependencies, Python version constraint |
| `src/fsaudit/__init__.py` | New | Root package, version string |
| `src/fsaudit/scanner/models.py` | New | FileRecord, DirectoryRecord, ScanResult dataclasses |
| `src/fsaudit/analyzer/metrics.py` | New | AnalysisResult dataclass stub |
| `src/fsaudit/classifier/categories.yaml` | New | Extension-to-category mapping (8 categories) |
| `src/fsaudit/logging_config.py` | New | Logging setup function |
| `src/fsaudit/scanner/__init__.py` | New | Scanner package init |
| `src/fsaudit/classifier/__init__.py` | New | Classifier package init |
| `src/fsaudit/analyzer/__init__.py` | New | Analyzer package init |
| `src/fsaudit/reporter/__init__.py` | New | Reporter package init |
| `tests/conftest.py` | New | Shared pytest fixtures |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| FileRecord fields don't match actual stat() output on all platforms | Low | Fields match PRD 8.1 and use Optional types where OS-dependent (permissions) |
| categories.yaml compound extension matching needs special handling | Medium | Document that classifier must implement longest-match; include .tar.gz entries explicitly |
| Dataclass frozen=True prevents mutation during pipeline | Low | Pipeline stages create new instances; frozen enforces immutability by design |

## Rollback Plan

This is a greenfield change (no existing code). Rollback = delete `src/`, `tests/`, and `pyproject.toml`. Since this is the first code in the repo, a simple `git revert` of the implementing commit(s) is sufficient.

## Dependencies

- Python 3.10+ installed on development machine
- No prior code exists — this is the first change

## Success Criteria

- [ ] `pip install -e .` succeeds from repo root
- [ ] `python -c "from fsaudit.scanner.models import FileRecord"` imports without error
- [ ] `python -c "from fsaudit.analyzer.metrics import AnalysisResult"` imports without error
- [ ] `categories.yaml` loads via PyYAML and contains all 8 PRD categories
- [ ] `pytest` runs (even with 0 tests collected) without import errors
- [ ] All dataclass fields match PRD section 8.1 types exactly
- [ ] Logging config produces output to both console and file
