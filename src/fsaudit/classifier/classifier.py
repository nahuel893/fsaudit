"""Classifier module — maps file extensions to semantic categories.

Reads categories.yaml and produces new FileRecord instances with the
``category`` field populated. FileRecord is frozen, so all output records
are fresh instances created via ``dataclasses.replace``.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Optional

import yaml

from fsaudit.scanner.models import FileRecord

# Type alias for the three lookup structures built from YAML.
CategoryMaps = tuple[dict[str, str], dict[str, str], Optional[str]]


_DEFAULT_YAML = Path(__file__).parent / "categories.yaml"


def load_categories(path: Path | None = None) -> CategoryMaps:
    """Load categories.yaml and build lookup structures.

    Args:
        path: Path to categories.yaml. Defaults to the bundled file
              co-located with this module.

    Returns:
        Tuple of ``(compound_ext_map, simple_ext_map, no_ext_category)``.

    Raises:
        FileNotFoundError: If the YAML file does not exist.
        ValueError: If the YAML structure is invalid (missing ``categories`` key).
    """
    yaml_path = path or _DEFAULT_YAML

    if not yaml_path.exists():
        raise FileNotFoundError(f"Categories file not found: {yaml_path}")

    with open(yaml_path, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)

    if not isinstance(data, dict) or "categories" not in data:
        raise ValueError(
            f"Invalid categories file: missing 'categories' key in {yaml_path}"
        )

    categories: dict = data["categories"]

    compound_ext_map: dict[str, str] = {}
    simple_ext_map: dict[str, str] = {}
    no_ext_category: str | None = None

    for category_name, rules in categories.items():
        if not isinstance(rules, dict):
            continue

        # Special match rule (e.g. match: no_extension)
        match_rule = rules.get("match")
        if match_rule == "no_extension":
            no_ext_category = category_name

        # Compound extensions (e.g. .tar.gz, .tar.bz2)
        for ext in rules.get("compound_extensions", []):
            compound_ext_map[ext.lower()] = category_name

        # Simple extensions
        for ext in rules.get("extensions", []):
            simple_ext_map[ext.lower()] = category_name

    # Sort compound keys by length descending so longest match wins.
    compound_ext_map = dict(
        sorted(compound_ext_map.items(), key=lambda item: len(item[0]), reverse=True)
    )

    return compound_ext_map, simple_ext_map, no_ext_category


def classify(
    records: list[FileRecord],
    categories_path: Path | None = None,
) -> list[FileRecord]:
    """Classify file records by extension.

    Calls :func:`load_categories` once, then iterates *records* applying
    the lookup order: compound extension → simple extension → no-extension
    rule → ``"Desconocido"`` fallback.

    This is a **pure function**: it returns a new list of ``FileRecord``
    instances and never mutates the originals.

    Args:
        records: FileRecord list from the Scanner.
        categories_path: Optional override for categories.yaml location.

    Returns:
        New list of FileRecord with the ``category`` field populated.
    """
    if not records:
        return []

    compound_ext_map, simple_ext_map, no_ext_category = load_categories(
        categories_path
    )

    # Pre-compute sorted compound keys (already sorted in load_categories).
    compound_keys = list(compound_ext_map.keys())

    result: list[FileRecord] = []

    for record in records:
        category: str | None = None
        name_lower = record.name.lower()

        # 1. Compound extension — longest suffix match
        for compound_ext in compound_keys:
            if name_lower.endswith(compound_ext):
                category = compound_ext_map[compound_ext]
                break

        # 2. Simple extension lookup
        if category is None:
            ext_lower = record.extension.lower()
            category = simple_ext_map.get(ext_lower)

        # 3. No-extension rule
        if category is None and record.extension == "":
            category = no_ext_category or "Desconocido"

        # 4. Fallback
        if category is None:
            category = "Desconocido"

        result.append(replace(record, category=category))

    return result
