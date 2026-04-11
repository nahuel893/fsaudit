"""FsauditApp — root Textual application.

Orchestrates the screen flow:
  FolderSelectorScreen → ConfigScreen → ProgressScreen → ResultsScreen
"""

from __future__ import annotations

from pathlib import Path

from textual.app import App

from fsaudit.tui.screens.folder_selector import FolderSelectorScreen
from fsaudit.tui.screens.config import ConfigScreen
from fsaudit.tui.screens.progress import ProgressScreen
from fsaudit.tui.screens.results import ResultsScreen


class FsauditApp(App):
    """Root TUI application for fsaudit."""

    CSS_PATH = "app.tcss"
    TITLE = "fsaudit"
    SUB_TITLE = "Filesystem Auditor"

    SCREENS = {
        "folder_selector": FolderSelectorScreen,
        "config": ConfigScreen,
        "progress": ProgressScreen,
        "results": ResultsScreen,
    }

    def on_mount(self) -> None:
        self.push_screen(FolderSelectorScreen(), self._on_folder_selected)

    def _on_folder_selected(self, path: Path | None) -> None:
        if path is None:
            self.exit()
            return
        self.push_screen(ConfigScreen(root_path=path), self._on_config_done)

    def _on_config_done(self, config) -> None:
        if config is None:
            return
        self.push_screen(ProgressScreen(config=config), self._on_progress_done)

    def _on_progress_done(self, results: dict | None) -> None:
        if results is None:
            return
        self.push_screen(ResultsScreen(results=results))


def main() -> None:
    """Entry point for the `fsaudit-tui` command."""
    app = FsauditApp()
    app.run()


if __name__ == "__main__":
    main()
