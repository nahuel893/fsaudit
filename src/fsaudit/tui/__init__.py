"""TUI package for fsaudit — requires textual.

Install the optional dependency with:
    pip install fsaudit[tui]
"""

from __future__ import annotations

try:
    import textual  # noqa: F401
except ImportError as exc:
    raise ImportError(
        "The fsaudit TUI requires Textual. "
        "Install it with: pip install fsaudit[tui]"
    ) from exc
