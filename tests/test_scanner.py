"""Integration tests for fsaudit.scanner.scanner.FileScanner."""

import os
import sys
from pathlib import Path

import pytest

from fsaudit.scanner.models import ScanResult
from fsaudit.scanner.scanner import FileScanner


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def flat_tree(tmp_path: Path) -> Path:
    """Flat directory with two files."""
    (tmp_path / "a.txt").write_text("hello")
    (tmp_path / "b.py").write_text("print(1)")
    return tmp_path


@pytest.fixture()
def nested_tree(tmp_path: Path) -> Path:
    """Tree with files at multiple depths.

    Structure::

        root/
        ├── root_file.txt
        ├── sub1/
        │   ├── sub1_file.txt
        │   └── sub2/
        │       ├── sub2_file.txt
        │       └── sub3/
        │           └── deep.txt
        └── empty_dir/
    """
    (tmp_path / "root_file.txt").write_text("r")
    sub1 = tmp_path / "sub1"
    sub1.mkdir()
    (sub1 / "sub1_file.txt").write_text("s1")
    sub2 = sub1 / "sub2"
    sub2.mkdir()
    (sub2 / "sub2_file.txt").write_text("s2")
    sub3 = sub2 / "sub3"
    sub3.mkdir()
    (sub3 / "deep.txt").write_text("d")
    (tmp_path / "empty_dir").mkdir()
    return tmp_path


# ===================================================================
# Task 5.1 — Basic flat directory scan
# ===================================================================


class TestBasicScan:
    """REQ-SCN-01: flat directory."""

    def test_flat_directory_file_count(self, flat_tree: Path) -> None:
        result = FileScanner().scan(flat_tree)
        assert len(result.files) == 2

    def test_flat_directory_depth_zero(self, flat_tree: Path) -> None:
        result = FileScanner().scan(flat_tree)
        for fr in result.files:
            assert fr.depth == 0

    def test_root_path_is_absolute(self, flat_tree: Path) -> None:
        result = FileScanner().scan(flat_tree)
        assert result.root_path == Path(os.path.abspath(flat_tree))


# ===================================================================
# Task 5.2 — Nested directory depth computation
# ===================================================================


class TestNestedDepth:
    """REQ-SCN-01 / REQ-SCN-02: nested directories."""

    def test_depth_computation(self, nested_tree: Path) -> None:
        result = FileScanner().scan(nested_tree)
        by_name = {fr.name: fr for fr in result.files}
        assert by_name["root_file.txt"].depth == 0
        assert by_name["sub1_file.txt"].depth == 1
        assert by_name["sub2_file.txt"].depth == 2
        assert by_name["deep.txt"].depth == 3

    def test_parent_dir_field(self, nested_tree: Path) -> None:
        result = FileScanner().scan(nested_tree)
        by_name = {fr.name: fr for fr in result.files}
        assert by_name["sub1_file.txt"].parent_dir == str(nested_tree / "sub1")


# ===================================================================
# Task 5.3 — Extension normalisation
# ===================================================================


class TestExtensionNormalization:
    """REQ-SCN-02: extension handling."""

    def test_uppercase_extension_lowered(self, tmp_path: Path) -> None:
        (tmp_path / "REPORT.PDF").write_text("pdf content")
        result = FileScanner().scan(tmp_path)
        assert result.files[0].extension == ".pdf"
        assert result.files[0].name == "REPORT.PDF"

    def test_no_extension(self, tmp_path: Path) -> None:
        (tmp_path / "Makefile").write_text("")
        result = FileScanner().scan(tmp_path)
        assert result.files[0].extension == ""


# ===================================================================
# Task 5.4 — Exclusion patterns
# ===================================================================


