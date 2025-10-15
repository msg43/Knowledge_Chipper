"""Completion summary component for transcription operations."""

from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)


class TranscriptionCompletionSummary(QDialog):
    """Dialog showing detailed completion summary for transcription operations."""

    # Signal to switch to summarization tab
    switch_to_summarization = pyqtSignal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Transcription Complete - Summary")
        self.setMinimumSize(700, 500)
        self.setModal(True)

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Setup the completion summary UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        # Header
        header_layout = QHBoxLayout()

        success_icon = QLabel("✅")
        success_icon.setStyleSheet("font-size: 24px;")
        header_layout.addWidget(success_icon)

        self.title_label = QLabel("Transcription Completed Successfully!")
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(16)
        self.title_label.setFont(title_font)
        self.title_label.setStyleSheet("color: #2e7d32; margin-left: 10px;")
        header_layout.addWidget(self.title_label)

        header_layout.addStretch()
        layout.addLayout(header_layout)

        # Summary statistics
        stats_group = QGroupBox("📊 Processing Statistics")
        stats_layout = QVBoxLayout(stats_group)

        # Create grid layout for statistics
        stats_grid = QWidget()
        stats_grid_layout = QHBoxLayout(stats_grid)

        # Files processed
        files_widget = self._create_stat_widget("📁 Files", "0 processed", "#1976d2")
        stats_grid_layout.addWidget(files_widget)

        # Success rate
        self.success_widget = self._create_stat_widget(
            "✅ Success", "0 files", "#4caf50"
        )
        stats_grid_layout.addWidget(self.success_widget)

        # Failures
        self.failures_widget = self._create_stat_widget(
            "❌ Failed", "0 files", "#f44336"
        )
        stats_grid_layout.addWidget(self.failures_widget)

        # Processing time
        self.time_widget = self._create_stat_widget("⏱️ Time", "0 seconds", "#ff9800")
        stats_grid_layout.addWidget(self.time_widget)

        stats_layout.addWidget(stats_grid)
        layout.addWidget(stats_group)

        # Performance metrics
        perf_group = QGroupBox("⚡ Performance Metrics")
        perf_layout = QVBoxLayout(perf_group)

        self.performance_label = QLabel(
            "📈 Average processing speed: -- files/minute\n"
            "📝 Total transcription text: -- characters\n"
            "🎯 Average quality score: --"
        )
        self.performance_label.setStyleSheet("color: white; line-height: 1.4;")
        perf_layout.addWidget(self.performance_label)

        layout.addWidget(perf_group)

        # Files processed (expandable list)
        files_group = QGroupBox("📂 Processed Files")
        files_layout = QVBoxLayout(files_group)

        self.files_list = QListWidget()
        self.files_list.setMaximumHeight(150)
        self.files_list.setStyleSheet(
            """
            QListWidget {
                border: 1px solid #ddd;
                border-radius: 5px;
                background-color: #fafafa;
            }
            QListWidget::item {
                padding: 5px;
                border-bottom: 1px solid #eee;
            }
            QListWidget::item:selected {
                background-color: #e3f2fd;
            }
        """
        )
        files_layout.addWidget(self.files_list)

        layout.addWidget(files_group)

        # Failed files (if any)
        self.failures_group = QGroupBox("⚠️ Failed Files")
        failures_layout = QVBoxLayout(self.failures_group)

        self.failures_list = QListWidget()
        self.failures_list.setMaximumHeight(100)
        self.failures_list.setStyleSheet(
            """
            QListWidget {
                border: 1px solid #f44336;
                border-radius: 5px;
                background-color: #ffebee;
            }
            QListWidget::item {
                padding: 5px;
                color: #c62828;
            }
        """
        )
        failures_layout.addWidget(self.failures_list)

        # Retry button for failed files
        retry_layout = QHBoxLayout()
        retry_layout.addStretch()

        self.retry_btn = QPushButton("🔄 Retry Failed Files")
        self.retry_btn.setStyleSheet(
            """
            QPushButton {
                background-color: #ff9800;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #f57c00;
            }
        """
        )
        retry_layout.addWidget(self.retry_btn)

        failures_layout.addLayout(retry_layout)
        layout.addWidget(self.failures_group)

        # Initially hide failures group
        self.failures_group.hide()

        # Next steps
        next_steps_group = QGroupBox("🚀 Next Steps")
        next_steps_layout = QVBoxLayout(next_steps_group)

        self.next_steps_label = QLabel()
        self.next_steps_label.setWordWrap(True)
        self.next_steps_label.setStyleSheet("color: white; line-height: 1.4;")
        next_steps_layout.addWidget(self.next_steps_label)

        layout.addWidget(next_steps_group)

        # Action buttons
        button_layout = QHBoxLayout()

        # View output folder
        output_btn = QPushButton("📁 Open Output Folder")
        output_btn.setStyleSheet(
            """
            QPushButton {
                background-color: #2196f3;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #1976d2;
            }
        """
        )
        button_layout.addWidget(output_btn)

        # Go to summarization
        summarize_btn = QPushButton("📝 Summarize Transcripts")
        summarize_btn.clicked.connect(self._go_to_summarization)
        summarize_btn.setStyleSheet(
            """
            QPushButton {
                background-color: #4caf50;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """
        )
        button_layout.addWidget(summarize_btn)

        button_layout.addStretch()

        # Close button
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        close_btn.setStyleSheet(
            """
            QPushButton {
                background-color: #757575;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #616161;
            }
        """
        )
        close_btn.setDefault(True)
        button_layout.addWidget(close_btn)

        layout.addLayout(button_layout)

    def _create_stat_widget(self, title: str, value: str, color: str) -> QWidget:
        """Create a statistics widget."""
        widget = QWidget()
        widget.setStyleSheet(
            """
            QWidget {{
                background-color: {color};
                border-radius: 8px;
                margin: 5px;
            }}
        """
        )

        layout = QVBoxLayout(widget)
        layout.setContentsMargins(15, 10, 15, 10)
        layout.setSpacing(5)

        title_label = QLabel(title)
        title_label.setStyleSheet("color: white; font-weight: bold; font-size: 12px;")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)

        value_label = QLabel(value)
        value_label.setStyleSheet("color: white; font-size: 18px; font-weight: bold;")
        value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(value_label)

        # Store reference to value label for updates
        widget.value_label = value_label

        return widget

    def _go_to_summarization(self):
        """Handle click on Summarize Transcripts button."""
        # Close this dialog and emit signal to switch to summarization tab
        self.accept()
        self.switch_to_summarization.emit()

    def show_summary(
        self,
        successful_files: list[dict],
        failed_files: list[dict],
        processing_time: float,
        total_characters: int = 0,
        operation_type: str = "transcription",
    ) -> None:
        """Show completion summary with results."""
        total_files = len(successful_files) + len(failed_files)
        success_count = len(successful_files)
        failure_count = len(failed_files)

        # Update title based on results
        if failure_count == 0:
            self.title_label.setText(
                f"🎉 {operation_type.title()} Completed Successfully!"
            )
            self.title_label.setStyleSheet(
                "color: #2e7d32; margin-left: 10px; font-weight: bold;"
            )
        else:
            self.title_label.setText(
                f"⚠️ {operation_type.title()} Completed with Some Failures"
            )
            self.title_label.setStyleSheet(
                "color: #f57c00; margin-left: 10px; font-weight: bold;"
            )

        # Update statistics
        self.success_widget.value_label.setText(f"{success_count}")
        self.failures_widget.value_label.setText(f"{failure_count}")

        # Calculate processing rate
        if processing_time > 0:
            files_per_minute = (total_files / processing_time) * 60
            time_text = self._format_duration(processing_time)
            self.time_widget.value_label.setText(time_text)

            # Update performance metrics
            avg_quality = "Good" if failure_count == 0 else "Mixed"
            self.performance_label.setText(
                f"📈 Average processing speed: {files_per_minute:.1f} files/minute\n"
                f"📝 Total transcription text: {total_characters:,} characters\n"
                f"🎯 Overall quality: {avg_quality}"
            )

        # Populate successful files list
        self.files_list.clear()
        for file_info in successful_files:
            file_name = Path(file_info.get("file", "Unknown")).name
            char_count = file_info.get("text_length", 0)
            item_text = f"✅ {file_name}"
            if char_count > 0:
                item_text += f" ({char_count:,} chars)"

            item = QListWidgetItem(item_text)
            item.setToolTip(
                f"File: {file_info.get('file', 'Unknown')}\nCharacters: {char_count:,}"
            )
            self.files_list.addItem(item)

        # Populate failed files list (if any)
        if failed_files:
            self.failures_group.show()
            self.failures_list.clear()

            for file_info in failed_files:
                file_name = Path(file_info.get("file", "Unknown")).name
                error = file_info.get("error", "Unknown error")
                item_text = f"❌ {file_name} - {error}"

                item = QListWidgetItem(item_text)
                item.setToolTip(
                    f"File: {file_info.get('file', 'Unknown')}\nError: {error}"
                )
                self.failures_list.addItem(item)
        else:
            self.failures_group.hide()

        # Update next steps
        if operation_type == "transcription":
            if success_count > 0:
                next_steps = (
                    "🎯 Your transcriptions are ready! Here's what you can do next:\n\n"
                    "• Use the Summarization tab to create summaries from your transcripts\n"
                    "• Generate Maps of Content (MOCs) to organize key topics and people\n"
                    "• Export transcripts as markdown files for further editing\n"
                    "• Upload summaries to SkipThePodcast.com for sharing"
                )
            else:
                next_steps = (
                    "😔 No files were successfully transcribed.\n\n"
                    "• Check the failed files list above for specific error details\n"
                    "• Try using different transcription settings\n"
                    "• Verify your audio files are in supported formats\n"
                    "• Consider using cloud transcription for difficult files"
                )
        else:  # cloud transcription
            if success_count > 0:
                next_steps = (
                    "☁️ Your cloud transcription is complete!\n\n"
                    "• Transcripts have been automatically processed and saved\n"
                    "• Use the Summarization tab to create summaries\n"
                    "• Check your SkipThePodcast.com account for additional features\n"
                    "• Consider upgrading for more transcription credits"
                )
            else:
                next_steps = (
                    "😔 Cloud transcription encountered issues.\n\n"
                    "• Check your SkipThePodcast.com account status\n"
                    "• Verify you have sufficient transcription credits\n"
                    "• Try again later if there are service issues\n"
                    "• Consider using local transcription as an alternative"
                )

        self.next_steps_label.setText(next_steps)

        # Show dialog
        self.show()

    def _open_dashboard(self) -> None:
        """Open the SkipThePodcast.com dashboard in the default browser."""
        import webbrowser

        try:
            webbrowser.open("https://skipthepodcast.com/dashboard")
        except Exception as e:
            from PyQt6.QtWidgets import QMessageBox

            QMessageBox.warning(
                self,
                "Cannot Open Dashboard",
                f"Unable to open the dashboard in your browser: {str(e)}\n\n"
                "Please visit https://skipthepodcast.com/dashboard manually.",
            )

    def _format_duration(self, seconds: float) -> str:
        """Format duration in human-readable format."""
        if seconds < 60:
            return f"{seconds:.0f}s"
        elif seconds < 3600:
            minutes = int(seconds // 60)
            secs = int(seconds % 60)
            return f"{minutes}m {secs}s"
        else:
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            return f"{hours}h {minutes}m"


class CloudTranscriptionSummary(QDialog):
    """Specialized summary for cloud transcription operations."""

    # Signal emitted when user wants to retry failed URLs
    retry_requested = pyqtSignal(list)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Cloud Transcription Summary")
        self.setMinimumSize(600, 400)
        self.setModal(True)

        # Initialize defaults - will be updated when show_cloud_summary is called
        self.failed_urls = 0
        self.successful_urls = 0

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Setup the cloud summary UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        # Header
        header_layout = QHBoxLayout()

        cloud_icon = QLabel("☁️")
        cloud_icon.setStyleSheet("font-size: 24px;")
        header_layout.addWidget(cloud_icon)

        self.title_label = QLabel("Cloud Transcription Complete!")
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(16)
        self.title_label.setFont(title_font)
        self.title_label.setStyleSheet("color: white; margin-left: 10px;")
        header_layout.addWidget(self.title_label)

        header_layout.addStretch()
        layout.addLayout(header_layout)

        # URL processing summary
        url_group = QGroupBox("🔗 URL Processing Summary")
        url_layout = QVBoxLayout(url_group)

        self.url_summary = QLabel()
        self.url_summary.setStyleSheet("color: white; font-size: 14px;")
        url_layout.addWidget(self.url_summary)

        layout.addWidget(url_group)

        # Service information
        service_group = QGroupBox("🌐 Service Information")
        service_layout = QVBoxLayout(service_group)

        self.service_info = QLabel()
        self.service_info.setStyleSheet("color: white; font-size: 12px;")
        service_layout.addWidget(self.service_info)

        layout.addWidget(service_group)

        # Next steps for cloud (dynamic based on success/failure)
        next_steps_group = QGroupBox("🚀 What's Next?")
        next_steps_layout = QVBoxLayout(next_steps_group)

        # Default next steps text - will be updated in show_cloud_summary
        default_next_steps_text = (
            "Your transcription results will be displayed here once processing is complete.\n\n"
            "• Transcripts will be automatically saved to your output folder\n"
            "• High-quality summaries will be generated using advanced AI\n"
            "• Use the local Summarization tab for further processing"
        )

        self.next_steps_label = QLabel(default_next_steps_text)
        self.next_steps_label.setWordWrap(True)
        self.next_steps_label.setStyleSheet("color: white; line-height: 1.4;")
        next_steps_layout.addWidget(self.next_steps_label)

        layout.addWidget(next_steps_group)

        # Action buttons
        button_layout = QHBoxLayout()

        dashboard_btn = QPushButton("🌐 Open Dashboard")
        dashboard_btn.setStyleSheet(
            """
            QPushButton {
                background-color: #1976d2;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1565c0;
            }
        """
        )
        dashboard_btn.clicked.connect(self._open_dashboard)
        button_layout.addWidget(dashboard_btn)

        # Retry button (initially hidden)
        self.retry_btn = QPushButton("🔄 Retry Failed Videos")
        self.retry_btn.setStyleSheet(
            """
            QPushButton {
                background-color: #ff9800;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #f57c00;
            }
        """
        )
        self.retry_btn.clicked.connect(self._show_retry_dialog)
        self.retry_btn.hide()  # Initially hidden
        button_layout.addWidget(self.retry_btn)

        button_layout.addStretch()

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        close_btn.setStyleSheet(
            """
            QPushButton {
                background-color: #4caf50;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """
        )
        close_btn.setDefault(True)
        button_layout.addWidget(close_btn)

        layout.addLayout(button_layout)

    def show_cloud_summary(
        self,
        successful_urls: int,
        failed_urls: int,
        total_processing_time: float,
        service_status: str = "Active",
        failed_urls_details: list[dict] | None = None,
        successful_urls_details: list[dict] | None = None,
    ) -> None:
        """Show cloud transcription summary."""
        # Update instance variables
        self.successful_urls = successful_urls
        self.failed_urls = failed_urls
        total_urls = successful_urls + failed_urls

        # Store videos for retry functionality
        if successful_urls_details:
            self._successful_videos_sample = successful_urls_details
        if failed_urls_details:
            self._failed_videos_details = failed_urls_details
            # Show retry button if there are failed videos
            if len(failed_urls_details) > 0:
                self.retry_btn.show()

        # Update title and summary
        if failed_urls == 0:
            self.title_label.setText("🎉 Cloud Transcription Complete!")
            self.title_label.setStyleSheet(
                "color: #2e7d32; margin-left: 10px; font-weight: bold;"
            )
        else:
            self.title_label.setText("❌ Cloud Transcription Failed")
            self.title_label.setStyleSheet(
                "color: #e74c3c; margin-left: 10px; font-weight: bold;"
            )

        # URL processing summary with detailed success and failure information
        if failed_urls == 0:
            summary_text = (
                f"📊 Successfully processed: {successful_urls} URLs\n"
                f"📈 Success rate: 100%\n"
                f"⏱️ Total processing time: {self._format_duration(total_processing_time)}\n\n"
                f"✅ All videos processed successfully!"
            )

            # Show sample of successful videos if available
            if hasattr(self, "_successful_videos_sample"):
                summary_text += f"\n\n🎯 Successfully processed videos:\n"
                for video in self._successful_videos_sample[:3]:
                    # Handle both dictionary and string formats
                    if isinstance(video, dict):
                        title = video.get("title", "Unknown")
                    elif isinstance(video, str):
                        # If it's just a URL string, extract video ID or use URL
                        title = f"Video {video[-11:]}" if len(video) >= 11 else video
                    else:
                        title = "Unknown"
                    display_title = title[:50] + "..." if len(title) > 50 else title
                    summary_text += f"  • {display_title}\n"
                if len(self._successful_videos_sample) > 3:
                    summary_text += f"  • ... and {len(self._successful_videos_sample) - 3} more videos"
        else:
            summary_text = (
                f"📊 Successfully processed: {successful_urls} URLs\n"
                f"❌ Failed to process: {failed_urls} URLs\n"
                f"📈 Success rate: {(successful_urls/total_urls*100):.1f}%\n"
                f"⏱️ Total processing time: {self._format_duration(total_processing_time)}\n"
            )

            # Show sample of successful videos if any
            if successful_urls > 0 and hasattr(self, "_successful_videos_sample"):
                summary_text += f"\n✅ Successfully processed videos (sample):\n"
                for video in self._successful_videos_sample[
                    :2
                ]:  # Show fewer for mixed case
                    # Handle both dictionary and string formats
                    if isinstance(video, dict):
                        title = video.get("title", "Unknown")
                    elif isinstance(video, str):
                        # If it's just a URL string, extract video ID or use URL
                        title = f"Video {video[-11:]}" if len(video) >= 11 else video
                    else:
                        title = "Unknown"
                    display_title = title[:45] + "..." if len(title) > 45 else title
                    summary_text += f"  • {display_title}\n"
                if len(self._successful_videos_sample) > 2:
                    summary_text += (
                        f"  • ... and {len(self._successful_videos_sample) - 2} more\n"
                    )

            summary_text += f"\n🔍 Failure Details:\n"

            # Add detailed error information if available
            if failed_urls_details:
                # Group errors by category for better presentation
                error_categories = self._group_errors_by_category(failed_urls_details)

                for category, failures in error_categories.items():
                    category_icon = self._get_category_icon(category)
                    category_name = self._get_category_name(category)

                    summary_text += f"\n  {category_icon} {category_name} ({len(failures)} videos):\n"

                    # Show up to 3 examples per category
                    for i, failure in enumerate(failures[:3]):
                        # Handle both dictionary and string formats
                        if isinstance(failure, dict):
                            title = failure.get("title", "Unknown")
                            failure.get("error", "Unknown error")
                        elif isinstance(failure, str):
                            # If it's just a URL string, extract video ID or use URL
                            title = (
                                f"Video {failure[-11:]}"
                                if len(failure) >= 11
                                else failure
                            )
                        else:
                            title = "Unknown"

                        # Truncate long titles for display
                        display_title = title[:40] + "..." if len(title) > 40 else title
                        summary_text += f"    • {display_title}\n"

                    if len(failures) > 3:
                        summary_text += f"    • ... and {len(failures) - 3} more\n"

                # Show total if there are many failures
                if len(failed_urls_details) > 5:
                    summary_text += (
                        f"\n  📊 Total failed: {len(failed_urls_details)} videos"
                    )
            else:
                summary_text += f"  Check the logs for detailed error information\n"

        self.url_summary.setText(summary_text)

        # Service information with error context
        if failed_urls == 0:
            self.service_info.setText(
                f"🔗 Service Status: {service_status}\n"
                "⚡ Processing Method: Cloud-based AI transcription\n"
                "🎯 Quality Level: Premium (cloud-optimized models)\n"
                "📁 Output Location: Automatically saved to your output folder"
            )
            # Update next steps for success case
            next_steps_text = (
                "Your content has been processed via SkipThePodcast.com's cloud service:\n\n"
                "• Transcripts are automatically saved to your output folder\n"
                "• High-quality summaries have been generated using advanced AI\n"
                "• Visit your SkipThePodcast.com dashboard for additional features\n"
                "• Use the local Summarization tab for further processing"
            )
        else:
            # Provide troubleshooting information when there are failures
            troubleshooting_text = (
                f"🔗 Service Status: {service_status}\n"
                "⚡ Processing Method: Cloud-based AI transcription\n\n"
                "🔧 Common Solutions:\n"
                "• Check your SkipThePodcast.com account status and credits\n"
                "• Verify network connectivity and try again\n"
                "• Ensure URLs are accessible and not private/restricted\n"
                "• Check for API rate limits or temporary service issues\n"
                "• Contact support if errors persist"
            )
            self.service_info.setText(troubleshooting_text)
            # Update next steps for failure case
            next_steps_text = (
                "Some URLs failed to process. Here's what you can do:\n\n"
                "• Review the failure details above to understand what went wrong\n"
                "• Check your SkipThePodcast.com account status and credits\n"
                "• Retry the failed URLs after addressing any issues\n"
                "• Use local transcription as an alternative for problematic files\n"
                "• Contact support if you need assistance resolving the errors"
            )

        # Update the next steps label with the appropriate text
        self.next_steps_label.setText(next_steps_text)

        self.show()

    def _open_dashboard(self) -> None:
        """Open the SkipThePodcast.com dashboard in the default browser."""
        import webbrowser

        try:
            webbrowser.open("https://skipthepodcast.com/dashboard")
        except Exception as e:
            from PyQt6.QtWidgets import QMessageBox

            QMessageBox.warning(
                self,
                "Cannot Open Dashboard",
                f"Unable to open the dashboard in your browser: {str(e)}\n\n"
                "Please visit https://skipthepodcast.com/dashboard manually.",
            )

    def _format_duration(self, seconds: float) -> str:
        """Format duration in human-readable format."""
        if seconds < 60:
            return f"{seconds:.0f} seconds"
        elif seconds < 3600:
            minutes = int(seconds // 60)
            secs = int(seconds % 60)
            return f"{minutes} minutes, {secs} seconds"
        else:
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            return f"{hours} hours, {minutes} minutes"

    def _group_errors_by_category(
        self, failed_urls_details: list[dict]
    ) -> dict[str, list[dict]]:
        """Group failed URLs by error category for better display."""
        categories = {}

        for failure in failed_urls_details:
            category = failure.get("error_category", "other")
            if category not in categories:
                categories[category] = []
            categories[category].append(failure)

        # Sort categories by priority (most common issues first)
        category_priority = {
            "copyright": 1,
            "unavailable": 2,
            "permission": 3,
            "network": 4,
            "rate_limit": 5,
            "format": 6,
            "other": 7,
        }

        # Sort categories and return
        sorted_categories = dict(
            sorted(categories.items(), key=lambda x: category_priority.get(x[0], 99))
        )
        return sorted_categories

    def _get_category_icon(self, category: str) -> str:
        """Get appropriate icon for error category."""
        icons = {
            "copyright": "🚫",
            "unavailable": "❌",
            "permission": "🔒",
            "network": "🌐",
            "rate_limit": "⏱️",
            "format": "📹",
            "other": "⚠️",
        }
        return icons.get(category, "⚠️")

    def _get_category_name(self, category: str) -> str:
        """Get human-readable name for error category."""
        names = {
            "copyright": "Copyright/Blocked Content",
            "unavailable": "Unavailable Videos",
            "permission": "Access Denied",
            "network": "Network Issues",
            "rate_limit": "Rate Limited",
            "format": "Format/Quality Issues",
            "other": "Other Errors",
        }
        return names.get(category, "Unknown Errors")

    def _show_retry_dialog(self) -> None:
        """Show retry dialog for failed videos."""
        if hasattr(self, "_failed_videos_details") and self._failed_videos_details:
            dialog = RetryFailedVideosDialog(self._failed_videos_details, self)
            result = dialog.exec()

            if result == QDialog.DialogCode.Accepted:
                selected_urls = dialog.get_selected_urls()
                if selected_urls:
                    self._retry_selected_videos(selected_urls)

    def _retry_selected_videos(self, urls: list[str]) -> None:
        """Handle retry of selected failed videos."""
        # Emit signal for parent to handle retry
        self.retry_requested.emit(urls)

        # Close the summary dialog since retry is starting
        self.accept()

    def _save_retry_urls_to_csv(self, urls: list[str]) -> None:
        """Save retry URLs to CSV file for manual retry."""
        try:
            from datetime import datetime

            from PyQt6.QtWidgets import QFileDialog, QMessageBox

            # Let user choose save location
            default_filename = (
                f"retry_failed_videos_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            )
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "Save Failed URLs for Retry",
                default_filename,
                "CSV Files (*.csv);;All Files (*)",
            )

            if file_path:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write("# Failed YouTube URLs for retry\n")
                    f.write(
                        f"# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                    )
                    f.write(
                        "# Load this file in the Cloud Transcription tab to retry\n"
                    )
                    f.write("#\n")
                    for url in urls:
                        f.write(f"{url}\n")

                QMessageBox.information(
                    self,
                    "Retry URLs Saved",
                    f"Failed URLs saved to:\n{file_path}\n\n"
                    "You can load this file in the Cloud Transcription tab to retry the failed videos.",
                )

        except Exception as e:
            from PyQt6.QtWidgets import QMessageBox

            QMessageBox.warning(
                self, "Save Failed", f"Could not save retry URLs: {str(e)}"
            )


class RetryFailedVideosDialog(QDialog):
    """Dialog for selecting which failed videos to retry."""

    def __init__(self, failed_videos: list[dict], parent=None):
        super().__init__(parent)
        self.failed_videos = failed_videos
        self.selected_urls = []

        self.setWindowTitle("Retry Failed Videos")
        self.setMinimumSize(600, 500)
        self.setModal(True)

        self._setup_ui()
        self._populate_videos()

    def _setup_ui(self):
        """Setup the retry dialog UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        # Header
        header_layout = QHBoxLayout()

        retry_icon = QLabel("🔄")
        retry_icon.setStyleSheet("font-size: 24px;")
        header_layout.addWidget(retry_icon)

        title_label = QLabel("Select Videos to Retry")
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(16)
        title_label.setFont(title_font)
        title_label.setStyleSheet("color: #333; margin-left: 10px;")
        header_layout.addWidget(title_label)

        header_layout.addStretch()
        layout.addLayout(header_layout)

        # Instructions
        instructions = QLabel(
            "Select which failed videos you want to retry. Videos are grouped by error type. "
            "Only select videos where the underlying issue (like network problems) might have been resolved."
        )
        instructions.setWordWrap(True)
        instructions.setStyleSheet("color: #666; margin-bottom: 10px;")
        layout.addWidget(instructions)

        # Scroll area for video list
        scroll_area = QScrollArea()
        scroll_widget = QWidget()
        self.scroll_layout = QVBoxLayout(scroll_widget)
        scroll_area.setWidget(scroll_widget)
        scroll_area.setWidgetResizable(True)
        scroll_area.setMinimumHeight(300)
        layout.addWidget(scroll_area)

        # Selection controls
        selection_layout = QHBoxLayout()

        select_all_btn = QPushButton("✅ Select All")
        select_all_btn.clicked.connect(self._select_all)
        select_all_btn.setStyleSheet(
            """
            QPushButton {
                background-color: #4caf50;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """
        )
        selection_layout.addWidget(select_all_btn)

        select_none_btn = QPushButton("❌ Select None")
        select_none_btn.clicked.connect(self._select_none)
        select_none_btn.setStyleSheet(
            """
            QPushButton {
                background-color: #f44336;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #d32f2f;
            }
        """
        )
        selection_layout.addWidget(select_none_btn)

        # Smart selection buttons
        smart_layout = QHBoxLayout()

        retry_network_btn = QPushButton("🌐 Retry Network Errors")
        retry_network_btn.clicked.connect(lambda: self._select_by_category(["network"]))
        retry_network_btn.setStyleSheet(
            """
            QPushButton {
                background-color: #2196f3;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #1976d2;
            }
        """
        )
        smart_layout.addWidget(retry_network_btn)

        retry_rate_limit_btn = QPushButton("⏱️ Retry Rate Limited")
        retry_rate_limit_btn.clicked.connect(
            lambda: self._select_by_category(["rate_limit"])
        )
        retry_rate_limit_btn.setStyleSheet(
            """
            QPushButton {
                background-color: #ff9800;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #f57c00;
            }
        """
        )
        smart_layout.addWidget(retry_rate_limit_btn)

        selection_layout.addStretch()
        selection_layout.addLayout(smart_layout)
        layout.addLayout(selection_layout)

        # Action buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setStyleSheet(
            """
            QPushButton {
                background-color: #757575;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #616161;
            }
        """
        )
        button_layout.addWidget(cancel_btn)

        self.retry_btn = QPushButton("🔄 Retry Selected Videos")
        self.retry_btn.clicked.connect(self._retry_selected)
        self.retry_btn.setStyleSheet(
            """
            QPushButton {
                background-color: #ff9800;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #f57c00;
            }
        """
        )
        self.retry_btn.setEnabled(False)  # Initially disabled
        button_layout.addWidget(self.retry_btn)

        layout.addLayout(button_layout)

    def _populate_videos(self):
        """Populate the video list grouped by error category."""
        # Group videos by category
        categories = {}
        for video in self.failed_videos:
            category = video.get("error_category", "other")
            if category not in categories:
                categories[category] = []
            categories[category].append(video)

        # Category order and info
        category_info = {
            "network": (
                "🌐 Network Issues",
                "These might succeed if network conditions improved",
            ),
            "rate_limit": (
                "⏱️ Rate Limited",
                "These might succeed if you wait a bit and try again",
            ),
            "format": (
                "📹 Format Issues",
                "These might succeed with different processing settings",
            ),
            "permission": (
                "🔒 Access Denied",
                "Check if permissions changed or try different authentication",
            ),
            "unavailable": (
                "❌ Unavailable Videos",
                "These videos might have become available again",
            ),
            "copyright": (
                "🚫 Copyright/Blocked",
                "These are unlikely to succeed without changes",
            ),
            "other": ("⚠️ Other Errors", "Mixed errors that might be worth retrying"),
        }

        self.checkboxes = []

        for category in [
            "network",
            "rate_limit",
            "format",
            "permission",
            "unavailable",
            "other",
            "copyright",
        ]:
            if category in categories:
                videos = categories[category]
                category_name, category_desc = category_info.get(
                    category, (f"Unknown ({category})", "Unknown error type")
                )

                # Category header
                category_label = QLabel(f"{category_name} ({len(videos)} videos)")
                category_label.setStyleSheet(
                    """
                    QLabel {
                        font-weight: bold;
                        font-size: 14px;
                        color: #333;
                        padding: 8px 0px 4px 0px;
                        border-bottom: 1px solid #ddd;
                    }
                """
                )
                self.scroll_layout.addWidget(category_label)

                # Category description
                desc_label = QLabel(category_desc)
                desc_label.setStyleSheet(
                    "color: #666; font-size: 12px; margin-bottom: 8px;"
                )
                self.scroll_layout.addWidget(desc_label)

                # Videos in this category
                for video in videos:
                    video_widget = self._create_video_checkbox(video, category)
                    self.scroll_layout.addWidget(video_widget)

                # Add spacing between categories
                self.scroll_layout.addSpacing(10)

        self.scroll_layout.addStretch()

    def _create_video_checkbox(self, video: dict, category: str) -> QWidget:
        """Create a checkbox widget for a video."""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(20, 4, 10, 4)

        checkbox = QCheckBox()
        checkbox.stateChanged.connect(self._update_retry_button)

        # Store video data with checkbox
        checkbox.video_data = video
        self.checkboxes.append(checkbox)

        layout.addWidget(checkbox)

        # Video info
        # Handle both dictionary and string formats
        if isinstance(video, dict):
            title = video.get("title", "Unknown Title")
            error = video.get("error", "Unknown error")
        elif isinstance(video, str):
            # If it's just a URL string, extract video ID or use URL
            title = f"Video {video[-11:]}" if len(video) >= 11 else video
            error = "Processing failed"
        else:
            title = "Unknown Title"
            error = "Unknown error"

        # Truncate long titles and errors
        display_title = title[:60] + "..." if len(title) > 60 else title
        display_error = error[:80] + "..." if len(error) > 80 else error

        info_label = QLabel(f"{display_title}\nError: {display_error}")
        info_label.setStyleSheet(
            """
            QLabel {
                color: #333;
                padding: 4px;
            }
        """
        )
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        layout.addStretch()

        return widget

    def _select_all(self):
        """Select all videos."""
        for checkbox in self.checkboxes:
            checkbox.setChecked(True)

    def _select_none(self):
        """Deselect all videos."""
        for checkbox in self.checkboxes:
            checkbox.setChecked(False)

    def _select_by_category(self, categories: list[str]):
        """Select videos by specific categories."""
        for checkbox in self.checkboxes:
            video = checkbox.video_data
            if video.get("error_category") in categories:
                checkbox.setChecked(True)
            else:
                checkbox.setChecked(False)

    def _update_retry_button(self):
        """Update retry button state based on selections."""
        selected_count = sum(1 for cb in self.checkboxes if cb.isChecked())
        self.retry_btn.setEnabled(selected_count > 0)
        self.retry_btn.setText(
            f"🔄 Retry {selected_count} Selected Videos"
            if selected_count > 0
            else "🔄 Retry Selected Videos"
        )

    def _retry_selected(self):
        """Handle retry of selected videos."""
        self.selected_urls = []
        for checkbox in self.checkboxes:
            if checkbox.isChecked():
                video = checkbox.video_data
                url = video.get("url")
                if url:
                    self.selected_urls.append(url)

        if self.selected_urls:
            self.accept()

    def get_selected_urls(self) -> list[str]:
        """Get the list of selected URLs for retry."""
        return self.selected_urls
