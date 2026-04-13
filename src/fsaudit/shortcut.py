"""Desktop shortcut creation for fsaudit TUI."""

from __future__ import annotations

import platform
import subprocess
import sys
import tempfile
from pathlib import Path


def _get_tui_executable() -> Path:
    """Find the fsaudit-tui executable next to the current Python binary."""
    scripts_dir = Path(sys.executable).parent
    for name in ("fsaudit-tui.exe", "fsaudit-tui"):
        candidate = scripts_dir / name
        if candidate.exists():
            return candidate
    # Fallback: assume it's on PATH
    return Path("fsaudit-tui")


def create_shortcut(*, console=None) -> bool:
    """Create a desktop shortcut for fsaudit-tui.

    Returns True on success, False on failure.
    """
    system = platform.system()
    tui_path = _get_tui_executable()

    if system == "Windows":
        return _create_windows_shortcut(tui_path, console)
    elif system == "Linux":
        return _create_linux_shortcut(tui_path, console)
    elif system == "Darwin":
        return _create_macos_shortcut(tui_path, console)
    else:
        if console:
            console.print(f"[yellow]Unsupported OS: {system}[/yellow]")
        return False


def _create_windows_shortcut(tui_path: Path, console=None) -> bool:
    """Create a .lnk shortcut on the Windows Desktop using VBScript."""
    desktop = Path.home() / "Desktop"
    if not desktop.exists():
        # Try OneDrive Desktop
        desktop = Path.home() / "OneDrive" / "Desktop"
    if not desktop.exists():
        desktop.mkdir(parents=True, exist_ok=True)

    lnk_path = desktop / "fsaudit TUI.lnk"
    vbs = (
        f'Set WshShell = WScript.CreateObject("WScript.Shell")\n'
        f'Set shortcut = WshShell.CreateShortcut("{lnk_path}")\n'
        f'shortcut.TargetPath = "{tui_path}"\n'
        f'shortcut.WorkingDirectory = "{Path.home()}"\n'
        f'shortcut.Description = "fsaudit - Filesystem Auditor TUI"\n'
        f"shortcut.Save"
    )

    try:
        with tempfile.NamedTemporaryFile(suffix=".vbs", delete=False, mode="w") as f:
            f.write(vbs)
            vbs_path = f.name
        subprocess.run(["cscript", "//nologo", vbs_path], check=True, capture_output=True)
        Path(vbs_path).unlink(missing_ok=True)
        if console:
            console.print(f"[green]Shortcut created: {lnk_path}[/green]")
        return True
    except Exception as e:
        if console:
            console.print(f"[red]Failed to create shortcut: {e}[/red]")
        return False


def _create_linux_shortcut(tui_path: Path, console=None) -> bool:
    """Create a .desktop application entry on Linux."""
    apps_dir = Path.home() / ".local" / "share" / "applications"
    apps_dir.mkdir(parents=True, exist_ok=True)

    desktop_file = apps_dir / "fsaudit-tui.desktop"
    content = (
        "[Desktop Entry]\n"
        "Name=fsaudit TUI\n"
        "Comment=Filesystem Auditor - Terminal User Interface\n"
        f"Exec={tui_path}\n"
        "Terminal=true\n"
        "Type=Application\n"
        "Categories=Utility;System;\n"
    )
    try:
        desktop_file.write_text(content)
        if console:
            console.print(f"[green]Application entry created: {desktop_file}[/green]")
        return True
    except Exception as e:
        if console:
            console.print(f"[red]Failed to create shortcut: {e}[/red]")
        return False


def _create_macos_shortcut(tui_path: Path, console=None) -> bool:
    """Print instructions for macOS (automatic .app creation not supported)."""
    if console:
        console.print("[yellow]macOS: automatic shortcut creation not supported.[/yellow]")
        console.print(
            f"You can create an alias manually by dragging [bold]{tui_path}[/bold] to the Dock."
        )
    return False