class TestExclusion:
    """REQ-SCN-04 / REQ-ERR-06: exclusion patterns."""

    def test_exclude_directory_pruned(self, tmp_path: Path) -> None:
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        for i in range(5):
            (git_dir / f"obj{i}").write_text("x")
        (tmp_path / "app.py").write_text("main")

        result = FileScanner(exclude_patterns=[".git"]).scan(tmp_path)
        assert len(result.files) == 1
        assert all(".git" not in str(fr.path) for fr in result.files)

    def test_exclude_file_glob(self, tmp_path: Path) -> None:
        (tmp_path / "app.py").write_text("code")
        (tmp_path / "app.pyc").write_text("bytecode")
        (tmp_path / "data.csv").write_text("1,2,3")

        result = FileScanner(exclude_patterns=["*.pyc"]).scan(tmp_path)
        names = {fr.name for fr in result.files}
        assert names == {"app.py", "data.csv"}

    def test_exclude_matches_basename_only(self, tmp_path: Path) -> None:
        """node_modules dir excluded, but node_modules_info.txt is NOT."""
        nm = tmp_path / "node_modules"
        nm.mkdir()
        (nm / "pkg.json").write_text("{}")
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "node_modules_info.txt").write_text("info")

        result = FileScanner(exclude_patterns=["node_modules"]).scan(tmp_path)
        names = {fr.name for fr in result.files}
        assert "node_modules_info.txt" in names
        assert "pkg.json" not in names


# ===================================================================
# Task 5.5 — Depth limiting
# ===================================================================


class TestDepthLimiting:
    """REQ-SCN-05 / REQ-ERR-05: depth limiting."""

    def test_max_depth_one(self, nested_tree: Path) -> None:
        result = FileScanner(max_depth=1).scan(nested_tree)
        for fr in result.files:
            assert fr.depth <= 1
        names = {fr.name for fr in result.files}
        assert "root_file.txt" in names
        assert "sub1_file.txt" in names
        assert "deep.txt" not in names

    def test_max_depth_zero(self, nested_tree: Path) -> None:
        result = FileScanner(max_depth=0).scan(nested_tree)
        for fr in result.files:
            assert fr.depth == 0
        assert len(result.files) == 1  # only root_file.txt

    def test_no_depth_limit(self, nested_tree: Path) -> None:
        result = FileScanner(max_depth=None).scan(nested_tree)
        assert len(result.files) == 4


# ===================================================================
# Task 5.6 — Empty directory detection
# ===================================================================


class TestEmptyDirectories:
    """REQ-SCN-03: empty directory records."""

    def test_empty_dir_produces_record(self, nested_tree: Path) -> None:
        result = FileScanner().scan(nested_tree)
        dir_paths = {str(d.path) for d in result.directories}
        assert str(nested_tree / "empty_dir") in dir_paths

    def test_non_empty_dir_no_record(self, nested_tree: Path) -> None:
        result = FileScanner().scan(nested_tree)
        dir_paths = {str(d.path) for d in result.directories}
        assert str(nested_tree / "sub1") not in dir_paths

    def test_empty_dir_depth(self, nested_tree: Path) -> None:
        result = FileScanner().scan(nested_tree)
        for d in result.directories:
            if "empty_dir" in str(d.path):
                assert d.depth == 1


# ===================================================================
# Task 5.7 — PermissionError resilience
# ===================================================================


