"""FolderSelectorScreen — lets the user choose a directory to audit."""

from __future__ import annotations

from pathlib import Path

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Button, DirectoryTree, Footer, Header, Input, Label


class FilterableDirectoryTree(DirectoryTree):
    """DirectoryTree that can filter visible entries by a substring."""

    def __init__(self, path: str, filter_text: str = "", **kwargs) -> None:
        super().__init__(path, **kwargs)
        self._filter_text = filter_text.lower()

    def set_filter(self, text: str) -> None:
        self._filter_text = text.lower()
        self.reload()

    def filter_paths(self, paths):
        """Override to filter directory entries by the search text."""
        if not self._filter_text:
            return paths
        return [
            p for p in paths
            if self._filter_text in p.name.lower()
        ]


class FolderSelectorScreen(Screen):
    """Full-screen folder browser with path input and tree filter."""

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
        yield Label("Type a path to navigate, or filter by name:", id="lbl-search-hint")
        yield Input(
            placeholder="e.g. /home/user/projects or Documents",
            id="inp-search",
        )
        yield Label("", id="lbl-search-status")
        yield FilterableDirectoryTree(str(self._start_path), id="folder-tree")
        yield Button("Select Folder", id="btn-select", variant="primary")
        yield Footer()

    def on_mount(self) -> None:
        self.title = "fsaudit - Select Folder"

    def on_input_changed(self, event: Input.Changed) -> None:
        """React to search input changes — navigate or filter."""
        if event.input.id != "inp-search":
            return

        text = event.value.strip()
        status = self.query_one("#lbl-search-status", Label)
        tree = self.query_one("#folder-tree", FilterableDirectoryTree)

        if not text:
            status.update("")
            tree.set_filter("")
            return

        # If it looks like an absolute path, try to navigate
        if text.startswith("/") or text.startswith("~"):
            expanded = Path(text).expanduser()
            if expanded.is_dir():
                status.update(f"[green]✓ {expanded}[/green]")
                self._selected = expanded
                tree.path = expanded
                tree.set_filter("")
            else:
                status.update(f"[yellow]Path not found — filtering tree[/yellow]")
                tree.set_filter(Path(text).name)
        else:
            # Plain text — filter the tree
            status.update(f"[dim]Filtering: {text}[/dim]")
            tree.set_filter(text)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Enter on the input navigates to path if valid, or selects current."""
        if event.input.id != "inp-search":
            return

        text = event.value.strip()
        if text:
            expanded = Path(text).expanduser()
            if expanded.is_dir():
                self._selected = expanded
                self.dismiss(self._selected)
                return

        # Fall through to normal select
        if self._selected is not None:
            self.dismiss(self._selected)

    def on_directory_tree_directory_selected(
        self, event: DirectoryTree.DirectorySelected
    ) -> None:
        self._selected = Path(event.path)
        status = self.query_one("#lbl-search-status", Label)
        status.update(f"[bold]{self._selected}[/bold]")

    def action_select_folder(self) -> None:
        """Confirm selection and dismiss with the chosen path."""
        if self._selected is not None:
            self.dismiss(self._selected)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-select":
            if self._selected is not None:
                self.dismiss(self._selected)
