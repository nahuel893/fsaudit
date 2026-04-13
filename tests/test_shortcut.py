"""Tests for fsaudit.shortcut — desktop shortcut creation."""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from fsaudit.shortcut import (
    _get_tui_executable,
    create_shortcut,
    _create_linux_shortcut,
    _create_windows_shortcut,
    _create_macos_shortcut,
)


# ---------------------------------------------------------------------------
# _get_tui_executable
# ---------------------------------------------------------------------------


def test_get_tui_executable_returns_path_when_exe_exists(tmp_path):
    """Returns the .exe path when fsaudit-tui.exe is present in scripts dir."""
    fake_exe = tmp_path / "fsaudit-tui.exe"
    fake_exe.touch()

    with patch("fsaudit.shortcut.sys") as mock_sys:
        mock_sys.executable = str(tmp_path / "python.exe")
        result = _get_tui_executable()

    assert result == fake_exe


def test_get_tui_executable_returns_unix_path_when_no_exe(tmp_path):
    """Returns the unix binary path when fsaudit-tui (no ext) is present."""
    fake_bin = tmp_path / "fsaudit-tui"
    fake_bin.touch()

    with patch("fsaudit.shortcut.sys") as mock_sys:
        mock_sys.executable = str(tmp_path / "python")
        result = _get_tui_executable()

    assert result == fake_bin


def test_get_tui_executable_fallback_when_none_found(tmp_path):
    """Falls back to bare 'fsaudit-tui' Path when neither binary exists."""
    with patch("fsaudit.shortcut.sys") as mock_sys:
        mock_sys.executable = str(tmp_path / "python")
        result = _get_tui_executable()

    assert result == Path("fsaudit-tui")


# ---------------------------------------------------------------------------
# _create_linux_shortcut
# ---------------------------------------------------------------------------


def test_create_shortcut_linux_creates_desktop_file(tmp_path):
    """Creates a .desktop file in the specified applications dir."""
    apps_dir = tmp_path / ".local" / "share" / "applications"

    with patch("fsaudit.shortcut.Path.home", return_value=tmp_path):
        result = _create_linux_shortcut(Path("/usr/bin/fsaudit-tui"))

    desktop_file = apps_dir / "fsaudit-tui.desktop"
    assert desktop_file.exists(), "Desktop file should have been created"
    assert result is True


def test_create_shortcut_linux_desktop_file_content(tmp_path):
    """Verifies .desktop file contains correct required fields."""
    with patch("fsaudit.shortcut.Path.home", return_value=tmp_path):
        _create_linux_shortcut(Path("/usr/bin/fsaudit-tui"))

    desktop_file = tmp_path / ".local" / "share" / "applications" / "fsaudit-tui.desktop"
    content = desktop_file.read_text()

    assert "[Desktop Entry]" in content
    assert "Name=fsaudit TUI" in content
    assert "Exec=/usr/bin/fsaudit-tui" in content
    assert "Terminal=true" in content
    assert "Type=Application" in content
    assert "Categories=Utility" in content


def test_create_shortcut_linux_prints_success_message(tmp_path):
    """Console receives a success message after Linux shortcut creation."""
    console = MagicMock()

    with patch("fsaudit.shortcut.Path.home", return_value=tmp_path):
        _create_linux_shortcut(Path("/usr/bin/fsaudit-tui"), console=console)

    console.print.assert_called_once()
    msg = console.print.call_args[0][0]
    assert "green" in msg.lower() or "[green]" in msg


def test_create_shortcut_linux_returns_false_on_error(tmp_path):
    """Returns False when writing the .desktop file raises an exception."""
    console = MagicMock()

    with patch("fsaudit.shortcut.Path.home", return_value=tmp_path), \
         patch("pathlib.Path.write_text", side_effect=OSError("permission denied")):
        result = _create_linux_shortcut(Path("/usr/bin/fsaudit-tui"), console=console)

    assert result is False
    console.print.assert_called_once()
    msg = console.print.call_args[0][0]
    assert "red" in msg.lower() or "[red]" in msg


# ---------------------------------------------------------------------------
# _create_windows_shortcut
# ---------------------------------------------------------------------------


