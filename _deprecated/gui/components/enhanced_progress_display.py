"""Enhanced progress display component for transcription operations."""

import time

from PyQt6.QtCore import QTimer, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)


class TranscriptionProgressDisplay(QFrame):
    """Enhanced progress display for transcription operations with detailed feedback."""

    cancellation_requested = pyqtSignal()
    retry_requested = pyqtSignal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFixedHeight(160)
        self.setFrameStyle(QFrame.Shape.Box)
        self.setStyleSheet(
            """
            QFrame {
                background-color: #2d2d2d;
                border: 2px solid #3c3c3c;
                border-radius: 8px;
                margin: 5px;
            }
        """
        )

        # Progress tracking data
        self.start_time = None
        self.total_files = 0
        self.completed_files = 0
        self.failed_files = 0
        self.current_file = ""
        self.operation_type = ""

        # Hide initially
        self.hide()

        # Setup UI
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Setup the enhanced progress display UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(8)

        # Top section: Operation header and controls
        header_layout = QHBoxLayout()

        # Operation title and status
        self.operation_label = QLabel("Transcription Progress")
        font = QFont()
        font.setBold(True)
        font.setPointSize(12)
        self.operation_label.setFont(font)
        self.operation_label.setStyleSheet("color: #2c3e50;")
        header_layout.addWidget(self.operation_label)

        header_layout.addStretch()

        # Control buttons
        self.retry_btn = QPushButton("🔄 Retry Failed")
        self.retry_btn.clicked.connect(self.retry_requested.emit)
        self.retry_btn.setStyleSheet(
            """
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
            QPushButton:disabled {
                background-color: #bdc3c7;
            }
        """
        )
        self.retry_btn.hide()
        header_layout.addWidget(self.retry_btn)

        self.cancel_btn = QPushButton("⏹ Cancel")
        self.cancel_btn.clicked.connect(self.cancellation_requested.emit)
        self.cancel_btn.setStyleSheet(
            """
            QPushButton {
                background-color: #e74c3c;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #c0392b;
            }
        """
        )
        self.cancel_btn.hide()
        header_layout.addWidget(self.cancel_btn)

        layout.addLayout(header_layout)

        # Progress bar section
        progress_layout = QVBoxLayout()

        # Main progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setStyleSheet(
            """
            QProgressBar {
                background-color: #ecf0f1;
                border: 1px solid #bdc3c7;
                border-radius: 4px;
                text-align: center;
                font-weight: bold;
                height: 24px;
                color: #2c3e50;
                font-size: 12px;
            }
            QProgressBar::chunk {
                background-color: #27ae60;
                border-radius: 4px;
            }
            QProgressBar::text {
                color: #2c3e50;
                font-weight: bold;
                font-size: 12px;
            }
        """
        )
        # Ensure percentage text is visible
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("%p%")  # Show percentage with % symbol
        progress_layout.addWidget(self.progress_bar)

        # Status and ETA info
        info_layout = QHBoxLayout()

        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("color: #34495e; font-weight: bold;")
        info_layout.addWidget(self.status_label)

        info_layout.addStretch()

        self.eta_label = QLabel("")
        self.eta_label.setStyleSheet("color: #7f8c8d; font-style: italic;")
        info_layout.addWidget(self.eta_label)

        progress_layout.addLayout(info_layout)
        layout.addLayout(progress_layout)

        # Statistics grid
        stats_layout = QGridLayout()

        # Files statistics
        self.total_files_label = QLabel("Total: 0")
        self.total_files_label.setStyleSheet("color: #34495e; font-weight: bold;")
        stats_layout.addWidget(QLabel("📁"), 0, 0)
        stats_layout.addWidget(self.total_files_label, 0, 1)

        self.completed_files_label = QLabel("✅ Completed: 0")
        self.completed_files_label.setStyleSheet("color: #27ae60; font-weight: bold;")
        stats_layout.addWidget(self.completed_files_label, 0, 2)

        self.failed_files_label = QLabel("❌ Failed: 0")
        self.failed_files_label.setStyleSheet("color: #e74c3c; font-weight: bold;")
        stats_layout.addWidget(self.failed_files_label, 0, 3)

        # Current operation info
        self.current_file_label = QLabel("Current: None")
        self.current_file_label.setStyleSheet("color: #2c3e50;")
        stats_layout.addWidget(QLabel("🎤"), 1, 0)
        stats_layout.addWidget(self.current_file_label, 1, 1, 1, 3)

        layout.addLayout(stats_layout)

    def start_operation(
        self, operation_type: str, total_files: int, title: str | None = None
    ) -> None:
        """Start a new transcription operation."""
        self.operation_type = operation_type
        self.total_files = total_files
        self.completed_files = 0
        self.failed_files = 0
        self.current_file = ""
        self.start_time = time.time()

        # Update UI
        display_title = title or f"{operation_type.title()} Progress"
        self.operation_label.setText(display_title)

        self.progress_bar.setMaximum(total_files)
        self.progress_bar.setValue(0)

        # Debug logging
        print(
            f"🔍 Progress bar initialized: max={total_files}, value=0, text_visible={self.progress_bar.isTextVisible()}"
        )

        self._update_statistics()
        self._update_status("Starting...")

        # Show controls
        self.cancel_btn.show()
        self.retry_btn.hide()

        # Show the widget
        self.show()

    def update_progress(
        self,
        completed: int,
        failed: int,
        current_file: str = "",
        current_status: str = "",
        step_progress: int = 0,
    ) -> None:
        """Update progress with current statistics."""
        self.completed_files = completed
        self.failed_files = failed
        self.current_file = current_file

        total_processed = completed + failed
        self.progress_bar.setValue(total_processed)

        # Debug logging
        percentage = (
            int((total_processed / self.total_files) * 100)
            if self.total_files > 0
            else 0
        )
        print(
            f"🔍 Progress updated: {total_processed}/{self.total_files} = {percentage}%, text_visible={self.progress_bar.isTextVisible()}"
        )

        # Update current status
        if current_file and current_status:
            display_status = f"{current_status}: {current_file}"
            if step_progress > 0:
                display_status += f" ({step_progress}%)"
        elif current_status:
            display_status = current_status
        else:
            display_status = (
                f"Processing file {total_processed + 1} of {self.total_files}"
            )

        self._update_status(display_status)
        self._update_statistics()
        self._update_eta()

    def set_current_step(self, step_description: str, step_progress: int = 0) -> None:
        """Update the current step being performed."""
        if step_progress > 0:
            status = f"{step_description} ({step_progress}%)"
        else:
            status = step_description
        self._update_status(status)

    def complete_operation(self, success_count: int, failure_count: int) -> None:
        """Complete the operation and show final results."""
        self.completed_files = success_count
        self.failed_files = failure_count

        # Update final status
        if failure_count == 0:
            self._update_status(
                f"✅ Completed! All {success_count} files processed successfully"
            )
            self.operation_label.setText("✅ Transcription Complete")
            self.operation_label.setStyleSheet("color: #27ae60; font-weight: bold;")
        else:
            self._update_status(
                f"⚠️ Completed with {failure_count} failed out of {success_count + failure_count} files"
            )
            self.operation_label.setText("⚠️ Transcription Complete (with failures)")
            self.operation_label.setStyleSheet("color: #f39c12; font-weight: bold;")

            # Show retry button if there were failures
            self.retry_btn.show()

        # Hide cancel button, update statistics
        self.cancel_btn.hide()
        self._update_statistics()
        self.eta_label.setText("")

        # Auto-hide after delay if no failures
        if failure_count == 0:
            QTimer.singleShot(5000, self.hide)

    def set_error(self, error_message: str) -> None:
        """Show error state with detailed message."""
        self.operation_label.setText("❌ Transcription Error")
        self.operation_label.setStyleSheet("color: #e74c3c; font-weight: bold;")
        self._update_status(f"Error: {error_message}")

        # Show retry button
        self.retry_btn.show()
        self.cancel_btn.hide()

        self.eta_label.setText("")

    def _update_status(self, status: str) -> None:
        """Update the status label."""
        self.status_label.setText(status)

    def _update_statistics(self) -> None:
        """Update the statistics display."""
        self.total_files_label.setText(f"Total: {self.total_files}")
        self.completed_files_label.setText(f"✅ Completed: {self.completed_files}")
        self.failed_files_label.setText(f"❌ Failed: {self.failed_files}")

        if self.current_file:
            display_name = self.current_file
            if len(display_name) > 40:
                display_name = "..." + display_name[-37:]
            self.current_file_label.setText(f"Current: {display_name}")
        else:
            self.current_file_label.setText("Current: None")

    def _update_eta(self) -> None:
        """Update the ETA display."""
        if not self.start_time or self.completed_files == 0:
            return

        elapsed = time.time() - self.start_time
        processed = self.completed_files + self.failed_files

        if processed > 0:
            avg_time_per_file = elapsed / processed
            remaining_files = self.total_files - processed
            eta_seconds = avg_time_per_file * remaining_files

            if eta_seconds > 60:
                eta_minutes = int(eta_seconds // 60)
                eta_secs = int(eta_seconds % 60)
                eta_text = f"ETA: ~{eta_minutes}m {eta_secs}s"
            else:
                eta_text = f"ETA: ~{int(eta_seconds)}s"

            # Add speed information
            files_per_minute = (processed / elapsed) * 60 if elapsed > 0 else 0
            eta_text += f" ({files_per_minute:.1f} files/min)"

            self.eta_label.setText(eta_text)

    def reset(self) -> None:
        """Reset the progress display to initial state."""
        self.hide()
        self.operation_label.setText("Transcription Progress")
        self.operation_label.setStyleSheet("color: #2c3e50; font-weight: bold;")
        self.status_label.setText("Ready")
        self.eta_label.setText("")
        self.progress_bar.setValue(0)
        self.cancel_btn.hide()
        self.retry_btn.hide()

        # Reset tracking data
        self.start_time = None
        self.total_files = 0
        self.completed_files = 0
        self.failed_files = 0
        self.current_file = ""
        self.operation_type = ""


class CloudTranscriptionStatusDisplay(QFrame):
    """Specialized status display for cloud transcription operations."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        # Just enough height for a progress bar
        self.setFixedHeight(30)
        # Remove all frame styling - no blue box, no borders
        self.setFrameStyle(QFrame.Shape.NoFrame)
        self.setStyleSheet("")  # No background styling

        self.hide()
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Setup ONLY a blue progress bar - no text, no labels, no clutter."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 5, 0, 5)  # Minimal margins
        layout.setSpacing(0)

        # ONLY the blue progress bar - nothing else
        self.cloud_progress = QProgressBar()
        self.cloud_progress.setStyleSheet(
            """
            QProgressBar {
                background-color: #3c3c3c;
                border: 1px solid #3498db;
                border-radius: 3px;
                text-align: center;
                height: 20px;
            }
            QProgressBar::chunk {
                background-color: #3498db;
                border-radius: 3px;
            }
        """
        )
        layout.addWidget(self.cloud_progress)

    def update_cloud_status(
        self,
        current_url: int,
        total_urls: int,
        current_operation: str,
        api_status: str = "",
        current_step: int = 0,
        steps_per_url: int = 6,
    ) -> None:
        """Update ONLY the progress bar with granular step-based progress."""
        self.show()

        # Calculate granular progress based on steps within each URL
        if total_urls > 0:
            total_steps = total_urls * steps_per_url
            # Add 1 to current_step to show progress for the step being worked on
            current_step_overall = (current_url * steps_per_url) + current_step + 1

            self.cloud_progress.setMaximum(total_steps)
            self.cloud_progress.setValue(min(current_step_overall, total_steps))
        else:
            self.cloud_progress.setMaximum(0)  # Indeterminate

    def set_connection_status(self, connected: bool, message: str = "") -> None:
        """No-op - only showing progress bar."""

    def set_error(self, error_message: str) -> None:
        """Show error by hiding the progress bar."""
        self.hide()

    def complete(self, success_count: int, failure_count: int) -> None:
        """Complete - set progress to 100% then auto-hide."""
        self.cloud_progress.setValue(self.cloud_progress.maximum())
        # Auto-hide after delay
        QTimer.singleShot(3000, self.hide)

    def reset(self) -> None:
        """Reset to initial state."""
        self.hide()
        self.cloud_progress.setValue(0)


class PipelineProgressDisplay(QFrame):
    """
    Progress display for the claims-first extraction pipeline.
    
    Shows 6 stages with individual progress tracking:
    1. Fetch Metadata
    2. Fetch Transcript
    3. Extract Claims (Mining)
    4. Evaluate Claims
    5. Match Timestamps
    6. Attribute Speakers
    
    Also supports batch mode for processing multiple episodes.
    """
    
    # Signals for user actions
    cancellation_requested = pyqtSignal()
    pause_requested = pyqtSignal()
    resume_requested = pyqtSignal()
    whisper_fallback_requested = pyqtSignal()
    
    # Stage definitions
    STAGES = [
        ("fetch_metadata", "Fetch Metadata", "📋"),
        ("fetch_transcript", "Fetch Transcript", "📝"),
        ("extract_claims", "Extract Claims", "🔍"),
        ("evaluate_claims", "Evaluate Claims", "⚖️"),
        ("match_timestamps", "Match Timestamps", "⏱️"),
        ("attribute_speakers", "Attribute Speakers", "🎤"),
    ]
    
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFrameStyle(QFrame.Shape.Box)
        self.setStyleSheet("""
            QFrame {
                background-color: #2d2d2d;
                border: 2px solid #3c3c3c;
                border-radius: 8px;
                margin: 5px;
            }
        """)
        
        # Tracking state
        self.start_time = None
        self.batch_start_time = None
        self.total_episodes = 0
        self.current_episode = 0
        self.current_stage_index = 0
        self.current_stage_progress = 0
        self.is_paused = False
        self.episode_title = ""
        
        # Hide initially
        self.hide()
        
        self._setup_ui()
    
    def _setup_ui(self) -> None:
        """Setup the pipeline progress display UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 10, 15, 10)
        layout.setSpacing(8)
        
        # Header with title and controls
        header_layout = QHBoxLayout()
        
        self.title_label = QLabel("Claims-First Extraction")
        font = QFont()
        font.setBold(True)
        font.setPointSize(12)
        self.title_label.setFont(font)
        self.title_label.setStyleSheet("color: #2c3e50;")
        header_layout.addWidget(self.title_label)
        
        header_layout.addStretch()
        
        # Pause/Resume button
        self.pause_btn = QPushButton("⏸ Pause")
        self.pause_btn.clicked.connect(self._toggle_pause)
        self.pause_btn.setStyleSheet("""
            QPushButton {
                background-color: #f39c12;
                color: white;
                border: none;
                padding: 5px 10px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #e67e22;
            }
        """)
        header_layout.addWidget(self.pause_btn)
        
        # Cancel button
        self.cancel_btn = QPushButton("⏹ Cancel")
        self.cancel_btn.clicked.connect(self.cancellation_requested.emit)
        self.cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c;
                color: white;
                border: none;
                padding: 5px 10px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #c0392b;
            }
        """)
        header_layout.addWidget(self.cancel_btn)
        
        layout.addLayout(header_layout)
        
        # Batch progress (if applicable)
        self.batch_layout = QHBoxLayout()
        self.batch_label = QLabel("Episode 0 of 0")
        self.batch_label.setStyleSheet("color: #7f8c8d; font-style: italic;")
        self.batch_layout.addWidget(self.batch_label)
        
        self.batch_progress = QProgressBar()
        self.batch_progress.setMaximumHeight(8)
        self.batch_progress.setStyleSheet("""
            QProgressBar {
                background-color: #ecf0f1;
                border: 1px solid #bdc3c7;
                border-radius: 4px;
            }
            QProgressBar::chunk {
                background-color: #9b59b6;
                border-radius: 4px;
            }
        """)
        self.batch_progress.setTextVisible(False)
        self.batch_layout.addWidget(self.batch_progress, 1)
        
        batch_widget = QFrame()
        batch_widget.setLayout(self.batch_layout)
        batch_widget.setStyleSheet("border: none; background: transparent;")
        self.batch_widget = batch_widget
        self.batch_widget.hide()
        layout.addWidget(self.batch_widget)
        
        # Current episode title
        self.episode_label = QLabel("")
        self.episode_label.setStyleSheet("color: #34495e; font-weight: bold;")
        layout.addWidget(self.episode_label)
        
        # Stage progress bar
        self.stage_progress = QProgressBar()
        self.stage_progress.setStyleSheet("""
            QProgressBar {
                background-color: #ecf0f1;
                border: 1px solid #bdc3c7;
                border-radius: 4px;
                text-align: center;
                font-weight: bold;
                height: 24px;
                color: #2c3e50;
            }
            QProgressBar::chunk {
                background-color: #27ae60;
                border-radius: 4px;
            }
        """)
        self.stage_progress.setTextVisible(True)
        self.stage_progress.setMaximum(100)
        layout.addWidget(self.stage_progress)
        
        # Stage indicator row
        stage_layout = QHBoxLayout()
        self.stage_labels = []
        
        for stage_id, stage_name, emoji in self.STAGES:
            label = QLabel(f"{emoji}")
            label.setToolTip(stage_name)
            label.setAlignment(label.alignment())
            label.setStyleSheet("""
                QLabel {
                    color: #bdc3c7;
                    font-size: 16px;
                    padding: 4px;
                }
            """)
            stage_layout.addWidget(label)
            self.stage_labels.append(label)
        
        layout.addLayout(stage_layout)
        
        # Status and ETA
        status_layout = QHBoxLayout()
        
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("color: #34495e;")
        status_layout.addWidget(self.status_label)
        
        status_layout.addStretch()
        
        self.eta_label = QLabel("")
        self.eta_label.setStyleSheet("color: #7f8c8d; font-style: italic;")
        status_layout.addWidget(self.eta_label)
        
        layout.addLayout(status_layout)
        
        # Whisper fallback button (shown when quality is low)
        self.whisper_btn = QPushButton("🔄 Re-run with Whisper")
        self.whisper_btn.clicked.connect(self.whisper_fallback_requested.emit)
        self.whisper_btn.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
        """)
        self.whisper_btn.hide()
        layout.addWidget(self.whisper_btn)
    
    def start_batch(self, total_episodes: int) -> None:
        """Start a batch operation with multiple episodes."""
        self.total_episodes = total_episodes
        self.current_episode = 0
        self.batch_start_time = time.time()
        
        if total_episodes > 1:
            self.batch_widget.show()
            self.batch_progress.setMaximum(total_episodes)
            self.batch_progress.setValue(0)
            self._update_batch_label()
        else:
            self.batch_widget.hide()
        
        self.show()
    
    def start_episode(self, episode_index: int, title: str = "") -> None:
        """Start processing a new episode."""
        self.current_episode = episode_index
        self.current_stage_index = 0
        self.current_stage_progress = 0
        self.start_time = time.time()
        self.episode_title = title
        
        # Update displays
        if title:
            display_title = title[:50] + "..." if len(title) > 50 else title
            self.episode_label.setText(f"📺 {display_title}")
        else:
            self.episode_label.setText(f"📺 Episode {episode_index + 1}")
        
        self._update_batch_label()
        self._update_stage_display()
        
        self.whisper_btn.hide()
        self.show()
    
    def update_stage(
        self,
        stage_id: str,
        progress: int = 0,
        status: str = "",
    ) -> None:
        """Update the current stage progress."""
        # Find stage index
        for i, (sid, name, _) in enumerate(self.STAGES):
            if sid == stage_id:
                self.current_stage_index = i
                break
        
        self.current_stage_progress = progress
        
        if status:
            self.status_label.setText(status)
        else:
            _, stage_name, _ = self.STAGES[self.current_stage_index]
            self.status_label.setText(f"{stage_name}...")
        
        self._update_stage_display()
        self._update_eta()
    
    def complete_stage(self, stage_id: str) -> None:
        """Mark a stage as complete and move to the next."""
        for i, (sid, _, _) in enumerate(self.STAGES):
            if sid == stage_id:
                self.current_stage_index = i + 1
                self.current_stage_progress = 0
                break
        
        self._update_stage_display()
    
    def complete_episode(self, success: bool = True, quality_warning: bool = False) -> None:
        """Complete the current episode."""
        self.current_stage_index = len(self.STAGES)
        
        if self.total_episodes > 1:
            self.batch_progress.setValue(self.current_episode + 1)
            self._update_batch_label()
        
        if quality_warning:
            self.whisper_btn.show()
            self.status_label.setText("⚠️ Low quality - consider Whisper re-extraction")
        elif success:
            self.status_label.setText("✅ Episode complete")
        else:
            self.status_label.setText("❌ Episode failed")
        
        self._update_stage_display()
    
    def complete_batch(self, success_count: int, failure_count: int) -> None:
        """Complete the entire batch operation."""
        total = success_count + failure_count
        
        if failure_count == 0:
            self.title_label.setText("✅ Extraction Complete")
            self.title_label.setStyleSheet("color: #27ae60; font-weight: bold;")
            self.status_label.setText(f"Successfully processed {success_count} episodes")
        else:
            self.title_label.setText("⚠️ Extraction Complete (with failures)")
            self.title_label.setStyleSheet("color: #f39c12; font-weight: bold;")
            self.status_label.setText(
                f"Processed {total}: {success_count} succeeded, {failure_count} failed"
            )
        
        self.cancel_btn.hide()
        self.pause_btn.hide()
        self.eta_label.setText("")
        
        # Auto-hide after delay if no failures
        if failure_count == 0:
            QTimer.singleShot(5000, self.hide)
    
    def show_quality_warning(self, suggestion: str) -> None:
        """Show a quality warning with the Whisper fallback button."""
        self.whisper_btn.show()
        self.status_label.setText(f"⚠️ {suggestion}")
    
    def _toggle_pause(self) -> None:
        """Toggle pause state."""
        self.is_paused = not self.is_paused
        
        if self.is_paused:
            self.pause_btn.setText("▶ Resume")
            self.pause_btn.setStyleSheet("""
                QPushButton {
                    background-color: #27ae60;
                    color: white;
                    border: none;
                    padding: 5px 10px;
                    border-radius: 4px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #2ecc71;
                }
            """)
            self.pause_requested.emit()
        else:
            self.pause_btn.setText("⏸ Pause")
            self.pause_btn.setStyleSheet("""
                QPushButton {
                    background-color: #f39c12;
                    color: white;
                    border: none;
                    padding: 5px 10px;
                    border-radius: 4px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #e67e22;
                }
            """)
            self.resume_requested.emit()
    
    def _update_batch_label(self) -> None:
        """Update the batch progress label."""
        self.batch_label.setText(
            f"Episode {self.current_episode + 1} of {self.total_episodes}"
        )
    
    def _update_stage_display(self) -> None:
        """Update the stage indicators and progress bar."""
        total_stages = len(self.STAGES)
        
        # Calculate overall progress
        completed_stages = self.current_stage_index
        stage_contribution = (self.current_stage_progress / 100) if completed_stages < total_stages else 0
        overall_progress = ((completed_stages + stage_contribution) / total_stages) * 100
        
        self.stage_progress.setValue(int(overall_progress))
        
        # Update stage labels
        for i, label in enumerate(self.stage_labels):
            if i < completed_stages:
                # Completed stage
                label.setStyleSheet("""
                    QLabel {
                        color: #27ae60;
                        font-size: 16px;
                        padding: 4px;
                        font-weight: bold;
                    }
                """)
            elif i == completed_stages and completed_stages < total_stages:
                # Current stage
                label.setStyleSheet("""
                    QLabel {
                        color: #3498db;
                        font-size: 16px;
                        padding: 4px;
                        font-weight: bold;
                    }
                """)
            else:
                # Pending stage
                label.setStyleSheet("""
                    QLabel {
                        color: #bdc3c7;
                        font-size: 16px;
                        padding: 4px;
                    }
                """)
    
    def _update_eta(self) -> None:
        """Update the ETA display."""
        if self.total_episodes > 1 and self.batch_start_time:
            # Batch ETA
            elapsed = time.time() - self.batch_start_time
            if self.current_episode > 0:
                avg_per_episode = elapsed / self.current_episode
                remaining = self.total_episodes - self.current_episode
                eta_seconds = avg_per_episode * remaining
                self._format_eta(eta_seconds)
        elif self.start_time:
            # Single episode ETA (rough estimate based on stage)
            elapsed = time.time() - self.start_time
            total_stages = len(self.STAGES)
            if self.current_stage_index > 0:
                avg_per_stage = elapsed / self.current_stage_index
                remaining_stages = total_stages - self.current_stage_index
                eta_seconds = avg_per_stage * remaining_stages
                self._format_eta(eta_seconds)
    
    def _format_eta(self, eta_seconds: float) -> None:
        """Format and display ETA."""
        if eta_seconds > 3600:
            hours = int(eta_seconds // 3600)
            minutes = int((eta_seconds % 3600) // 60)
            self.eta_label.setText(f"ETA: ~{hours}h {minutes}m")
        elif eta_seconds > 60:
            minutes = int(eta_seconds // 60)
            secs = int(eta_seconds % 60)
            self.eta_label.setText(f"ETA: ~{minutes}m {secs}s")
        else:
            self.eta_label.setText(f"ETA: ~{int(eta_seconds)}s")
    
    def reset(self) -> None:
        """Reset the display to initial state."""
        self.hide()
        self.title_label.setText("Claims-First Extraction")
        self.title_label.setStyleSheet("color: #2c3e50; font-weight: bold;")
        self.status_label.setText("Ready")
        self.eta_label.setText("")
        self.episode_label.setText("")
        self.stage_progress.setValue(0)
        self.batch_widget.hide()
        self.whisper_btn.hide()
        self.cancel_btn.show()
        self.pause_btn.show()
        self.pause_btn.setText("⏸ Pause")
        self.is_paused = False
        
        # Reset stage labels
        for label in self.stage_labels:
            label.setStyleSheet("""
                QLabel {
                    color: #bdc3c7;
                    font-size: 16px;
                    padding: 4px;
                }
            """)
        
        # Reset tracking
        self.start_time = None
        self.batch_start_time = None
        self.total_episodes = 0
        self.current_episode = 0
        self.current_stage_index = 0
        self.current_stage_progress = 0
