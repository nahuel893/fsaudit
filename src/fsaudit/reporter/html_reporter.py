"""HTML report generator using Jinja2 templates."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from jinja2 import Environment, PackageLoader, select_autoescape

from fsaudit.analyzer.metrics import AnalysisResult
from fsaudit.reporter.base import BaseReporter
from fsaudit.scanner.models import FileRecord

# Maximum penalty weight — used for bar scaling (sum of all weights = 100)
_MAX_PENALTY_WEIGHT = 100.0


class HtmlReporter(BaseReporter):
    """Generate a self-contained HTML audit report.

    Args:
        max_rows: Maximum table rows per section before truncation notice
            is shown. Defaults to 500.
    """

    def __init__(self, max_rows: int = 500) -> None:
        self.max_rows = max_rows

    def generate(
        self,
        records: list[FileRecord],
        analysis: AnalysisResult,
        output_path: Path,
    ) -> Path:
        """Render and write the HTML report.

        Args:
            records: Classified file records.
            analysis: Pre-computed analysis metrics.
            output_path: Destination ``.html`` file. Parent dir must exist.

        Returns:
            ``output_path`` after writing.
        """
        env = Environment(
            loader=PackageLoader("fsaudit.reporter", "templates"),
            autoescape=select_autoescape(["html"]),
        )
        env.filters["format_int"] = lambda v: f"{v:,}"
        env.filters["mb"] = lambda v: f"{v / 1048576:.2f}"

        template = env.get_template("report.html")

        score = analysis.health_score
        if score >= 80:
            health_color = "#198754"
        elif score >= 60:
            health_color = "#ffc107"
        else:
            health_color = "#dc3545"

        html = template.render(
            root_path=str(getattr(analysis, "root_path", "/")),
            generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            analysis=analysis,
            records=records,
            max_rows=self.max_rows,
            health_color=health_color,
            max_penalty_weight=_MAX_PENALTY_WEIGHT,
        )

        output_path = Path(output_path)
        output_path.write_text(html, encoding="utf-8")
        return output_path
