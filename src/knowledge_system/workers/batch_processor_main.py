#!/usr/bin/env python3
"""
Standalone Batch Processor - Main Entry Point

This script runs as a separate process to handle batch processing operations
without risking the main GUI application. It communicates with the parent
process via JSON messages on stdout and receives commands via signals.

Usage:
    python -m knowledge_system.workers.batch_processor_main \
        --files file1.mp3 file2.mp4 \
        --config config.json \
        --output-dir /path/to/output \
        --checkpoint-file /path/to/checkpoint.json

Features:
- Process isolation from GUI
- Checkpoint-based recovery
- Real-time progress reporting
- Graceful shutdown handling
- Memory pressure monitoring
"""

import argparse
import json
import logging
import signal
import sys
import time
import traceback
from pathlib import Path
from typing import Any

# Add parent directories to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from knowledge_system.processors.audio_processor import AudioProcessor
from knowledge_system.processors.moc_processor import MOCProcessor
from knowledge_system.processors.summarizer_processor import SummarizerProcessor
from knowledge_system.utils.ipc_communication import IPCCommunicator
from knowledge_system.utils.memory_monitor import MemoryMonitor
from knowledge_system.utils.tracking import ProgressTracker


class BatchProcessor:
    """Standalone batch processor for crash-isolated operations."""

    def __init__(self, args: argparse.Namespace):
        self.args = args
        self.files = args.files
        self.config = self._load_config(args.config)
        self.output_dir = Path(args.output_dir)
        self.checkpoint_file = (
            Path(args.checkpoint_file) if args.checkpoint_file else None
        )

        # Initialize components
        self.ipc = IPCCommunicator()
        self.memory_monitor = MemoryMonitor()
        self.tracker = ProgressTracker(
            self.output_dir,
            enable_checkpoints=True,
            checkpoint_file=self.checkpoint_file,
        )

        # Signal handling
        self.should_stop = False
        self.paused = False
        signal.signal(signal.SIGTERM, self._handle_sigterm)
        signal.signal(signal.SIGINT, self._handle_sigint)
        signal.signal(signal.SIGUSR1, self._handle_sigusr1)

        # Processing components (lazy loaded)
        self.audio_processor = None
        self.summarizer_processor = None
        self.moc_processor = None

        # Statistics
        self.start_time = time.time()
        self.files_processed = 0
        self.files_failed = 0

    def _load_config(self, config_path: str) -> dict[str, Any]:
        """Load configuration from JSON file."""
        try:
            with open(config_path) as f:
                return json.load(f)
        except Exception as e:
            self.ipc.send_error(f"Failed to load config: {e}")
            sys.exit(1)

    def _handle_sigterm(self, signum, frame):
        """Handle SIGTERM for graceful shutdown."""
        self.ipc.send_message("info", "Received SIGTERM, shutting down gracefully...")
        self.should_stop = True

    def _handle_sigint(self, signum, frame):
        """Handle SIGINT (Ctrl+C) for graceful shutdown."""
        self.ipc.send_message("info", "Received SIGINT, shutting down gracefully...")
        self.should_stop = True

    def _handle_sigusr1(self, signum, frame):
        """Handle SIGUSR1 for pause/resume toggle."""
        self.paused = not self.paused
        status = "paused" if self.paused else "resumed"
        self.ipc.send_message("info", f"Processing {status}")

    def _initialize_processors(self):
        """Lazy initialization of processors to save memory."""
        try:
            if self.config.get("transcribe") and not self.audio_processor:
                self.ipc.send_message("info", "Initializing audio processor...")
                self.audio_processor = AudioProcessor(
                    device=self.config.get("device", "cpu"),
                    model=self.config.get("transcription_model", "base"),
                    progress_callback=self._audio_progress_callback,
                )

            if self.config.get("summarize") and not self.summarizer_processor:
                self.ipc.send_message("info", "Initializing summarizer processor...")
                self.summarizer_processor = SummarizerProcessor(
                    progress_callback=self._summarizer_progress_callback
                )

            if self.config.get("create_moc") and not self.moc_processor:
                self.ipc.send_message("info", "Initializing MOC processor...")
                self.moc_processor = MOCProcessor(
                    progress_callback=self._moc_progress_callback
                )

        except Exception as e:
            self.ipc.send_error(f"Failed to initialize processors: {e}")
            raise

    def _audio_progress_callback(self, message: str, progress: int | None = None):
        """Forward audio processing progress to parent."""
        self.ipc.send_progress(
            current_file=self.files_processed + 1,
            total_files=len(self.files),
            stage="transcription",
            message=message,
            progress=progress,
        )

    def _summarizer_progress_callback(self, message: str, progress: int | None = None):
        """Forward summarization progress to parent."""
        self.ipc.send_progress(
            current_file=self.files_processed + 1,
            total_files=len(self.files),
            stage="summarization",
            message=message,
            progress=progress,
        )

    def _moc_progress_callback(self, message: str, progress: int | None = None):
        """Forward MOC generation progress to parent."""
        self.ipc.send_progress(
            current_file=self.files_processed + 1,
            total_files=len(self.files),
            stage="moc_generation",
            message=message,
            progress=progress,
        )

    def _check_memory_pressure(self) -> bool:
        """Check if we're under memory pressure and need to take action."""
        is_pressure, message = self.memory_monitor.check_memory_pressure()
        if is_pressure:
            self.ipc.send_message("warning", f"Memory pressure detected: {message}")

            # Attempt emergency cleanup
            self.memory_monitor.emergency_cleanup()

            # Check again after cleanup
            is_pressure_after, _ = self.memory_monitor.check_memory_pressure()
            if is_pressure_after:
                self.ipc.send_error("Critical memory pressure - aborting processing")
                return True
        return False

    def _should_resume_from_checkpoint(self, file_path: str) -> bool:
        """Check if this file should be skipped due to checkpoint resume."""
        if not self.tracker.has_checkpoint():
            return False

        checkpoint_data = self.tracker.load_checkpoint()
        completed_files = checkpoint_data.get("completed_files", [])
        return file_path in completed_files

    def _process_single_file(self, file_path: str) -> dict[str, Any]:
        """Process a single file through the complete pipeline."""
        file_path_obj = Path(file_path)
        result = {
            "file_path": file_path,
            "success": False,
            "transcription_path": None,
            "summary_path": None,
            "moc_path": None,
            "error": None,
            "processing_time": 0,
        }

        start_time = time.time()

        try:
            self.ipc.send_progress(
                current_file=self.files_processed + 1,
                total_files=len(self.files),
                stage="starting",
                message=f"Processing {file_path_obj.name}",
                progress=0,
            )

            # Check memory before starting
            if self._check_memory_pressure():
                result["error"] = "Memory pressure - skipping file"
                return result

            # Audio transcription
            if self.config.get("transcribe") and self.audio_processor:
                self.ipc.send_message("info", f"Transcribing {file_path_obj.name}")
                transcription_result = self.audio_processor.process(file_path)

                if transcription_result.get("success"):
                    result["transcription_path"] = transcription_result.get(
                        "output_path"
                    )
                    self.ipc.send_progress(
                        current_file=self.files_processed + 1,
                        total_files=len(self.files),
                        stage="transcription",
                        message="Transcription completed",
                        progress=100,
                    )
                else:
                    result[
                        "error"
                    ] = f"Transcription failed: {transcription_result.get('error')}"
                    return result

            # Summarization
            if (
                self.config.get("summarize")
                and self.summarizer_processor
                and result.get("transcription_path")
            ):
                self.ipc.send_message("info", f"Summarizing {file_path_obj.name}")
                summary_result = self.summarizer_processor.process(
                    result["transcription_path"]
                )

                if summary_result.get("success"):
                    result["summary_path"] = summary_result.get("output_path")
                    self.ipc.send_progress(
                        current_file=self.files_processed + 1,
                        total_files=len(self.files),
                        stage="summarization",
                        message="Summarization completed",
                        progress=100,
                    )
                else:
                    result[
                        "error"
                    ] = f"Summarization failed: {summary_result.get('error')}"
                    return result

            # MOC Generation
            if (
                self.config.get("create_moc")
                and self.moc_processor
                and result.get("summary_path")
            ):
                self.ipc.send_message("info", f"Creating MOC for {file_path_obj.name}")
                moc_result = self.moc_processor.process(result["summary_path"])

                if moc_result.get("success"):
                    result["moc_path"] = moc_result.get("output_path")
                    self.ipc.send_progress(
                        current_file=self.files_processed + 1,
                        total_files=len(self.files),
                        stage="moc_generation",
                        message="MOC generation completed",
                        progress=100,
                    )
                else:
                    result[
                        "error"
                    ] = f"MOC generation failed: {moc_result.get('error')}"
                    return result

            result["success"] = True
            result["processing_time"] = time.time() - start_time

        except Exception as e:
            result["error"] = f"Unexpected error: {str(e)}"
            result["processing_time"] = time.time() - start_time
            self.ipc.send_error(f"Error processing {file_path}: {e}")

        return result

    def run(self) -> int:
        """Main processing loop."""
        try:
            self.ipc.send_message(
                "info", f"Starting batch processing of {len(self.files)} files"
            )

            # Check for existing checkpoint
            if self.tracker.has_checkpoint():
                checkpoint_data = self.tracker.load_checkpoint()
                completed_count = len(checkpoint_data.get("completed_files", []))
                self.ipc.send_message(
                    "info",
                    f"Resuming from checkpoint - {completed_count} files already completed",
                )

            # Initialize processors
            self._initialize_processors()

            # Process each file
            for i, file_path in enumerate(self.files):
                if self.should_stop:
                    self.ipc.send_message("info", "Processing stopped by signal")
                    break

                # Handle pause
                while self.paused and not self.should_stop:
                    time.sleep(1)

                # Skip if already completed (checkpoint resume)
                if self._should_resume_from_checkpoint(file_path):
                    self.ipc.send_message(
                        "info", f"Skipping {Path(file_path).name} (already completed)"
                    )
                    self.files_processed += 1
                    continue

                # Process the file
                result = self._process_single_file(file_path)

                # Update statistics
                if result["success"]:
                    self.files_processed += 1
                    self.ipc.send_file_completed(
                        file_path, True, "Processing completed successfully"
                    )
                else:
                    self.files_failed += 1
                    self.ipc.send_file_completed(
                        file_path, False, result.get("error", "Unknown error")
                    )

                # Save checkpoint
                self.tracker.complete_task(file_path, result)

                # Force garbage collection between files
                self.memory_monitor.cleanup_between_files()

            # Send final results
            total_time = time.time() - self.start_time
            final_results = {
                "total_files": len(self.files),
                "files_processed": self.files_processed,
                "files_failed": self.files_failed,
                "total_time": total_time,
                "average_time_per_file": total_time / max(1, self.files_processed),
            }

            self.ipc.send_finished(final_results)

            if self.files_failed == 0:
                self.ipc.send_message(
                    "info",
                    f"Batch processing completed successfully - {self.files_processed} files processed",
                )
                return 0
            else:
                self.ipc.send_message(
                    "warning",
                    f"Batch processing completed with {self.files_failed} failures",
                )
                return 1

        except Exception as e:
            self.ipc.send_error(f"Fatal error in batch processor: {e}")
            self.ipc.send_error(f"Traceback: {traceback.format_exc()}")
            return 2


