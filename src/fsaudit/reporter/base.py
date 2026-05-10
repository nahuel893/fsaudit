"""Abstract base class for all report generators."""

from abc import ABC, abstractmethod
from pathlib import Path

from fsaudit.analyzer.metrics import AnalysisResult
from fsaudit.scanner.models import FileRecord


class BaseReporter(ABC):
    """Abstract reporter contract.

    Subclasses implement ``generate()`` to produce a report file
    from raw scan records and pre-computed analysis metrics.
    """

    @abstractmethod
    def generate(
        self,
        records: list[FileRecord],
        analysis: AnalysisResult,
        output_path: Path,
        *,
        overflow_strategy: str = "shard",
    ) -> Path:
        """Generate report file.

        Args:
            records: Classified file records (one per scanned file).
            analysis: Pre-computed analysis metrics.
            output_path: Destination file path. Parent dir must exist.
            overflow_strategy: How to handle Excel row overflow.
                ``"shard"`` splits into multiple sheets; ``"csv"``
                writes a CSV file instead.  Default ``"shard"``.

        Returns:
            Path to the created report file.
        """
        ...