def test_create_shortcut_windows_runs_cscript(tmp_path):
    """On Windows, creates a temp .vbs file and runs cscript."""
    desktop = tmp_path / "Desktop"
    desktop.mkdir()

    with patch("fsaudit.shortcut.Path.home", return_value=tmp_path), \
         patch("fsaudit.shortcut.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        result = _create_windows_shortcut(Path(r"C:\Scripts\fsaudit-tui.exe"))

    assert result is True
    mock_run.assert_called_once()
    cmd = mock_run.call_args[0][0]
    assert cmd[0] == "cscript"
    assert cmd[1] == "//nologo"
    assert cmd[2].endswith(".vbs")


def test_create_shortcut_windows_vbs_content_includes_target(tmp_path):
    """The generated VBS script references the correct TargetPath."""
    desktop = tmp_path / "Desktop"
    desktop.mkdir()
    captured: list[str] = []

    # Use a real temp file but intercept the write call to capture content
    real_ntf = tempfile.NamedTemporaryFile

    def fake_ntf(**kwargs):
        # Write to a StringIO buffer AND a real temp file so we can capture content
        real = real_ntf(**kwargs)
        original_write = real.write

        def capturing_write(data):
            captured.append(data)
            return original_write(data)

        real.write = capturing_write
        return real

    tui_path = Path(r"C:\Scripts\fsaudit-tui.exe")

    with patch("fsaudit.shortcut.Path.home", return_value=tmp_path), \
         patch("fsaudit.shortcut.subprocess.run") as mock_run, \
         patch("fsaudit.shortcut.tempfile.NamedTemporaryFile", side_effect=fake_ntf):
        mock_run.return_value = MagicMock(returncode=0)
        _create_windows_shortcut(tui_path)

    assert captured, "VBS content should have been written"
    combined = "".join(captured)
    assert str(tui_path) in combined
    assert "CreateShortcut" in combined


def test_create_shortcut_windows_returns_false_on_cscript_error(tmp_path):
    """Returns False when cscript raises CalledProcessError."""
    desktop = tmp_path / "Desktop"
    desktop.mkdir()
    console = MagicMock()

    with patch("fsaudit.shortcut.Path.home", return_value=tmp_path), \
         patch("fsaudit.shortcut.subprocess.run",
               side_effect=subprocess.CalledProcessError(1, "cscript")):
        result = _create_windows_shortcut(
            Path(r"C:\Scripts\fsaudit-tui.exe"), console=console
        )

    assert result is False
    console.print.assert_called_once()


# ---------------------------------------------------------------------------
# _create_macos_shortcut
# ---------------------------------------------------------------------------


def test_create_macos_shortcut_returns_false():
    """macOS shortcut creation returns False (not supported)."""
    result = _create_macos_shortcut(Path("/usr/local/bin/fsaudit-tui"))
    assert result is False


def test_create_macos_shortcut_prints_instructions():
    """macOS shortcut creation prints guidance to console."""
    console = MagicMock()
    _create_macos_shortcut(Path("/usr/local/bin/fsaudit-tui"), console=console)
    assert console.print.call_count >= 1


# ---------------------------------------------------------------------------
# create_shortcut (dispatcher)
# ---------------------------------------------------------------------------


def test_create_shortcut_dispatches_to_linux(tmp_path):
    """On Linux, create_shortcut delegates to _create_linux_shortcut."""
    with patch("fsaudit.shortcut.platform.system", return_value="Linux"), \
         patch("fsaudit.shortcut._create_linux_shortcut", return_value=True) as mock_linux, \
         patch("fsaudit.shortcut._get_tui_executable", return_value=Path("fsaudit-tui")):
        result = create_shortcut()

    mock_linux.assert_called_once()
    assert result is True


def test_create_shortcut_dispatches_to_windows(tmp_path):
    """On Windows, create_shortcut delegates to _create_windows_shortcut."""
    with patch("fsaudit.shortcut.platform.system", return_value="Windows"), \
         patch("fsaudit.shortcut._create_windows_shortcut", return_value=True) as mock_win, \
         patch("fsaudit.shortcut._get_tui_executable", return_value=Path("fsaudit-tui")):
        result = create_shortcut()

    mock_win.assert_called_once()
    assert result is True


def test_create_shortcut_dispatches_to_macos(tmp_path):
    """On Darwin, create_shortcut delegates to _create_macos_shortcut."""
    with patch("fsaudit.shortcut.platform.system", return_value="Darwin"), \
         patch("fsaudit.shortcut._create_macos_shortcut", return_value=False) as mock_mac, \
         patch("fsaudit.shortcut._get_tui_executable", return_value=Path("fsaudit-tui")):
        result = create_shortcut()

    mock_mac.assert_called_once()
    assert result is False


def test_create_shortcut_unsupported_os_prints_warning():
    """Unsupported OS prints a warning and returns False."""
    console = MagicMock()

    with patch("fsaudit.shortcut.platform.system", return_value="FreeBSD"), \
         patch("fsaudit.shortcut._get_tui_executable", return_value=Path("fsaudit-tui")):
        result = create_shortcut(console=console)

    assert result is False
    console.print.assert_called_once()
    msg = console.print.call_args[0][0]
    assert "FreeBSD" in msg


def test_create_shortcut_returns_true_on_success():
    """Returns True when the platform-specific function succeeds."""
    with patch("fsaudit.shortcut.platform.system", return_value="Linux"), \
         patch("fsaudit.shortcut._create_linux_shortcut", return_value=True), \
         patch("fsaudit.shortcut._get_tui_executable", return_value=Path("fsaudit-tui")):
        assert create_shortcut() is True


def test_create_shortcut_returns_false_on_error():
    """Returns False when the platform-specific function fails."""
    with patch("fsaudit.shortcut.platform.system", return_value="Linux"), \
         patch("fsaudit.shortcut._create_linux_shortcut", return_value=False), \
         patch("fsaudit.shortcut._get_tui_executable", return_value=Path("fsaudit-tui")):
        assert create_shortcut() is False
