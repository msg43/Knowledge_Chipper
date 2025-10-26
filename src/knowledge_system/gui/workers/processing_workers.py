"""Enhanced worker threads for background processing operations."""

from pathlib import Path
from typing import Any

from PyQt6.QtCore import QDateTime, QThread, pyqtSignal

from ...logger import get_logger
from ...utils.progress import SummarizationProgress

logger = get_logger(__name__)

# Reports directory for processing outcomes
REPORTS_DIR = Path.home() / ".knowledge_system" / "reports"

# YouTube logs directory for detailed session logs
YOUTUBE_LOGS_DIR = Path.home() / ".knowledge_system" / "logs" / "youtube"


class ProcessingReport:
    """Track and generate processing reports."""

    def __init__(self, operation_type: str) -> None:
        self.operation_type = operation_type
        self.start_time = QDateTime.currentDateTime()
        self.end_time = None
        self.total_files = 0
        self.processed_files = 0
        self.successful_files = []
        self.failed_files = []
        self.skipped_files = []
        self.warnings = []
        self.output_files = []

        # Summarization-specific statistics
        self.summarization_stats = {
            "total_tokens_consumed": 0,
            "total_processing_time": 0.0,
            "longest_input_length": 0,
            "shortest_input_length": float("in"),
            "average_compression_ratio": 0.0,
            "total_input_length": 0,
            "total_summary_length": 0,
            "models_used": set(),
            "providers_used": set(),
            "tokens_per_second": 0.0,
            "file_stats": [],  # Detailed stats per file
        }

    def finish(self) -> None:
        """Mark the report as finished."""
        self.end_time = QDateTime.currentDateTime()

        # Calculate final summarization statistics
        if (
            self.operation_type == "summarization"
            and self.summarization_stats["file_stats"]
        ):
            stats = self.summarization_stats
            if stats["total_input_length"] > 0:
                stats["average_compression_ratio"] = (
                    stats["total_summary_length"] / stats["total_input_length"]
                )
            if stats["total_processing_time"] > 0:
                stats["tokens_per_second"] = (
                    stats["total_tokens_consumed"] / stats["total_processing_time"]
                )
            if stats["shortest_input_length"] == float("in"):
                stats["shortest_input_length"] = 0

    def add_success(
        self,
        filename: str,
        output_file: str | None = None,
        metadata: dict[str, Any] | None = None,
    ):
        """Add a successful file."""
        self.successful_files.append(filename)
        self.processed_files += 1
        if output_file:
            self.output_files.append(output_file)

        # Store detailed file processing information
        if not hasattr(self, "file_details"):
            self.file_details = []

        file_detail = {
            "input_file": filename,
            "output_file": output_file or "Unknown",
            "output_type": (
                metadata.get("output_type", "new_file") if metadata else "new_file"
            ),
            "status": "success",
        }
        self.file_details.append(file_detail)

        # Track summarization statistics
        if self.operation_type == "summarization" and metadata:
            stats = self.summarization_stats
            stats["total_tokens_consumed"] += metadata.get("total_tokens", 0)
            stats["total_processing_time"] += metadata.get("processing_time", 0.0)
            stats["total_input_length"] += metadata.get("input_length", 0)
            stats["total_summary_length"] += metadata.get("summary_length", 0)

            input_length = metadata.get("input_length", 0)
            if input_length > stats["longest_input_length"]:
                stats["longest_input_length"] = input_length
            if input_length < stats["shortest_input_length"]:
                stats["shortest_input_length"] = input_length

            if metadata.get("model"):
                stats["models_used"].add(metadata["model"])
            if metadata.get("provider"):
                stats["providers_used"].add(metadata["provider"])

            # Store detailed file stats
            file_stat = {
                "filename": filename,
                "input_length": metadata.get("input_length", 0),
                "summary_length": metadata.get("summary_length", 0),
                "tokens_consumed": metadata.get("total_tokens", 0),
                "processing_time": metadata.get("processing_time", 0.0),
                "compression_ratio": metadata.get("compression_ratio", 0.0),
                "model": metadata.get("model", "unknown"),
                "provider": metadata.get("provider", "unknown"),
            }
            stats["file_stats"].append(file_stat)

    def add_failure(self, filename: str, error: str):
        """Add a failed file."""
        self.failed_files.append((filename, error))
        self.processed_files += 1

        # Store detailed file processing information
        if not hasattr(self, "file_details"):
            self.file_details = []

        file_detail = {
            "input_file": filename,
            "output_file": "Failed",
            "output_type": "failed",
            "status": "failed",
            "error": error,
        }
        self.file_details.append(file_detail)

    def add_skipped(self, filename: str, reason: str):
        """Add a skipped file."""
        self.skipped_files.append((filename, reason))

    def add_warning(self, message: str):
        """Add a warning message."""
        self.warnings.append(message)

    def get_duration(self) -> str:
        """Get processing duration as string."""
        if self.end_time is None:
            return "In progress..."
        duration = self.start_time.secsTo(self.end_time)
        hours = duration // 3600
        minutes = (duration % 3600) // 60
        seconds = duration % 60
        return (
            f"{hours}h {minutes}m {seconds}s" if hours > 0 else f"{minutes}m {seconds}s"
        )

    def save_report(self) -> Path:
        """Save report to file and return path."""
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)

        timestamp = self.start_time.toString("yyyy-MM-dd_HH-mm-ss")
        report_file = REPORTS_DIR / f"{self.operation_type}_{timestamp}.md"

        with open(report_file, "w", encoding="utf-8") as f:
            f.write(f"# {self.operation_type.title()} Processing Report\n\n")
            f.write(f"**Started:** {self.start_time.toString('yyyy-MM-dd HH:mm:ss')}\n")
            f.write(
                f"**Completed:** {self.end_time.toString('yyyy-MM-dd HH:mm:ss') if self.end_time is not None else 'In progress'}\n"
            )
            f.write(f"**Duration:** {self.get_duration()}\n\n")

            f.write("## Summary\n\n")
            f.write(f"- **Total files:** {self.total_files}\n")
            f.write(f"- **Processed:** {self.processed_files}\n")
            f.write(f"- **Successful:** {len(self.successful_files)}\n")
            f.write(f"- **Failed:** {len(self.failed_files)}\n")
            f.write(f"- **Skipped:** {len(self.skipped_files)}\n\n")

            # Add summarization-specific statistics
            if (
                self.operation_type == "summarization"
                and self.summarization_stats["file_stats"]
            ):
                stats = self.summarization_stats
                f.write("## Summarization Statistics\n\n")
                f.write(
                    f"- **Total tokens consumed:** {stats['total_tokens_consumed']:,}\n"
                )
                f.write(
                    f"- **Total processing time:** {stats['total_processing_time']:.2f}s\n"
                )
                f.write(
                    f"- **Average tokens per second:** {stats['tokens_per_second']:.2f}\n"
                )
                f.write(
                    f"- **Total input length:** {stats['total_input_length']:,} characters\n"
                )
                f.write(
                    f"- **Total summary length:** {stats['total_summary_length']:,} characters\n"
                )
                f.write(
                    f"- **Average compression ratio:** {stats['average_compression_ratio']:.2%}\n"
                )
                f.write(
                    f"- **Longest input:** {stats['longest_input_length']:,} characters\n"
                )
                f.write(
                    f"- **Shortest input:** {stats['shortest_input_length']:,} characters\n"
                )
                f.write(f"- **Models used:** {', '.join(stats['models_used'])}\n")
                f.write(
                    f"- **Providers used:** {', '.join(stats['providers_used'])}\n\n"
                )

                f.write("### Per-File Statistics\n\n")
                f.write(
                    "| File | Input Length | Summary Length | Tokens | Time (s) | Compression | Model | Provider |\n"
                )
                f.write(
                    "|------|-------------|----------------|--------|----------|-------------|-------|----------|\n"
                )
                for file_stat in stats["file_stats"]:
                    f.write(
                        f"| {file_stat['filename']} | {file_stat['input_length']:,} | "
                        f"{file_stat['summary_length']:,} | {file_stat['tokens_consumed']:,} | "
                        f"{file_stat['processing_time']:.2f} | {file_stat['compression_ratio']:.2%} | "
                        f"{file_stat['model']} | {file_stat['provider']} |\n"
                    )
                f.write("\n")

            if self.successful_files:
                f.write("## Successfully Processed\n\n")
                for file in self.successful_files:
                    f.write(f"- ✅ {file}\n")
                f.write("\n")

            # Add detailed file processing information
            if hasattr(self, "file_details") and self.file_details:
                f.write("## Detailed File Processing\n\n")
                f.write("| Input File | Output File | Type | Status |\n")
                f.write("|------------|-------------|------|--------|\n")
                for detail in self.file_details:
                    output_info = detail["output_file"]
                    if detail["output_type"] == "in_place":
                        output_info = f"✏️ Updated in-place: {detail['input_file']}"
                    elif detail["output_type"] == "new_file":
                        output_info = f"📄 New file: {detail['output_file']}"
                    elif detail["output_type"] == "failed":
                        output_info = (
                            f"❌ Failed: {detail.get('error', 'Unknown error')}"
                        )

                    status_icon = "✅" if detail["status"] == "success" else "❌"
                    f.write(
                        f"| {detail['input_file']} | {output_info} | {detail['output_type']} | {status_icon} |\n"
                    )
                f.write("\n")

            if self.failed_files:
                f.write("## Failed\n\n")
                for file, error in self.failed_files:
                    f.write(f"- ❌ {file}\n")
                    f.write(f"  - Error: {error}\n")
                f.write("\n")

            if self.skipped_files:
                f.write("## Skipped\n\n")
                for file, reason in self.skipped_files:
                    f.write(f"- ⏭️ {file}\n")
                    f.write(f"  - Reason: {reason}\n")
                f.write("\n")

            if self.warnings:
                f.write("## Warnings\n\n")
                for warning in self.warnings:
                    f.write(f"- ⚠️ {warning}\n")
                f.write("\n")

            if self.output_files:
                f.write("## Output Files\n\n")
                for file in self.output_files:
                    f.write(f"- 📄 {file}\n")

        return report_file


