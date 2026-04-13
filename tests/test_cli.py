"""Tests for the fsaudit CLI entry point."""

from __future__ import annotations

from datetime import datetime
from io import StringIO
from pathlib import Path

import pytest
from rich.console import Console

from fsaudit.cli import build_parser, main


class TestBuildParser:
    """Tests for build_parser() argument definitions."""

    def test_path_is_required(self) -> None:
        # --path is enforced at main() level (not parser), so that --create-shortcut
        # can work without it. Running main() with no args and no --create-shortcut
        # must return exit code 1.
        result = main([])
        assert result == 1

    def test_defaults(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["--path", "/tmp"])
        assert args.path == "/tmp"
        assert args.output_dir is None
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

    def test_default_output_dir(self, tmp_tree: Path) -> None:
        """When --output-dir is omitted, report goes to Home (Linux) or Desktop (Windows)."""
        result = main(["--path", str(tmp_tree)])
        assert result == 0
        date_str = datetime.now().strftime("%Y-%m-%d")
        expected_name = f"{tmp_tree.name}_audit_{date_str}.xlsx"
        from fsaudit.cli import _default_output_dir
        assert (_default_output_dir() / expected_name).exists()

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


class TestRichProgressCallback:
    """Task 2B.3 — scan uses on_file callback for progress reporting."""

    def test_cli_scan_uses_progress_callback(self, tmp_tree: Path) -> None:
        """FileScanner.scan is called with on_file= kwarg."""
        from unittest.mock import patch, MagicMock
        from fsaudit.scanner.scanner import FileScanner
        from fsaudit.scanner.models import ScanResult

        # Build a minimal real ScanResult using actual scanner to avoid complex mocking
        real_result = FileScanner().scan(tmp_tree)

        with patch.object(FileScanner, "scan", wraps=FileScanner().scan) as mock_scan:
            # Replace with a simpler approach: patch the class method
            pass

        # Simpler: just check that scan is called with on_file keyword
        scan_calls: list[dict] = []
        original_scan = FileScanner.scan

        def capturing_scan(self_inner, root, *, on_file=None):
            scan_calls.append({"on_file": on_file})
            return original_scan(self_inner, root, on_file=on_file)

        with patch.object(FileScanner, "scan", capturing_scan):
            buf = StringIO()
            result = main(
                ["--path", str(tmp_tree), "--output-dir", str(tmp_tree)],
                _console=Console(file=buf, highlight=False),
            )

        assert result == 0
        assert len(scan_calls) == 1, "scan() should have been called once"
        assert scan_calls[0]["on_file"] is not None, "on_file callback must be passed to scan()"


class TestRichConsoleInjection:
    """Task 2B.2 — rich Console injection into main()."""

    def test_main_accepts_console_injection(self, tmp_tree: Path) -> None:
        """main() accepts _console= kwarg and returns 0."""
        buf = StringIO()
        console = Console(file=buf, highlight=False)
        result = main(
            ["--path", str(tmp_tree), "--output-dir", str(tmp_tree)],
            _console=console,
        )
        assert result == 0

    def test_main_no_bare_print(self) -> None:
        """cli.py must contain zero bare print( calls after the migration."""
        import ast
        from pathlib import Path as P

        src = P("/home/nh/fsaudit/src/fsaudit/cli.py").read_text()
        tree = ast.parse(src)

        bare_prints = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "print"
        ]
        assert bare_prints == [], (
            f"Found {len(bare_prints)} bare print() call(s) in cli.py at lines "
            + str([n.lineno for n in bare_prints])
        )


