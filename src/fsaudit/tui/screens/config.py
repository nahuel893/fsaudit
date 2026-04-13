"""ConfigScreen — collect audit parameters before running the scan."""

from __future__ import annotations

from pathlib import Path

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import (
    Button,
    Footer,
    Header,
    Input,
    Label,
    RadioButton,
    RadioSet,
    Switch,
)

from fsaudit.tui.models import ScanConfig


class ConfigScreen(Screen):
    """Configuration form shown after a folder is selected."""

    BINDINGS = [
        ("escape", "go_back", "Back"),
    ]

    def __init__(self, root_path: Path) -> None:
        super().__init__()
        self._root_path = root_path

    def compose(self) -> ComposeResult:
        yield Header()
        yield Label(f"Selected folder: {self._root_path}", id="lbl-path")
        yield Label("Max depth (leave empty for unlimited):", classes="field-label")
        yield Input(placeholder="e.g. 5", id="inp-depth")
        yield Label("Exclude patterns (comma-separated):", classes="field-label")
        yield Input(placeholder="e.g. .git,node_modules", id="inp-exclude")
        yield Label("Minimum file size (bytes):", classes="field-label")
        yield Input(placeholder="0", value="0", id="inp-min-size")
        yield Label("Inactive days threshold:", classes="field-label")
        yield Input(placeholder="365", value="365", id="inp-inactive-days")
        yield Label("Output format:", classes="field-label")
        with RadioSet(id="radio-format"):
            yield RadioButton("Excel", id="radio-excel", value=True)
            yield RadioButton("HTML", id="radio-html")
        yield Label("Hash duplicates (slower, more accurate):", classes="field-label")
        yield Switch(id="switch-hash-dup", value=False)
        yield Label("Extract author from documents (.docx, .pdf, etc.):", classes="field-label")
        yield Switch(id="switch-extract-author", value=True)
        yield Label("", id="lbl-error", classes="error")
        yield Button("Start Audit", id="btn-start", variant="primary")
        yield Button("Back", id="btn-back", variant="default")
        yield Footer()

    def on_mount(self) -> None:
        self.title = "fsaudit - Configure Audit"

    def _get_int(self, widget_id: str, default: int | None = None) -> int | None:
        """Parse an integer from an Input, returning default on empty/invalid."""
        raw = self.query_one(f"#{widget_id}", Input).value.strip()
        if not raw:
            return default
        try:
            return int(raw)
        except ValueError:
            return None  # signals parse error

    def action_go_back(self) -> None:
        self.app.pop_screen()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-back":
            self.app.pop_screen()
            return

        if event.button.id == "btn-start":
            self._submit()

    def _submit(self) -> None:
        error_label = self.query_one("#lbl-error", Label)

        # Validate depth
        depth_raw = self.query_one("#inp-depth", Input).value.strip()
        depth: int | None = None
        if depth_raw:
            try:
                depth = int(depth_raw)
            except ValueError:
                error_label.update("Depth must be a whole number.")
                return

        # Validate min_size
        min_size_val = self._get_int("inp-min-size", 0)
        if min_size_val is None:
            error_label.update("Min size must be a whole number.")
            return

        # Validate inactive_days
        inactive_val = self._get_int("inp-inactive-days", 365)
        if inactive_val is None:
            error_label.update("Inactive days must be a whole number.")
            return

        # Exclude patterns
        exclude_raw = self.query_one("#inp-exclude", Input).value.strip()
        exclude = [p.strip() for p in exclude_raw.split(",") if p.strip()] if exclude_raw else []

        # Format
        radio_set = self.query_one("#radio-format", RadioSet)
        fmt = "html" if radio_set.pressed_index == 1 else "excel"

        # Hash duplicates
        hash_dup = self.query_one("#switch-hash-dup", Switch).value

        # Extract author
        extract_author = self.query_one("#switch-extract-author", Switch).value

        error_label.update("")
        self.dismiss(
            ScanConfig(
                root=self._root_path,
                depth=depth,
                exclude=exclude,
                min_size=min_size_val or 0,
                inactive_days=inactive_val or 365,
                format=fmt,
                hash_duplicates=hash_dup,
                extract_author=extract_author,
            )
        )
