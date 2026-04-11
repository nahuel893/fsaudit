"""FolderSelectorScreen — lets the user choose a directory to audit."""

from __future__ import annotations

from pathlib import Path

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Button, DirectoryTree, Footer, Header


class FolderSelectorScreen(Screen):
    """Full-screen folder browser backed by DirectoryTree."""

    BINDINGS = [
        ("enter", "select_folder", "Select"),
        ("escape", "app.quit", "Quit"),
    ]

    def __init__(self, start_path: Path | None = None) -> None:
        super().__init__()
        self._start_path = start_path or Path.home()
        self._selected: Path | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        yield DirectoryTree(str(self._start_path), id="folder-tree")
        yield Button("Select Folder", id="btn-select", variant="primary")
        yield Footer()

    def on_mount(self) -> None:
        self.title = "fsaudit - Select Folder"

    def on_directory_tree_directory_selected(
        self, event: DirectoryTree.DirectorySelected
    ) -> None:
        self._selected = Path(event.path)

    def action_select_folder(self) -> None:
        """Confirm selection and dismiss with the chosen path."""
        if self._selected is not None:
            self.dismiss(self._selected)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-select":
            if self._selected is not None:
                self.dismiss(self._selected)
