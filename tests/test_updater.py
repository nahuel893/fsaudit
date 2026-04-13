"""Tests for fsaudit.updater — auto-update checker."""

from __future__ import annotations

import json
from io import StringIO
from unittest.mock import MagicMock, patch
from urllib.error import URLError

import pytest

from fsaudit.updater import _is_newer, check_update, run_update


# ---------------------------------------------------------------------------
# _is_newer
# ---------------------------------------------------------------------------


def test_is_newer_true():
    assert _is_newer("1.0.0", "0.9.0") is True


def test_is_newer_false_same():
    assert _is_newer("0.9.0", "0.9.0") is False


def test_is_newer_false_older():
    assert _is_newer("0.8.0", "0.9.0") is False


def test_is_newer_patch():
    assert _is_newer("0.9.1", "0.9.0") is True


def test_is_newer_invalid():
    assert _is_newer("abc", "0.9.0") is False


# ---------------------------------------------------------------------------
# check_update
# ---------------------------------------------------------------------------


def _make_pypi_response(version: str) -> MagicMock:
    """Return a mock context manager that yields a response with PyPI JSON."""
    payload = json.dumps({"info": {"version": version}}).encode()
    mock_resp = MagicMock()
    mock_resp.read.return_value = payload
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    return mock_resp


def test_check_update_returns_version():
    """When PyPI returns a newer version, check_update() returns that version string."""
    mock_resp = _make_pypi_response("1.0.0")
    with patch("fsaudit.updater.urlopen", return_value=mock_resp):
        result = check_update()
    assert result == "1.0.0"


def test_check_update_returns_none_when_current():
    """When PyPI returns the current version (not newer), check_update() returns None."""
    from fsaudit import __version__
    mock_resp = _make_pypi_response(__version__)
    with patch("fsaudit.updater.urlopen", return_value=mock_resp):
        result = check_update()
    assert result is None


def test_check_update_returns_none_on_error():
    """When urlopen raises URLError, check_update() returns None without raising."""
    with patch("fsaudit.updater.urlopen", side_effect=URLError("unreachable")):
        result = check_update()
    assert result is None


def test_check_update_returns_none_on_timeout():
    """When urlopen raises TimeoutError, check_update() returns None without raising."""
    with patch("fsaudit.updater.urlopen", side_effect=TimeoutError("timed out")):
        result = check_update()
    assert result is None


# ---------------------------------------------------------------------------
# run_update
# ---------------------------------------------------------------------------


def test_run_update_success():
    """When pip exits 0, run_update() returns True."""
    mock_result = MagicMock()
    mock_result.returncode = 0
    with patch("fsaudit.updater.subprocess.run", return_value=mock_result):
        assert run_update() is True


def test_run_update_failure():
    """When pip exits non-zero, run_update() returns False."""
    mock_result = MagicMock()
    mock_result.returncode = 1
    mock_result.stderr = "some error"
    with patch("fsaudit.updater.subprocess.run", return_value=mock_result):
        assert run_update() is False


def test_run_update_prints_success_message():
    """run_update() prints a success message via console on success."""
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_console = MagicMock()
    with patch("fsaudit.updater.subprocess.run", return_value=mock_result):
        run_update(console=mock_console)
    mock_console.print.assert_called_once()
    call_args = mock_console.print.call_args[0][0]
    assert "updated successfully" in call_args


def test_run_update_prints_failure_message():
    """run_update() prints a failure message via console on pip failure."""
    mock_result = MagicMock()
    mock_result.returncode = 1
    mock_result.stderr = "pip error details"
    mock_console = MagicMock()
    with patch("fsaudit.updater.subprocess.run", return_value=mock_result):
        run_update(console=mock_console)
    mock_console.print.assert_called_once()
    call_args = mock_console.print.call_args[0][0]
    assert "Update failed" in call_args


def test_run_update_exception_returns_false():
    """When subprocess.run raises, run_update() returns False without raising."""
    with patch("fsaudit.updater.subprocess.run", side_effect=Exception("broken")):
        assert run_update() is False
