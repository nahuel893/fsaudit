"""Tests for logging_config module."""

import logging
from pathlib import Path

from fsaudit.logging_config import setup_logging


class TestSetupLogging:
    """REQ-PRJ-06: Logging configuration module."""

    def setup_method(self) -> None:
        """Reset the fsaudit logger between tests to avoid handler accumulation."""
        logger = logging.getLogger("fsaudit")
        logger.handlers.clear()
        logger.setLevel(logging.WARNING)

    def test_returns_logger(self) -> None:
        """setup_logging returns a Logger instance."""
        logger = setup_logging()
        assert isinstance(logger, logging.Logger)
        assert logger.name == "fsaudit"

    def test_accepts_level_parameter(self) -> None:
        """PRJ-06b: Accepts level='DEBUG' and sets it."""
        logger = setup_logging(level="DEBUG")
        assert logger.level == logging.DEBUG

    def test_console_handler_added(self) -> None:
        """PRJ-06c: A StreamHandler (console) is always added."""
        logger = setup_logging()
        stream_handlers = [
            h for h in logger.handlers if isinstance(h, logging.StreamHandler)
            and not isinstance(h, logging.FileHandler)
        ]
        assert len(stream_handlers) >= 1

    def test_file_handler_when_log_file_provided(self, tmp_path: Path) -> None:
        """PRJ-06c: FileHandler added when log_file is given."""
        log_file = tmp_path / "test.log"
        logger = setup_logging(log_file=log_file)

        file_handlers = [
            h for h in logger.handlers if isinstance(h, logging.FileHandler)
        ]
        assert len(file_handlers) == 1

    def test_log_message_written_to_file(self, tmp_path: Path) -> None:
        """PRJ-06c: Log message appears in the specified log file."""
        log_file = tmp_path / "test.log"
        logger = setup_logging(level="DEBUG", log_file=log_file)
        logger.info("test message")

        # Flush handlers
        for handler in logger.handlers:
            handler.flush()

        content = log_file.read_text()
        assert "test message" in content

    def test_no_file_handler_when_no_log_file(self) -> None:
        """No FileHandler when log_file is not provided."""
        logger = setup_logging()
        file_handlers = [
            h for h in logger.handlers if isinstance(h, logging.FileHandler)
        ]
        assert len(file_handlers) == 0
