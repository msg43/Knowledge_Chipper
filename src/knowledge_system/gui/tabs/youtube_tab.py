""" YouTube extraction tab for downloading and processing YouTube transcripts."""

import json
import os  # Added for os.access
import random
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from PyQt6.QtCore import QThread, QTimer, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QTextEdit,
    QVBoxLayout,
)

from ...logger import get_logger
from ...utils.cancellation import CancellationToken
from ..components.base_tab import BaseTab
from ..core.settings_manager import get_gui_settings_manager

logger = get_logger(__name__)


class YouTubeExtractionWorker(QThread):
    """ Worker thread for YouTube transcript extraction."""

    progress_updated = pyqtSignal(int, int, str)  # current, total, status
    url_completed = pyqtSignal(str, bool, str)  # url, success, message
    extraction_finished = pyqtSignal(dict)  # final results
    extraction_error = pyqtSignal(str)
    payment_required = pyqtSignal()  # 402 Payment Required error
    playlist_info_updated = pyqtSignal(dict)  # playlist metadata for display

    def __init__(self, urls: Any, config: Any, parent: Any = None) -> None:
        super().__init__(parent)
        self.urls = urls
        self.config = config
        self.should_stop = False
        self.cancellation_token = CancellationToken()

        # Log worker creation details
        logger.info(f"YouTubeExtractionWorker created with {len(urls)} URLs")
        if len(urls) == 0:
            logger.warning("YouTubeExtractionWorker created with EMPTY URL list!")
        else:
            logger.info(f"URLs to process: {urls[:3]}{'...' if len(urls) > 3 else ''}")

    def run(self) -> None:
        """ Run the YouTube extraction process."""
        logger.info(f"YouTubeExtractionWorker.run() started with {len(self.urls)} URLs")

        # Early check for empty URL list
        if not self.urls or len(self.urls) == 0:
            logger.warning("Worker started with empty URL list - exiting immediately")
            self.extraction_finished.emit(
                {"successful": 0, "failed": 0, "urls_processed": [], "failed_urls": []}
            )
            return

        try:
            import json
            from datetime import datetime
            from pathlib import Path

            from ...processors.youtube_transcript import YouTubeTranscriptProcessor
            from ...utils.youtube_utils import expand_playlist_urls_with_metadata

            # CRITICAL DEBUG: Log the config received by worker
            logger.info(f"🔧 Worker received config: {self.config}")
            logger.info(
                f"🔧 Output directory from config: {repr(self.config.get('output_dir'))} (type: {type(self.config.get('output_dir'))})"
            )

            # Log cancellation token state before starting
            logger.info(
                f"Cancellation token state at start - cancelled: {self.cancellation_token.is_cancelled}, paused: {self.cancellation_token.is_paused()}"
            )
            logger.info(f"should_stop flag: {self.should_stop}")

            # Expand playlists and get metadata
            logger.info(f"Expanding {len(self.urls)} URLs (checking for playlists)...")
            expansion_result = expand_playlist_urls_with_metadata(self.urls)
            expanded_urls = expansion_result["expanded_urls"]
            playlist_info = expansion_result["playlist_info"]

            # Calculate total videos across ALL sources (playlists + individual videos)
            total_playlist_videos = (
                sum(p["total_videos"] for p in playlist_info) if playlist_info else 0
            )
            individual_videos = len(expanded_urls) - total_playlist_videos
            total_videos_all_sources = len(expanded_urls)

            # Emit comprehensive video information
            if playlist_info or individual_videos > 0:
                summary_parts = []
                if playlist_info:
                    summary_parts.append(
                        f"{len(playlist_info)} playlist(s) with {total_playlist_videos} videos"
                    )
                if individual_videos > 0:
                    summary_parts.append(f"{individual_videos} individual video(s)")

                summary = " + ".join(summary_parts)
                logger.info(
                    f"📊 Total content to process: {summary} = {total_videos_all_sources} videos total"
                )

                self.playlist_info_updated.emit(
                    {
                        "playlists": playlist_info,
                        "total_playlists": len(playlist_info),
                        "total_videos": total_videos_all_sources,
                        "playlist_videos": total_playlist_videos,
                        "individual_videos": individual_videos,
                        "summary": summary,
                    }
                )
            else:
                logger.info(
                    f"📊 Total content to process: {total_videos_all_sources} videos"
                )

            processor = YouTubeTranscriptProcessor()
            results = {
                "successful": 0,
                "failed": 0,
                "urls_processed": [],
                "failed_urls": [],
                "playlist_info": playlist_info,
            }

            total_urls = len(expanded_urls)
            logger.info(f"Processing {total_urls} URLs (after playlist expansion)")

            # Initial progress update with comprehensive summary
            if playlist_info:
                start_msg = f"🚀 Starting extraction of {total_videos_all_sources} videos total ({summary})"
            else:
                start_msg = (
                    f"🚀 Starting extraction of {total_videos_all_sources} videos"
                )
            self.progress_updated.emit(0, total_urls, start_msg)

            for i, url in enumerate(expanded_urls):
                # Detailed logging of cancellation check
                is_should_stop = self.should_stop
                is_token_cancelled = self.cancellation_token.is_cancelled()
                logger.info(
                    f"URL {i+1}/{total_urls}: should_stop={is_should_stop}, token_cancelled={is_token_cancelled}"
                )

                # Check cancellation before processing each URL
                if is_should_stop or is_token_cancelled:
                    logger.warning(
                        f"Cancellation detected: should_stop={is_should_stop}, token_cancelled={is_token_cancelled}"
                    )
                    logger.info(f"YouTube extraction stopped by user after {i} URLs")
                    self.progress_updated.emit(
                        i, total_urls, f"❌ Extraction cancelled after {i} URLs"
                    )
                    break

                # Extract video ID for title lookup
                video_id = None
                if "youtu.be/" in url:
                    video_id = url.split("youtu.be/")[1].split("?")[0]
                elif "watch?v=" in url:
                    video_id = url.split("watch?v=")[1].split("&")[0]
                elif "playlist?list=" in url:
                    video_id = f"Playlist-{url.split('list=')[1][:11]}"

                # Calculate percentage
                percent = int((i / total_urls) * 100)

                # Determine playlist context for enhanced progress display
                playlist_context = ""
                playlist_number = 0
                for idx, playlist in enumerate(playlist_info):
                    if playlist["start_index"] <= i <= playlist["end_index"]:
                        playlist_position = i - playlist["start_index"] + 1
                        playlist_number = idx + 1
                        total_playlists = len(playlist_info)
                        playlist_title = playlist["title"][:25] + (
                            "..." if len(playlist["title"]) > 25 else ""
                        )
                        playlist_context = f" [📋 PL{playlist_number}/{total_playlists}: {playlist_title} - #{playlist_position}/{playlist['total_videos']}]"
                        break

                # Try to get a meaningful title for progress display
                display_title = (
                    f"Video {video_id}" if video_id else url[-50:]
                )  # Show last 50 chars of URL as fallback

                # Enhanced global progress with playlist context
                global_progress = f"Video {i+1}/{total_urls}"
                self.progress_updated.emit(
                    i,
                    total_urls,
                    f"📹 {global_progress} ({percent}%) Processing: {display_title}{playlist_context}",
                )

                try:
                    # Sub-step progress: Starting processing
                    self.progress_updated.emit(
                        i,
                        total_urls,
                        f"🔄 {global_progress} ({percent}%) Fetching metadata for: {display_title}{playlist_context}",
                    )

                    # CRITICAL DEBUG: Log processor call parameters for each URL
                    output_dir_param = self.config.get("output_dir")
                    logger.info(
                        f"🔧 About to call processor for URL {i+1}/{total_urls}: {url}"
                    )
                    logger.info(f"🔧 Processor parameters:")
                    logger.info(
                        f"   output_dir: {repr(output_dir_param)} (type: {type(output_dir_param)})"
                    )
                    logger.info(f"   output_format: {self.config.get('format', 'md')}")
                    logger.info(
                        f"   include_timestamps: {self.config.get('timestamps', True)}"
                    )

                    # CRITICAL VALIDATION: Check output directory before processing
                    if output_dir_param:
                        output_path = Path(output_dir_param)
                        logger.info(f"🔧 Output directory validation:")
                        logger.info(f"   Path exists: {output_path.exists()}")
                        logger.info(
                            f"   Is directory: {output_path.is_dir() if output_path.exists() else 'N/A'}"
                        )
                        logger.info(
                            f"   Is writable: {os.access(output_path, os.W_OK) if output_path.exists() else 'N/A'}"
                        )
                        logger.info(f"   Absolute path: {output_path.absolute()}")

                        # Try to create directory if it doesn't exist
                        if not output_path.exists():
                            try:
                                output_path.mkdir(parents=True, exist_ok=True)
                                logger.info(
                                    f"✅ Created output directory: {output_path}"
                                )
                            except Exception as e:
                                logger.error(
                                    f"❌ Failed to create output directory {output_path}: {e}"
                                )
                    else:
                        logger.warning(f"⚠️ No output_dir parameter provided!")

                    # Pass cancellation token to processor
                    result = processor.process(
                        url,
                        output_dir=self.config.get("output_dir"),
                        output_format=self.config.get("format", "md"),
                        include_timestamps=self.config.get("timestamps", True),
                        overwrite=self.config.get("overwrite", False),
                        cancellation_token=self.cancellation_token,
                    )

                    # CRITICAL DEBUG: Log result summary
                    logger.info(f"🔧 Processor result for {url}:")
                    logger.info(f"   success: {result.success}")
                    if result.data:
                        saved_files = result.data.get("saved_files", [])
                        skipped_files = result.data.get("skipped_files", [])
                        logger.info(f"   saved_files count: {len(saved_files)}")
                        logger.info(f"   skipped_files count: {len(skipped_files)}")
                        if saved_files:
                            logger.info(f"   saved_files: {saved_files}")
                        if skipped_files:
                            logger.info(f"   skipped_files: {skipped_files}")
                    if result.errors:
                        logger.info(f"   errors: {result.errors}")

                    if result.success:
                        # Get actual title from successful result
                        actual_title = "Unknown Title"
                        if result.data and result.data.get("transcripts"):
                            transcripts = result.data["transcripts"]
                            if transcripts and len(transcripts) > 0:
                                actual_title = transcripts[0].get(
                                    "title", "Unknown Title"
                                )

                        # Truncate long titles for display
                        if len(actual_title) > 60:
                            display_actual_title = actual_title[:57] + "..."
                        else:
                            display_actual_title = actual_title

                        # Sub-step progress: Transcript extraction complete
                        self.progress_updated.emit(
                            i,
                            total_urls,
                            f"📝 {global_progress} ({percent}%) Transcript extracted: {display_actual_title}{playlist_context}",
                        )

                        # Check if files were actually saved or skipped
                        saved_files = result.data.get("saved_files", [])
                        skipped_files = result.data.get("skipped_files", [])
                        file_count = len(saved_files)
                        skipped_count = len(skipped_files)

                        if file_count > 0:
                            # Files were actually saved - true success
                            self.progress_updated.emit(
                                i,
                                total_urls,
                                f"💾 {global_progress} ({percent}%) Saved {file_count} file(s): {display_actual_title}{playlist_context}",
                            )

                            results["successful"] += 1
                            results["urls_processed"].append(url)

                            # Success message for this URL (include playlist context)
                            success_msg = f"✅ Video {i+1}/{total_urls}: {display_actual_title} ({file_count} file(s)){playlist_context}"
                            self.url_completed.emit(url, True, success_msg)
                        elif skipped_count > 0:
                            # Files were skipped due to overwrite=False - this is also success
                            self.progress_updated.emit(
                                i,
                                total_urls,
                                f"⏭️ {global_progress} ({percent}%) Skipped existing: {display_actual_title}{playlist_context}",
                            )

                            # Track skipped files separately
                            if "skipped" not in results:
                                results["skipped"] = 0
                                results["skipped_urls"] = []
                            results["skipped"] += 1
                            results["skipped_urls"].append(
                                {
                                    "url": url,
                                    "title": actual_title,
                                    "reason": "File already exists (overwrite disabled)",
                                }
                            )

                            # Success message for skipped URL
                            skip_msg = f"⏭️ Video {i+1}/{total_urls}: {display_actual_title} (overwrite disabled){playlist_context}"
                            self.url_completed.emit(url, True, skip_msg)
                        else:
                            # Success reported but no files saved or skipped - this is actually a partial failure
                            self.progress_updated.emit(
                                i,
                                total_urls,
                                f"⚠️ {global_progress} ({percent}%) Extracted but not saved: {display_actual_title}{playlist_context}",
                            )

                            results["failed"] += 1
                            error_reason = (
                                "Transcript extracted but no files were saved"
                            )
                            if result.errors:
                                error_reason = "; ".join(result.errors)
                            results["failed_urls"].append(
                                {
                                    "url": url,
                                    "title": actual_title,
                                    "error": error_reason,
                                }
                            )

                            # Partial failure message
                            failure_msg = f"⚠️ Extracted transcript but failed to save files: {display_actual_title}"
                            self.url_completed.emit(url, False, failure_msg)

                    else:
                        # Check if this is actually a successful skip (not a true failure)
                        skipped_via_index = (
                            result.data.get("skipped_via_index", 0)
                            if result.data
                            else 0
                        )
                        if skipped_via_index > 0 and result.data.get("skipped_files"):
                            # This is actually a successful skip, not a failure
                            logger.info(
                                f"✅ Video already exists and was skipped: {url}"
                            )
                            results["skipped"] += 1
                            results["skipped_urls"].append(
                                {
                                    "url": url,
                                    "title": display_title,
                                    "reason": "Already exists (via index)",
                                }
                            )
                            skip_msg = f"⏭️ Already exists: {display_title}"
                            self.url_completed.emit(url, True, skip_msg)
                        else:
                            # True failure - extraction failed
                            error_msg = (
                                "; ".join(result.errors)
                                if result.errors
                                else "Unknown error"
                            )
                            logger.error(
                                f"Failed to extract transcript for {url}: {error_msg}"
                            )

                            # Check for payment required error in result errors
                            if (
                                "402 Payment Required" in error_msg
                                or "payment required" in error_msg.lower()
                            ):
                                self.payment_required.emit()

                            results["failed"] += 1
                            results["failed_urls"].append(
                                {"url": url, "title": display_title, "error": error_msg}
                            )

                            # Failure message
                            failure_msg = (
                                f"❌ Failed to extract: {display_title} - {error_msg}"
                            )
                            self.url_completed.emit(url, False, failure_msg)

                except Exception as e:
                    error_msg = str(e)
                    logger.error(f"Error processing {url}: {error_msg}")
                    results["failed"] += 1
                    results["failed_urls"].append(url)

                    # Check for 402 Payment Required error and emit special signal
                    if "402 Payment Required" in error_msg:
                        self.payment_required.emit()

                    # Sub-step progress: Exception
                    self.progress_updated.emit(
                        i,
                        total_urls,
                        f"💥 [{i+1}/{total_urls}] ({percent}%) Exception: {display_title}",
                    )

                    # Exception message for this URL
                    exception_msg = (
                        f"💥 Exception processing: {display_title} - {error_msg}"
                    )
                    self.url_completed.emit(url, False, exception_msg)

            # Final progress update
            final_percent = 100
            completion_msg = f"🎉 Extraction complete! ✅ {results['successful']} successful, ❌ {results['failed']} failed out of {total_urls} total URLs"
            self.progress_updated.emit(total_urls, total_urls, completion_msg)

            # Emit completion
            self.extraction_finished.emit(results)

        except Exception as e:
            error_msg = f"YouTube extraction failed: {str(e)}"
            logger.error(error_msg)
            self.extraction_error.emit(error_msg)
            self.progress_updated.emit(0, len(self.urls), f"💥 Fatal error: {error_msg}")

    def stop(self) -> None:
        """ Stop the extraction process."""
        logger.info("YouTubeExtractionWorker.stop() called")
        self.should_stop = True
        if self.cancellation_token:
            self.cancellation_token.cancel("User requested cancellation")

    def _write_failure_log(self, failed_urls: list[str]) -> None:
        """
        Write failed URL extractions to timestamped log files

        Returns:
            tuple: (log_file_path, csv_file_path) or (None, None) if failed
        """
        try:

        try:
            import csv
            import json
            from datetime import datetime
            from pathlib import Path

            # Get the logs directory from settings
            from ...config import get_settings

            settings = get_settings()
            logs_dir = Path(settings.paths.logs).expanduser()
            logs_dir.mkdir(parents=True, exist_ok=True)

            # Create timestamped filenames instead of overwriting
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            log_file = logs_dir / f"youtube_extraction_failures_{timestamp}.log"
            csv_file = logs_dir / f"youtube_extraction_failures_{timestamp}.csv"

            # Write new timestamped log file
            with open(log_file, "w", encoding="utf-8") as f:
                f.write(f"{'='*70}\n")
                f.write(f"YouTube Extraction Failures\n")
                f.write(f"Session: {datetime.now().isoformat()}\n")
                f.write(f"Total failed: {len(failed_urls)}\n")
                f.write(f"{'='*70}\n\n")

                # Write detailed failure information
                for i, failed_item in enumerate(failed_urls, 1):
                    if isinstance(failed_item, dict):
                        url = failed_item.get("url", "Unknown URL")
                        title = failed_item.get("title", "Unknown Title")
                        error = failed_item.get("error", "Unknown error")

                        f.write(f"{i}. Title: {title}\n")
                        f.write(f"   URL: {url}\n")
                        f.write(f"   Error: {error}\n\n")
                    else:
                        # Fallback for simple string URLs
                        f.write(f"{i}. URL: {failed_item}\n")
                        f.write(f"   Error: No additional information available\n\n")

                f.write(f"\n{'='*70}\n")
                f.write(f"Note: This is a session-specific failure log.\n")
                f.write(f"For retry, use the corresponding CSV file: {csv_file.name}\n")
                f.write(f"{'='*70}\n")

            # Create timestamped CSV file with failed URLs for easy re-import
            formatted_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            with open(csv_file, "w", newline="", encoding="utf-8") as csvfile:
                # Write header comments
                csvfile.write("# YouTube Extraction Failures - URLs for retry\n")
                csvfile.write(f"# Session: {formatted_timestamp}\n")
                csvfile.write(f"# Total failures: {len(failed_urls)}\n")
                csvfile.write("#\n")
                csvfile.write("# Instructions:\n")
                csvfile.write(
                    "# 1. You can load this file directly into the YouTube tab\n"
                )
                csvfile.write(
                    "# 2. Select 'Or Select File' option and browse to this CSV\n"
                )
                csvfile.write("# 3. Click 'Extract Transcripts' to retry failed URLs\n")
                csvfile.write("#\n")

                # Write URLs - one per line for simplicity
                for failed_item in failed_urls:
                    if isinstance(failed_item, dict):
                        url = failed_item.get("url", "")
                        if url and url != "Unknown URL":
                            csvfile.write(f"{url}\n")
                    else:
                        # Fallback for simple string URLs
                        if failed_item:
                            csvfile.write(f"{failed_item}\n")

            logger.info(f"Failed extractions logged to: {log_file}")
            logger.info(f"Failed URLs saved for retry to: {csv_file}")

            return log_file, csv_file

        except Exception as e:
            logger.error(f"Failed to write failure log: {e}")
            return None, None


