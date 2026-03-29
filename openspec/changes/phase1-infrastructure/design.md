# Design: Phase 1 Infrastructure — Project Foundation

## Technical Approach

Bootstrap fsaudit as a PEP 621 src-layout package with frozen dataclasses as inter-module contracts. All data models defined upfront so Scanner, Classifier, Analyzer, and Reporter phases can develop in parallel against stable interfaces. `categories.yaml` uses a longest-match-first structure for compound extensions.

## Architecture Decisions

| # | Decision | Choice | Alternatives Rejected | Rationale |
|---|----------|--------|-----------------------|-----------|
| 1 | Data contracts | `@dataclass(frozen=True)` | Pydantic, TypedDict, NamedTuple | Performance at 100k+ instances; no validation overhead needed (data comes from OS, not user input). Frozen enforces pipeline immutability. |
| 2 | Project layout | src layout + `pyproject.toml` (PEP 621) | flat layout, setup.py, requirements.txt | Prevents accidental local imports during dev. Modern standard. `pip install -e .` for dev. |
| 3 | Filesystem traversal | `os.walk()` | `pathlib.rglob()`, `scandir` | Better control for directory exclusion (prune `dirs` in-place). Built-in symlink control via `followlinks=False`. `os.walk` already uses `scandir` internally since Python 3.5. |
| 4 | CLI framework | `argparse` (stdlib) | click, typer | Sufficient for Phase 1 flags. Zero dependencies. Upgrade path to typer exists for Phase 2 if needed. |
| 5 | Category default | `"Unclassified"` for unknown extensions | `"Desconocido"`, `"Unknown"` | English codebase convention. PRD says "Desconocido" but code identifiers should be English. Reports can localize display labels later. |
| 6 | Hidden file detection (Windows) | `os.stat().st_file_attributes & FILE_ATTRIBUTE_HIDDEN` | `ctypes` + `GetFileAttributesW` | Simpler, no ctypes import. Available on Python 3.x Windows. `stat_result.st_file_attributes` is Windows-only attr; guarded by `hasattr` check. |
| 7 | Timestamp types | `datetime` (from `datetime` module) | `float` (epoch), `arrow` | PRD specifies `datetime`. Stdlib, no dependency. Conversion from `st_mtime` via `datetime.fromtimestamp()`. |

## Data Flow

```
pyproject.toml
    └─ defines → src/fsaudit/ package
                    ├── scanner/models.py    → FileRecord, DirectoryRecord, ScanResult
                    ├── analyzer/metrics.py  → AnalysisResult
                    ├── classifier/categories.yaml → extension mapping
                    └── logging_config.py    → setup_logging()

Future pipeline (NOT this phase):
    CLI ──→ Scanner ──→ Classifier ──→ Analyzer ──→ Reporter
            uses            uses         uses         uses
          FileRecord    categories   AnalysisResult  AnalysisResult
          ScanResult      .yaml
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `pyproject.toml` | Create | PEP 621 metadata, Python >=3.10, deps: openpyxl, Jinja2, PyYAML; dev deps: pytest, pytest-cov |
| `src/fsaudit/__init__.py` | Create | Package root, `__version__ = "0.1.0"` |
| `src/fsaudit/scanner/__init__.py` | Create | Empty, enables package import |
| `src/fsaudit/scanner/models.py` | Create | `FileRecord`, `DirectoryRecord`, `ScanResult` dataclasses |
| `src/fsaudit/classifier/__init__.py` | Create | Empty |
| `src/fsaudit/classifier/categories.yaml` | Create | 8 categories + compound extensions, longest-match order |
| `src/fsaudit/analyzer/__init__.py` | Create | Empty |
| `src/fsaudit/analyzer/metrics.py` | Create | `AnalysisResult` dataclass stub |
| `src/fsaudit/reporter/__init__.py` | Create | Empty |
| `src/fsaudit/logging_config.py` | Create | `setup_logging(level, log_file)` using stdlib `logging` |
| `tests/__init__.py` | Create | Empty |
| `tests/conftest.py` | Create | Shared pytest fixtures (`tmp_path`-based filesystem trees) |

## Interfaces / Contracts

```python
# src/fsaudit/scanner/models.py
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

@dataclass(frozen=True)
class FileRecord:
    path: Path
    name: str
    extension: str              # lowercase, empty string if none
    size_bytes: int
    mtime: datetime
    creation_time: datetime     # OS-aware via get_creation_time_safe()
    atime: datetime
    depth: int                  # relative to scan root
    is_hidden: bool
    permissions: Optional[str]  # octal string e.g. "755", None on Windows
    category: str = "Unclassified"  # set by Classifier
    parent_dir: str = ""        # str(path.parent)

