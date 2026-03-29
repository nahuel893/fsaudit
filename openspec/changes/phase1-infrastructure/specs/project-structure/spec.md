# Spec: Project Structure — Package Layout and Configuration

**Change**: phase1-infrastructure
**Domain**: project-structure
**Type**: NEW

---

## REQ-PRJ-01: pyproject.toml with PEP 621

The project MUST have a `pyproject.toml` at the repository root following PEP 621 metadata format.

### Scenario PRJ-01a: Valid pyproject.toml

- **Given** the file `pyproject.toml` at the repo root
- **When** parsed by a PEP 621 compliant tool (e.g., `pip install -e .`)
- **Then** the installation MUST succeed without errors

### Scenario PRJ-01b: Python version constraint

- **Given** the `pyproject.toml` `requires-python` field
- **When** inspected
- **Then** it MUST specify `>= 3.10`

### Scenario PRJ-01c: Required dependencies declared

- **Given** the `pyproject.toml` `dependencies` list
- **When** inspected
- **Then** it MUST include: `openpyxl`, `Jinja2`, `PyYAML`

### Scenario PRJ-01d: Dev dependencies declared

- **Given** the `pyproject.toml` optional dependencies or dev group
- **When** inspected
- **Then** it MUST include `pytest` as a development dependency

---

## REQ-PRJ-02: src layout

The project MUST use a src layout with the package at `src/fsaudit/`.

### Scenario PRJ-02a: Root package exists

- **Given** the directory `src/fsaudit/`
- **When** its contents are inspected
- **Then** an `__init__.py` file MUST exist

### Scenario PRJ-02b: Package is importable

- **Given** the package is installed via `pip install -e .`
- **When** `import fsaudit` is executed
- **Then** no `ImportError` SHALL be raised

---

## REQ-PRJ-03: Sub-package structure

The `src/fsaudit/` package MUST contain these sub-packages, each with an `__init__.py`:

- `scanner/`
- `classifier/`
- `analyzer/`
- `reporter/`

### Scenario PRJ-03a: All sub-packages exist

- **Given** the `src/fsaudit/` directory
- **When** its subdirectories are listed
- **Then** `scanner/`, `classifier/`, `analyzer/`, and `reporter/` MUST each exist with an `__init__.py`

### Scenario PRJ-03b: Sub-packages are importable

- **Given** the package is installed
- **When** the following imports are executed:
  - `from fsaudit.scanner import models`
  - `from fsaudit.classifier import __init__`
  - `from fsaudit.analyzer import metrics`
  - `from fsaudit.reporter import __init__`
- **Then** no `ImportError` SHALL be raised for any of them

---

## REQ-PRJ-04: Version string

The root package `src/fsaudit/__init__.py` MUST expose a `__version__` string attribute.

### Scenario PRJ-04a: Version accessible

- **Given** the package is installed
- **When** `from fsaudit import __version__` is executed
- **Then** `__version__` MUST be a non-empty string

---

## REQ-PRJ-05: Test directory structure

A `tests/` directory MUST exist at the repository root with a `conftest.py` file providing shared pytest fixtures.

### Scenario PRJ-05a: conftest.py exists

- **Given** the `tests/` directory
- **When** its contents are inspected
- **Then** a `conftest.py` file MUST be present

### Scenario PRJ-05b: pytest collects without errors

- **Given** the project is installed and `tests/conftest.py` exists
- **When** `pytest --collect-only` is run
- **Then** pytest MUST exit without import errors (0 tests collected is acceptable)

---

## REQ-PRJ-06: Logging configuration module

The system MUST provide a `src/fsaudit/logging_config.py` module with a `setup_logging()` function.

### Scenario PRJ-06a: setup_logging exists

- **Given** the package is installed
- **When** `from fsaudit.logging_config import setup_logging` is executed
- **Then** no `ImportError` SHALL be raised
- **And** `setup_logging` MUST be callable

### Scenario PRJ-06b: setup_logging accepts level parameter

- **Given** the `setup_logging()` function
- **When** called with `level="DEBUG"`
- **Then** it MUST configure logging at the specified level without error

### Scenario PRJ-06c: setup_logging configures console and file handlers

- **Given** `setup_logging()` is called with a log file path
- **When** a log message is emitted
- **Then** the message MUST appear in both the console output and the specified log file
