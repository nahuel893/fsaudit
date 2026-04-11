"""Tests for the fsaudit TUI — Tasks 2C.1 through 2C.6.

All tests follow strict TDD: tests are written BEFORE implementation.
Textual app tests use app.run_test() (async context manager).
"""

from __future__ import annotations

import sys
from dataclasses import fields
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Task 2C.1 — TUI package skeleton + ImportError guard
# ---------------------------------------------------------------------------


def test_tui_import_guard_message(monkeypatch):
    """Hiding textual from sys.modules must cause ImportError with helpful message."""
    # Remove textual and any cached fsaudit.tui modules from sys.modules
    tui_keys = [k for k in sys.modules if k.startswith("fsaudit.tui") or k == "textual" or k.startswith("textual.")]
    for k in tui_keys:
        monkeypatch.delitem(sys.modules, k, raising=False)

    # Make textual unimportable
    monkeypatch.setitem(sys.modules, "textual", None)  # None causes ImportError on import

    with pytest.raises(ImportError) as exc_info:
        import fsaudit.tui  # noqa: F401

    assert "pip install fsaudit[tui]" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Task 2C.2 — ScanConfig dataclass
# ---------------------------------------------------------------------------


def test_scan_config_defaults():
    """ScanConfig(root=Path('/tmp')) has correct default field values."""
    from fsaudit.tui.models import ScanConfig

    cfg = ScanConfig(root=Path("/tmp"))
    assert cfg.root == Path("/tmp")
    assert cfg.depth is None
    assert cfg.exclude == []
    assert cfg.min_size == 0
    assert cfg.inactive_days == 365
    assert cfg.format == "excel"
    assert cfg.hash_duplicates is False
    assert isinstance(cfg.output_dir, Path)


def test_scan_config_root_required():
    """ScanConfig() without root raises TypeError."""
    from fsaudit.tui.models import ScanConfig

    with pytest.raises(TypeError):
        ScanConfig()  # type: ignore[call-arg]


def test_scan_config_is_dataclass():
    """ScanConfig must be a dataclass."""
    from dataclasses import is_dataclass

    from fsaudit.tui.models import ScanConfig

    assert is_dataclass(ScanConfig)


# ---------------------------------------------------------------------------
# Task 2C.3 — FolderSelectorScreen
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_folder_selector_screen_renders():
    """FolderSelectorScreen can be mounted in a test app without crashing."""
    from textual.app import App, ComposeResult

    from fsaudit.tui.screens.folder_selector import FolderSelectorScreen

    class TestApp(App):
        def on_mount(self) -> None:
            self.push_screen(FolderSelectorScreen())

    async with TestApp().run_test(headless=True) as pilot:
        await pilot.pause()
        # If we reached here without exception, the screen rendered fine


@pytest.mark.asyncio
async def test_folder_selector_has_directory_tree():
    """FolderSelectorScreen must contain a DirectoryTree widget."""
    from textual.app import App
    from fsaudit.tui.screens.folder_selector import FolderSelectorScreen, FilterableDirectoryTree

    class TestApp(App):
        def on_mount(self) -> None:
            self.push_screen(FolderSelectorScreen())

    async with TestApp().run_test(headless=True) as pilot:
        await pilot.pause()
        screen = pilot.app.screen
        tree = screen.query_one(FilterableDirectoryTree)
        assert tree is not None


# ---------------------------------------------------------------------------
# Task 2C.4 — ConfigScreen with validation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_config_screen_renders():
    """ConfigScreen can be mounted without crashing."""
    from textual.app import App

    from fsaudit.tui.screens.config import ConfigScreen

    class TestApp(App):
        def on_mount(self) -> None:
            self.push_screen(ConfigScreen(root_path=Path("/tmp")))

    async with TestApp().run_test(headless=True) as pilot:
        await pilot.pause()


@pytest.mark.asyncio
async def test_config_screen_has_inputs():
    """ConfigScreen must have Input widgets for config fields."""
    from textual.app import App
    from textual.widgets import Input

    from fsaudit.tui.screens.config import ConfigScreen

    class TestApp(App):
        def on_mount(self) -> None:
            self.push_screen(ConfigScreen(root_path=Path("/tmp")))

    async with TestApp().run_test(headless=True) as pilot:
        await pilot.pause()
        # Query from the active screen (the pushed ConfigScreen)
        inputs = pilot.app.screen.query(Input)
        assert len(inputs) > 0, "ConfigScreen must have at least one Input widget"


# ---------------------------------------------------------------------------
# Task 2C.5 — ProgressScreen
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_progress_screen_renders():
    """ProgressScreen can be mounted without crashing (scan is mocked)."""
    from unittest.mock import MagicMock, patch

    from textual.app import App

    from fsaudit.tui.models import ScanConfig
    from fsaudit.tui.screens.progress import ProgressScreen

    cfg = ScanConfig(root=Path("/tmp"))

    # Mock the entire pipeline so no real I/O happens
    mock_scan_result = MagicMock()
    mock_scan_result.files = []
    mock_scan_result.errors = []

    mock_analysis = MagicMock()
    mock_analysis.health_score = 85.0
    mock_analysis.health_breakdown = {}
    mock_analysis.by_category = {}
    mock_analysis.top_largest = []
    mock_analysis.inactive_files = []
    mock_analysis.duplicates_by_name = {}
    mock_analysis.duplicates_by_hash = {}

    class TestApp(App):
        def on_mount(self) -> None:
            self.push_screen(ProgressScreen(config=cfg))

    with (
        patch("fsaudit.tui.screens.progress.FileScanner") as mock_scanner_cls,
        patch("fsaudit.tui.screens.progress.classify", return_value=[]),
        patch("fsaudit.tui.screens.progress.analyze", return_value=mock_analysis),
        patch("fsaudit.tui.screens.progress.ExcelReporter") as mock_reporter_cls,
    ):
        mock_scanner_cls.return_value.scan.return_value = mock_scan_result
        mock_reporter_cls.return_value.generate.return_value = Path("/tmp/report.xlsx")

        async with TestApp().run_test(headless=True) as pilot:
            await pilot.pause()


# ---------------------------------------------------------------------------
# Task 2C.6 — ResultsScreen + FsauditApp
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_results_screen_renders():
    """ResultsScreen can be mounted with mock audit results."""
    from unittest.mock import MagicMock

    from textual.app import App

    from fsaudit.tui.screens.results import ResultsScreen

    mock_analysis = MagicMock()
    mock_analysis.health_score = 85.0
    mock_analysis.health_breakdown = {}
    mock_analysis.by_category = {}
    mock_analysis.top_largest = []
    mock_analysis.inactive_files = []
    mock_analysis.duplicates_by_name = {}
    mock_analysis.duplicates_by_hash = {}
    mock_analysis.total_files = 0
    mock_analysis.total_size_bytes = 0

    results = {
        "records": [],
        "analysis": mock_analysis,
        "scan_result": MagicMock(),
        "report_path": Path("/tmp/report.xlsx"),
    }

    class TestApp(App):
        def on_mount(self) -> None:
            self.push_screen(ResultsScreen(results=results))

    async with TestApp().run_test(headless=True) as pilot:
        await pilot.pause()


@pytest.mark.asyncio
async def test_app_starts_with_folder_selector():
    """FsauditApp initial screen must be FolderSelectorScreen."""
    from fsaudit.tui.app import FsauditApp
    from fsaudit.tui.screens.folder_selector import FolderSelectorScreen

    async with FsauditApp().run_test(headless=True) as pilot:
        await pilot.pause()
        assert isinstance(pilot.app.screen, FolderSelectorScreen)
