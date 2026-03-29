"""Tests for classifier/categories.yaml."""

from pathlib import Path

import yaml


CATEGORIES_PATH = (
    Path(__file__).resolve().parent.parent
    / "src"
    / "fsaudit"
    / "classifier"
    / "categories.yaml"
)

REQUIRED_CATEGORIES = {
    "Oficina",
    "Codigo",
    "Multimedia",
    "Datos",
    "Comprimidos",
    "Ejecutables",
    "Sistema",
    "SinExtension",
}


def _load_categories() -> dict:
    with open(CATEGORIES_PATH) as f:
        return yaml.safe_load(f)["categories"]


class TestCategoriesYaml:
    """REQ-CAT-01 through REQ-CAT-06."""

    def test_file_loads_successfully(self) -> None:
        """CAT-01a: File loads with safe_load and produces a dict."""
        data = _load_categories()
        assert isinstance(data, dict)

    def test_all_categories_present(self) -> None:
        """CAT-02a: All 8 required categories are present."""
        data = _load_categories()
        assert set(data.keys()) == REQUIRED_CATEGORIES

    def test_no_extra_categories(self) -> None:
        """CAT-02b: Exactly 8 keys, no extras."""
        data = _load_categories()
        assert len(data) == 8

    def test_extensions_are_lists(self) -> None:
        """CAT-03a: Each category's extensions value is a list."""
        data = _load_categories()
        for cat, info in data.items():
            if cat == "SinExtension":
                continue  # special rule, no extensions list
            exts = info.get("extensions", [])
            assert isinstance(exts, list), f"{cat} extensions is not a list"

    def test_extensions_start_with_dot(self) -> None:
        """CAT-03b: Every extension starts with '.'."""
        data = _load_categories()
        for cat, info in data.items():
            for ext in info.get("extensions", []):
                assert ext.startswith("."), f"{cat}: {ext} missing dot prefix"
            for ext in info.get("compound_extensions", []):
                assert ext.startswith("."), f"{cat}: {ext} missing dot prefix"

    def test_extensions_are_lowercase(self) -> None:
        """CAT-03c: Every extension is lowercase."""
        data = _load_categories()
        for cat, info in data.items():
            for ext in info.get("extensions", []):
                assert ext == ext.lower(), f"{cat}: {ext} not lowercase"
            for ext in info.get("compound_extensions", []):
                assert ext == ext.lower(), f"{cat}: {ext} not lowercase"

    def test_oficina_extensions(self) -> None:
        """CAT-04a: Oficina has all PRD-mandated extensions."""
        data = _load_categories()
        exts = set(data["Oficina"]["extensions"])
        required = {
            ".docx", ".doc", ".xlsx", ".xls", ".xlsm",
            ".pptx", ".ppt", ".odt", ".ods", ".odp",
            ".pdf", ".rtf", ".csv",
        }
        assert required.issubset(exts)

    def test_codigo_extensions(self) -> None:
        """CAT-04b: Codigo has all PRD-mandated extensions."""
        data = _load_categories()
        exts = set(data["Codigo"]["extensions"])
        required = {
            ".py", ".js", ".ts", ".java", ".c", ".cpp", ".h", ".cs",
            ".go", ".rs", ".rb", ".php", ".sh", ".bash", ".sql",
            ".html", ".css", ".json", ".yaml", ".toml", ".xml",
            ".md", ".ipynb",
        }
        assert required.issubset(exts)

    def test_multimedia_extensions(self) -> None:
        """CAT-04c: Multimedia has all PRD-mandated extensions."""
        data = _load_categories()
        exts = set(data["Multimedia"]["extensions"])
        required = {
            ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".svg",
            ".mp4", ".avi", ".mkv", ".mp3", ".wav", ".flac",
            ".aac", ".mov", ".webm", ".webp",
        }
        assert required.issubset(exts)

    def test_comprimidos_compound_extensions(self) -> None:
        """CAT-04d: Comprimidos includes .tar.gz and .tar.bz2."""
        data = _load_categories()
        compound = data["Comprimidos"].get("compound_extensions", [])
        assert ".tar.gz" in compound
        assert ".tar.bz2" in compound

    def test_no_duplicate_extensions(self) -> None:
        """CAT-05a: No extension appears in more than one category."""
        data = _load_categories()
        seen: dict[str, str] = {}
        for cat, info in data.items():
            all_exts = info.get("extensions", []) + info.get("compound_extensions", [])
            for ext in all_exts:
                assert ext not in seen, (
                    f"Duplicate extension {ext}: found in both {seen[ext]} and {cat}"
                )
                seen[ext] = cat

    def test_sin_extension_exists(self) -> None:
        """CAT-06a / SinExtension exists as fallback for no-extension files."""
        data = _load_categories()
        assert "SinExtension" in data
        assert data["SinExtension"].get("match") == "no_extension"
