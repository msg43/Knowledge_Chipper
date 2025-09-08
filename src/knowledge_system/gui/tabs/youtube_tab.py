"""YouTube extraction tab for downloading and processing YouTube transcripts."""

import os  # Added for os.access
from pathlib import Path
from typing import Any

from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
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

from ...config import get_valid_whisper_models
from ...logger import get_logger
from ...utils.cancellation import CancellationToken
from ..components.base_tab import BaseTab
from ..components.completion_summary import CloudTranscriptionSummary
from ..components.enhanced_error_dialog import show_enhanced_error
from ..components.enhanced_progress_display import CloudTranscriptionStatusDisplay
from ..core.settings_manager import get_gui_settings_manager
from ..dialogs.diarization_ffmpeg_dialog import DiarizationFFmpegDialog
from ..dialogs.ffmpeg_prompt_dialog import FFmpegPromptDialog
from ..workers.youtube_batch_worker import YouTubeBatchWorker

logger = get_logger(__name__)


class YouTubeExtractionWorker(QThread):
    """Worker thread for YouTube transcript extraction."""

    progress_updated = pyqtSignal(int, int, str)  # current, total, status
    url_completed = pyqtSignal(str, bool, str)  # url, success, message
    extraction_finished = pyqtSignal(dict)  # final results
    extraction_error = pyqtSignal(str)
    payment_required = pyqtSignal()  # 402 Payment Required error
    playlist_info_updated = pyqtSignal(dict)  # playlist metadata for display
    log_message = pyqtSignal(str)  # for log messages from worker
    speaker_assignment_requested = pyqtSignal(
        object, str, object, object
    )  # data, path, metadata, result_callback

    def __init__(self, urls: Any, config: Any, parent: Any = None) -> None:
        super().__init__(parent)
        self.urls = urls
        self.config = config
        self.should_stop = False
        self.cancellation_token = CancellationToken()
        # Speaker assignment synchronization
        self._speaker_assignment_event = None
        self._speaker_assignment_result = None

        # Log worker creation details
        logger.info(f"YouTubeExtractionWorker created with {len(urls)} URLs")
        if len(urls) == 0:
            logger.warning("YouTubeExtractionWorker created with EMPTY URL list!")
        else:
            logger.info(f"URLs to process: {urls[:3]}{'...' if len(urls) > 3 else ''}")

    def run(self) -> None:
        """Run the YouTube extraction process."""
        logger.info(f"YouTubeExtractionWorker.run() started with {len(self.urls)} URLs")

        # Early check for empty URL list
        if not self.urls or len(self.urls) == 0:
            logger.warning("Worker started with empty URL list - exiting immediately")
            self.extraction_finished.emit(
                {"successful": 0, "failed": 0, "urls_processed": [], "failed_urls": []}
            )
            return

        try:
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

            # Instantiate processor; if diarization is enabled, force diarization path to bypass transcript requirement
            enable_diarization_cfg = bool(self.config.get("enable_diarization", False))
            if enable_diarization_cfg:
                logger.info(
                    "Diarization enabled in GUI - forcing diarization mode in processor"
                )
                processor = YouTubeTranscriptProcessor(
                    force_diarization=True,
                    require_diarization=False,
                )
            else:
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
                        i, total_urls, f"❌ Cloud transcription cancelled after {i} URLs"
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
                    logger.info("🔧 Processor parameters:")
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
                        logger.info("🔧 Output directory validation:")
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
                        logger.warning("⚠️ No output_dir parameter provided!")

                    # Create progress callback to forward diarization progress to GUI
                    def progress_callback(message: str, percent: int = 0):
                        """Forward diarization progress messages to GUI console."""
                        # Emit progress update with detailed message
                        self.progress_updated.emit(
                            i,
                            total_urls,
                            f"🎙️ {global_progress} ({percent}%) {message}",
                        )

                    # Pass cancellation token and progress callback to processor
                    enable_diarization = self.config.get("enable_diarization", False)
                    testing_mode = (
                        os.environ.get("KNOWLEDGE_CHIPPER_TESTING_MODE") == "1"
                    )

                    result = processor.process(
                        url,
                        output_dir=self.config.get("output_dir"),
                        output_format=self.config.get("format", "md"),
                        include_timestamps=self.config.get("timestamps", True),
                        overwrite=self.config.get("overwrite", False),
                        enable_diarization=enable_diarization,
                        gui_mode=not testing_mode,  # Enable GUI mode unless testing
                        show_speaker_dialog=(
                            enable_diarization and not testing_mode
                        ),  # Show dialog if diarization enabled and not testing
                        cancellation_token=self.cancellation_token,
                        progress_callback=progress_callback,
                        speaker_assignment_callback=self._speaker_assignment_callback,
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

                            # CRITICAL: Do NOT create dialogs from worker threads!
                            # Instead, emit a signal to show guidance on the main thread
                            if (
                                "Diarization failed" in error_msg
                                or "diarization" in error_msg.lower()
                            ):
                                guidance = (
                                    "Diarization failed. To fix:\n\n"
                                    "1) Ensure HuggingFace token is set (Settings → API Keys).\n"
                                    "2) Accept access to pyannote/speaker-diarization-3.1 on HuggingFace.\n"
                                    "3) Verify ffmpeg/ffprobe are installed and on PATH.\n"
                                    "4) Check network stability and retry.\n\n"
                                    "This URL has been added to the failure CSV for easy re-run."
                                )

                                # Emit signal to show guidance on main thread (thread-safe)
                                self.log_message.emit(f"❌ {error_msg}")
                                self.log_message.emit(f"💡 {guidance}")

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
            completion_msg = f"🎉 Cloud transcription complete! ✅ {results['successful']} successful, ❌ {results['failed']} failed out of {total_urls} total URLs"
            self.progress_updated.emit(total_urls, total_urls, completion_msg)

            # Emit completion
            self.extraction_finished.emit(results)

        except Exception as e:
            error_msg = f"YouTube extraction failed: {str(e)}"
            logger.error(error_msg)
            self.extraction_error.emit(error_msg)
            self.progress_updated.emit(0, len(self.urls), f"💥 Fatal error: {error_msg}")

    def stop(self) -> None:
        """Stop the extraction process."""
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
                f.write("YouTube Cloud Transcription Failures\n")
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
                        f.write("   Error: No additional information available\n\n")

                f.write(f"\n{'='*70}\n")
                f.write("Note: This is a session-specific failure log.\n")
                f.write(f"For retry, use the corresponding CSV file: {csv_file.name}\n")
                f.write(f"{'='*70}\n")

            # Create timestamped CSV file with failed URLs for easy re-import
            formatted_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            with open(csv_file, "w", newline="", encoding="utf-8") as csvfile:
                # Write header comments
                csvfile.write(
                    "# YouTube Cloud Transcription Failures - URLs for retry\n"
                )
                csvfile.write(f"# Session: {formatted_timestamp}\n")
                csvfile.write(f"# Total failures: {len(failed_urls)}\n")
                csvfile.write("#\n")
                csvfile.write("# Instructions:\n")
                csvfile.write(
                    "# 1. You can load this file directly into the Cloud Transcription tab\n"
                )
                csvfile.write(
                    "# 2. Select 'Or Select File' option and browse to this CSV\n"
                )
                csvfile.write("# 3. Click 'Start Transcription' to retry failed URLs\n")
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

    def _speaker_assignment_callback(
        self, speaker_data_list, recording_path, metadata=None
    ):
        """
        Thread-safe callback for speaker assignment requests from worker thread.
        Emits a signal to the main thread to show the dialog, then waits for result.
        """
        import threading

        self._speaker_assignment_event = threading.Event()
        self._speaker_assignment_result = None

        # Emit to main thread with a result callback
        self.speaker_assignment_requested.emit(
            speaker_data_list,
            recording_path,
            metadata,
            self._on_speaker_assignment_result,
        )

        # Wait up to 5 minutes
        if self._speaker_assignment_event:
            self._speaker_assignment_event.wait(timeout=300)

        result = self._speaker_assignment_result
        self._speaker_assignment_result = None
        self._speaker_assignment_event = None
        return result

    def _on_speaker_assignment_result(self, result):
        self._speaker_assignment_result = result
        if self._speaker_assignment_event:
            self._speaker_assignment_event.set()


class YouTubeTab(BaseTab):
    """Tab for YouTube transcript extraction and processing."""

    def __init__(self, parent: Any = None) -> None:
        self.extraction_worker = None
        self.gui_settings = get_gui_settings_manager()
        self.tab_name = "Cloud Transcription"
        # Reentrancy guard for progress updates to prevent recursion
        self._progress_update_inflight = False
        super().__init__(parent)

    def _setup_ui(self) -> None:
        """Setup the YouTube extraction UI."""
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
        """Create the URL input section."""
        group = QGroupBox("YouTube or RSS URLs")
        layout = QVBoxLayout()

        # Radio button for URL input
        self.url_radio = QRadioButton("YouTube or RSS URLs")
        self.url_radio.setChecked(True)  # Default selection
        self.url_radio.toggled.connect(self._on_input_method_changed)
        self.url_radio.setToolTip(
            "Enter YouTube URLs or RSS feeds directly in the text area below"
        )
        layout.addWidget(self.url_radio)

        # URL input
        self.url_input = QTextEdit()
        self.url_input.setPlaceholderText(
            "Enter YouTube URLs, Playlist URLs, or RSS feeds (one per line):\n"
            "https://www.youtube.com/watch?v=...\n"
            "https://youtu.be/...\n"
            "https://www.youtube.com/playlist?list=...\n"
            "https://example.com/feed.rss"
        )
        self.url_input.setMinimumHeight(150)
        self.url_input.setMaximumHeight(200)  # Prevent it from growing too large
        from PyQt6.QtWidgets import QSizePolicy

        self.url_input.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self.url_input.setToolTip(
            "Enter YouTube URLs or RSS feeds to process (one per line).\n"
            "• Individual videos: https://www.youtube.com/watch?v=...\n"
            "• Short URLs: https://youtu.be/...\n"
            "• Playlists: https://www.youtube.com/playlist?list=...\n"
            "• RSS feeds: https://example.com/feed.rss\n"
            "• Mix any combination of videos, playlists, and RSS feeds\n"
            "• Total video count will be calculated automatically\n"
            "• Private or unavailable content will be skipped with warnings"
        )
        layout.addWidget(self.url_input)

        # Radio button for file input
        self.file_radio = QRadioButton("Or Select File")
        self.file_radio.toggled.connect(self._on_input_method_changed)
        self.file_radio.setToolTip(
            "Select this option to load URLs from a file.\n"
            "• Supports .TXT, .RTF, and .CSV files\n"
            "• File should contain one URL per line (YouTube or RSS)\n"
            "• Useful for large collections of URLs"
        )
        layout.addWidget(self.file_radio)

        # File input
        file_layout = QHBoxLayout()
        file_layout.addWidget(
            QLabel(
                "Select a .TXT, .RTF, or .CSV file with YouTube URLs/Playlists or RSS feeds:"
            )
        )

        self.file_input = QLineEdit()
        self.file_input.setPlaceholderText("Select a file containing URLs...")
        self.file_input.setEnabled(False)  # Start disabled
        self.file_input.setToolTip(
            "Path to file containing YouTube URLs or RSS feeds.\n"
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
            "Browse and select a file containing YouTube URLs or RSS feeds.\n"
            "• Choose a .TXT, .RTF, or .CSV file\n"
            "• File should have one URL per line\n"
            "• Will automatically count total videos"
        )
        file_layout.addWidget(self.browse_btn)

        layout.addLayout(file_layout)
        group.setLayout(layout)
        return group

    def _on_input_method_changed(self) -> None:
        """Handle radio button changes to enable/disable input sections."""
        if self.url_radio.isChecked():
            # Enable URL input, disable file input
            self.url_input.setEnabled(True)
            self.file_input.setEnabled(False)
            self.browse_btn.setEnabled(False)

            # BUGFIX: Reset URL input styling with proper font and apply disabled styling to file input
            self.url_input.setStyleSheet(
                "font-family: 'Arial', sans-serif;"
            )  # Reset URL input with font
            self.file_input.setStyleSheet(
                "color: gray; font-family: 'Arial', sans-serif;"
            )  # Gray out file input with font
        else:
            # Enable file input, disable URL input
            self.url_input.setEnabled(False)
            self.file_input.setEnabled(True)
            self.browse_btn.setEnabled(True)

            # BUGFIX: Reset file input styling with proper font and apply disabled styling to URL input
            self.url_input.setStyleSheet(
                "color: gray; font-family: 'Arial', sans-serif;"
            )  # Gray out URL input with font
            self.file_input.setStyleSheet(
                "font-family: 'Arial', sans-serif;"
            )  # Reset file input with font

        # Save the radio button state change
        self._save_settings()

    def _create_settings_section(self) -> QGroupBox:
        """Create the extraction settings section."""
        group = QGroupBox("Cloud Transcription Settings")
        layout = QGridLayout()

        # Output directory
        self.output_dir_input = QLineEdit()
        self.output_dir_input.setPlaceholderText(
            "Click Browse to select output directory (required)"
        )
        # Make output directory field significantly longer (300% of original)
        self.output_dir_input.setMinimumWidth(450)
        # Remove default setting - require user selection
        self.output_dir_input.textChanged.connect(self._on_setting_changed)
        self._add_field_with_info(
            layout,
            "Output Directory:",
            self.output_dir_input,
            "Directory where transcript files and thumbnails will be saved.\n"
            "• Click Browse to select a directory\n"
            "• Ensure it has write permissions\n"
            "• Transcripts will be in .md format, thumbnails in a subdirectory",
            0,
            0,
        )

        browse_output_btn = QPushButton("Browse")
        browse_output_btn.clicked.connect(self._select_output_directory)
        browse_output_btn.setToolTip(
            "Browse and select the output directory for transcript files and thumbnails.\n"
            "• Choose a directory to save transcript .md files and thumbnail images"
        )
        layout.addWidget(browse_output_btn, 0, 2)

        # Format selection
        self.format_combo = QComboBox()
        self.format_combo.addItems(["md", "txt", "json"])
        self.format_combo.setCurrentText("md")
        self.format_combo.currentTextChanged.connect(self._on_setting_changed)
        self._add_field_with_info(
            layout,
            "Output Format:",
            self.format_combo,
            "Select the output format for the transcript.\n"
            "• md: Markdown format (default)\n"
            "• txt: Plain text\n"
            "• json: JSON format (for advanced processing)",
            1,
            0,
        )

        # Transcription model selection - on the same line as Output Format
        self.transcription_model_combo = QComboBox()
        self.transcription_model_combo.addItems(get_valid_whisper_models())
        self.transcription_model_combo.setCurrentText("base")
        self.transcription_model_combo.currentTextChanged.connect(
            self._on_setting_changed
        )
        self.transcription_model_combo.setToolTip(
            "<b>Transcription Model</b> - Choose Whisper model for diarization<br/><br/>"
            "<b>Models (accuracy vs speed):</b><br/>"
            "• <b>tiny</b>: Fastest, least accurate (39 MB)<br/>"
            "• <b>base</b>: Good balance (74 MB) - recommended<br/>"
            "• <b>small</b>: Better accuracy (244 MB)<br/>"
            "• <b>medium</b>: High accuracy (769 MB)<br/>"
            "• <b>large</b>: Best accuracy (1550 MB)<br/><br/>"
            "<b>💡 Tip:</b> Start with 'base' model. Use larger models only if you need better accuracy."
        )
        self._add_field_with_info(
            layout,
            "Transcription Model:",
            self.transcription_model_combo,
            "Model used for speech recognition during diarization",
            1,
            2,
        )

        self.overwrite_checkbox = QCheckBox("Overwrite existing transcripts")
        self.overwrite_checkbox.setChecked(False)
        self.overwrite_checkbox.toggled.connect(self._on_setting_changed)
        self.overwrite_checkbox.setToolTip(
            "If enabled, existing transcript files will be overwritten.\n"
            "• If disabled, new transcript files will be named with a timestamp\n"
            "• This prevents accidental overwriting of existing work"
        )
        layout.addWidget(self.overwrite_checkbox, 2, 0, 1, 2)

        # Enable speaker diarization - on the same line as Overwrite checkbox
        self.diarization_checkbox = QCheckBox("Enable speaker diarization")
        self.diarization_checkbox.setChecked(True)
        self.diarization_checkbox.toggled.connect(self._on_setting_changed)
        self.diarization_checkbox.setToolTip(
            "<b>Speaker Diarization</b> - AI-powered speaker identification<br/><br/>"
            "<b>🎯 What it does:</b><br/>"
            "• Identifies and labels different speakers in audio/video content<br/>"
            "• Creates transcripts with speaker labels (Speaker 1, Speaker 2, etc.)<br/>"
            "• Uses advanced AI to distinguish voices, accents, and speaking patterns<br/><br/>"
            "<b>📝 Example Output:</b><br/>"
            "<i>Speaker 1: Welcome to today's podcast.<br/>"
            "Speaker 2: Thanks for having me on the show.<br/>"
            "Speaker 1: Let's dive into the topic...</i><br/><br/>"
            "<b>✅ Perfect for:</b><br/>"
            "• Podcasts, interviews, debates, panel discussions<br/>"
            "• Conference calls, meetings, webinars<br/>"
            "• Multi-person conversations or presentations<br/><br/>"
            "<b>❌ Skip for:</b><br/>"
            "• Single-speaker content (lectures, monologues, tutorials)<br/>"
            "• Music videos or content with background music<br/><br/>"
            "<b>⚙️ Requirements:</b><br/>"
            "• HuggingFace token (free - configure in API Keys tab)<br/>"
            "• Additional processing time (2-3x longer)<br/>"
            "• Automatically falls back to regular transcript if it fails<br/><br/>"
            "<b>💡 Pro Tip:</b> Try it on a short video first to see if it adds value for your content type!"
        )
        layout.addWidget(self.diarization_checkbox, 2, 2)

        # Download-all mode checkbox - positioned directly below Enable speaker diarization
        self.download_all_checkbox = QCheckBox("Download all audio files first")
        self.download_all_checkbox.setChecked(False)
        self.download_all_checkbox.toggled.connect(self._on_setting_changed)
        self.download_all_checkbox.setToolTip(
            "Download all audio files before processing (for slow internet connections).\n"
            "• Phase 1: Downloads all audio files (can disconnect internet after)\n"
            "• Phase 2: Processes all files offline with diarization\n"
            "• Best for: Slow internet, large disk space, overnight processing\n"
            "• System automatically checks if you have enough disk space\n"
            "• Falls back to normal mode if insufficient space"
        )
        layout.addWidget(self.download_all_checkbox, 3, 2)

        group.setLayout(layout)
        return group

    def _create_action_layout(self) -> QHBoxLayout:
        """Create the action buttons layout."""
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
            "• Requires Bright Data API key for YouTube access\n"
            "• Progress will be shown in real-time below"
        )
        # Make green and take 3/4 of the width
        self.start_btn.setStyleSheet(
            """
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
        layout.addWidget(self.start_btn, 3)  # 3/4 stretch factor

        self.stop_btn = QPushButton("Stop Cloud Transcription")
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
        layout.addWidget(self.stop_btn, 1)  # 1/4 stretch factor

        return layout

    def _create_progress_section(self) -> QVBoxLayout:
        """Create the progress tracking section."""
        layout = QVBoxLayout()

        # Enhanced cloud status display - this replaces all legacy progress components
        self.cloud_status_display = CloudTranscriptionStatusDisplay()
        layout.addWidget(self.cloud_status_display)

        # Legacy progress components - kept for compatibility but NOT added to layout to prevent overlap
        self.progress_label = QLabel("Ready to extract transcripts")
        self.progress_label.setVisible(False)  # Hidden - enhanced display handles this

        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)  # Hidden - enhanced display handles this

        # NOTE: Legacy components are intentionally NOT added to layout to prevent overlapping progress bars

        return layout

    def _create_output_section(self) -> QVBoxLayout:
        """Create the output section with improved resizing behavior."""
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
        """Select file containing YouTube URLs or RSS feeds."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select URL File", "", "Text files (*.txt *.csv);;All files (*.*)"
        )
        if file_path:
            self.file_input.setText(file_path)

    def _select_output_directory(self) -> None:
        """Select output directory for YouTube transcripts."""
        dir_path = QFileDialog.getExistingDirectory(self, "Select Output Directory")
        if dir_path:
            self.output_dir_input.setText(dir_path)

    def _get_start_button_text(self) -> str:
        """Get the text for the start button."""
        return "🎬 Start Transcription"

    def _check_diarization_dependencies(self) -> None:
        """Check and report status of diarization dependencies asynchronously."""
        # Start with immediate feedback
        self.append_log("🔍 Checking diarization dependencies...")

        # Use QThread for heavy dependency checking
        from PyQt6.QtCore import QThread, pyqtSignal

        class DiarizationCheckWorker(QThread):
            check_completed = pyqtSignal(bool, str, dict)  # success, message, gpu_info

            def run(self):
                try:
                    # Import and check dependencies (potentially slow)
                    from ...processors.diarization import (
                        _check_diarization_dependencies,
                    )

                    deps_available = _check_diarization_dependencies()

                    if deps_available:
                        # Check GPU availability (potentially slow)
                        gpu_info = {"has_torch": False, "backend": "cpu"}
                        try:
                            import torch

                            gpu_info["has_torch"] = True
                            if torch.backends.mps.is_available():
                                gpu_info["backend"] = "mps"
                            elif torch.cuda.is_available():
                                gpu_info["backend"] = "cuda"
                            else:
                                gpu_info["backend"] = "cpu"
                        except ImportError:
                            gpu_info["has_torch"] = False
                            gpu_info["backend"] = "cpu"

                        self.check_completed.emit(
                            True, "Dependencies available", gpu_info
                        )
                    else:
                        self.check_completed.emit(False, "Dependencies missing", {})

                except Exception as e:
                    self.check_completed.emit(False, f"Error: {e}", {})

        # Create and start worker
        self._diarization_worker = DiarizationCheckWorker()
        self._diarization_worker.check_completed.connect(
            self._handle_diarization_check_result
        )
        self._diarization_worker.start()

    def _handle_diarization_check_result(
        self, success: bool, message: str, gpu_info: dict
    ) -> None:
        """Handle the result of async diarization dependency check."""
        try:
            if success:
                self.append_log("✅ Diarization dependencies (pyannote.audio) available")

                # Check for HuggingFace token
                hf_token = getattr(self.settings.api_keys, "huggingface_token", None)
                if hf_token:
                    self.append_log(
                        "✅ HuggingFace token found - can use premium models"
                    )
                else:
                    self.append_log("ℹ️ No HuggingFace token - using default models")

                # Report GPU status
                if gpu_info.get("has_torch", False):
                    backend = gpu_info.get("backend", "cpu")
                    if backend == "mps":
                        self.append_log(
                            "✅ Apple Silicon GPU (MPS) available for diarization"
                        )
                    elif backend == "cuda":
                        self.append_log("✅ NVIDIA GPU (CUDA) available for diarization")
                    else:
                        self.append_log(
                            "ℹ️ Using CPU for diarization (slower but functional)"
                        )
                else:
                    self.append_log(
                        "ℹ️ Using CPU for diarization (PyTorch not available)"
                    )
            else:
                if "Dependencies missing" in message:
                    self.append_log("❌ Diarization dependencies missing!")
                    try:
                        from ..dialogs.diarization_setup_dialog import (
                            DiarizationSetupDialog,
                        )

                        # Offer guided installation
                        install_dialog = DiarizationSetupDialog(self)

                        def _after_install(success: bool):
                            if success:
                                self.append_log(
                                    "✅ Diarization dependencies installed. Continuing..."
                                )
                            else:
                                self.append_log(
                                    "❌ Diarization installation failed. You can retry later."
                                )

                        install_dialog.installation_completed.connect(_after_install)
                        install_dialog.exec()
                    except Exception:
                        # Fallback to simple warning if dialog import fails
                        self.append_log(
                            "   Install with: pip install -e '.[diarization]'"
                        )
                        self.show_warning(
                            "Diarization Dependencies Missing",
                            "Speaker diarization requires additional dependencies.\n\n"
                            "Please install with:\n"
                            "pip install -e '.[diarization]'\n\n"
                            "Or disable diarization to continue.",
                        )
                else:
                    self.append_log(
                        f"⚠️ Error checking diarization dependencies: {message}"
                    )
                    self.append_log(
                        "   Processing will continue but diarization may fail"
                    )

        finally:
            # Clean up worker
            if hasattr(self, "_diarization_worker"):
                self._diarization_worker.deleteLater()
                del self._diarization_worker

            # Continue processing if we have pending parameters
            if hasattr(self, "_pending_urls"):
                urls = self._pending_urls
                output_dir = self._pending_output_dir
                enable_diarization = self._pending_enable_diarization

                # Clean up pending parameters
                del self._pending_urls
                del self._pending_output_dir
                del self._pending_enable_diarization

                # Continue with processing
                self._finalize_and_start_processing(
                    urls, output_dir, enable_diarization
                )

    def _start_processing(self) -> None:
        """Start YouTube transcript extraction using intelligent processing mode selection."""
        # Clear output and show immediate initialization feedback
        self.output_text.clear()
        self.append_log("🔄 Initializing YouTube processing...")

        # Disable start button immediately to prevent multiple clicks
        self.start_btn.setEnabled(False)
        self.start_btn.setText("Initializing...")

        # Process UI events to show immediate feedback
        from PyQt6.QtWidgets import QApplication

        QApplication.processEvents()

        # Check if diarization is enabled first to determine FFMPEG requirements
        enable_diarization = self.diarization_checkbox.isChecked()

        # For diarization, we need a more thorough FFMPEG check with user interaction
        if enable_diarization:
            if not self._check_ffmpeg_for_diarization():
                self._reset_button_state()
                return
        else:
            # For non-diarization, use the standard check
            if not self._check_ffmpeg_availability():
                self._reset_button_state()
                return

        # Check Bright Data API key from settings
        self.append_log("🔐 Checking Bright Data API credentials...")
        bright_data_api_key = getattr(
            self.settings.api_keys, "bright_data_api_key", None
        )

        if not bright_data_api_key or len(str(bright_data_api_key).strip()) == 0:
            self.append_log("❌ Bright Data API key missing!")
            self._reset_button_state()
            self.show_error(
                "Bright Data API Key Required",
                "YouTube transcription requires a Bright Data API key to avoid anti-bot restrictions.\n\n"
                "Please:\n"
                "1. Go to the 'API Keys' tab\n"
                "2. Enter your Bright Data API key\n"
                "3. Click 'Save API Keys'\n"
                "4. Return here to start processing\n\n"
                "💡 Get your API key at: https://brightdata.com/\n\n"
                "Note: Without this key, YouTube processing will fail due to anti-bot protections.",
            )
            return

        # Validate API key format (basic check)
        api_key_str = str(bright_data_api_key).strip()
        if len(api_key_str) < 10:
            self.append_log("❌ Bright Data API key appears invalid!")
            self._reset_button_state()
            self.show_error(
                "Invalid Bright Data API Key",
                "The Bright Data API key appears to be invalid (too short).\n\n"
                "Please check your API key in the 'API Keys' tab and ensure it's entered correctly.\n\n"
                "💡 Get your API key at: https://brightdata.com/",
            )
            return

        self.append_log("✅ Bright Data API key configured")

        # Use async URL collection to prevent GUI blocking
        self.append_log("📋 Collecting URLs from input...")
        logger.info("Starting YouTube extraction process - collecting URLs...")

        # Collect URLs asynchronously
        from PyQt6.QtCore import QTimer

        QTimer.singleShot(0, self._async_collect_and_start)

    def _async_collect_and_start(self) -> None:
        """Asynchronously collect URLs and start processing to prevent GUI blocking."""
        try:
            urls = self._collect_urls()
            logger.info(f"Collected {len(urls)} URLs for processing")

            if not urls:
                self.append_log("❌ No URLs found in input!")
                logger.info("No URLs found - showing warning to user")
                self._reset_button_state()
                self.show_warning(
                    "No URLs",
                    "Please enter YouTube URLs or RSS feeds, or select a file containing URLs.",
                )
                return

            self.append_log(f"✅ Found {len(urls)} URLs to process")

            # Validate inputs
            self.append_log("🔍 Validating inputs...")
            if not self.validate_inputs():
                self.append_log("❌ Input validation failed!")
                logger.info("Input validation failed - aborting processing")
                self._reset_button_state()
                return
            self.append_log("✅ Input validation passed")

            # Continue with the rest of processing
            self._continue_processing_with_urls(urls)

        except Exception as e:
            logger.error(f"Error in async URL collection: {e}")
            self.append_log(f"❌ Error collecting URLs: {e}")
            self._reset_button_state()

    def _continue_processing_with_urls(self, urls: list[str]) -> None:
        """Continue processing after URLs have been collected."""
        # Schedule validation and setup asynchronously to prevent blocking
        from PyQt6.QtCore import QTimer

        QTimer.singleShot(0, lambda: self._async_validate_and_start(urls))

    def _async_validate_and_start(self, urls: list[str]) -> None:
        """Asynchronously validate inputs and start processing."""
        try:
            # Validate inputs asynchronously to prevent filesystem blocking
            self.append_log("🔍 Validating inputs...")
            from PyQt6.QtCore import QTimer

            QTimer.singleShot(0, lambda: self._async_validate_inputs_and_continue(urls))
        except Exception as e:
            logger.error(f"Error starting async validation: {e}")
            self.append_log(f"❌ Validation error: {e}")
            self._reset_button_state()

    def _async_validate_inputs_and_continue(self, urls: list[str]) -> None:
        """Perform validation checks and continue processing."""
        try:
            # Get output directory first (non-blocking)
            self.append_log("📁 Setting up output directory...")
            output_dir = self.output_dir_input.text().strip()
            if not output_dir:
                self.show_error("Invalid Output", "Output directory must be selected.")
                self._reset_button_state()
                return

            # Store URLs for later use
            self._pending_urls = urls
            self._pending_output_dir = output_dir

            # Use async directory validation to prevent filesystem blocking
            self.append_log("🔍 Validating output directory...")
            self.async_validate_directory(
                output_dir,
                self._handle_directory_validation_result,
                check_writable=True,  # Cloud Transcription tab needs writable directory
                check_parent=False,
            )

        except Exception as e:
            logger.error(f"Error in async validation: {e}")
            self.append_log(f"❌ Validation error: {e}")
            self._reset_button_state()

    def _handle_directory_validation_result(
        self, valid: bool, path: str, error_message: str
    ) -> None:
        """Handle the result of async directory validation."""
        try:
            if not valid:
                self.append_log(f"❌ Directory validation failed: {error_message}")
                self.show_error("Invalid Output Directory", error_message)
                self._reset_button_state()
                return

            self.append_log(f"✅ Output directory validated: {path}")

            # Continue with other validations (non-filesystem ones)
            if not self._validate_non_filesystem_inputs():
                return

            self.append_log("✅ All input validation passed")

            # Retrieve stored parameters
            urls = self._pending_urls
            output_dir = self._pending_output_dir

            # Clean up stored parameters
            del self._pending_urls
            del self._pending_output_dir

            logger.info(f"Starting extraction of {len(urls)} URLs to {output_dir}")

            # Schedule diarization check asynchronously if needed
            enable_diarization = self.diarization_checkbox.isChecked()
            if enable_diarization:
                self.append_log("🎙️ Diarization enabled - checking dependencies...")
                # Process UI events before running potentially slow diarization check
                from PyQt6.QtWidgets import QApplication

                QApplication.processEvents()

                # Check diarization dependencies asynchronously
                from PyQt6.QtCore import QTimer

                QTimer.singleShot(
                    0,
                    lambda: self._async_check_diarization_and_start(
                        urls, output_dir, enable_diarization
                    ),
                )
            else:
                # No diarization, proceed directly
                self._finalize_and_start_processing(
                    urls, output_dir, enable_diarization
                )

        except Exception as e:
            logger.error(f"Error handling directory validation: {e}")
            self.append_log(f"❌ Validation error: {e}")
            self._reset_button_state()

    def _validate_non_filesystem_inputs(self) -> bool:
        """Validate inputs that don't require filesystem access."""
        # Check Bright Data API key (required for YouTube processing)
        bright_data_api_key = getattr(
            self.settings.api_keys, "bright_data_api_key", None
        )

        if not bright_data_api_key:
            self.append_log("❌ Bright Data API key missing!")
            self.show_error(
                "Missing Bright Data API Key",
                "YouTube processing requires a Bright Data API key for reliable access.\n\n"
                "Please configure your Bright Data API Key in the Settings tab.\n\n"
                "Bright Data provides pay-per-request residential proxies for YouTube access.\n\n"
                "Sign up at: https://brightdata.com/",
            )
            self._reset_button_state()
            return False

        # Check speaker diarization requirements if enabled
        if self.diarization_checkbox.isChecked():
            hf_token = getattr(self.settings.api_keys, "huggingface_token", None)
            if not hf_token:
                self.append_log("⚠️ Warning: HuggingFace token missing for diarization")
                self.append_log(
                    "   Diarization will use default models (may be slower)"
                )

        return True

    def _async_check_diarization_and_start(
        self, urls: list[str], output_dir: str, enable_diarization: bool
    ) -> None:
        """Asynchronously check diarization dependencies and start processing."""
        try:
            # Store the parameters for later use
            self._pending_urls = urls
            self._pending_output_dir = output_dir
            self._pending_enable_diarization = enable_diarization

            # Start async diarization check - it will call _continue_after_diarization_check when done
            self._check_diarization_dependencies()

        except Exception as e:
            logger.error(f"Error in diarization check: {e}")
            self.append_log(f"❌ Diarization check error: {e}")
            self._reset_button_state()

    def _finalize_and_start_processing(
        self, urls: list[str], output_dir: str, enable_diarization: bool
    ) -> None:
        """Finalize configuration and start the processing worker."""
        self.append_log(f"🚀 Ready to process {len(urls)} URLs")
        self.append_log("-" * 50)

        # Configure extraction
        config = {
            "output_dir": output_dir,
            "format": self.format_combo.currentText(),
            "timestamps": False,  # Do not include timestamps for YouTube transcripts
            "overwrite": self.overwrite_checkbox.isChecked(),
            "enable_diarization": enable_diarization,
            "transcription_model": self.transcription_model_combo.currentText(),  # Pass selected model
            "download_all_mode": self.download_all_checkbox.isChecked(),
        }

        # Choose worker based on processing requirements
        use_batch_worker = (
            config["enable_diarization"]
            and len(urls) > 1  # Use batch worker for diarization with multiple URLs
        ) or len(
            urls
        ) > 10  # Or for large batches even without diarization

        if use_batch_worker:
            self.append_log(
                "📦 Using intelligent batch processing with resource management"
            )
            if config["download_all_mode"]:
                self.append_log(
                    "📥 Download-all mode: Will download all audio files first"
                )
            else:
                self.append_log("🔄 Conveyor belt mode: Processing in optimized batches")
            self.append_log("-" * 50)
            self._start_batch_processing(urls, config)
        else:
            self.append_log("🔄 Using sequential processing")
            self.append_log("-" * 50)
            self._start_sequential_processing(urls, config)

    def _reset_button_state(self) -> None:
        """Reset button to original state."""
        self.start_btn.setEnabled(True)
        self.start_btn.setText(self._get_start_button_text())

    def _start_batch_processing(self, urls: list[str], config: dict) -> None:
        """Start processing using the YouTubeBatchWorker."""
        # Disable start button
        self.start_btn.setEnabled(False)
        if config.get("download_all_mode", False):
            self.start_btn.setText("Processing (Download-All Mode)...")
        else:
            self.start_btn.setText("Processing (Batch Mode)...")
        self.stop_btn.setEnabled(True)

        # Create and configure batch worker
        self.extraction_worker = YouTubeBatchWorker(urls, config, self)

        # Connect batch worker signals
        self.extraction_worker.progress_updated.connect(
            self._update_extraction_progress
        )
        self.extraction_worker.url_completed.connect(self._url_extraction_completed)
        self.extraction_worker.batch_status.connect(self._handle_batch_status)
        self.extraction_worker.memory_pressure.connect(self._handle_memory_pressure)
        self.extraction_worker.resource_warning.connect(self._handle_resource_warning)
        self.extraction_worker.extraction_finished.connect(self._extraction_finished)
        self.extraction_worker.extraction_error.connect(self._extraction_error)

        # Add to active workers
        self.active_workers.append(self.extraction_worker)
        logger.info("Starting YouTube batch processing worker")
        self.extraction_worker.start()

        self.status_updated.emit("YouTube batch processing in progress...")

    def _start_sequential_processing(self, urls: list[str], config: dict) -> None:
        """Start processing using the original YouTubeExtractionWorker."""
        # Disable start button
        self.start_btn.setEnabled(False)
        self.start_btn.setText("Processing...")
        self.stop_btn.setEnabled(True)

        # Use original worker
        self.extraction_worker = YouTubeExtractionWorker(urls, config, self)

        # Connect original worker signals
        self.extraction_worker.progress_updated.connect(
            self._update_extraction_progress
        )
        self.extraction_worker.url_completed.connect(self._url_extraction_completed)
        self.extraction_worker.extraction_finished.connect(self._extraction_finished)
        self.extraction_worker.extraction_error.connect(self._extraction_error)
        self.extraction_worker.log_message.connect(self.append_log)
        self.extraction_worker.payment_required.connect(
            self._show_payment_required_dialog
        )
        self.extraction_worker.playlist_info_updated.connect(self._handle_playlist_info)
        # Ensure speaker assignment dialog is shown on the main thread
        self.extraction_worker.speaker_assignment_requested.connect(
            self._handle_speaker_assignment_request
        )

        # Add to active workers
        self.active_workers.append(self.extraction_worker)
        logger.info("Starting YouTube extraction worker thread")
        self.extraction_worker.start()

        self.status_updated.emit("YouTube extraction in progress...")

    def _handle_speaker_assignment_request(
        self, speaker_data_list, recording_path, metadata, result_callback
    ):
        """
        Handle speaker assignment request from worker thread.
        Ensures the dialog is shown on the main thread and returns assignments
        via the provided callback.
        """
        try:
            logger.info("Main thread handling speaker assignment request (YouTubeTab)")
            # Import dialog lazily to avoid circular deps
            from ..dialogs.speaker_assignment_dialog import (
                show_speaker_assignment_dialog,
            )

            # Show dialog (main thread guarded by show_speaker_assignment_dialog itself)
            assignments = show_speaker_assignment_dialog(
                speaker_data_list, recording_path, metadata, self
            )

            # Return assignments through callback to unblock worker
            if callable(result_callback):
                result_callback(assignments)
        except Exception as e:
            logger.error(f"Error in YouTube speaker assignment dialog: {e}")
            # Return None on error
            if callable(result_callback):
                result_callback(None)

    def _handle_batch_status(self, status: dict) -> None:
        """Handle batch status updates from YouTubeBatchWorker."""
        batch_number = status.get("batch_number", 0)
        batch_processed = status.get("batch_processed", 0)
        total_processed = status.get("total_processed", 0)
        total_successful = status.get("total_successful", 0)
        total_failed = status.get("total_failed", 0)
        memory_usage = status.get("memory_usage", 0)
        current_concurrency = status.get("current_concurrency", 0)
        initial_concurrency = status.get("initial_concurrency", 0)

        self.append_log(f"\n📦 Batch {batch_number} completed:")
        self.append_log(f"   • Processed: {batch_processed} videos")
        self.append_log(f"   • Total progress: {total_processed} videos")
        self.append_log(f"   • Success: {total_successful}, Failed: {total_failed}")
        self.append_log(f"   • Memory usage: {memory_usage:.1f}%")
        if current_concurrency != initial_concurrency:
            self.append_log(
                f"   • Concurrency adjusted: {current_concurrency} (from {initial_concurrency})"
            )

    def _handle_memory_pressure(self, level: int, message: str) -> None:
        """Handle memory pressure warnings from YouTubeBatchWorker."""
        if level >= 3:  # Emergency
            self.append_log(f"🚨 EMERGENCY: {message}")
        elif level >= 2:  # Critical
            self.append_log(f"🔥 CRITICAL: {message}")
        else:  # Warning
            self.append_log(f"⚠️ WARNING: {message}")

    def _handle_resource_warning(self, warning: str) -> None:
        """Handle resource warnings from YouTubeBatchWorker."""
        self.append_log(f"⚠️ Resource Warning: {warning}")

    def _stop_processing(self):
        """Stop the currently running extraction process."""
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
        """Collect URLs from input fields based on selected input method."""
        urls = []

        # BUGFIX: Only collect URLs from the selected source, not both
        if self.url_radio.isChecked():
            # Get URLs from text input ONLY
            logger.debug("Collecting URLs from text input (URL radio selected)")
            text_urls = self.url_input.toPlainText().strip()
            if text_urls:
                for line in text_urls.split("\n"):
                    line = line.strip()
                    if line and self._is_supported_url(line):
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
                            if self._is_supported_url(url):
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
                                        if url and self._is_supported_url(url):
                                            urls.append(url)
                                else:
                                    # Plain text format: one URL per line
                                    if self._is_supported_url(line):
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

    def _is_supported_url(self, url: str) -> bool:
        """Check if URL is supported by any registered processor."""
        try:
            from knowledge_system.processors.registry import get_processor_for_input

            return get_processor_for_input(url) is not None
        except Exception as e:
            logger.debug(f"Error checking URL support for {url}: {e}")
            # Fallback to YouTube check for backwards compatibility
            return "youtube.com" in url or "youtu.be" in url

    def _update_extraction_progress(self, current: int, total: int, status: str):
        """Update extraction progress with enhanced messaging."""
        # Prevent re-entrant recursion if progress signals arrive during GUI repaint
        if not hasattr(self, "_progress_update_inflight"):
            self._progress_update_inflight = False
        if self._progress_update_inflight:
            return

        self._progress_update_inflight = True
        try:
            # Update enhanced cloud status display
            if total > 0:
                # Determine operation type from status
                if "downloading" in status.lower() or "download" in status.lower():
                    operation = f"📥 Downloading audio from URL {current + 1}"
                elif "processing" in status.lower() or "diarization" in status.lower():
                    operation = f"🎙️ Processing audio for URL {current + 1}"
                elif "transcript" in status.lower():
                    operation = f"📝 Extracting transcript from URL {current + 1}"
                elif current >= total:
                    operation = "✅ Cloud transcription completed"
                else:
                    operation = f"🔄 Processing URL {current + 1}"

                self.cloud_status_display.update_cloud_status(
                    current_url=current + 1,
                    total_urls=total,
                    current_operation=operation,
                    api_status="Active",
                )
            else:
                # Indeterminate progress
                self.cloud_status_display.update_cloud_status(
                    current_url=0,
                    total_urls=0,
                    current_operation=status,
                    api_status="Initializing",
                )

            # For download progress and similar repetitive updates, update the same line
            # For other status messages, append normally
            if any(
                indicator in status
                for indicator in ["📥", "Downloading:", "%", "MB/s", "🔄", "Processing:"]
            ):
                self.update_last_log_line(status)
            else:
                self.append_log(status)

            if total > 0:
                percent = (current / total) * 100

                # Enhanced progress label with more detail
                # Legacy progress updates removed - enhanced display handles all progress updates
                # (progress_label and progress_bar updates moved to enhanced display)
                pass
            else:
                # Indeterminate progress handled by enhanced display
                pass
        finally:
            self._progress_update_inflight = False

    def _url_extraction_completed(self, url: str, success: bool, message: str):
        """Handle completion of single URL extraction."""
        # Handle both completion and progress messages
        if success is None:
            # This is a progress update, not a completion
            self.append_log(f"  → {message}")
        else:
            # This is an actual completion
            status_icon = "✅" if success else "❌"
            self.append_log(f"  {status_icon} {message}")

    def _extraction_finished(self, results: dict[str, Any]):
        """Handle completion of all extractions."""
        # Update cloud status display with completion
        success_count = results.get("successful", 0)
        failed_count = results.get("failed", 0)
        self.cloud_status_display.complete(success_count, failed_count)
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

        # Show processing mode
        processing_mode = results.get("processing_mode", "unknown")
        if processing_mode in ["download-all", "conveyor-belt"]:
            self.append_log(f"🔧 Processing mode: {processing_mode}")

        # Calculate files that were extracted but not saved (partial failures)
        results["successful"] + results["failed"] + skipped_count

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
                    "   💡 Tip: You can load the CSV file directly to retry failed extractions"
                )
            else:
                self.append_log(
                    "\n⚠️ Warning: Could not write failure logs (check logs directory permissions)"
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
            self.append_log("\n📊 Summary: No files were saved. Check the issues above.")

        # Reset UI
        self.start_btn.setEnabled(True)
        self.start_btn.setText(self._get_start_button_text())
        self.stop_btn.setEnabled(False)  # Disable stop button
        # Legacy progress bar updates removed - enhanced display handles completion

        # Enhanced completion message with playlist context
        total_processed = results["successful"] + skipped_count
        playlist_count = len(results.get("playlist_info", []))

        # Completion message now handled by enhanced cloud display
        success_count = results["successful"]
        failure_count = total_processed - success_count
        self.cloud_status_display.complete(success_count, failure_count)

        self.status_updated.emit("YouTube extraction completed")
        self.processing_finished.emit()

        # Generate session report for View Last Report functionality
        self._generate_session_report(results)

        # Show cloud completion summary
        if results["successful"] > 0 or results["failed"] > 0:
            self._show_cloud_summary(results)

    def _extraction_error(self, error_msg: str):
        """Handle extraction error."""
        # CRITICAL: Thread safety check - ensure we're on the main thread
        from PyQt6.QtCore import QThread
        from PyQt6.QtWidgets import QApplication

        if QThread.currentThread() != QApplication.instance().thread():
            logger.error(
                "🚨 CRITICAL: _extraction_error called from background thread - BLOCKED!"
            )
            logger.error(f"Current thread: {QThread.currentThread()}")
            logger.error(f"Main thread: {QApplication.instance().thread()}")
            # Still update status display and log on any thread
            self.cloud_status_display.set_error(error_msg)
            self.append_log(f"❌ Error: {error_msg}")
            return

        # Update cloud status display with error
        self.cloud_status_display.set_error(error_msg)

        self.append_log(f"❌ Error: {error_msg}")
        show_enhanced_error(
            self,
            "Cloud Transcription Error",
            error_msg,
            context="YouTube cloud transcription via SkipThePodcast API",
        )

        # Reset UI
        self.start_btn.setEnabled(True)
        self.start_btn.setText(self._get_start_button_text())
        self.stop_btn.setEnabled(False)  # Disable stop button
        # Error handled by enhanced cloud display
        self.cloud_status_display.set_error(error_msg)

        self.status_updated.emit("Ready")

    def _show_cloud_summary(self, results: dict):
        """Show cloud transcription completion summary."""
        # CRITICAL: Thread safety check - ensure we're on the main thread
        from PyQt6.QtCore import QThread
        from PyQt6.QtWidgets import QApplication

        if QThread.currentThread() != QApplication.instance().thread():
            logger.error(
                "🚨 CRITICAL: _show_cloud_summary called from background thread - BLOCKED!"
            )
            logger.error(f"Current thread: {QThread.currentThread()}")
            logger.error(f"Main thread: {QApplication.instance().thread()}")
            return

        summary = CloudTranscriptionSummary(self)

        # Calculate processing time (mock - would be tracked in real implementation)
        processing_time = 120.0  # Mock 2 minutes

        summary.show_cloud_summary(
            successful_urls=results["successful"],
            failed_urls=results["failed"],
            total_processing_time=processing_time,
            service_status="Active",
        )

    def _show_payment_required_dialog(self):
        """Show popup dialog for 402 Payment Required error."""

        from ..assets.icons import get_app_icon

        payment_dialog = QMessageBox(self)
        payment_dialog.setIcon(QMessageBox.Icon.Warning)
        payment_dialog.setWindowTitle("Bright Data Payment Required")
        payment_dialog.setText("💰 Bright Data Payment/Quota Required")
        payment_dialog.setInformativeText(
            "Your Bright Data account may be out of quota or requires payment to continue.\n\n"
            "Please visit https://brightdata.com/ to check your account and add funds if needed.\n\n"
            "This is not a bug in our application - it's a billing issue with your proxy service."
        )
        payment_dialog.setStandardButtons(QMessageBox.StandardButton.Ok)

        # Set custom window icon
        custom_icon = get_app_icon()
        if custom_icon:
            payment_dialog.setWindowIcon(custom_icon)

        payment_dialog.exec()

    def _handle_playlist_info(self, playlist_data: dict):
        """Handle enhanced playlist and video information from worker."""
        playlists = playlist_data.get("playlists", [])
        total_playlists = playlist_data.get("total_playlists", 0)
        total_videos = playlist_data.get("total_videos", 0)
        playlist_data.get("playlist_videos", 0)
        playlist_data.get("individual_videos", 0)
        summary = playlist_data.get("summary", "")

        # Show comprehensive content summary
        self.append_log("\n📊 Summarization:")
        if summary:
            self.append_log(f"   • {summary}")
            self.append_log(f"   • Grand Total: {total_videos} videos to process")
        else:
            self.append_log(f"   • Total: {total_videos} videos to process")

        # Show detailed playlist breakdown
        if total_playlists > 0:
            self.append_log("\n📋 Playlist Details:")
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
        """Load saved settings from session."""
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

            # Timestamps are always enabled for YouTube (no longer configurable)
            self.overwrite_checkbox.setChecked(
                self.gui_settings.get_checkbox_state(
                    self.tab_name, "overwrite_existing", False
                )
            )
            self.diarization_checkbox.setChecked(
                self.gui_settings.get_checkbox_state(
                    self.tab_name, "enable_diarization", True
                )
            )
            self.download_all_checkbox.setChecked(
                self.gui_settings.get_checkbox_state(
                    self.tab_name, "download_all_mode", False
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
        """Save current settings to session."""
        try:
            # Save output directory
            self.gui_settings.set_output_directory(
                self.tab_name, self.output_dir_input.text()
            )

            # Save combo selections
            self.gui_settings.set_combo_selection(
                self.tab_name, "format", self.format_combo.currentText()
            )

            # Timestamps are always enabled for YouTube (no longer configurable)
            self.gui_settings.set_checkbox_state(
                self.tab_name, "overwrite_existing", self.overwrite_checkbox.isChecked()
            )
            self.gui_settings.set_checkbox_state(
                self.tab_name,
                "enable_diarization",
                self.diarization_checkbox.isChecked(),
            )
            self.gui_settings.set_checkbox_state(
                self.tab_name,
                "download_all_mode",
                self.download_all_checkbox.isChecked(),
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
        """Called when any setting changes to automatically save."""
        self._save_settings()

    def validate_inputs(self) -> bool:
        """Validate inputs before processing."""
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

        # Check Bright Data API key (required for YouTube processing)
        bright_data_api_key = getattr(
            self.settings.api_keys, "bright_data_api_key", None
        )

        if not bright_data_api_key:
            self.show_error(
                "Missing Bright Data API Key",
                "YouTube processing requires a Bright Data API key for reliable access.\n\n"
                "Please configure your Bright Data API Key in the Settings tab.\n\n"
                "Bright Data provides pay-per-request residential proxies for YouTube access.\n\n"
                "Sign up at: https://brightdata.com/",
            )
            return False

        # Check speaker diarization requirements if enabled
        if self.diarization_checkbox.isChecked():
            # Check if diarization is available
            try:
                from knowledge_system.processors.diarization import (
                    get_diarization_installation_instructions,
                    is_diarization_available,
                )

                if not is_diarization_available():
                    # Offer guided installation dialog, then re-check
                    try:
                        from ..dialogs.diarization_setup_dialog import (
                            DiarizationSetupDialog,
                        )

                        install_dialog = DiarizationSetupDialog(self)
                        # Block until finished so we can re-check immediately
                        install_dialog.exec()

                        # Re-check availability after installer closes
                        if not is_diarization_available():
                            self.show_error(
                                "Missing Diarization Dependencies",
                                "Speaker diarization requires additional dependencies.\n\n"
                                + get_diarization_installation_instructions(),
                            )
                            return False
                    except Exception:
                        # If dialog cannot be shown, display instructions directly
                        self.show_error(
                            "Missing Diarization Dependencies",
                            "Speaker diarization requires additional dependencies.\n\n"
                            + get_diarization_installation_instructions(),
                        )
                        return False
            except ImportError:
                self.show_error(
                    "Missing Dependency",
                    "Speaker diarization requires 'pyannote.audio' to be installed.\n\n"
                    "Install it with: pip install -e '.[diarization]'\n\n"
                    "Please install this dependency or disable speaker diarization.",
                )
                return False

            # Check if HuggingFace token is configured
            hf_token = getattr(self.settings.api_keys, "huggingface_token", None)
            if not hf_token:
                self.show_warning(
                    "Missing HuggingFace Token",
                    "Speaker diarization requires a HuggingFace token to access the pyannote models.\n\n"
                    "Please configure your HuggingFace token in the Settings tab or disable speaker diarization.\n\n"
                    "You can get a free token at: https://huggingface.co/settings/tokens",
                )
                # Don't return False here, just warn - let the user proceed if they want

        return True

    def _check_ffmpeg_availability(self) -> bool:
        """Check if FFmpeg is available and prompt for installation if needed."""
        import os
        import shutil
        from pathlib import Path

        # Try multiple resolution strategies consistent with Settings page
        candidates: list[str] = []

        # 1) Environment override set by Settings/installer
        env_ffmpeg = os.environ.get("FFMPEG_PATH")
        if env_ffmpeg:
            candidates.append(env_ffmpeg)

        # 2) PATH lookup
        which_ffmpeg = shutil.which("ffmpeg")
        if which_ffmpeg:
            candidates.append(which_ffmpeg)

        # 3) App-managed bin dir (where our installer drops binaries)
        app_bin = (
            Path.home()
            / "Library"
            / "Application Support"
            / "Knowledge_Chipper"
            / "bin"
            / "ffmpeg"
        )
        candidates.append(str(app_bin))

        # 4) Common Homebrew locations
        candidates.extend(["/opt/homebrew/bin/ffmpeg", "/usr/local/bin/ffmpeg"])

        # Return true on first runnable candidate
        for candidate in candidates:
            try:
                if not candidate:
                    continue
                p = Path(candidate)
                if p.exists() and os.access(p, os.X_OK):
                    # Verify it's runnable
                    import subprocess

                    result = subprocess.run(
                        [str(p), "-version"], capture_output=True, text=True
                    )
                    if result.returncode == 0:
                        # Best-effort: expose to environment for downstream tools
                        os.environ.setdefault("FFMPEG_PATH", str(p))
                        probe_guess = str(p).replace("ffmpeg", "ffprobe")
                        if Path(probe_guess).exists():
                            os.environ.setdefault("FFPROBE_PATH", probe_guess)
                        self.append_log("✅ FFmpeg found - YouTube processing ready")
                        return True
            except Exception:
                continue

        # FFmpeg not found - show prompt
        self.append_log("⚠️ FFmpeg not found - required for YouTube transcription")

        prompt_dialog = FFmpegPromptDialog("YouTube transcription", self)
        result = prompt_dialog.exec()

        if result == QDialog.DialogCode.Accepted:
            # User chose to install - check again after installation dialog closes
            if shutil.which("ffmpeg"):
                self.append_log("✅ FFmpeg installed successfully!")
                return True
            else:
                self.append_log("❌ FFmpeg installation was not completed")
                return False
        else:
            # User chose not to install
            self.append_log("❌ YouTube processing cancelled - FFmpeg required")
            return False

    def _check_ffmpeg_for_diarization(self) -> bool:
        """Check if FFmpeg is available for diarization, with installation dialog if needed."""
        import os
        import shutil
        from pathlib import Path

        # Try multiple resolution strategies consistent with Settings page
        candidates: list[str] = []

        # 1) Environment override set by Settings/installer
        env_ffmpeg = os.environ.get("FFMPEG_PATH")
        if env_ffmpeg:
            candidates.append(env_ffmpeg)

        # 2) PATH lookup
        which_ffmpeg = shutil.which("ffmpeg")
        if which_ffmpeg:
            candidates.append(which_ffmpeg)

        # 3) App-managed bin dir (where our installer drops binaries)
        app_bin = (
            Path.home()
            / "Library"
            / "Application Support"
            / "Knowledge_Chipper"
            / "bin"
            / "ffmpeg"
        )
        candidates.append(str(app_bin))

        # 4) Common Homebrew locations
        candidates.extend(["/opt/homebrew/bin/ffmpeg", "/usr/local/bin/ffmpeg"])

        # Return true on first runnable candidate
        for candidate in candidates:
            try:
                if not candidate:
                    continue
                p = Path(candidate)
                if p.exists() and os.access(p, os.X_OK):
                    # Verify it's runnable
                    import subprocess

                    result = subprocess.run(
                        [str(p), "-version"], capture_output=True, text=True
                    )
                    if result.returncode == 0:
                        # Best-effort: expose to environment for downstream tools
                        os.environ.setdefault("FFMPEG_PATH", str(p))
                        probe_guess = str(p).replace("ffmpeg", "ffprobe")
                        if Path(probe_guess).exists():
                            os.environ.setdefault("FFPROBE_PATH", probe_guess)
                        self.append_log("✅ FFmpeg found - diarization ready")
                        return True
            except Exception:
                continue

        # FFmpeg not found - show diarization-specific dialog
        self.append_log("⚠️ FFmpeg required for cloud transcription with diarization")

        try:
            # Import here to avoid circular imports
            from PyQt6.QtWidgets import QDialog

            dialog = DiarizationFFmpegDialog(self)
            result = dialog.exec()

            if result == QDialog.DialogCode.Accepted:
                # User chose to install - check again after installation
                # First, check if environment was updated by the installer
                if os.environ.get("FFMPEG_PATH"):
                    self.append_log("✅ FFmpeg installed and configured!")
                    return True
                elif shutil.which("ffmpeg"):
                    self.append_log("✅ FFmpeg installation completed!")
                    return True
                else:
                    self.append_log("❌ FFmpeg installation was not completed")
                    return False
            else:
                # User chose to cancel
                self.append_log(
                    "❌ Cloud transcription cancelled - FFmpeg required for diarization"
                )
                return False

        except Exception as e:
            logger.error(f"Error showing diarization FFmpeg dialog: {e}")
            self.append_log(f"❌ Error showing installation dialog: {e}")
            return False

    def _generate_session_report(self, results: dict[str, Any]) -> None:
        """Generate comprehensive session report for cloud transcription."""
        try:
            import json
            from datetime import datetime
            from pathlib import Path

            # Create report data
            report_data = {
                "session_info": {
                    "timestamp": datetime.now().isoformat(),
                    "operation_type": "Cloud Transcription",
                    "total_urls": results.get("successful", 0)
                    + results.get("failed", 0)
                    + results.get("skipped", 0),
                    "successful": results.get("successful", 0),
                    "failed": results.get("failed", 0),
                    "skipped": results.get("skipped", 0),
                    "processing_mode": results.get("processing_mode", "unknown"),
                },
                "configuration": {
                    "output_directory": self.output_dir_input.text().strip()
                    or str(Path.cwd()),
                    "output_format": self.format_combo.currentText(),
                    "transcription_model": self.transcription_model_combo.currentText(),
                    "include_timestamps": True,  # Always enabled for YouTube transcripts
                    "overwrite_existing": self.overwrite_checkbox.isChecked(),
                    "enable_speaker_diarization": self.diarization_checkbox.isChecked(),
                    "download_all_audio": self.download_all_checkbox.isChecked(),
                },
                "results": {
                    "successful_urls": results.get("urls_processed", []),
                    "failed_urls": results.get("failed_urls", []),
                    "skipped_urls": results.get("skipped_urls", []),
                    "playlist_info": results.get("playlist_info", []),
                },
            }

            # Save report to logs directory
            logs_dir = Path("logs")
            logs_dir.mkdir(parents=True, exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            report_path = logs_dir / f"cloud_transcription_report_{timestamp}.json"

            with open(report_path, "w", encoding="utf-8") as f:
                json.dump(report_data, f, indent=2, ensure_ascii=False)

            # Store report path for viewing
            self.current_report = str(report_path)

            # Also generate a human-readable markdown report
            md_report_path = logs_dir / f"cloud_transcription_report_{timestamp}.md"
            with open(md_report_path, "w", encoding="utf-8") as f:
                f.write(f"# Cloud Transcription Session Report\n\n")
                f.write(
                    f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                )

                f.write("## Summary\n\n")
                f.write(
                    f"- **Total URLs processed:** {report_data['session_info']['total_urls']}\n"
                )
                f.write(
                    f"- **Successful:** {report_data['session_info']['successful']}\n"
                )
                f.write(f"- **Failed:** {report_data['session_info']['failed']}\n")
                f.write(f"- **Skipped:** {report_data['session_info']['skipped']}\n")
                f.write(
                    f"- **Processing Mode:** {report_data['session_info']['processing_mode']}\n\n"
                )

                f.write("## Configuration\n\n")
                f.write(
                    f"- **Output Directory:** {report_data['configuration']['output_directory']}\n"
                )
                f.write(
                    f"- **Output Format:** {report_data['configuration']['output_format']}\n"
                )
                f.write(
                    f"- **Include Timestamps:** {report_data['configuration']['include_timestamps']}\n"
                )
                f.write(
                    f"- **Overwrite Existing:** {report_data['configuration']['overwrite_existing']}\n"
                )
                f.write(
                    f"- **Speaker Diarization:** {report_data['configuration']['enable_speaker_diarization']}\n"
                )
                f.write(
                    f"- **Download All Audio:** {report_data['configuration']['download_all_audio']}\n\n"
                )

                if report_data["results"]["successful_urls"]:
                    f.write("## Successfully Processed URLs\n\n")
                    for url in report_data["results"]["successful_urls"]:
                        f.write(f"- {url}\n")
                    f.write("\n")

                if report_data["results"]["failed_urls"]:
                    f.write("## Failed URLs\n\n")
                    for item in report_data["results"]["failed_urls"]:
                        if isinstance(item, dict):
                            title = item.get("title", "Unknown Title")
                            error = item.get("error", "Unknown error")
                            url = item.get("url", "Unknown URL")
                            f.write(f"- **{title}** ({url}): {error}\n")
                        else:
                            f.write(f"- {item}\n")
                    f.write("\n")

                if report_data["results"]["skipped_urls"]:
                    f.write("## Skipped URLs\n\n")
                    for item in report_data["results"]["skipped_urls"]:
                        if isinstance(item, dict):
                            title = item.get("title", "Unknown Title")
                            reason = item.get("reason", "Already exists")
                            f.write(f"- **{title}**: {reason}\n")
                        else:
                            f.write(f"- {item}\n")
                    f.write("\n")

            # Store markdown report path as well for easy viewing
            self.current_report = str(md_report_path)

            self.append_log(f"📋 Session report saved to: {md_report_path.name}")

        except Exception as e:
            from ...logger import get_logger

            logger = get_logger(__name__)
            logger.error(f"Failed to generate session report: {e}")
            self.append_log(f"⚠️ Warning: Could not generate session report: {e}")

    def cleanup_workers(self):
        """Clean up any active workers."""
        if self.extraction_worker and self.extraction_worker.isRunning():
            self.extraction_worker.stop()
            self.extraction_worker.wait(3000)
        super().cleanup_workers()

    def _reset_ui_state(self):
        """Reset UI to initial state."""
        self.start_btn.setEnabled(True)
        self.start_btn.setText(self._get_start_button_text())
        self.stop_btn.setEnabled(False)
        # Reset handled by enhanced cloud display
        self.cloud_status_display.reset()