class TestFormatFlag:
    """Task 2B.5 — --format flag and HTML output."""

    def test_cli_format_flag_accepted_excel(self) -> None:
        """Parser accepts --format excel."""
        parser = build_parser()
        args = parser.parse_args(["--path", "/tmp", "--format", "excel"])
        assert args.format == "excel"

    def test_cli_format_flag_accepted_html(self) -> None:
        """Parser accepts --format html."""
        parser = build_parser()
        args = parser.parse_args(["--path", "/tmp", "--format", "html"])
        assert args.format == "html"

    def test_cli_format_default_is_excel(self) -> None:
        """--format defaults to 'excel'."""
        parser = build_parser()
        args = parser.parse_args(["--path", "/tmp"])
        assert args.format == "excel"

    def test_cli_format_html_creates_html_file(self, tmp_tree: Path) -> None:
        """Running with --format html produces an .html output file."""
        result = main([
            "--path", str(tmp_tree),
            "--output-dir", str(tmp_tree),
            "--format", "html",
        ])
        assert result == 0
        html_files = list(tmp_tree.glob("*.html"))
        assert len(html_files) == 1, f"Expected one .html file, got: {html_files}"

    def test_cli_html_filename_has_html_extension(self, tmp_tree: Path) -> None:
        """HTML output file has .html extension."""
        from datetime import datetime as dt
        main([
            "--path", str(tmp_tree),
            "--output-dir", str(tmp_tree),
            "--format", "html",
        ])
        date_str = dt.now().strftime("%Y-%m-%d")
        expected = tmp_tree / f"{tmp_tree.name}_audit_{date_str}.html"
        assert expected.exists(), f"Expected {expected} to exist"


class TestHashDuplicatesCLI:
    """Tests for --hash-duplicates CLI flag (Task 2A.4)."""

    def test_cli_hash_duplicates_flag_accepted(self) -> None:
        """Parser accepts --hash-duplicates without error."""
        from fsaudit.cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["--path", "/tmp", "--hash-duplicates"])
        assert args.hash_duplicates is True

    def test_cli_hash_duplicates_default_false(self) -> None:
        """--hash-duplicates defaults to False."""
        from fsaudit.cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["--path", "/tmp"])
        assert args.hash_duplicates is False

    def test_cli_hash_duplicates_passed_to_analyze(self, tmp_path: Path) -> None:
        """When --hash-duplicates is set, analyze() is called with hash_duplicates=True."""
        from unittest.mock import patch, MagicMock
        from fsaudit.analyzer.metrics import AnalysisResult

        dummy_result = AnalysisResult()

        with patch("fsaudit.cli.analyze", return_value=dummy_result) as mock_analyze, \
             patch("fsaudit.cli.ExcelReporter") as mock_reporter:
            mock_reporter.return_value.generate.return_value = None
            result = main([
                "--path", str(tmp_path),
                "--output-dir", str(tmp_path),
                "--hash-duplicates",
            ])

        assert result == 0
        call_kwargs = mock_analyze.call_args.kwargs
        assert call_kwargs.get("hash_duplicates") is True


# ---------------------------------------------------------------------------
# Task 2D.4: --save, --db, --history, --diff flags
# ---------------------------------------------------------------------------

class TestPersistenceFlags:
    """Tests for CLI persistence flags (Task 2D.4)."""

    def test_cli_save_flag_accepted(self) -> None:
        """Parser recognizes --save."""
        parser = build_parser()
        args = parser.parse_args(["--path", "/tmp", "--save"])
        assert args.save is True

    def test_cli_db_flag_accepted(self) -> None:
        """Parser recognizes --db with string argument."""
        parser = build_parser()
        args = parser.parse_args(["--path", "/tmp", "--db", "/tmp/test.db"])
        assert args.db == "/tmp/test.db"

    def test_cli_history_flag_accepted(self) -> None:
        """Parser recognizes --history."""
        parser = build_parser()
        args = parser.parse_args(["--path", "/tmp", "--history"])
        assert args.history is True

    def test_cli_diff_flag_accepted(self) -> None:
        """Parser recognizes --diff with int argument."""
        parser = build_parser()
        args = parser.parse_args(["--path", "/tmp", "--diff", "42"])
        assert args.diff == 42

    def test_cli_save_creates_db(self, tmp_path: Path, tmp_tree: Path) -> None:
        """Integration: main with --save --db creates the db file."""
        db_path = tmp_path / "test.db"
        result = main([
            "--path", str(tmp_tree),
            "--output-dir", str(tmp_tree),
            "--save",
            "--db", str(db_path),
        ])
        assert result == 0
        assert db_path.exists()

    def test_cli_no_save_no_db(self, tmp_path: Path, tmp_tree: Path) -> None:
        """main without --save does not create a db file."""
        db_path = tmp_path / "test.db"
        result = main([
            "--path", str(tmp_tree),
            "--output-dir", str(tmp_tree),
            "--db", str(db_path),
        ])
        assert result == 0
        assert not db_path.exists()

    def test_cli_history_empty(self, tmp_path: Path) -> None:
        """--history on non-existent db exits 0 and prints 'No runs recorded'."""
        from io import StringIO
        from rich.console import Console

        db_path = tmp_path / "nonexistent.db"
        buf = StringIO()
        console = Console(file=buf, highlight=False)
        result = main(
            ["--path", "/tmp", "--history", "--db", str(db_path)],
            _console=console,
        )
        assert result == 0
        output = buf.getvalue()
        assert "No runs recorded" in output


