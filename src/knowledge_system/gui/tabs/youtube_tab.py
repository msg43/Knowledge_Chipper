"""YouTube extraction tab for downloading and processing YouTube transcripts."""

import json
import re
import random
import time
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime

from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QGroupBox, QGridLayout,
    QLabel, QPushButton, QLineEdit, QComboBox,
    QCheckBox, QTextEdit, QFileDialog, QMessageBox, QRadioButton, QProgressBar
)
from PyQt6.QtCore import QTimer, pyqtSignal, QThread
from PyQt6.QtGui import QFont

from ..components.base_tab import BaseTab
from ..core.settings_manager import get_gui_settings_manager
from ...logger import get_logger
from ...utils.cancellation import CancellationToken

logger = get_logger(__name__)


class YouTubeExtractionWorker(QThread):
    """Worker thread for YouTube transcript extraction."""
    
    progress_updated = pyqtSignal(int, int, str)  # current, total, status
    url_completed = pyqtSignal(str, bool, str)  # url, success, message
    extraction_finished = pyqtSignal(dict)  # final results
    extraction_error = pyqtSignal(str)
    payment_required = pyqtSignal()  # 402 Payment Required error
    
    def __init__(self, urls, config, parent=None):
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
        
    def run(self):
        """Run the YouTube extraction process."""
        logger.info(f"YouTubeExtractionWorker.run() started with {len(self.urls)} URLs")
        
        # Early check for empty URL list
        if not self.urls or len(self.urls) == 0:
            logger.warning("Worker started with empty URL list - exiting immediately")
            self.extraction_finished.emit({
                'successful': 0,
                'failed': 0,
                'urls_processed': [],
                'failed_urls': []
            })
            return
            
        try:
            from ...processors.youtube_transcript import YouTubeTranscriptProcessor
            import json
            from pathlib import Path
            from datetime import datetime
            
            # Log cancellation token state before starting
            logger.info(f"Cancellation token state at start - cancelled: {self.cancellation_token.is_cancelled}, paused: {self.cancellation_token.is_paused()}")
            logger.info(f"should_stop flag: {self.should_stop}")
            
            processor = YouTubeTranscriptProcessor()
            results = {
                'successful': 0,
                'failed': 0,
                'urls_processed': [],
                'failed_urls': []
            }
            
            total_urls = len(self.urls)
            logger.info(f"Processing {total_urls} URLs")
            
            # Initial progress update
            self.progress_updated.emit(0, total_urls, f"🚀 Starting extraction of {total_urls} YouTube URLs...")
            
            for i, url in enumerate(self.urls):
                # Detailed logging of cancellation check
                is_should_stop = self.should_stop
                is_token_cancelled = self.cancellation_token.is_cancelled()
                logger.info(f"URL {i+1}/{total_urls}: should_stop={is_should_stop}, token_cancelled={is_token_cancelled}")
                
                # Check cancellation before processing each URL
                if is_should_stop or is_token_cancelled:
                    logger.warning(f"Cancellation detected: should_stop={is_should_stop}, token_cancelled={is_token_cancelled}")
                    logger.info(f"YouTube extraction stopped by user after {i} URLs")
                    self.progress_updated.emit(i, total_urls, f"❌ Extraction cancelled after {i} URLs")
                    break
                
                # Extract video ID for title lookup
                video_id = None
                if 'youtu.be/' in url:
                    video_id = url.split('youtu.be/')[1].split('?')[0]
                elif 'watch?v=' in url:
                    video_id = url.split('watch?v=')[1].split('&')[0]
                elif 'playlist?list=' in url:
                    video_id = f"Playlist-{url.split('list=')[1][:11]}"
                
                # Calculate percentage
                percent = int((i / total_urls) * 100)
                
                # Try to get a meaningful title for progress display
                display_title = f"Video {video_id}" if video_id else url[-50:]  # Show last 50 chars of URL as fallback
                self.progress_updated.emit(i, total_urls, f"📹 [{i+1}/{total_urls}] ({percent}%) Processing: {display_title}")
                
                try:
                    # Sub-step progress: Starting processing
                    self.progress_updated.emit(i, total_urls, f"🔄 [{i+1}/{total_urls}] ({percent}%) Fetching metadata for: {display_title}")
                    
                    # Pass cancellation token to processor
                    result = processor.process(
                        url,
                        output_dir=self.config.get('output_dir'),
                        output_format=self.config.get('format', 'md'),
                        include_timestamps=self.config.get('timestamps', True),
                        cancellation_token=self.cancellation_token
                    )
                    
                    if result.success:
                        # Get actual title from successful result
                        actual_title = "Unknown Title"
                        if result.data and result.data.get('transcripts'):
                            transcripts = result.data['transcripts']
                            if transcripts and len(transcripts) > 0:
                                actual_title = transcripts[0].get('title', 'Unknown Title')
                        
                        # Truncate long titles for display
                        if len(actual_title) > 60:
                            display_actual_title = actual_title[:57] + "..."
                        else:
                            display_actual_title = actual_title
                        
                        # Sub-step progress: Transcript extraction complete
                        self.progress_updated.emit(i, total_urls, f"📝 [{i+1}/{total_urls}] ({percent}%) Transcript extracted: {display_actual_title}")
                        
                        # Sub-step progress: Saving files
                        saved_files = result.data.get('saved_files', [])
                        file_count = len(saved_files)
                        self.progress_updated.emit(i, total_urls, f"💾 [{i+1}/{total_urls}] ({percent}%) Saved {file_count} file(s): {display_actual_title}")
                        
                        results['successful'] += 1
                        results['urls_processed'].append(url)
                        
                        # Success message for this URL
                        success_msg = f"✅ Successfully extracted: {display_actual_title}"
                        if file_count > 0:
                            success_msg += f" ({file_count} file(s) saved)"
                        self.url_completed.emit(url, True, success_msg)
                        
                    else:
                        # Handle failure
                        error_msg = '; '.join(result.errors) if result.errors else 'Unknown error'
                        results['failed'] += 1
                        results['failed_urls'].append(url)
                        
                        # Check for 402 Payment Required error and emit special signal
                        if "402 Payment Required" in error_msg:
                            self.payment_required.emit()
                        
                        # Sub-step progress: Failed
                        self.progress_updated.emit(i, total_urls, f"❌ [{i+1}/{total_urls}] ({percent}%) Failed: {display_title}")
                        
                        # Failure message for this URL
                        failure_msg = f"❌ Failed to extract: {display_title} - {error_msg}"
                        self.url_completed.emit(url, False, failure_msg)
                
                except Exception as e:
                    error_msg = str(e)
                    logger.error(f"Error processing {url}: {error_msg}")
                    results['failed'] += 1
                    results['failed_urls'].append(url)
                    
                    # Check for 402 Payment Required error and emit special signal
                    if "402 Payment Required" in error_msg:
                        self.payment_required.emit()
                    
                    # Sub-step progress: Exception
                    self.progress_updated.emit(i, total_urls, f"💥 [{i+1}/{total_urls}] ({percent}%) Exception: {display_title}")
                    
                    # Exception message for this URL
                    exception_msg = f"💥 Exception processing: {display_title} - {error_msg}"
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
    
    def stop(self):
        """Stop the extraction process."""
        logger.info("YouTubeExtractionWorker.stop() called")
        self.should_stop = True
        if self.cancellation_token:
            self.cancellation_token.cancel("User requested cancellation")

    def _write_failure_log(self, failed_urls):
        """Write failed URL extractions to a consolidated log file."""
        try:
            from datetime import datetime
            from pathlib import Path
            import json
            
            # Get the logs directory from settings
            from ...config import get_settings
            settings = get_settings()
            logs_dir = Path(settings.paths.logs).expanduser()
            logs_dir.mkdir(parents=True, exist_ok=True)
            
            # Use a single consolidated log file that appends entries
            log_file = logs_dir / "youtube_extraction_failures.log"
            
            # Prepare log data
            log_entry = {
                'timestamp': datetime.now().isoformat(),
                'total_failed': len(failed_urls),
                'extraction_type': 'youtube_transcripts',
                'failed_urls': failed_urls
            }
            
            # Append to existing log file
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write(f"\n{'='*70}\n")
                f.write(f"YouTube Extraction Failures - {datetime.now().isoformat()}\n")
                f.write(f"Total failed: {len(failed_urls)}\n")
                f.write(f"{'='*70}\n")
                json.dump(log_entry, f, indent=2, ensure_ascii=False)
                f.write(f"\n{'='*70}\n")
                
            logger.info(f"Failed extractions logged to: {log_file}")
            
        except Exception as e:
            logger.error(f"Failed to write failure log: {e}")


