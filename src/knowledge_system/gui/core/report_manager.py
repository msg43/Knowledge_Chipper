"""
Report Manager for GUI

Manages processing reports and results display in the GUI.
"""

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from ...logger import get_logger

logger = get_logger(__name__)


class ProcessingReport:
    """Represents a processing report."""

    def __init__(
        self,
        report_type: str,
        title: str,
        content: str,
        timestamp: datetime | None = None,
    ) -> None:
        self.type = report_type
        self.title = title
        self.content = content
        self.timestamp = timestamp or datetime.now()
        self.file_path: Path | None = None

    def save_to_file(self, output_dir: str | Path) -> Path:
        """Save the report to a file."""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # Create filename with timestamp
        timestamp_str = self.timestamp.strftime("%Y%m%d_%H%M%S")
        filename = f"{self.type}_report_{timestamp_str}.md"
        file_path = output_path / filename

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(f"# {self.title}\n\n")
            f.write(f"Generated: {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write(self.content)

        self.file_path = file_path
        return file_path

    def to_dict(self) -> dict[str, Any]:
        """Convert report to dictionary."""
        return {
            "type": self.type,
            "title": self.title,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "file_path": str(self.file_path) if self.file_path else None,
        }


class ReportManager:
    """Manages processing reports and results."""

    def __init__(self) -> None:
        self.reports: list[ProcessingReport] = []
        self.max_reports = 50  # Keep last 50 reports in memory

    def add_report(
        self, report_type: str, title: str, content: str
    ) -> ProcessingReport:
        """Add a new report."""
        report = ProcessingReport(report_type, title, content)
        self.reports.append(report)

        # Trim old reports
        if len(self.reports) > self.max_reports:
            self.reports = self.reports[-self.max_reports :]

        logger.debug(f"Added report: {title}")
        return report

    def get_reports(self, report_type: str | None = None) -> list[ProcessingReport]:
        """Get reports, optionally filtered by type."""
        if report_type:
            return [r for r in self.reports if r.type == report_type]
        return self.reports.copy()

    def get_latest_report(
        self, report_type: str | None = None
    ) -> ProcessingReport | None:
        """Get the most recent report, optionally filtered by type."""
        reports = self.get_reports(report_type)
        return reports[-1] if reports else None

    def save_report(
        self, report: ProcessingReport, output_dir: str | Path
    ) -> Path:
        """Save a report to file."""
        return report.save_to_file(output_dir)

    def clear_reports(self, report_type: str | None = None):
        """Clear reports, optionally filtered by type."""
        if report_type:
            self.reports = [r for r in self.reports if r.type != report_type]
            logger.info(f"Cleared {report_type} reports")
        else:
            self.reports.clear()
            logger.info("Cleared all reports")

    def generate_summary_report(
        self, include_types: list[str] | None = None
    ) -> ProcessingReport:
        """Generate a summary report of all processing activities."""
        if include_types:
            reports = [r for r in self.reports if r.type in include_types]
        else:
            reports = self.reports

        if not reports:
            content = "No processing reports available."
        else:
            # Group by type
            by_type: dict[str, list[ProcessingReport]] = {}
            for report in reports:
                if report.type not in by_type:
                    by_type[report.type] = []
                by_type[report.type].append(report)

            content_parts = ["## Processing Summary\n"]

            for report_type, type_reports in by_type.items():
                content_parts.append(
                    f"### {report_type.title()} Reports ({len(type_reports)})\n"
                )

                for report in type_reports[-5:]:  # Last 5 of each type
                    timestamp_str = report.timestamp.strftime("%Y-%m-%d %H:%M:%S")
                    content_parts.append(f"- **{report.title}** ({timestamp_str})")
                    if report.file_path:
                        content_parts.append(f"  - File: {report.file_path}")
                    content_parts.append("")

                content_parts.append("")

            content = "\n".join(content_parts)

        return self.add_report("summary", "Processing Summary", content)


# Global report manager instance
_report_manager: ReportManager | None = None


def get_report_manager() -> ReportManager:
    """Get the global report manager instance."""
    global _report_manager
    if _report_manager is None:
        _report_manager = ReportManager()
    return _report_manager