# ---------------------------------------------------------------------------
# Task 2D.5: --save-files, --query flags
# ---------------------------------------------------------------------------

class TestQueryFlags:
    """Tests for --save-files and --query CLI flags (Task 2D.5)."""

    def test_cli_save_files_flag_accepted(self) -> None:
        """Parser recognizes --save-files."""
        parser = build_parser()
        args = parser.parse_args(["--path", "/tmp", "--save-files"])
        assert args.save_files is True

    def test_cli_query_flag_accepted(self) -> None:
        """Parser recognizes --query with string argument."""
        parser = build_parser()
        args = parser.parse_args(["--path", "/tmp", "--query", "SELECT id FROM runs"])
        assert args.query == "SELECT id FROM runs"

    def test_cli_query_non_select_exits_1(self, tmp_path: Path) -> None:
        """--query with non-SELECT SQL exits with code 1."""
        db_path = tmp_path / "test.db"
        result = main([
            "--path", "/tmp",
            "--query", "DELETE FROM runs",
            "--db", str(db_path),
        ])
        assert result == 1


# ---------------------------------------------------------------------------
# Task file-author-metadata: --extract-author flag
# ---------------------------------------------------------------------------

class TestExtractAuthorFlag:
    """Tests for --extract-author CLI flag."""

    def test_cli_extract_author_flag_accepted(self) -> None:
        """Parser accepts --extract-author as a boolean store_true flag."""
        parser = build_parser()
        args = parser.parse_args(["--path", "/tmp", "--extract-author"])
        assert args.extract_author is True

    def test_cli_extract_author_default_false(self) -> None:
        """--extract-author defaults to False when not provided."""
        parser = build_parser()
        args = parser.parse_args(["--path", "/tmp"])
        assert args.extract_author is False

    def test_cli_extract_author_calls_enricher(self, tmp_path: Path) -> None:
        """When --extract-author is given, enrich_authors() is called."""
        from unittest.mock import patch, MagicMock
        from fsaudit.analyzer.metrics import AnalysisResult

        dummy_result = AnalysisResult()

        with patch("fsaudit.cli.analyze", return_value=dummy_result), \
             patch("fsaudit.cli.ExcelReporter") as mock_reporter, \
             patch("fsaudit.enricher.enrich_authors", return_value=[]) as mock_enrich:
            mock_reporter.return_value.generate.return_value = None
            result = main([
                "--path", str(tmp_path),
                "--output-dir", str(tmp_path),
                "--extract-author",
            ])

        assert result == 0
        mock_enrich.assert_called_once()

    def test_cli_no_extract_author_skips_enricher(self, tmp_path: Path) -> None:
        """When --extract-author is absent, enrich_authors() is NOT called."""
        from unittest.mock import patch, MagicMock
        from fsaudit.analyzer.metrics import AnalysisResult

        dummy_result = AnalysisResult()

        with patch("fsaudit.cli.analyze", return_value=dummy_result), \
             patch("fsaudit.cli.ExcelReporter") as mock_reporter, \
             patch("fsaudit.enricher.enrich_authors") as mock_enrich:
            mock_reporter.return_value.generate.return_value = None
            result = main([
                "--path", str(tmp_path),
                "--output-dir", str(tmp_path),
            ])

        assert result == 0
        mock_enrich.assert_not_called()


# ---------------------------------------------------------------------------
# --create-shortcut flag
# ---------------------------------------------------------------------------