@pytest.mark.skipif(sys.platform == "win32", reason="chmod not reliable on Windows")
class TestPermissionErrors:
    """REQ-ERR-01 / REQ-ERR-02: errors collected, scan continues."""

    def test_permission_denied_file(self, tmp_path: Path) -> None:
        """Restrict a subdirectory so its files cannot be stat'd."""
        restricted = tmp_path / "noaccess"
        restricted.mkdir()
        (restricted / "secret.txt").write_text("nope")
        # Remove all perms on the directory so stat of files inside fails.
        restricted.chmod(0o000)

        ok = tmp_path / "ok.txt"
        ok.write_text("fine")

        try:
            result = FileScanner().scan(tmp_path)
            # ok.txt should succeed; contents of noaccess/ are unreachable.
            names = {fr.name for fr in result.files}
            assert "ok.txt" in names
            assert "secret.txt" not in names
            assert any("noaccess" in e for e in result.errors)
        finally:
            restricted.chmod(0o755)

    def test_permission_denied_directory(self, tmp_path: Path) -> None:
        restricted = tmp_path / "restricted"
        restricted.mkdir()
        (restricted / "inside.txt").write_text("x")
        restricted.chmod(0o000)

        ok_dir = tmp_path / "ok_dir"
        ok_dir.mkdir()
        (ok_dir / "visible.txt").write_text("y")

        try:
            result = FileScanner().scan(tmp_path)
            assert any("restricted" in e for e in result.errors)
            # Sibling directory was still scanned.
            names = {fr.name for fr in result.files}
            assert "visible.txt" in names
        finally:
            restricted.chmod(0o755)


# ===================================================================
# Task 5.8 — Symlink cycle detection
# ===================================================================


@pytest.mark.skipif(sys.platform == "win32", reason="Symlinks need privileges on Windows")
class TestSymlinkCycles:
    """REQ-ERR-03: symlink handling."""

    def test_symlinks_not_followed_by_default(self, tmp_path: Path) -> None:
        target = tmp_path / "target"
        target.mkdir()
        (target / "inside.txt").write_text("x")
        link = tmp_path / "link"
        link.symlink_to(target)

        result = FileScanner(follow_symlinks=False).scan(tmp_path)
        # inside.txt found once via target/, NOT again via link/
        names = [fr.name for fr in result.files]
        assert names.count("inside.txt") == 1

    def test_symlink_cycle_detected(self, tmp_path: Path) -> None:
        sub = tmp_path / "a"
        sub.mkdir()
        (sub / "file.txt").write_text("x")
        loop = sub / "loop"
        loop.symlink_to(tmp_path)

        result = FileScanner(follow_symlinks=True).scan(tmp_path)
        # Scan must complete (no infinite loop).
        assert isinstance(result, ScanResult)
        # Cycle should appear in errors.
        assert any("cycle" in e.lower() for e in result.errors)

    def test_valid_symlink_followed(self, tmp_path: Path) -> None:
        data = tmp_path / "data"
        data.mkdir()
        (data / "file.txt").write_text("content")
        link = tmp_path / "link"
        link.symlink_to(data)

        result = FileScanner(follow_symlinks=True).scan(tmp_path)
        names = [fr.name for fr in result.files]
        # file.txt reachable via data/ and via link/ (same realpath → only once after cycle detection)
        assert "file.txt" in names


# ===================================================================
# Task 5.9 — Hidden file detection
# ===================================================================


class TestHiddenFiles:
    """REQ-PLT-02 integration: is_hidden flag on FileRecord."""

    def test_dotfile_is_hidden(self, tmp_path: Path) -> None:
        (tmp_path / ".hidden").write_text("secret")
        (tmp_path / "visible.txt").write_text("hi")

        result = FileScanner().scan(tmp_path)
        by_name = {fr.name: fr for fr in result.files}
        assert by_name[".hidden"].is_hidden is True
        assert by_name["visible.txt"].is_hidden is False


# ===================================================================
# Task 5.10 — ScanResult structure
# ===================================================================


class TestScanResultStructure:
    """REQ-SCN-06: complete result."""

    def test_all_fields_populated(self, nested_tree: Path) -> None:
        result = FileScanner().scan(nested_tree)
        assert isinstance(result.files, list)
        assert isinstance(result.directories, list)
        assert isinstance(result.errors, list)
        assert result.root_path == Path(os.path.abspath(nested_tree))

    def test_result_is_frozen(self, flat_tree: Path) -> None:
        result = FileScanner().scan(flat_tree)
        with pytest.raises(AttributeError):
            result.root_path = Path("/nope")  # type: ignore[misc]
