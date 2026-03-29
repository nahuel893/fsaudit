# FSAudit

Filesystem audit tool that scans, classifies, analyzes, and generates Excel reports from directory metadata.

FSAudit operates exclusively on filesystem metadata (timestamps, sizes, permissions) -- it never reads file contents. The tool is read-only by design and requires no elevated privileges.

## Features

- Recursive directory scanning with depth limits and exclusion patterns
- Extension-based file classification into semantic categories
- Temporal analysis: monthly distribution, inactive file detection
- Volume analysis: per-category and per-directory breakdowns
- Alert detection: empty files, empty directories, hidden files, duplicate names
- Multi-sheet Excel report with KPI dashboard
- Cross-platform support (Linux and Windows)

## Installation

```bash
pip install .
```

For development:

```bash
pip install -e ".[dev]"
```

Requires Python 3.10+.

## Usage

Basic audit of a directory:

```bash
fsaudit --path ~/Documents
```

Custom output directory and depth limit:

```bash
fsaudit --path ~/Projects --output-dir ~/reports --depth 5
```

Exclude patterns and filter small files:

```bash
fsaudit --path ~/work --exclude node_modules --exclude .git --min-size 1024
```

Set inactive threshold and enable debug logging:

```bash
fsaudit --path /home/user --inactive-days 180 --log-level DEBUG --log-file audit.log
```

### Output file naming

Reports are saved as `{folder_name}_audit_{YYYY-MM-DD}.xlsx`. For example, auditing `~/Documents` on 2026-03-29 produces:

```
Documents_audit_2026-03-29.xlsx
```

## CLI Flags

| Flag | Required | Default | Description |
|------|----------|---------|-------------|
| `--path` | Yes | -- | Root directory to audit |
| `--output-dir` | No | `.` (current directory) | Directory for the output report |
| `--depth` | No | Unlimited | Maximum recursion depth |
| `--exclude` | No | None | Directory/file patterns to exclude (repeatable) |
| `--min-size` | No | `0` | Minimum file size in bytes to include |
| `--inactive-days` | No | `365` | Days without modification to classify a file as inactive |
| `--log-level` | No | `INFO` | Logging verbosity: DEBUG, INFO, WARNING, ERROR |
| `--log-file` | No | None (stderr only) | Path to log file |

## Excel Report Sheets

The generated `.xlsx` workbook contains 8 sheets:

| Sheet | Content |
|-------|---------|
| Dashboard | KPI overview: total files, total size, category counts |
| Por Categoria | File count and size breakdown by category |
| Timeline | Monthly distribution of files by modification date |
| Top Archivos Pesados | Largest files ranked by size |
| Archivos Inactivos | Files not modified within the inactive-days threshold |
| Alertas | Warnings: empty files, empty directories, hidden files, duplicate names |
| Por Directorio | Top directories ranked by total volume |
| Inventario Completo | Full file listing with all metadata and autofilter |

## File Categories

Files are classified by extension into these categories:

| Category | Extensions (sample) |
|----------|-------------------|
| Oficina | .docx, .xlsx, .pptx, .pdf, .csv, .odt, .ods, .rtf |
| Codigo | .py, .js, .ts, .java, .go, .rs, .html, .css, .json, .yaml, .md |
| Multimedia | .jpg, .png, .gif, .svg, .mp4, .mp3, .wav, .mkv, .webm |
| Datos | .db, .sqlite, .parquet, .arrow, .pickle, .h5, .hdf5 |
| Comprimidos | .zip, .tar, .gz, .tar.gz, .tar.bz2, .7z, .rar |
| Ejecutables | .exe, .msi, .deb, .rpm, .appimage, .bat, .ps1 |
| Sistema | .log, .ini, .cfg, .conf, .env, .lock, .tmp, .bak |
| SinExtension | Files with no extension |
| Unclassified | Any extension not matching the above |

The full mapping is defined in `src/fsaudit/classifier/categories.yaml`.

## Architecture

FSAudit implements a modular pipeline pattern where each stage is stateless and independently testable:

```
CLI --> Scanner --> Classifier --> Analyzer --> Reporter
```

| Module | Responsibility |
|--------|---------------|
| `cli.py` | Argument parsing, input validation, pipeline orchestration |
| `scanner/` | Recursive filesystem walk, metadata extraction, platform-aware timestamps |
| `classifier/` | Extension-to-category mapping from YAML config |
| `analyzer/` | Metric computation: category stats, timeline, top files, inactive detection, alerts |
| `reporter/` | Excel workbook generation via openpyxl |

```
src/fsaudit/
    __init__.py
    cli.py
    logging_config.py
    analyzer/
        analyzer.py
        metrics.py
    classifier/
        classifier.py
        categories.yaml
    reporter/
        base.py
        excel_reporter.py
    scanner/
        scanner.py
        models.py
        platform_utils.py
```

## Development

Run tests:

```bash
pytest
```

Run tests with coverage:

```bash
pytest --cov=fsaudit
```

## License

TBD
