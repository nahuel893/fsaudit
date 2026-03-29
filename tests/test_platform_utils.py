"""Unit tests for fsaudit.scanner.platform_utils."""

import os
import stat
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest

import fsaudit.scanner.platform_utils as pu


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_stat(
    st_mtime: float = 1_700_000_000.0,
    st_ctime: float = 1_700_000_000.0,
    st_atime: float = 1_700_000_000.0,
    st_mode: int = 0o100644,
    st_size: int = 100,
    st_birthtime: float | None = None,
    st_file_attributes: int | None = None,
) -> os.stat_result:
    """Build a real-ish stat_result-like object with controllable fields."""
    mock = MagicMock(spec=os.stat_result)
    mock.st_mtime = st_mtime
    mock.st_ctime = st_ctime
    mock.st_atime = st_atime
    mock.st_mode = st_mode
    mock.st_size = st_size

    # Only attach optional attrs when explicitly provided.
    if st_birthtime is not None:
        mock.st_birthtime = st_birthtime
    else:
        # Remove the attribute so hasattr() returns False.
        del mock.st_birthtime

    if st_file_attributes is not None:
        mock.st_file_attributes = st_file_attributes
    else:
        del mock.st_file_attributes

    return mock


# ===================================================================
# Task 4.1 — get_creation_time_safe
# ===================================================================


class TestGetCreationTimeSafe:
    """REQ-PLT-01 scenarios."""

    def test_windows_uses_st_ctime(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(pu, "PLATFORM", "win32")
        ctime = 1_705_276_800.0  # 2024-01-15 00:00 UTC
        sr = _make_stat(st_ctime=ctime, st_mtime=ctime + 86_400)
        result = pu.get_creation_time_safe(sr)
        assert result == datetime.fromtimestamp(ctime)

    def test_linux_uses_min_mtime_ctime(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(pu, "PLATFORM", "linux")
        mtime = 1_708_000_000.0  # earlier
        ctime = 1_709_000_000.0
        sr = _make_stat(st_mtime=mtime, st_ctime=ctime)
        result = pu.get_creation_time_safe(sr)
        assert result == datetime.fromtimestamp(mtime)

    def test_linux_ctime_earlier(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(pu, "PLATFORM", "linux")
        mtime = 1_709_000_000.0
        ctime = 1_708_000_000.0  # earlier
        sr = _make_stat(st_mtime=mtime, st_ctime=ctime)
        result = pu.get_creation_time_safe(sr)
        assert result == datetime.fromtimestamp(ctime)

    def test_darwin_uses_birthtime(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(pu, "PLATFORM", "darwin")
        btime = 1_701_388_800.0  # 2023-12-01
        sr = _make_stat(st_birthtime=btime, st_mtime=btime + 86_400, st_ctime=btime + 86_400)
        result = pu.get_creation_time_safe(sr)
        assert result == datetime.fromtimestamp(btime)

    def test_darwin_fallback_no_birthtime(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(pu, "PLATFORM", "darwin")
        mtime = 1_708_000_000.0
        ctime = 1_709_000_000.0
        sr = _make_stat(st_mtime=mtime, st_ctime=ctime)  # no st_birthtime
        result = pu.get_creation_time_safe(sr)
        assert result == datetime.fromtimestamp(mtime)


# ===================================================================
# Task 4.2 — is_hidden
# ===================================================================


class TestIsHidden:
    """REQ-PLT-02 scenarios."""

    def test_linux_dotfile_hidden(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(pu, "PLATFORM", "linux")
        sr = _make_stat()
        assert pu.is_hidden(".bashrc", sr) is True

    def test_linux_normal_not_hidden(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(pu, "PLATFORM", "linux")
        sr = _make_stat()
        assert pu.is_hidden("readme.md", sr) is False

    def test_darwin_dotfile_hidden(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(pu, "PLATFORM", "darwin")
        sr = _make_stat()
        assert pu.is_hidden(".DS_Store", sr) is True

    def test_win32_file_attribute_hidden(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(pu, "PLATFORM", "win32")
        sr = _make_stat(st_file_attributes=0x2)  # FILE_ATTRIBUTE_HIDDEN
        assert pu.is_hidden("desktop.ini", sr) is True

    def test_win32_no_hidden_attribute(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(pu, "PLATFORM", "win32")
        sr = _make_stat(st_file_attributes=0x20)  # ARCHIVE, not hidden
        assert pu.is_hidden("readme.md", sr) is False

    def test_win32_fallback_dot_prefix(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(pu, "PLATFORM", "win32")
        sr = _make_stat()  # no st_file_attributes
        assert pu.is_hidden(".env", sr) is True

    def test_win32_fallback_not_hidden(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(pu, "PLATFORM", "win32")
        sr = _make_stat()  # no st_file_attributes
        assert pu.is_hidden("app.py", sr) is False


# ===================================================================
# Task 4.3 — get_permissions
# ===================================================================


class TestGetPermissions:
    """REQ-PLT-03 scenarios."""

    def test_linux_755(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(pu, "PLATFORM", "linux")
        sr = _make_stat(st_mode=0o100755)
        assert pu.get_permissions(sr) == "755"

    def test_linux_644(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(pu, "PLATFORM", "linux")
        sr = _make_stat(st_mode=0o100644)
        assert pu.get_permissions(sr) == "644"

    def test_darwin_permissions(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(pu, "PLATFORM", "darwin")
        sr = _make_stat(st_mode=0o100700)
        assert pu.get_permissions(sr) == "700"

    def test_win32_returns_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(pu, "PLATFORM", "win32")
        sr = _make_stat()
        assert pu.get_permissions(sr) is None
