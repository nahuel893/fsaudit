# Design: Phase 1 — Classifier Module

## Technical Approach

Pure-function pipeline stage: load YAML once, build flat lookup dicts, iterate records producing new frozen instances via `dataclasses.replace`. Zero side effects, zero mutation — fits the Scanner -> **Classifier** -> Analyzer pipeline from the PRD (section 5).

## Architecture Decisions

| # | Decision | Alternatives | Rationale |
|---|----------|-------------|-----------|
| 1 | **Two flat dicts** (`compound_ext_map`, `simple_ext_map`) built at load time | Single dict with all extensions; regex matching | O(1) lookup for simple case, small linear scan for compounds. Compounds are rare (2 entries today) so no perf concern. Keeps logic trivially testable. |
| 2 | **Longest-suffix match for compounds** — sort compound keys by length descending, check `name.endswith(ext)` | Split on dots and reconstruct; regex capture groups | `endswith` is idiomatic, correct for `file.backup.tar.gz`, and avoids dot-splitting edge cases. Sorting by length descending guarantees longest match wins. |
| 3 | **`dataclasses.replace`** to produce classified records | Mutable FileRecord; wrapper class; dict-based records | FileRecord is `frozen=True` by design (PRD 8.1). `replace` is stdlib, zero-copy semantics, and preserves type safety. |
| 4 | **Default YAML path via `Path(__file__).parent / "categories.yaml"`** | Require explicit path always; env var; config object | Co-located default is discoverable, works in tests via override param, no config machinery needed for Phase 1. |
| 5 | **"SinExtension" category from YAML** `match: no_extension` rule | Hardcode in Python; separate config key | Keeps all category names in YAML — single source of truth. Classifier reads the `match` field and stores the category name for the `extension == ""` case. |

## Data Flow

```
categories.yaml
      |
      v
load_categories(path)
      |
      v
+---------------------------+
| compound_ext_map (dict)   |   {".tar.gz": "Comprimidos", ".tar.bz2": "Comprimidos"}
| simple_ext_map   (dict)   |   {".py": "Codigo", ".docx": "Oficina", ...}
| no_ext_category  (str)    |   "SinExtension"
+---------------------------+
      |
      v
classify(records, categories_path?) -> list[FileRecord]
      |
      +--- for each FileRecord:
      |      1. name.endswith(compound)? -> category   (longest first)
      |      2. extension in simple_ext_map? -> category
      |      3. extension == "" and no_ext_category? -> "SinExtension"
      |      4. else -> "Desconocido"
      |      5. dataclasses.replace(record, category=matched)
      v
list[FileRecord]  (new instances, originals untouched)
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `src/fsaudit/classifier/classifier.py` | Create | Core module: `load_categories()`, `classify()` |
| `src/fsaudit/classifier/__init__.py` | Modify | Export `classify` and `load_categories` |
| `src/fsaudit/classifier/categories.yaml` | None | Read-only, no changes |
| `tests/test_classifier.py` | Create | Unit tests covering all branches |

## Interfaces / Contracts

```python
from pathlib import Path
from fsaudit.scanner.models import FileRecord

CategoryMaps = tuple[dict[str, str], dict[str, str], str | None]
# (compound_ext_map, simple_ext_map, no_ext_category)

def load_categories(path: Path | None = None) -> CategoryMaps:
    """Load YAML and build lookup structures.

    Args:
        path: Path to categories.yaml. Defaults to bundled file.

    Returns:
        Tuple of (compound_ext_map, simple_ext_map, no_ext_category).

    Raises:
        FileNotFoundError: If YAML file does not exist (includes path in message).
        ValueError: If YAML structure is invalid.
    """

def classify(
    records: list[FileRecord],
    categories_path: Path | None = None,
) -> list[FileRecord]:
    """Classify file records by extension.

    Calls load_categories once, then iterates records.
    Pure function — returns new list, originals untouched.

    Args:
        records: FileRecord list from Scanner.
        categories_path: Optional override for categories.yaml location.

    Returns:
        New list of FileRecord with category field populated.
    """
```

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit | `load_categories` — correct dict construction from YAML | Inline YAML via `tmp_path` fixture |
| Unit | Simple extension match (`.py` -> `Codigo`) | Fabricate FileRecord, assert category |
| Unit | Compound extension (`.tar.gz` -> `Comprimidos`) | Fabricate FileRecord with name `archive.tar.gz` |
| Unit | No-extension file -> `SinExtension` | FileRecord with `extension=""`, `name="Makefile"` |
| Unit | Unknown extension -> `Desconocido` | FileRecord with `.xyz` |
| Unit | Multi-dot name (`data.backup.tar.gz`) -> `Comprimidos` | Verify longest-suffix wins |
| Unit | Missing YAML -> `FileNotFoundError` | Pass nonexistent path |
| Unit | Frozen invariant — originals unchanged | Assert input records still have `"Unclassified"` |
| Unit | Empty record list -> empty result | Edge case |

## Migration / Rollout

No migration required. New module, no existing consumers yet.

## Open Questions

None — all decisions are straightforward for Phase 1 scope.