class WorkerThread(QThread):
    """Generic worker thread for running operations."""

    message_signal = pyqtSignal(dict)
    finished_signal = pyqtSignal()
    error_signal = pyqtSignal(str)

    def __init__(self, target, args=()):
        super().__init__()
        self.target = target
        self.args = args

    def run(self):
        """Run."""
        try:
            self.target(*self.args)
            self.finished_signal.emit()
        except Exception as e:
            self.error_signal.emit(str(e))


def setup_youtube_logger():
    """Set up dedicated YouTube logging to a specific file."""
    from datetime import datetime

    from loguru import logger as loguru_logger

    # Create logs directory
    YOUTUBE_LOGS_DIR.mkdir(parents=True, exist_ok=True)

    # Create timestamped log file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = YOUTUBE_LOGS_DIR / f"youtube_session_{timestamp}.log"

    # Clear any existing YouTube log handlers if they exist
    if hasattr(setup_youtube_logger, "handler_id"):
        try:
            loguru_logger.remove(setup_youtube_logger.handler_id)
        except ValueError:
            pass

    # Add dedicated YouTube log handler with clear formatting
    handler_id = loguru_logger.add(
        str(log_file),
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}",
        level="INFO",
        rotation="10 MB",
        retention="30 days",
        enqueue=True,
        filter=lambda record: record.get("extra", {}).get("youtube_session", False),
    )

    # Store for later use
    setup_youtube_logger.current_log_file = log_file
    setup_youtube_logger.handler_id = handler_id

    return log_file


def get_youtube_logger():
    """Get the YouTube-specific logger."""
    from loguru import logger as loguru_logger

    return loguru_logger.bind(youtube_session=True)
