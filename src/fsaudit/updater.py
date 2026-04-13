"""Auto-update checker for fsaudit."""

from __future__ import annotations

import json
import subprocess
import sys
from urllib.error import URLError
from urllib.request import urlopen

from fsaudit import __version__

_PYPI_URL = "https://pypi.org/pypi/fsaudit/json"
_TIMEOUT = 3  # seconds


def check_update(*, timeout: int = _TIMEOUT) -> str | None:
    """Check PyPI for a newer version. Returns new version string or None.

    Never raises — returns None on any error (offline, timeout, etc).
    """
    try:
        with urlopen(_PYPI_URL, timeout=timeout) as resp:
            data = json.loads(resp.read())
            latest = data["info"]["version"]
            if _is_newer(latest, __version__):
                return latest
    except Exception:
        return None
    return None


def _is_newer(latest: str, current: str) -> bool:
    """Compare version strings. Returns True if latest > current."""

    def parse(v: str) -> tuple[int, ...]:
        return tuple(int(x) for x in v.split("."))

    try:
        return parse(latest) > parse(current)
    except (ValueError, TypeError):
        return False


def run_update(*, console=None) -> bool:
    """Run pip install --upgrade fsaudit. Returns True on success."""
    try:
        cmd = [sys.executable, "-m", "pip", "install", "--upgrade", "fsaudit"]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode == 0:
            if console:
                console.print(
                    "[green]fsaudit updated successfully! Restart to use the new version.[/green]"
                )
            return True
        else:
            if console:
                console.print(f"[red]Update failed: {result.stderr.strip()}[/red]")
            return False
    except Exception as e:
        if console:
            console.print(f"[red]Update failed: {e}[/red]")
        return False
