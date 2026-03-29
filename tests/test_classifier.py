"""Tests for the Classifier module (phase1-classifier).

Covers all spec scenarios CL-01 through CL-07.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from fsaudit.classifier import classify, load_categories
from fsaudit.scanner.models import FileRecord


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_record(
    name: str = "file.txt",
    extension: str = ".txt",
    **overrides,
) -> FileRecord:
    """Create a minimal FileRecord for testing."""
    defaults = dict(
        path=Path(f"/tmp/{name}"),
        name=name,
        extension=extension,
        size_bytes=100,
        mtime=datetime(2025, 1, 1),
        creation_time=datetime(2025, 1, 1),
        atime=datetime(2025, 1, 1),
        depth=0,
        is_hidden=False,
        permissions="644",
        category="Unclassified",
        parent_dir="/tmp",
    )
    defaults.update(overrides)
    return FileRecord(**defaults)


# ---------------------------------------------------------------------------
# Fixtures — YAML files written to tmp_path
# ---------------------------------------------------------------------------

VALID_YAML = """\
categories:
  Oficina:
    extensions:
      - .pdf
      - .docx
  Codigo:
    extensions:
      - .py
      - .js
  Comprimidos:
    compound_extensions:
      - .tar.gz
      - .tar.bz2
    extensions:
      - .zip
      - .gz
  SinExtension:
    match: no_extension
"""

MISSING_KEY_YAML = """\
something_else:
  - foo
