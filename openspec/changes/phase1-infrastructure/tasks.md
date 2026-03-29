# Tasks: Phase 1 Infrastructure — Project Foundation

## Phase 1: Project Setup

- [x] 1.1 Create `pyproject.toml` at repo root with PEP 621 metadata, `requires-python = ">=3.10"`, deps (openpyxl, Jinja2, PyYAML), dev deps (pytest, pytest-cov), setuptools build backend, and `[tool.setuptools.packages.find] where = ["src"]`
- [x] 1.2 Create `src/fsaudit/__init__.py` with `__version__ = "0.1.0"`
- [x] 1.3 Create empty `__init__.py` in: `src/fsaudit/scanner/`, `src/fsaudit/classifier/`, `src/fsaudit/analyzer/`, `src/fsaudit/reporter/`
- [x] 1.4 Create `tests/__init__.py` (empty)

## Phase 2: Data Models

- [x] 2.1 Create `src/fsaudit/scanner/models.py` with `FileRecord` frozen dataclass (12 fields per design: path, name, extension, size_bytes, mtime, creation_time, atime, depth, is_hidden, permissions, category, parent_dir)
- [x] 2.2 Add `DirectoryRecord` frozen dataclass to `models.py` (path, depth, is_hidden)
- [x] 2.3 Add `ScanResult` frozen dataclass to `models.py` (files, directories, root_path, errors with `field(default_factory=list)`)
- [x] 2.4 Create `src/fsaudit/analyzer/metrics.py` with `AnalysisResult` dataclass stub (total_files, total_size_bytes, by_category, top_largest, inactive_files, zero_byte_files, empty_directories, duplicates_by_name, timeline, permission_issues)

## Phase 3: Configuration

- [x] 3.1 Create `src/fsaudit/classifier/categories.yaml` with 8 categories (Oficina, Codigo, Multimedia, Datos, Comprimidos, Ejecutables, Sistema, SinExtension), compound extensions under `compound_extensions` key for Comprimidos, and `match: no_extension` for SinExtension
- [x] 3.2 Create `src/fsaudit/logging_config.py` with `setup_logging(level, log_file)` — configure `fsaudit` logger with console handler (always) and file handler (optional), format: `%(asctime)s [%(levelname)s] %(name)s: %(message)s`

## Phase 4: Test Scaffolding

- [x] 4.1 Create `tests/conftest.py` with shared fixtures: `sample_file_record` (valid FileRecord), `sample_scan_result` (ScanResult with test data), `tmp_tree` (tmp_path-based directory tree for filesystem tests)
- [x] 4.2 Create `tests/test_models.py` — tests for FileRecord creation, immutability (FrozenInstanceError), no-extension case, None permissions; DirectoryRecord creation; ScanResult with populated and empty lists
- [x] 4.3 Create `tests/test_categories.py` — load YAML, verify 8 categories, all PRD extensions present, dot prefix, lowercase, compound extensions exist, no duplicates across categories
- [x] 4.4 Create `tests/test_logging.py` — verify `setup_logging()` returns logger, accepts level param, creates console handler, writes to file when log_file provided
- [x] 4.5 Verify `pip install -e .` succeeds and all imports resolve (`fsaudit`, `fsaudit.scanner.models`, `fsaudit.analyzer.metrics`, `fsaudit.logging_config`)