class YouTubeTab(BaseTab):
    """Tab for YouTube transcript extraction and processing."""
    
    def __init__(self, parent=None):
        self.extraction_worker = None
        self.gui_settings = get_gui_settings_manager()
        self.tab_name = "YouTube"
        super().__init__(parent)
        
    def _setup_ui(self):
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
        layout.addLayout(output_layout)
        
        layout.addStretch()
        
        # Load saved settings after UI is set up
        self._load_settings()
        
    def _create_input_section(self) -> QGroupBox:
        """Create the URL input section."""
        group = QGroupBox("YouTube URLs")
        layout = QVBoxLayout()
        
        # Radio button for URL input
        self.url_radio = QRadioButton("YouTube URLs")
        self.url_radio.setChecked(True)  # Default selection
        self.url_radio.toggled.connect(self._on_input_method_changed)
        layout.addWidget(self.url_radio)
        
        # URL input
        self.url_input = QTextEdit()
        self.url_input.setPlaceholderText(
            "Enter YouTube URLs or Playlist URLs (one per line):\n"
            "https://www.youtube.com/watch?v=...\n"
            "https://youtu.be/...\n"
            "https://www.youtube.com/playlist?list=..."
        )
        self.url_input.setMinimumHeight(150)
        self.url_input.setMaximumHeight(200)  # Prevent it from growing too large
        from PyQt6.QtWidgets import QSizePolicy
        self.url_input.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout.addWidget(self.url_input)
        
        # Radio button for file input
        self.file_radio = QRadioButton("Or Select File")
        self.file_radio.toggled.connect(self._on_input_method_changed)
        layout.addWidget(self.file_radio)
        
        # File input
        file_layout = QHBoxLayout()
        file_layout.addWidget(QLabel("Select a .TXT, .RTF, or .CSV file with Youtube URLs or Playlist URLs:"))
        
        self.file_input = QLineEdit()
        self.file_input.setPlaceholderText("Select a file containing URLs...")
        self.file_input.setEnabled(False)  # Start disabled
        file_layout.addWidget(self.file_input)
        
        self.browse_btn = QPushButton("Browse")
        self.browse_btn.clicked.connect(self._select_url_file)
        self.browse_btn.setEnabled(False)  # Start disabled
        file_layout.addWidget(self.browse_btn)
        
        layout.addLayout(file_layout)
        group.setLayout(layout)
        return group
        
    def _on_input_method_changed(self):
        """Handle radio button changes to enable/disable input sections."""
        if self.url_radio.isChecked():
            # Enable URL input, disable file input
            self.url_input.setEnabled(True)
            self.file_input.setEnabled(False)
            self.browse_btn.setEnabled(False)
            
            # Visual styling for disabled state
            self.file_input.setStyleSheet("color: gray;")
        else:
            # Enable file input, disable URL input
            self.url_input.setEnabled(False)
            self.file_input.setEnabled(True)
            self.browse_btn.setEnabled(True)
            
            # Visual styling for disabled state
            self.url_input.setStyleSheet("color: gray;")
            self.file_input.setStyleSheet("")  # Reset to default
        
    def _create_settings_section(self) -> QGroupBox:
        """Create the extraction settings section."""
        group = QGroupBox("Extraction Settings")
        layout = QGridLayout()
        
        # Output directory
        layout.addWidget(QLabel("Output Directory:"), 0, 0)
        self.output_dir_input = QLineEdit()
        self.output_dir_input.setPlaceholderText("Choose output directory...")
        # Set default to transcripts directory
        default_output = self.get_output_directory(str(self.settings.paths.transcripts))
        self.output_dir_input.setText(str(default_output))
        self.output_dir_input.textChanged.connect(self._on_setting_changed)
        layout.addWidget(self.output_dir_input, 0, 1)
        
        browse_output_btn = QPushButton("Browse")
        browse_output_btn.clicked.connect(self._select_output_directory)
        layout.addWidget(browse_output_btn, 0, 2)
        
        # Format selection
        layout.addWidget(QLabel("Output Format:"), 1, 0)
        self.format_combo = QComboBox()
        self.format_combo.addItems(["md", "txt", "json"])
        self.format_combo.setCurrentText("md")
        self.format_combo.currentTextChanged.connect(self._on_setting_changed)
        layout.addWidget(self.format_combo, 1, 1)
        
        # Options
        self.timestamps_checkbox = QCheckBox("Include timestamps")
        self.timestamps_checkbox.setChecked(True)
        self.timestamps_checkbox.toggled.connect(self._on_setting_changed)
        layout.addWidget(self.timestamps_checkbox, 2, 0, 1, 2)
        
        self.overwrite_checkbox = QCheckBox("Overwrite existing transcripts")
        self.overwrite_checkbox.setChecked(False)
        self.overwrite_checkbox.toggled.connect(self._on_setting_changed)
        layout.addWidget(self.overwrite_checkbox, 2, 2)
        
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
        self.start_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        # Make green and take 3/4 of the width
        self.start_btn.setStyleSheet("""
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
        """)
        layout.addWidget(self.start_btn, 3)  # 3/4 stretch factor
        
        self.stop_btn = QPushButton("Stop Extraction")
        self.stop_btn.clicked.connect(self._stop_processing)
        self.stop_btn.setEnabled(False) # Initially disabled
        # Set fixed height for consistent sizing
        self.stop_btn.setFixedHeight(50)
        self.stop_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        # Make red and take 1/4 of the width
        self.stop_btn.setStyleSheet("""
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
        """)
        layout.addWidget(self.stop_btn, 1)  # 1/4 stretch factor
        
        return layout
        
    def _create_progress_section(self) -> QVBoxLayout:
        """Create the progress tracking section."""
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
        """Create the output section with improved resizing behavior."""
        layout = QVBoxLayout()
        
        # Header with report button
        header_layout = QHBoxLayout()
        output_label = QLabel("Output:")
        header_layout.addWidget(output_label)
        header_layout.addStretch()
        
        self.report_btn = QPushButton("View Last Report")
        self.report_btn.clicked.connect(self._view_last_report)
        self.report_btn.setEnabled(False)
        self.report_btn.setStyleSheet("background-color: #1976d2;")
        header_layout.addWidget(self.report_btn)
        
        layout.addLayout(header_layout)
        
        # Output text area with improved size policy for better resizing
        self.output_text = QTextEdit()
        self.output_text.setReadOnly(True)
        self.output_text.setMinimumHeight(200)
        # Remove the maximum height constraint that was causing layout issues
        from PyQt6.QtWidgets import QSizePolicy
        # Use MinimumExpanding vertically to allow proper resizing
        self.output_text.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.MinimumExpanding)
        layout.addWidget(self.output_text)
        
        return layout
        
    def _select_url_file(self):
        """Select file containing YouTube URLs."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select URL File",
            "",
            "Text files (*.txt *.csv);;All files (*.*)"
        )
        if file_path:
            self.file_input.setText(file_path)
            
    def _select_output_directory(self):
        """Select output directory for YouTube transcripts."""
        dir_path = QFileDialog.getExistingDirectory(self, "Select Output Directory")
        if dir_path:
            self.output_dir_input.setText(dir_path)
            
    def _get_start_button_text(self) -> str:
        """Get the text for the start button."""
        return "🎬 Extract Transcripts"
        
    def _start_processing(self):
        """Start YouTube transcript extraction."""
        # Check WebShare credentials from settings
        webshare_username = self.settings.api_keys.webshare_username
        webshare_password = self.settings.api_keys.webshare_password
        
        if not webshare_username or not webshare_password:
            self.show_warning(
                "Missing Credentials",
                "WebShare proxy credentials are required for YouTube processing.\n\n"
                "Please go to the Settings tab and enter your WebShare Username and Password."
            )
            return
            
        # Get URLs with early logging
        logger.info("Starting YouTube extraction process - collecting URLs...")
        urls = self._collect_urls()
        logger.info(f"Collected {len(urls)} URLs for processing")
        
        if not urls:
            logger.info("No URLs found - showing warning to user")
            self.show_warning("No URLs", "Please enter YouTube URLs or select a file containing URLs.")
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
        self.stop_btn.setEnabled(True) # Enable stop button
        
        # Configure extraction
        config = {
            'output_dir': output_dir,
            'format': self.format_combo.currentText(),
            'timestamps': self.timestamps_checkbox.isChecked(),
            'overwrite': self.overwrite_checkbox.isChecked()
        }
        
        # Final safety check before creating worker
        if not urls or len(urls) == 0:
            logger.error("CRITICAL: Attempting to create worker with empty URL list - aborting!")
            self.show_error("Internal Error", "No URLs available for processing")
            self._reset_ui_state()
            return
        
        # Start extraction worker
        logger.info(f"Creating YouTube extraction worker with {len(urls)} URLs")
        self.extraction_worker = YouTubeExtractionWorker(urls, config, self)
        self.extraction_worker.progress_updated.connect(self._update_extraction_progress)
        self.extraction_worker.url_completed.connect(self._url_extraction_completed)
        self.extraction_worker.extraction_finished.connect(self._extraction_finished)
        self.extraction_worker.extraction_error.connect(self._extraction_error)
        self.extraction_worker.payment_required.connect(self._show_payment_required_dialog)
        
        self.active_workers.append(self.extraction_worker)
        logger.info("Starting YouTube extraction worker thread")
        self.extraction_worker.start()
        
        self.status_updated.emit("YouTube extraction in progress...")
        
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
            self.show_warning("No Process Running", "No YouTube extraction process is currently running.")
            
    def _collect_urls(self) -> List[str]:
        """Collect URLs from input fields."""
        urls = []
        
        # Get URLs from text input
        text_urls = self.url_input.toPlainText().strip()
        if text_urls:
            for line in text_urls.split('\n'):
                line = line.strip()
                if line and ('youtube.com' in line or 'youtu.be' in line):
                    urls.append(line)
                    
        # Get URLs from file
        file_path = self.file_input.text().strip()
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                # Handle RTF files
                if content.startswith('{\\rtf'):
                    import re
                    url_pattern = r'https?://[^\s\\,}]+'
                    found_urls = re.findall(url_pattern, content)
                    for url in found_urls:
                        url = url.rstrip('\\,}')
                        if 'youtube.com' in url or 'youtu.be' in url:
                            urls.append(url)
                else:
                    # Plain text/CSV file
                    for line in content.split('\n'):
                        line = line.strip()
                        if line and not line.startswith('#'):
                            for url in line.split(','):
                                url = url.strip()
                                if url and ('youtube.com' in url or 'youtu.be' in url):
                                    urls.append(url)
            except Exception as e:
                self.show_error("File Error", f"Could not read URL file: {e}")
                return []
                
        return list(set(urls))  # Remove duplicates
        
    def _update_extraction_progress(self, current: int, total: int, status: str):
        """Update extraction progress."""
        if total > 0:
            percent = (current / total) * 100
            # Display the full enhanced status message
            self.append_log(status)
            
            # Create a cleaner progress label 
            if "Processing:" in status or "Fetching metadata" in status or "Transcript extracted:" in status or "Saved" in status:
                # Extract just the essential info for the progress label
                if current < total:
                    self.progress_label.setText(f"Processing {current + 1} of {total} URLs ({percent:.1f}%)")
                else:
                    self.progress_label.setText(f"Completed {total} of {total} URLs (100%)")
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
        """Handle completion of single URL extraction."""
        self.append_log(f"  → {message}")
        
    def _extraction_finished(self, results: Dict[str, Any]):
        """Handle completion of all extractions."""
        self.append_log("\n" + "="*50)
        self.append_log("🎬 YouTube extraction completed!")
        self.append_log(f"✅ Successful: {results['successful']}")
        self.append_log(f"❌ Failed: {results['failed']}")
        
        # Show where files were saved
        output_dir = self.output_dir_input.text().strip()
        if not output_dir:
            output_dir = str(Path.cwd())
        
        self.append_log(f"\n📁 Files saved to: {output_dir}")
        self.append_log(f"🖼️  Thumbnails saved to: {output_dir}/Thumbnails/")
        
        if results['successful'] > 0:
            self.append_log(f"\n🎉 Successfully processed {results['successful']} video(s)!")
            self.append_log("📝 Check the output directory for .md transcript files")
            self.append_log("🖼️  Check the Thumbnails subdirectory for thumbnail images")
        
        if results['failed_urls']:
            self.append_log(f"\n⚠️  {len(results['failed_urls'])} URL(s) failed:")
            for failed_url in results['failed_urls']:
                if isinstance(failed_url, dict):
                    self.append_log(f"  • {failed_url.get('title', 'Unknown')} - {failed_url.get('error', 'Unknown error')}")
                else:
                    self.append_log(f"  • {failed_url}")
        
        # Reset UI
        self.start_btn.setEnabled(True)
        self.start_btn.setText(self._get_start_button_text())
        self.stop_btn.setEnabled(False) # Disable stop button
        self.progress_bar.setVisible(False)
        self.progress_bar.setValue(100)
        self.progress_label.setText("Extraction completed successfully!")
        
        self.status_updated.emit("YouTube extraction completed")
        self.processing_finished.emit()
        
    def _extraction_error(self, error_msg: str):
        """Handle extraction error."""
        self.append_log(f"❌ Error: {error_msg}")
        self.show_error("Extraction Error", f"YouTube extraction failed: {error_msg}")
        
        # Reset UI
        self.start_btn.setEnabled(True)
        self.start_btn.setText(self._get_start_button_text())
        self.stop_btn.setEnabled(False) # Disable stop button
        self.progress_bar.setVisible(False)
        self.progress_bar.setValue(0)
        self.progress_label.setText("Extraction failed")
        
        self.status_updated.emit("Ready")
        
    def _show_payment_required_dialog(self):
        """Show popup dialog for 402 Payment Required error."""
        from PyQt6.QtWidgets import QMessageBox
        
        msg_box = QMessageBox(self)
        msg_box.setIcon(QMessageBox.Icon.Warning)
        msg_box.setWindowTitle("WebShare Payment Required")
        msg_box.setText("💰 WebShare Account Insufficient Funds")
        msg_box.setInformativeText("Please add payment at https://panel.webshare.io/ to continue using YouTube extraction")
        msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg_box.button(QMessageBox.StandardButton.Ok).setText("DISMISS")
        msg_box.exec()
        
    def validate_inputs(self) -> bool:
        """Validate inputs before processing."""
        # Check output directory
        output_dir = self.output_dir_input.text().strip()
        if output_dir:
            output_path = Path(output_dir)
            if not output_path.parent.exists():
                self.show_error("Invalid Output", "Output directory parent doesn't exist")
                return False
        
        # Check WebShare proxy credentials (required for YouTube processing)
        webshare_username = getattr(self.settings.api_keys, 'webshare_username', None)
        webshare_password = getattr(self.settings.api_keys, 'webshare_password', None)
        
        if not webshare_username or not webshare_password:
            self.show_error(
                "Missing WebShare Credentials", 
                "YouTube processing requires WebShare rotating residential proxy credentials.\n\n"
                "Please configure your WebShare Username and Password in the API Keys tab.\n\n"
                "This system uses only WebShare proxies for YouTube access - no other methods are supported.\n\n"
                "Sign up at: https://www.webshare.io/"
            )
            return False
                
        return True
        
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
    
    def _load_settings(self):
        """Load saved settings from session."""
        try:
            # Load output directory
            saved_output_dir = self.gui_settings.get_output_directory(
                self.tab_name, 
                str(self.settings.paths.transcripts)
            )
            self.output_dir_input.setText(saved_output_dir)
            
            # Load format selection
            saved_format = self.gui_settings.get_combo_selection(self.tab_name, "format", "md")
            index = self.format_combo.findText(saved_format)
            if index >= 0:
                self.format_combo.setCurrentIndex(index)
            
            # Load checkbox states
            self.timestamps_checkbox.setChecked(
                self.gui_settings.get_checkbox_state(self.tab_name, "include_timestamps", True)
            )
            self.overwrite_checkbox.setChecked(
                self.gui_settings.get_checkbox_state(self.tab_name, "overwrite_existing", False)
            )
            
            logger.debug(f"Loaded settings for {self.tab_name} tab")
        except Exception as e:
            logger.error(f"Failed to load settings for {self.tab_name} tab: {e}")
    
    def _save_settings(self):
        """Save current settings to session."""
        try:
            # Save output directory
            self.gui_settings.set_output_directory(self.tab_name, self.output_dir_input.text())
            
            # Save format selection
            self.gui_settings.set_combo_selection(self.tab_name, "format", self.format_combo.currentText())
            
            # Save checkbox states
            self.gui_settings.set_checkbox_state(self.tab_name, "include_timestamps", self.timestamps_checkbox.isChecked())
            self.gui_settings.set_checkbox_state(self.tab_name, "overwrite_existing", self.overwrite_checkbox.isChecked())
            
            logger.debug(f"Saved settings for {self.tab_name} tab")
        except Exception as e:
            logger.error(f"Failed to save settings for {self.tab_name} tab: {e}")
    
    def _on_setting_changed(self):
        """Called when any setting changes to automatically save."""
        self._save_settings()
        self.stop_btn.setEnabled(False)
        self.status_updated.emit("Ready") 