"""

EMPTY_YAML = ""


@pytest.fixture()
def valid_yaml_path(tmp_path: Path) -> Path:
    p = tmp_path / "categories.yaml"
    p.write_text(VALID_YAML)
    return p


@pytest.fixture()
def missing_key_yaml_path(tmp_path: Path) -> Path:
    p = tmp_path / "categories.yaml"
    p.write_text(MISSING_KEY_YAML)
    return p


# ---------------------------------------------------------------------------
# REQ-CL-01: YAML Loading and Parsing
# ---------------------------------------------------------------------------


class TestLoadCategories:
    """CL-01 scenarios."""

    def test_successful_load(self, valid_yaml_path: Path) -> None:
        """CL-01.1 — valid YAML produces correct lookup structures."""
        compound, simple, no_ext = load_categories(valid_yaml_path)

        assert ".tar.gz" in compound
        assert compound[".tar.gz"] == "Comprimidos"
        assert ".tar.bz2" in compound
        assert ".pdf" in simple
        assert simple[".pdf"] == "Oficina"
        assert ".py" in simple
        assert simple[".py"] == "Codigo"
        assert no_ext == "SinExtension"

    def test_missing_file_raises(self, tmp_path: Path) -> None:
        """CL-01.2 — missing YAML raises FileNotFoundError with path."""
        bad_path = tmp_path / "nonexistent.yaml"
        with pytest.raises(FileNotFoundError, match=str(bad_path)):
            load_categories(bad_path)

    def test_malformed_yaml_raises(self, missing_key_yaml_path: Path) -> None:
        """CL-01.3 — YAML without 'categories' key raises ValueError."""
        with pytest.raises(ValueError, match="missing 'categories' key"):
            load_categories(missing_key_yaml_path)

    def test_empty_yaml_raises(self, tmp_path: Path) -> None:
        """Edge case — empty YAML file raises ValueError."""
        p = tmp_path / "categories.yaml"
        p.write_text(EMPTY_YAML)
        with pytest.raises(ValueError, match="missing 'categories' key"):
            load_categories(p)

    def test_compound_keys_sorted_longest_first(self, valid_yaml_path: Path) -> None:
        """Compound keys must be sorted by length descending."""
        compound, _, _ = load_categories(valid_yaml_path)
        keys = list(compound.keys())
        assert keys == sorted(keys, key=len, reverse=True)


# ---------------------------------------------------------------------------
# REQ-CL-02: Simple Extension Mapping
# ---------------------------------------------------------------------------


class TestSimpleExtension:
    """CL-02 scenarios."""

    def test_known_extension(self, valid_yaml_path: Path) -> None:
        """CL-02.1 — .pdf -> Oficina."""
        records = [_make_record(name="report.pdf", extension=".pdf")]
        result = classify(records, valid_yaml_path)
        assert result[0].category == "Oficina"

    def test_case_insensitive(self, valid_yaml_path: Path) -> None:
        """CL-02.2 — .PDF (uppercase) -> Oficina."""
        records = [_make_record(name="report.PDF", extension=".PDF")]
        result = classify(records, valid_yaml_path)
        assert result[0].category == "Oficina"


# ---------------------------------------------------------------------------
# REQ-CL-03: Compound Extension Handling
# ---------------------------------------------------------------------------


class TestCompoundExtension:
    """CL-03 scenarios."""

    def test_compound_match(self, valid_yaml_path: Path) -> None:
        """CL-03.1 — archive.tar.gz matched via compound, not simple .gz."""
        records = [_make_record(name="archive.tar.gz", extension=".gz")]
        result = classify(records, valid_yaml_path)
        assert result[0].category == "Comprimidos"

    def test_simple_fallback_when_no_compound(self, valid_yaml_path: Path) -> None:
        """CL-03.2 — data.gz falls through to simple .gz."""
        records = [_make_record(name="data.gz", extension=".gz")]
        result = classify(records, valid_yaml_path)
        assert result[0].category == "Comprimidos"

    def test_multi_dot_no_false_compound(self, valid_yaml_path: Path) -> None:
        """CL-03.3 — my.backup.zip has no compound match, uses simple .zip."""
        records = [_make_record(name="my.backup.zip", extension=".zip")]
        result = classify(records, valid_yaml_path)
        assert result[0].category == "Comprimidos"

    def test_multi_dot_with_compound(self, valid_yaml_path: Path) -> None:
        """data.backup.tar.gz — longest suffix .tar.gz should match."""
        records = [_make_record(name="data.backup.tar.gz", extension=".gz")]
        result = classify(records, valid_yaml_path)
        assert result[0].category == "Comprimidos"


# ---------------------------------------------------------------------------
# REQ-CL-04: No-Extension Files
# ---------------------------------------------------------------------------


class TestNoExtension:
    """CL-04 scenarios."""

    def test_no_extension_file(self, valid_yaml_path: Path) -> None:
        """CL-04.1 — Makefile (extension='') -> SinExtension."""
        records = [_make_record(name="Makefile", extension="")]
        result = classify(records, valid_yaml_path)
        assert result[0].category == "SinExtension"


# ---------------------------------------------------------------------------
# REQ-CL-05: Unknown Extension Fallback
# ---------------------------------------------------------------------------


class TestUnknownExtension:
    """CL-05 scenarios."""

    def test_unrecognized_extension(self, valid_yaml_path: Path) -> None:
        """CL-05.1 — .xyz123 -> Desconocido."""
        records = [_make_record(name="mystery.xyz123", extension=".xyz123")]
        result = classify(records, valid_yaml_path)
        assert result[0].category == "Desconocido"


# ---------------------------------------------------------------------------
# REQ-CL-06: Frozen FileRecord Constraint
# ---------------------------------------------------------------------------


class TestFrozenInvariant:
    """CL-06 scenarios."""

    def test_original_unchanged(self, valid_yaml_path: Path) -> None:
        """CL-06.1 — original record retains 'Unclassified' after classify."""
        original = _make_record(name="script.py", extension=".py")
        result = classify([original], valid_yaml_path)
        assert original.category == "Unclassified"
        assert result[0].category == "Codigo"
        assert result[0] is not original


# ---------------------------------------------------------------------------
# REQ-CL-07: Function Signature and Statelessness
# ---------------------------------------------------------------------------


class TestFunctionContract:
    """CL-07 scenarios."""

    def test_empty_input(self, valid_yaml_path: Path) -> None:
        """CL-07.1 — empty list -> empty list."""
        assert classify([], valid_yaml_path) == []

    def test_mixed_input_order_preserved(self, valid_yaml_path: Path) -> None:
        """CL-07.2 — mixed extensions produce correct categories in order."""
        records = [
            _make_record(name="app.py", extension=".py"),
            _make_record(name="archive.tar.gz", extension=".gz"),
            _make_record(name="Makefile", extension=""),
            _make_record(name="weird.xyz", extension=".xyz"),
        ]
        result = classify(records, valid_yaml_path)
        categories = [r.category for r in result]
        assert categories == ["Codigo", "Comprimidos", "SinExtension", "Desconocido"]

    def test_output_length_matches_input(self, valid_yaml_path: Path) -> None:
        """CL-07.3 — output has exactly N elements."""
        records = [
            _make_record(name=f"file{i}.py", extension=".py") for i in range(5)
        ]
        result = classify(records, valid_yaml_path)
        assert len(result) == len(records)


# ---------------------------------------------------------------------------
# Integration: test with bundled categories.yaml
# ---------------------------------------------------------------------------


class TestWithBundledYaml:
    """Smoke tests using the real categories.yaml shipped with the package."""

    def test_load_bundled(self) -> None:
        """Bundled categories.yaml loads without error."""
        compound, simple, no_ext = load_categories()
        assert len(simple) > 0
        assert no_ext == "SinExtension"

    def test_classify_with_bundled(self) -> None:
        """Full classify using bundled YAML."""
        records = [
            _make_record(name="doc.pdf", extension=".pdf"),
            _make_record(name="script.py", extension=".py"),
            _make_record(name="backup.tar.gz", extension=".gz"),
            _make_record(name="README", extension=""),
        ]
        result = classify(records)
        assert result[0].category == "Oficina"
        assert result[1].category == "Codigo"
        assert result[2].category == "Comprimidos"
        assert result[3].category == "SinExtension"