@dataclass(frozen=True)
class DirectoryRecord:
    path: Path
    depth: int
    is_hidden: bool

@dataclass(frozen=True)
class ScanResult:
    files: list[FileRecord]           # all scanned files
    directories: list[DirectoryRecord] # empty dirs detected
    root_path: Path                    # scan root for reference
    errors: list[str] = field(default_factory=list)  # PermissionError paths

# src/fsaudit/analyzer/metrics.py
from dataclasses import dataclass, field
from typing import Any

@dataclass
class AnalysisResult:
    """Container for all analyzer outputs. NOT frozen — analyzer builds incrementally."""
    total_files: int = 0
    total_size_bytes: int = 0
    by_category: dict[str, Any] = field(default_factory=dict)
    top_largest: list[Any] = field(default_factory=list)
    inactive_files: list[Any] = field(default_factory=list)
    zero_byte_files: list[Any] = field(default_factory=list)
    empty_directories: list[Any] = field(default_factory=list)
    duplicates_by_name: dict[str, list[Any]] = field(default_factory=dict)
    timeline: dict[str, Any] = field(default_factory=dict)
    permission_issues: list[Any] = field(default_factory=list)
```

### categories.yaml Schema

```yaml
# Compound extensions MUST appear before their single-extension counterparts.
# Classifier must implement longest-match: check ".tar.gz" before ".gz".
categories:
  Oficina:
    extensions: [.docx, .doc, .xlsx, .xls, .xlsm, .pptx, .ppt, .odt, .ods, .odp, .pdf, .rtf, .csv]
  Codigo:
    extensions: [.py, .js, .ts, .java, .c, .cpp, .h, .cs, .go, .rs, .rb, .php, .sh, .bash, .sql, .html, .css, .json, .yaml, .toml, .xml, .md, .ipynb]
  Multimedia:
    extensions: [.jpg, .jpeg, .png, .gif, .bmp, .svg, .mp4, .avi, .mkv, .mp3, .wav, .flac, .aac, .mov, .webm, .webp]
  Datos:
    extensions: [.db, .sqlite, .sqlite3, .parquet, .arrow, .feather, .pickle, .pkl, .npy, .npz, .h5, .hdf5]
  Comprimidos:
    compound_extensions: [.tar.gz, .tar.bz2]
    extensions: [.zip, .tar, .gz, .bz2, .xz, .7z, .rar]
  Ejecutables:
    extensions: [.exe, .msi, .deb, .rpm, .appimage, .bat, .cmd, .ps1, .vbs]
  Sistema:
    extensions: [.log, .ini, .cfg, .conf, .env, .lock, .tmp, .bak, .swp, .DS_Store, .lnk]
  SinExtension:
    match: no_extension    # special rule: files where extension == ""
```

### Logging Configuration

```python
# src/fsaudit/logging_config.py
import logging
from pathlib import Path
from typing import Optional

def setup_logging(
    level: str = "INFO",
    log_file: Optional[Path] = None,
) -> logging.Logger:
    """Configure root fsaudit logger with console + optional file handler."""
    logger = logging.getLogger("fsaudit")
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    # Console handler (always)
    console = logging.StreamHandler()
    console.setFormatter(formatter)
    logger.addHandler(console)
    # File handler (if log_file provided)
    if log_file:
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    return logger
```

### pyproject.toml Dependencies

```toml
[project]
name = "fsaudit"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = [
    "openpyxl>=3.1",
    "Jinja2>=3.1",
    "PyYAML>=6.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0",
    "pytest-cov>=4.0",
]

[build-system]
requires = ["setuptools>=68.0"]
build-backend = "setuptools.backends._legacy:_Backend"

[tool.setuptools.packages.find]
where = ["src"]
```

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit | FileRecord creation, frozen enforcement | `pytest` — construct instances, verify fields, assert `FrozenInstanceError` on mutation |
| Unit | categories.yaml loading | `pytest` — load YAML, verify 8 categories present, compound extensions exist |
| Unit | ScanResult container | `pytest` — construct with lists, verify access patterns |
| Unit | Logging config | `pytest` + `tmp_path` — call `setup_logging()`, verify handlers created, log file written |
| Integration | `pip install -e .` | CI or manual — verify all imports work after install |

## Migration / Rollout

No migration required. Greenfield project — first code in the repository.

## Open Questions

None — all technical decisions resolved during exploration phase.