def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Standalone batch processor for Knowledge Chipper"
    )

    parser.add_argument(
        "--files", nargs="+", required=True, help="List of files to process"
    )

    parser.add_argument(
        "--config", required=True, help="Path to JSON configuration file"
    )

    parser.add_argument(
        "--output-dir", required=True, help="Output directory for processed files"
    )

    parser.add_argument(
        "--checkpoint-file", help="Path to checkpoint file for resume functionality"
    )

    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging level",
    )

    parser.add_argument(
        "--heartbeat-interval",
        type=int,
        default=30,
        help="Heartbeat interval in seconds",
    )

    return parser.parse_args()


def setup_logging(level: str):
    """Configure logging for the standalone process."""
    logging.basicConfig(
        level=getattr(logging, level),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(
                sys.stderr
            )  # Send logs to stderr, keep stdout for IPC
        ],
    )


def load_environment_variables():
    """Load environment variables for API keys and other settings."""
    # Load from various sources - environment, config files, etc.


def main():
    """Main entry point."""
    try:
        args = parse_arguments()
        setup_logging(args.log_level)
        load_environment_variables()

        # Create and run processor
        processor = BatchProcessor(args)
        exit_code = processor.run()

        sys.exit(exit_code)

    except KeyboardInterrupt:
        print("Interrupted by user", file=sys.stderr)
        sys.exit(130)
    except Exception as e:
        print(f"Fatal error: {e}", file=sys.stderr)
        print(f"Traceback: {traceback.format_exc()}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