class TestCreateShortcutFlag:
    """Tests for --create-shortcut CLI flag."""

    def test_cli_create_shortcut_flag_accepted(self) -> None:
        """Parser accepts --create-shortcut without error."""
        args = build_parser().parse_args(["--create-shortcut"])
        assert args.create_shortcut is True

    def test_cli_create_shortcut_does_not_require_path(self) -> None:
        """--create-shortcut works without --path (no SystemExit)."""
        args = build_parser().parse_args(["--create-shortcut"])
        assert args.create_shortcut is True

    def test_cli_create_shortcut_default_false(self) -> None:
        """--create-shortcut defaults to False."""
        args = build_parser().parse_args(["--path", "/tmp"])
        assert args.create_shortcut is False

    def test_cli_create_shortcut_returns_0_on_success(self) -> None:
        """main() returns 0 when create_shortcut() succeeds."""
        from unittest.mock import patch

        with patch("fsaudit.cli.create_shortcut", return_value=True) as mock_sc:
            result = main(["--create-shortcut"])

        assert result == 0
        mock_sc.assert_called_once()

    def test_cli_create_shortcut_returns_1_on_failure(self) -> None:
        """main() returns 1 when create_shortcut() returns False."""
        from unittest.mock import patch

        with patch("fsaudit.cli.create_shortcut", return_value=False):
            result = main(["--create-shortcut"])

        assert result == 1

    def test_cli_create_shortcut_passes_console(self) -> None:
        """create_shortcut() is called with the console instance."""
        from io import StringIO
        from unittest.mock import patch
        from rich.console import Console

        console = Console(file=StringIO(), highlight=False)

        with patch("fsaudit.cli.create_shortcut", return_value=True) as mock_sc:
            main(["--create-shortcut"], _console=console)

        _, kwargs = mock_sc.call_args
        assert "console" in kwargs


# ---------------------------------------------------------------------------
# Auto-update: --update flag and update notification
# ---------------------------------------------------------------------------


class TestCliUpdateFlag:
    """Tests for the --update flag and update notification."""

    def test_cli_update_flag_accepted(self) -> None:
        """--update flag is accepted by the parser without error."""
        from unittest.mock import patch

        with patch("fsaudit.cli.run_update", return_value=True):
            result = main(["--update"])
        assert result == 0

    def test_cli_update_calls_run_update(self) -> None:
        """main(["--update"]) calls run_update() exactly once."""
        from io import StringIO
        from unittest.mock import patch
        from rich.console import Console

        console = Console(file=StringIO(), highlight=False)

        with patch("fsaudit.cli.run_update", return_value=True) as mock_update:
            result = main(["--update"], _console=console)

        mock_update.assert_called_once()
        assert result == 0

    def test_cli_update_returns_1_on_failure(self) -> None:
        """main(["--update"]) returns 1 when run_update() returns False."""
        from unittest.mock import patch

        with patch("fsaudit.cli.run_update", return_value=False):
            result = main(["--update"])
        assert result == 1

    def test_cli_update_flag_default_false(self) -> None:
        """--update defaults to False in parser."""
        parser = build_parser()
        args = parser.parse_args(["--path", "/tmp"])
        assert args.update is False

    def test_cli_shows_notification_when_newer_version(self, tmp_path) -> None:
        """When a newer version is available, main() prints an update notification."""
        from io import StringIO
        from unittest.mock import patch
        from rich.console import Console

        buf = StringIO()
        console = Console(file=buf, highlight=False)

        with patch("fsaudit.cli.check_update", return_value="9.9.9"):
            # Use --history to avoid needing a real path (exits early, still checks update)
            main(["--history"], _console=console)

        output = buf.getvalue()
        assert "9.9.9" in output
        assert "fsaudit --update" in output

    def test_cli_no_notification_when_up_to_date(self, tmp_path) -> None:
        """When no newer version, main() does NOT print an update notification."""
        from io import StringIO
        from unittest.mock import patch
        from rich.console import Console

        buf = StringIO()
        console = Console(file=buf, highlight=False)

        with patch("fsaudit.cli.check_update", return_value=None):
            main(["--history"], _console=console)

        output = buf.getvalue()
        assert "New version available" not in output
