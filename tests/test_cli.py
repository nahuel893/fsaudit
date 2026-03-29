"""Tests for the fsaudit CLI entry point."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from fsaudit.cli import build_parser, main


class TestBuildParser:
    """Tests for build_parser() argument definitions."""

    def test_path_is_required(self) -> None:
        parser = build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args([])

    def test_defaults(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["--path", "/tmp"])
        assert args.path == "/tmp"
        assert args.output_dir == "."
        assert args.depth is None
        assert args.exclude == []
        assert args.min_size == 0
        assert args.inactive_days == 365
        assert args.log_level == "INFO"
        assert args.log_file is None

    def test_exclude_repeatable(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["--path", "/tmp", "--exclude", ".git", "--exclude", "node_modules"])
        assert args.exclude == [".git", "node_modules"]

    def test_log_level_case_insensitive(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["--path", "/tmp", "--log-level", "debug"])
        assert args.log_level == "DEBUG"

    def test_log_level_invalid_rejected(self) -> None:
        parser = build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["--path", "/tmp", "--log-level", "TRACE"])

    def test_all_flags(self) -> None:
        parser = build_parser()
        args = parser.parse_args([
            "--path", "/data",
            "--output-dir", "/reports",
            "--depth", "3",
            "--exclude", "*.pyc",
            "--min-size", "1024",
            "--inactive-days", "90",
            "--log-level", "WARNING",
            "--log-file", "/var/log/fsaudit.log",
        ])
        assert args.path == "/data"
        assert args.output_dir == "/reports"
        assert args.depth == 3
        assert args.exclude == ["*.pyc"]
        assert args.min_size == 1024
        assert args.inactive_days == 90
        assert args.log_level == "WARNING"
        assert args.log_file == "/var/log/fsaudit.log"


class TestMainInvalidPath:
    """Tests for main() input validation."""

    def test_nonexistent_path_returns_1(self) -> None:
        result = main(["--path", "/nonexistent_dir_xyz"])
        assert result == 1

    def test_file_as_path_returns_1(self, tmp_path: Path) -> None:
        f = tmp_path / "afile.txt"
        f.write_text("hi")
        result = main(["--path", str(f)])
        assert result == 1

    def test_invalid_output_dir_returns_1(self, tmp_path: Path) -> None:
        result = main(["--path", str(tmp_path), "--output-dir", "/nonexistent_output_xyz"])
        assert result == 1


class TestMainHappyPath:
    """Tests for main() pipeline execution (end-to-end)."""

    def test_basic_run_returns_0(self, tmp_tree: Path) -> None:
        result = main(["--path", str(tmp_tree), "--output-dir", str(tmp_tree)])
        assert result == 0

    def test_output_file_created(self, tmp_tree: Path) -> None:
        main(["--path", str(tmp_tree), "--output-dir", str(tmp_tree)])
        date_str = datetime.now().strftime("%Y-%m-%d")
        expected_name = f"{tmp_tree.name}_audit_{date_str}.xlsx"
        output_file = tmp_tree / expected_name
        assert output_file.exists(), f"Expected {output_file} to exist"

    def test_output_naming_convention(self, tmp_tree: Path) -> None:
        main(["--path", str(tmp_tree), "--output-dir", str(tmp_tree)])
        date_str = datetime.now().strftime("%Y-%m-%d")
        expected_name = f"{tmp_tree.name}_audit_{date_str}.xlsx"
        output_file = tmp_tree / expected_name
        assert output_file.exists()
        assert output_file.suffix == ".xlsx"

    def test_default_output_dir(self, tmp_tree: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """When --output-dir is omitted, report goes to cwd."""
        monkeypatch.chdir(tmp_tree)
        result = main(["--path", str(tmp_tree)])
        assert result == 0
        date_str = datetime.now().strftime("%Y-%m-%d")
        expected_name = f"{tmp_tree.name}_audit_{date_str}.xlsx"
        assert (tmp_tree / expected_name).exists()

    def test_progress_messages(self, tmp_tree: Path, capsys: pytest.CaptureFixture[str]) -> None:
        main(["--path", str(tmp_tree), "--output-dir", str(tmp_tree)])
        out = capsys.readouterr().out
        assert "Scanning" in out
        assert "Scan complete" in out
        assert "Classifying" in out
        assert "Classification complete" in out
        assert "Analyzing" in out
        assert "Analysis complete" in out
        assert "Generating Excel report" in out
        assert "Report saved" in out


class TestMainMinSize:
    """Tests for --min-size filtering."""

    def test_min_size_filters_small_files(self, tmp_path: Path) -> None:
        # Create files of known sizes
        (tmp_path / "small.txt").write_text("hi")        # 2 bytes
        (tmp_path / "big.txt").write_text("x" * 2000)   # 2000 bytes

        result = main([
            "--path", str(tmp_path),
            "--output-dir", str(tmp_path),
            "--min-size", "1000",
        ])
        assert result == 0


class TestMainCustomOutputDir:
    """Tests for --output-dir flag."""

    def test_report_written_to_custom_dir(self, tmp_tree: Path, tmp_path: Path) -> None:
        output_dir = tmp_path / "reports"
        output_dir.mkdir()
        result = main(["--path", str(tmp_tree), "--output-dir", str(output_dir)])
        assert result == 0
        date_str = datetime.now().strftime("%Y-%m-%d")
        expected_name = f"{tmp_tree.name}_audit_{date_str}.xlsx"
        assert (output_dir / expected_name).exists()


class TestMainExclude:
    """Tests for --exclude flag."""

    def test_exclude_patterns_passed(self, tmp_tree: Path) -> None:
        result = main([
            "--path", str(tmp_tree),
            "--output-dir", str(tmp_tree),
            "--exclude", ".git",
            "--exclude", "node_modules",
        ])
        assert result == 0
