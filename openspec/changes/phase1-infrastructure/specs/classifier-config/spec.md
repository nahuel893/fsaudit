# Spec: Classifier Config — categories.yaml

**Change**: phase1-infrastructure
**Domain**: classifier-config
**Type**: NEW

---

## REQ-CAT-01: Category file location and format

The system MUST provide a `categories.yaml` file at `src/fsaudit/classifier/categories.yaml`. The file MUST be valid YAML loadable by PyYAML's `safe_load`.

### Scenario CAT-01a: File loads successfully

- **Given** the file `src/fsaudit/classifier/categories.yaml` exists
- **When** loaded with `yaml.safe_load()`
- **Then** the result MUST be a Python dictionary
- **And** no YAML parsing error SHALL be raised

---

## REQ-CAT-02: Required categories

The file MUST contain exactly these 8 top-level category keys: `Oficina`, `Codigo`, `Multimedia`, `Datos`, `Comprimidos`, `Ejecutables`, `Sistema`, `SinExtension`.

### Scenario CAT-02a: All categories present

- **Given** the loaded YAML dictionary
- **When** the top-level keys are inspected
- **Then** all 8 required categories MUST be present

### Scenario CAT-02b: No extra categories

- **Given** the loaded YAML dictionary
- **When** the top-level keys are counted
- **Then** there MUST be exactly 8 keys (no extras beyond the required set)

---

## REQ-CAT-03: Extension mapping structure

Each category key MUST map to a list of extension strings. Each extension MUST start with a dot (`.`) and MUST be lowercase.

### Scenario CAT-03a: Extensions are lists

- **Given** the loaded YAML
- **When** each category's value is inspected
- **Then** it MUST be a list of strings (except `SinExtension` which uses a `match: no_extension` rule instead of an extension list)

### Scenario CAT-03b: Extensions start with dot

- **Given** all extension strings across all categories
- **When** each is inspected
- **Then** every extension MUST start with `.`

### Scenario CAT-03c: Extensions are lowercase

- **Given** all extension strings across all categories
- **When** each is inspected
- **Then** every extension MUST equal its lowercase form

---

## REQ-CAT-04: PRD-mandated extensions

Each category MUST include at minimum the extensions listed in PRD section 8.2.

### Scenario CAT-04a: Oficina extensions

- **Given** the `Oficina` category
- **When** its extensions are inspected
- **Then** it MUST contain at least: `.docx`, `.doc`, `.xlsx`, `.xls`, `.xlsm`, `.pptx`, `.ppt`, `.odt`, `.ods`, `.odp`, `.pdf`, `.rtf`, `.csv`

### Scenario CAT-04b: Codigo extensions

- **Given** the `Codigo` category
- **When** its extensions are inspected
- **Then** it MUST contain at least: `.py`, `.js`, `.ts`, `.java`, `.c`, `.cpp`, `.h`, `.cs`, `.go`, `.rs`, `.rb`, `.php`, `.sh`, `.bash`, `.sql`, `.html`, `.css`, `.json`, `.yaml`, `.toml`, `.xml`, `.md`, `.ipynb`

### Scenario CAT-04c: Multimedia extensions

- **Given** the `Multimedia` category
- **When** its extensions are inspected
- **Then** it MUST contain at least: `.jpg`, `.jpeg`, `.png`, `.gif`, `.bmp`, `.svg`, `.mp4`, `.avi`, `.mkv`, `.mp3`, `.wav`, `.flac`, `.aac`, `.mov`, `.webm`, `.webp`

### Scenario CAT-04d: Comprimidos includes compound extensions

- **Given** the `Comprimidos` category
- **When** its extensions are inspected
- **Then** it MUST contain `.tar.gz` and `.tar.bz2` in addition to single extensions

---

## REQ-CAT-05: No duplicate extensions across categories

An extension MUST NOT appear in more than one category. Each extension maps to exactly one category.

### Scenario CAT-05a: Uniqueness check

- **Given** all extensions from all categories are collected
- **When** duplicates are checked
- **Then** no extension SHALL appear in two or more categories

---

## REQ-CAT-06: SinExtension for extensionless files

The `SinExtension` category captures files with no extension (e.g., `Makefile`, `Dockerfile`). It uses a `match: no_extension` rule instead of an extension list.

### Scenario CAT-06a: SinExtension exists for extensionless files

- **Given** a file with no extension (extension == "")
- **When** the classifier looks it up
- **Then** it SHOULD be classified as `SinExtension`