class YouTubeTab(BaseTab):
    """ Tab for YouTube transcript extraction and processing."""

    def __init__(self, parent: Any = None) -> None:
        self.extraction_worker = None
        self.gui_settings = get_gui_settings_manager()
        self.tab_name = "YouTube"
        super().__init__(parent)

    def _setup_ui(self) -> None:
        """ Setup the YouTube extraction UI."""
        layout = QVBoxLayout(self)

        # Input section
        input_section = self._create_input_section()
        layout.addWidget(input_section)

        # Settings section
        settings_section = self._create_settings_section()
        layout.addWidget(settings_section)

        # Action buttons
        action_layout = self._create_action_layout()
        layout.addLayout(action_layout)

        # Progress section
        progress_layout = self._create_progress_section()
        layout.addLayout(progress_layout)

        # Output section
        output_layout = self._create_output_section()
        layout.addLayout(
            output_layout, 1
        )  # Give stretch factor of 1 to allow expansion

        # Load saved settings after UI is set up
        self._load_settings()

    def _create_input_section(self) -> QGroupBox:
        """ Create the URL input section."""
        group = QGroupBox("YouTube URLs")
        layout = QVBoxLayout()

        # Radio button for URL input
        self.url_radio = QRadioButton("YouTube URLs")
        self.url_radio.setChecked(True)  # Default selection
        self.url_radio.toggled.connect(self._on_input_method_changed)
        self.url_radio.setToolTip(
            "Select this option to enter YouTube URLs directly.\n"
            "• Supports individual videos and playlists\n"
            "• Enter one URL per line in the text area below\n"
            "• Automatically detects and counts total videos"
        )
        layout.addWidget(self.url_radio)

        # URL input
        self.url_input = QTextEdit()
        self.url_input.setPlaceholderText(
            "Enter YouTube URLs or Playlist URLs (one per line) - shows total video count across all playlists:\n"
            "https://www.youtube.com/watch?v=...\n"
            "https://youtu.be/...\n"
            "https://www.youtube.com/playlist?list=..."
        )
        self.url_input.setMinimumHeight(150)
        self.url_input.setMaximumHeight(200)  # Prevent it from growing too large
        from PyQt6.QtWidgets import QSizePolicy

        self.url_input.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self.url_input.setToolTip(
            "Enter YouTube URLs to process (one per line).\n"
            "• Individual videos: https://www.youtube.com/watch?v=...\n"
            "• Short URLs: https://youtu.be/...\n"
            "• Playlists: https://www.youtube.com/playlist?list=...\n"
            "• Mix any combination of videos and playlists\n"
            "• Total video count will be calculated automatically\n"
            "• Private or unavailable videos will be skipped with warnings"
        )
        layout.addWidget(self.url_input)

        # Radio button for file input
        self.file_radio = QRadioButton("Or Select File")
        self.file_radio.toggled.connect(self._on_input_method_changed)
        self.file_radio.setToolTip(
            "Select this option to load URLs from a file.\n"
            "• Supports .TXT, .RTF, and .CSV files\n"
            "• File should contain one URL per line\n"
            "• Useful for large collections of URLs"
        )
        layout.addWidget(self.file_radio)

        # File input
        file_layout = QHBoxLayout()
        file_layout.addWidget(
            QLabel(
                "Select a .TXT, .RTF, or .CSV file with YouTube URLs/Playlists (shows total video count across all):"
            )
        )

        self.file_input = QLineEdit()
        self.file_input.setPlaceholderText("Select a file containing URLs...")
        self.file_input.setEnabled(False)  # Start disabled
        self.file_input.setToolTip(
            "Path to file containing YouTube URLs.\n"
            "• Supported formats: .TXT, .RTF, .CSV\n"
            "• One URL per line in the file\n"
            "• Comments starting with # are ignored\n"
            "• Empty lines are skipped\n"
            "• Click Browse to select a file"
        )
        file_layout.addWidget(self.file_input)

        self.browse_btn = QPushButton("Browse")
        self.browse_btn.clicked.connect(self._select_url_file)
        self.browse_btn.setEnabled(False)  # Start disabled
        self.browse_btn.setToolTip(
            "Browse and select a file containing YouTube URLs.\n"
            "• Choose a .TXT, .RTF, or .CSV file\n"
            "• File should have one URL per line\n"
            "• Will automatically count total videos"
        )
        file_layout.addWidget(self.browse_btn)

        layout.addLayout(file_layout)
        group.setLayout(layout)
        return group

    def _on_input_method_changed(self) -> None:
        """ Handle radio button changes to enable/disable input sections."""
        if self.url_radio.isChecked():
            # Enable URL input, disable file input
            self.url_input.setEnabled(True)
            self.file_input.setEnabled(False)
            self.browse_btn.setEnabled(False)

            # BUGFIX: Reset URL input styling and apply disabled styling to file input
            self.url_input.setStyleSheet("")  # Reset URL input to default
            self.file_input.setStyleSheet("color: gray;")  # Gray out file input
        else:
            # Enable file input, disable URL input
            self.url_input.setEnabled(False)
            self.file_input.setEnabled(True)
            self.browse_btn.setEnabled(True)

            # BUGFIX: Reset file input styling and apply disabled styling to URL input
            self.url_input.setStyleSheet("color: gray;")  # Gray out URL input
            self.file_input.setStyleSheet("")  # Reset file input to default

        # Save the radio button state change
        self._save_settings()

    def _create_settings_section(self) -> QGroupBox:
        """ Create the extraction settings section."""
        group = QGroupBox("Extraction Settings")
        layout = QGridLayout()

        # Output directory
        layout.addWidget(QLabel("Output Directory:"), 0, 0)
        self.output_dir_input = QLineEdit()
        self.output_dir_input.setPlaceholderText(
            "Click Browse to select output directory (required)"
        )
        # Remove default setting - require user selection
        self.output_dir_input.textChanged.connect(self._on_setting_changed)
        self.output_dir_input.setToolTip(
            "Directory where transcript files and thumbnails will be saved.\n"
            "• Click Browse to select a directory\n"
            "• Ensure it has write permissions\n"
            "• Transcripts will be in .md format, thumbnails in a subdirectory"
        )
        layout.addWidget(self.output_dir_input, 0, 1)

        browse_output_btn = QPushButton("Browse")
        browse_output_btn.clicked.connect(self._select_output_directory)
        browse_output_btn.setToolTip(
            "Browse and select the output directory for transcript files and thumbnails.\n"
            "• Choose a directory to save transcript .md files and thumbnail images"
        )
        layout.addWidget(browse_output_btn, 0, 2)

        # Format selection
        layout.addWidget(QLabel("Output Format:"), 1, 0)
        self.format_combo = QComboBox()
        self.format_combo.addItems(["md", "txt", "json"])
        self.format_combo.setCurrentText("md")
        self.format_combo.currentTextChanged.connect(self._on_setting_changed)
        self.format_combo.setToolTip(
            "Select the output format for the transcript.\n"
            "• md: Markdown format (default)\n"
            "• txt: Plain text\n"
            "• json: JSON format (for advanced processing)"
        )
        layout.addWidget(self.format_combo, 1, 1)

        # Options
        self.timestamps_checkbox = QCheckBox("Include timestamps")
        self.timestamps_checkbox.setChecked(True)
        self.timestamps_checkbox.toggled.connect(self._on_setting_changed)
        self.timestamps_checkbox.setToolTip(
            "Include timestamps in the transcript.\n"
            "• Timestamps are useful for navigation and searching\n"
            "• Only available for YouTube videos with timestamps"
        )
        layout.addWidget(self.timestamps_checkbox, 2, 0, 1, 2)

        self.overwrite_checkbox = QCheckBox("Overwrite existing transcripts")
        self.overwrite_checkbox.setChecked(False)
        self.overwrite_checkbox.toggled.connect(self._on_setting_changed)
        self.overwrite_checkbox.setToolTip(
            "If enabled, existing transcript files will be overwritten.\n"
            "• If disabled, new transcript files will be named with a timestamp\n"
            "• This prevents accidental overwriting of existing work"
        )
        layout.addWidget(self.overwrite_checkbox, 2, 2)

        group.setLayout(layout)
        return group

    def _create_action_layout(self) -> QHBoxLayout:
        """ Create the action buttons layout."""
        layout = QHBoxLayout()

        self.start_btn = QPushButton(self._get_start_button_text())
        self.start_btn.clicked.connect(self._start_processing)
        # Set fixed height for consistent sizing
        self.start_btn.setFixedHeight(50)
        from PyQt6.QtWidgets import QSizePolicy

        self.start_btn.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self.start_btn.setToolTip(
            "Start YouTube transcript extraction process.\n"
            "• Downloads transcripts for all provided URLs\n"
            "• Downloads thumbnails for each video\n"
            "• Processes both individual videos and playlists\n"
            "• Requires WebShare proxy credentials for YouTube access\n"
            "• Progress will be shown in real-time below"
        )
        # Make green and take 3/4 of the width
        self.start_btn.setStyleSheet(
            """
            QPushButton {

            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
                padding: 12px;
                font-size: 14px;
                border: none;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """
        )

        )
        layout.addWidget(self.start_btn, 3)  # 3/4 stretch factor

        self.stop_btn = QPushButton("Stop Extraction")
        self.stop_btn.clicked.connect(self._stop_processing)
        self.stop_btn.setEnabled(False)  # Initially disabled
        # Set fixed height for consistent sizing
        self.stop_btn.setFixedHeight(50)
        self.stop_btn.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self.stop_btn.setToolTip(
            "Stop the current extraction process.\n"
            "• Safely stops processing after current video completes\n"
            "• Already processed videos will be saved\n"
            "• Can resume later with unprocessed videos\n"
            "• Process will stop gracefully, not immediately"
        )
        # Make red and take 1/4 of the width
        self.stop_btn.setStyleSheet(
            """
            QPushButton {

            QPushButton {
                background-color: #f44336;
                color: white;
                font-weight: bold;
                padding: 12px;
                font-size: 14px;
                border: none;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #da190b;
            }
            QPushButton:disabled {
                background-color: #cc3629;
                color: #ffffff;
                opacity: 0.7;
            }
        """
        )

        )
        layout.addWidget(self.stop_btn, 1)  # 1/4 stretch factor

        return layout

    def _create_progress_section(self) -> QVBoxLayout:
        """ Create the progress tracking section."""
        layout = QVBoxLayout()

        # Progress label
        self.progress_label = QLabel("Ready to extract transcripts")
        layout.addWidget(self.progress_label)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)  # Hidden initially
        layout.addWidget(self.progress_bar)

        return layout

    def _create_output_section(self) -> QVBoxLayout:
        """ Create the output section with improved resizing behavior."""
        layout = QVBoxLayout()

        # Header with report button
        header_layout = QHBoxLayout()
        output_label = QLabel("Output:")
        header_layout.addWidget(output_label)
        header_layout.addStretch()

        self.report_btn = QPushButton("View Last Report")
        self.report_btn.clicked.connect(self._view_last_report)
        self.report_btn.setEnabled(
            True
        )  # Always enabled since we can find reports automatically
        self.report_btn.setStyleSheet("background-color: #1976d2;")
        self.report_btn.setToolTip(
            "View detailed report of the last YouTube extraction process.\n"
            "• Shows which videos were processed successfully\n"
            "• Lists any errors or skipped videos\n"
            "• Includes download statistics and timing information\n"
            "• Opens the report in your default web browser"
        )
        header_layout.addWidget(self.report_btn)

        layout.addLayout(header_layout)

        # Output text area with improved size policy for better resizing
        self.output_text = QTextEdit()
        self.output_text.setReadOnly(True)
        self.output_text.setMinimumHeight(200)
        # Remove the maximum height constraint that was causing layout issues
        from PyQt6.QtWidgets import QSizePolicy

        # Use MinimumExpanding vertically to allow proper resizing
        self.output_text.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.MinimumExpanding
        )
        layout.addWidget(self.output_text)

        return layout

    def _select_url_file(self) -> None:
        """ Select file containing YouTube URLs."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select URL File", "", "Text files (*.txt *.csv);;All files (*.*)"
        )
        if file_path:
            self.file_input.setText(file_path)

    def _select_output_directory(self) -> None:
        """ Select output directory for YouTube transcripts."""
        dir_path = QFileDialog.getExistingDirectory(self, "Select Output Directory")
        if dir_path:
            self.output_dir_input.setText(dir_path)

    def _get_start_button_text(self) -> str:
        """ Get the text for the start button."""
        return "🎬 Extract Transcripts"

    def _start_processing(self) -> None:
        """ Start YouTube transcript extraction."""
        # Check WebShare credentials from settings
        webshare_username = self.settings.api_keys.webshare_username
        webshare_password = self.settings.api_keys.webshare_password

        if not webshare_username or not webshare_password:
            self.show_warning(
                "Missing Credentials",
                "WebShare proxy credentials are required for YouTube processing.\n\n"
                "Please go to the Settings tab and enter your WebShare Username and Password.",
            )
            return

        # Get URLs with early logging
        logger.info("Starting YouTube extraction process - collecting URLs...")
        logger.info(f"URL radio checked: {self.url_radio.isChecked()}")
        logger.info(f"File radio checked: {self.file_radio.isChecked()}")
        if self.file_radio.isChecked():
            logger.info(f"Selected file: {self.file_input.text().strip()}")

        urls = self._collect_urls()
        logger.info(f"Collected {len(urls)} URLs for processing")

        # DEBUGGING: Log first few URLs to verify they're valid
        if urls:
            logger.info(f"First few URLs: {urls[:3]}")
            # Validate URLs are properly formatted
            invalid_urls = [
                url
                for url in urls
                if not (
                    url.startswith("http")
                    and ("youtube.com" in url or "youtu.be" in url)
                )
            ]
            if invalid_urls:
                logger.warning(
                    f"Found {len(invalid_urls)} invalid URLs: {invalid_urls[:3]}"
                )

        if not urls:
            logger.info("No URLs found - showing warning to user")
            self.show_warning(
                "No URLs", "Please enter YouTube URLs or select a file containing URLs."
            )
            return

        # Additional safety check to prevent empty worker creation
        if len(urls) == 0:
            logger.warning("URL list is empty - aborting processing")
            return

        # Validate inputs
        if not self.validate_inputs():
            logger.info("Input validation failed - aborting processing")
            return

        # Get output directory
        output_dir = self.output_dir_input.text().strip()
        if not output_dir:
            output_dir = str(Path.cwd())

        logger.info(f"Starting extraction of {len(urls)} YouTube URLs to {output_dir}")

        # Clear output and start processing
        self.output_text.clear()
        self.append_log(f"Starting extraction of {len(urls)} YouTube URLs...")
        self.append_log(f"Using WebShare proxy: {webshare_username}")
        self.append_log(f"Output directory: {output_dir}")
        self.append_log("-" * 50)

        # Disable start button
        self.start_btn.setEnabled(False)
        self.start_btn.setText("Processing...")
        self.stop_btn.setEnabled(True)  # Enable stop button

        # Configure extraction
        config = {
            "output_dir": output_dir,
            "format": self.format_combo.currentText(),
            "timestamps": self.timestamps_checkbox.isChecked(),
            "overwrite": self.overwrite_checkbox.isChecked(),
        }

        # CRITICAL DEBUG: Log the exact config being passed to worker
        logger.info(f"🔧 Extraction config created:")
        logger.info(
            f"   output_dir: {repr(config['output_dir'])} (type: {type(config['output_dir'])})"
        )
        logger.info(f"   format: {config['format']}")
        logger.info(f"   timestamps: {config['timestamps']}")
        logger.info(f"   overwrite: {config['overwrite']}")
        logger.info(
            f"   Output directory exists: {Path(config['output_dir']).exists() if config['output_dir'] else False}"
        )
        logger.info(
            f"   Output directory is writable: {os.access(config['output_dir'], os.W_OK) if config['output_dir'] and Path(config['output_dir']).exists() else 'Unknown'}"
        )

        # Final safety check before creating worker
        if not urls or len(urls) == 0:
            logger.error(
                "CRITICAL: Attempting to create worker with empty URL list - aborting!"
            )
            self.show_error("Internal Error", "No URLs available for processing")
            self._reset_ui_state()
            return

        # Start extraction worker
        logger.info(f"Creating YouTube extraction worker with {len(urls)} URLs")
        logger.info(f"Worker config will be: {config}")
        self.extraction_worker = YouTubeExtractionWorker(urls, config, self)
        self.extraction_worker.progress_updated.connect(
            self._update_extraction_progress
        )
        self.extraction_worker.url_completed.connect(self._url_extraction_completed)
        self.extraction_worker.extraction_finished.connect(self._extraction_finished)
        self.extraction_worker.extraction_error.connect(self._extraction_error)
        self.extraction_worker.payment_required.connect(
            self._show_payment_required_dialog
        )
        self.extraction_worker.playlist_info_updated.connect(self._handle_playlist_info)

        self.active_workers.append(self.extraction_worker)
        logger.info("Starting YouTube extraction worker thread")
        self.extraction_worker.start()

        self.status_updated.emit("YouTube extraction in progress...")

    def _stop_processing(self):
        """ Stop the currently running extraction process."""
        if self.extraction_worker and self.extraction_worker.isRunning():
            self.extraction_worker.stop()
            self.stop_btn.setEnabled(False)
            self.start_btn.setEnabled(True)
            self.start_btn.setText(self._get_start_button_text())
            self.status_updated.emit("YouTube extraction stopped.")
            self.append_log("YouTube extraction stopped by user.")
        else:
            self.show_warning(
                "No Process Running",
                "No YouTube extraction process is currently running.",
            )

    def _collect_urls(self) -> list[str]:
        """ Collect URLs from input fields based on selected input method."""
        urls = []

        # BUGFIX: Only collect URLs from the selected source, not both
        if self.url_radio.isChecked():
            # Get URLs from text input ONLY
            logger.debug("Collecting URLs from text input (URL radio selected)")
            text_urls = self.url_input.toPlainText().strip()
            if text_urls:
                for line in text_urls.split("\n"):
                    line = line.strip()
                    if line and ("youtube.com" in line or "youtu.be" in line):
                        urls.append(line)
                logger.debug(f"Found {len(urls)} URLs in text input")
            else:
                logger.debug("No URLs found in text input")

        elif self.file_radio.isChecked():
            # Get URLs from file ONLY
            file_path = self.file_input.text().strip()
            logger.debug(
                f"Collecting URLs from file (file radio selected): {file_path}"
            )
            if file_path:
                try:
                    with open(file_path, encoding="utf-8") as f:
                        content = f.read()

                    # Handle RTF files
                    if content.startswith("{\\rtf"):
                        import re

                        url_pattern = r"https?://[^\s\\,}]+"
                        found_urls = re.findall(url_pattern, content)
                        for url in found_urls:
                            url = url.rstrip("\\,}")
                            if "youtube.com" in url or "youtu.be" in url:
                                urls.append(url)
                    else:
                        # Plain text/CSV file
                        for line in content.split("\n"):
                            line = line.strip()
                            if line and not line.startswith("#"):
                                # Handle both comma-separated and line-separated URLs
                                if "," in line:
                                    # CSV format: split by comma
                                    for url in line.split(","):
                                        url = url.strip()
                                        if url and (
                                            "youtube.com" in url or "youtu.be" in url
                                        ):
                                            urls.append(url)
                                else:
                                    # Plain text format: one URL per line
                                    if "youtube.com" in line or "youtu.be" in line:
                                        urls.append(line)
                    logger.debug(f"Found {len(urls)} URLs in file: {file_path}")
                except Exception as e:
                    logger.error(f"Failed to read URL file {file_path}: {e}")
                    self.show_error("File Error", f"Could not read URL file: {e}")
                    return []
            else:
                logger.debug("No file selected")
        else:
            logger.warning("Neither radio button is selected - this should not happen")

        # Remove duplicates and log final result
        unique_urls = list(set(urls))
        logger.info(
            f"Collected {len(unique_urls)} unique URLs from {'text input' if self.url_radio.isChecked() else 'file'}"
        )
        if len(unique_urls) != len(urls):
            logger.debug(f"Removed {len(urls) - len(unique_urls)} duplicate URLs")

        return unique_urls

    def _update_extraction_progress(self, current: int, total: int, status: str):
        """ Update extraction progress."""
        if total > 0:
            percent = (current / total) * 100
            # Display the full enhanced status message
            self.append_log(status)

            # Create a cleaner progress label
            if (
                "Processing:" in status
                or "Fetching metadata" in status
                or "Transcript extracted:" in status
                or "Saved" in status
            ):
                # Extract just the essential info for the progress label
                if current < total:
                    self.progress_label.setText(
                        f"Processing {current + 1} of {total} URLs ({percent:.1f}%)"
                    )
                else:
                    self.progress_label.setText(
                        f"Completed {total} of {total} URLs (100%)"
                    )
            else:
                self.progress_label.setText(f"Processing {current} of {total} URLs...")

            self.progress_bar.setValue(int(percent))
            self.progress_bar.setVisible(True)
        else:
            self.append_log(status)
            self.progress_bar.setValue(0)
            self.progress_bar.setVisible(False)
            self.progress_label.setText(status)

    def _url_extraction_completed(self, url: str, success: bool, message: str):
        """ Handle completion of single URL extraction."""
        self.append_log(f"  → {message}")

    def _extraction_finished(self, results: dict[str, Any]):
        """ Handle completion of all extractions."""
        self.append_log("\n" + "=" * 50)
        self.append_log("🎬 YouTube extraction completed!")
        self.append_log(
            f"✅ Fully successful: {results['successful']} (extracted and saved)"
        )

        # Show skipped files if any
        skipped_count = results.get("skipped", 0)
        if skipped_count > 0:
            self.append_log(
                f"⏭️ Skipped existing: {skipped_count} (files already exist, overwrite disabled)"
            )

        self.append_log(f"❌ Failed: {results['failed']}")

        # Calculate files that were extracted but not saved (partial failures)
        total_attempted = results["successful"] + results["failed"] + skipped_count

        # Show where files were saved
        output_dir = self.output_dir_input.text().strip()
        if not output_dir:
            output_dir = str(Path.cwd())

        self.append_log(f"\n📁 Output directory: {output_dir}")

        if results["successful"] > 0:
            self.append_log(
                f"\n🎉 Successfully processed and saved {results['successful']} video(s)!"
            )
            self.append_log("📝 Check the output directory for .md transcript files")
            self.append_log(
                "🖼️  Check the Thumbnails subdirectory for thumbnail images"
            )

        if skipped_count > 0:
            self.append_log(f"\n⏭️ Skipped {skipped_count} existing file(s):")
            for skipped_item in results.get("skipped_urls", []):
                if isinstance(skipped_item, dict):
                    title = skipped_item.get("title", "Unknown Title")
                    reason = skipped_item.get("reason", "Already exists")
                    self.append_log(f"  • {title} - {reason}")
            self.append_log(
                "💡 To overwrite existing files, check the 'Overwrite existing transcripts' option"
            )

        if results["failed"] > 0:
            self.append_log(f"\n⚠️  {results['failed']} video(s) had issues:")
            for failed_item in results["failed_urls"]:
                if isinstance(failed_item, dict):
                    title = failed_item.get("title", "Unknown Title")
                    error = failed_item.get("error", "Unknown error")
                    self.append_log(f"  • {title} - {error}")
                else:
                    self.append_log(f"  • {failed_item}")

        # Write failure log if there were any failures
        if (
            results["failed"] > 0
            and results.get("failed_urls")
            and self.extraction_worker
        ):
            log_file, csv_file = self.extraction_worker._write_failure_log(
                results["failed_urls"]
            )
            if log_file and csv_file:
                self.append_log(f"\n📋 Failed extractions logged to: {log_file}")
                self.append_log(f"🔄 Failed URLs saved for retry to: {csv_file}")
                self.append_log(
                    f"   💡 Tip: You can load the CSV file directly to retry failed extractions"
                )
            else:
                self.append_log(
                    f"\n⚠️ Warning: Could not write failure logs (check logs directory permissions)"
                )

        # Show summary of what files were actually created
        total_processed = results["successful"] + skipped_count
        if total_processed > 0:
            if results["successful"] > 0 and skipped_count > 0:
                self.append_log(
                    f"\n📊 Summary: {results['successful']} new files saved, {skipped_count} existing files skipped"
                )
            elif results["successful"] > 0:
                self.append_log(
                    f"\n📊 Summary: {results['successful']} transcript files saved to {output_dir}"
                )
            else:
                self.append_log(
                    f"\n📊 Summary: {skipped_count} files already existed (no new files created)"
                )
        else:
            self.append_log(
                f"\n📊 Summary: No files were saved. Check the issues above."
            )

        # Reset UI
        self.start_btn.setEnabled(True)
        self.start_btn.setText(self._get_start_button_text())
        self.stop_btn.setEnabled(False)  # Disable stop button
        self.progress_bar.setVisible(False)
        self.progress_bar.setValue(100)

        # Enhanced completion message with playlist context
        total_processed = results["successful"] + skipped_count
        playlist_count = len(results.get("playlist_info", []))

        if results["successful"] > 0:
            if playlist_count > 0:
                self.progress_label.setText(
                    f"Completed! {results['successful']} files saved from {playlist_count} playlist(s) + individual videos."
                )
            else:
                self.progress_label.setText(
                    f"Completed! {results['successful']} files saved successfully."
                )
        else:
            if playlist_count > 0:
                self.progress_label.setText(
                    f"Completed - processed {playlist_count} playlist(s) but no files were saved. See log for details."
                )
            else:
                self.progress_label.setText(
                    "Completed - but no files were saved. See log for details."
                )

        self.status_updated.emit("YouTube extraction completed")
        self.processing_finished.emit()

    def _extraction_error(self, error_msg: str):
        """ Handle extraction error."""
        self.append_log(f"❌ Error: {error_msg}")
        self.show_error("Extraction Error", f"YouTube extraction failed: {error_msg}")

        # Reset UI
        self.start_btn.setEnabled(True)
        self.start_btn.setText(self._get_start_button_text())
        self.stop_btn.setEnabled(False)  # Disable stop button
        self.progress_bar.setVisible(False)
        self.progress_bar.setValue(0)
        self.progress_label.setText("Extraction failed")

        self.status_updated.emit("Ready")

    def _show_payment_required_dialog(self):
        """ Show popup dialog for 402 Payment Required error."""
        from PyQt6.QtWidgets import QMessageBox

        from ..assets.icons import get_app_icon

        payment_dialog = QMessageBox(self)
        payment_dialog.setIcon(QMessageBox.Icon.Warning)
        payment_dialog.setWindowTitle("WebShare Payment Required")
        payment_dialog.setText("💰 WebShare Proxy Payment Required")
        payment_dialog.setInformativeText(
            "Your WebShare proxy account has run out of funds and requires payment to continue.\n\n"
            "Please visit https://panel.webshare.io/ to add payment to your account.\n\n"
            "This is not a bug in our application - it's a billing issue with your proxy service."
        )
        payment_dialog.setStandardButtons(QMessageBox.StandardButton.Ok)

        # Set custom window icon
        custom_icon = get_app_icon()
        if custom_icon:
            payment_dialog.setWindowIcon(custom_icon)

        payment_dialog.exec()

    def _handle_playlist_info(self, playlist_data: dict):
        """ Handle enhanced playlist and video information from worker."""
        playlists = playlist_data.get("playlists", [])
        total_playlists = playlist_data.get("total_playlists", 0)
        total_videos = playlist_data.get("total_videos", 0)
        playlist_videos = playlist_data.get("playlist_videos", 0)
        individual_videos = playlist_data.get("individual_videos", 0)
        summary = playlist_data.get("summary", "")

        # Show comprehensive content summary
        self.append_log(f"\n📊 Content Analysis:")
        if summary:
            self.append_log(f"   • {summary}")
            self.append_log(f"   • Grand Total: {total_videos} videos to process")
        else:
            self.append_log(f"   • Total: {total_videos} videos to process")

        # Show detailed playlist breakdown
        if total_playlists > 0:
            self.append_log(f"\n📋 Playlist Details:")
            for i, playlist in enumerate(playlists, 1):
                title = playlist.get("title", "Unknown Playlist")
                video_count = playlist.get("total_videos", 0)
                start_index = playlist.get("start_index", 0) + 1  # Convert to 1-indexed
                end_index = playlist.get("end_index", 0) + 1  # Convert to 1-indexed

                # Truncate long playlist titles for readability
                display_title = title[:50] + "..." if len(title) > 50 else title
                self.append_log(f"   {i}. {display_title}")
                self.append_log(
                    f"      └─ {video_count} videos (Global positions {start_index}-{end_index})"
                )

        self.append_log("")  # Add blank line for spacing

    def _load_settings(self) -> None:
        """ Load saved settings from session."""
        try:
            # Load output directory
            saved_output_dir = self.gui_settings.get_output_directory(
                self.tab_name, str(self.settings.paths.transcripts)
            )
            self.output_dir_input.setText(saved_output_dir)

            # Load format selection
            saved_format = self.gui_settings.get_combo_selection(
                self.tab_name, "format", "md"
            )
            index = self.format_combo.findText(saved_format)
            if index >= 0:
                self.format_combo.setCurrentIndex(index)

            # Load checkbox states
            self.timestamps_checkbox.setChecked(
                self.gui_settings.get_checkbox_state(
                    self.tab_name, "include_timestamps", True
                )
            )
            self.overwrite_checkbox.setChecked(
                self.gui_settings.get_checkbox_state(
                    self.tab_name, "overwrite_existing", False
                )
            )

            # Load radio button state (use checkbox method for boolean values)
            url_radio_selected = self.gui_settings.get_checkbox_state(
                self.tab_name, "url_radio_selected", True
            )
            if url_radio_selected:
                self.url_radio.setChecked(True)
            else:
                self.file_radio.setChecked(True)
            self._on_input_method_changed()  # Apply the selection

            logger.debug(f"Loaded settings for {self.tab_name} tab")
        except Exception as e:
            logger.error(f"Failed to load settings for {self.tab_name} tab: {e}")

    def _save_settings(self) -> None:
        """ Save current settings to session."""
        try:
            # Save output directory
            self.gui_settings.set_output_directory(
                self.tab_name, self.output_dir_input.text()
            )

            # Save combo selections
            self.gui_settings.set_combo_selection(
                self.tab_name, "format", self.format_combo.currentText()
            )

            # Save checkbox states
            self.gui_settings.set_checkbox_state(
                self.tab_name,
                "include_timestamps",
                self.timestamps_checkbox.isChecked(),
            )
            self.gui_settings.set_checkbox_state(
                self.tab_name, "overwrite_existing", self.overwrite_checkbox.isChecked()
            )

            # Save radio button state (use checkbox method for boolean values)
            self.gui_settings.set_checkbox_state(
                self.tab_name, "url_radio_selected", self.url_radio.isChecked()
            )

            # Save session data to disk
            self.gui_settings.save()

            logger.debug(f"Saved settings for {self.tab_name} tab")
        except Exception as e:
            logger.error(f"Failed to save settings for {self.tab_name} tab: {e}")

    def _on_setting_changed(self):
        """ Called when any setting changes to automatically save."""
        self._save_settings()

    def validate_inputs(self) -> bool:
        """ Validate inputs before processing."""
        # Check output directory
        output_dir = self.output_dir_input.text().strip()
        if not output_dir:
            self.show_error("Invalid Output", "Output directory must be selected.")
            return False

        if not Path(output_dir).exists():
            self.show_error(
                "Invalid Output", f"Output directory does not exist: {output_dir}"
            )
            return False

        if not Path(output_dir).is_dir():
            self.show_error(
                "Invalid Output", f"Output directory is not a directory: {output_dir}"
            )
            return False

        if not os.access(output_dir, os.W_OK):
            self.show_error(
                "Invalid Output", f"Output directory is not writable: {output_dir}"
            )
            return False

        # Check WebShare proxy credentials (required for YouTube processing)
        webshare_username = getattr(self.settings.api_keys, "webshare_username", None)
        webshare_password = getattr(self.settings.api_keys, "webshare_password", None)

        if not webshare_username or not webshare_password:
            self.show_error(
                "Missing WebShare Credentials",
                "YouTube processing requires WebShare rotating residential proxy credentials.\n\n"
                "Please configure your WebShare Username and Password in the Settings tab.\n\n"
                "This system uses only WebShare proxies for YouTube access - no other methods are supported.\n\n"
                "Sign up at: https://www.webshare.io/",
            )
            return False

        return True

    def cleanup_workers(self):
        """ Clean up any active workers."""
        if self.extraction_worker and self.extraction_worker.isRunning():
            self.extraction_worker.stop()
            self.extraction_worker.wait(3000)
        super().cleanup_workers()

    def _reset_ui_state(self):
        """ Reset UI to initial state."""
        self.start_btn.setEnabled(True)
        self.start_btn.setText(self._get_start_button_text())
        self.stop_btn.setEnabled(False)
        self.progress_bar.setVisible(False)
        self.progress_bar.setValue(0)
        self.progress_label.setText("Ready to extract transcripts")
