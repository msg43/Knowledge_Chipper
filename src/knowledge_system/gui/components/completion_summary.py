"""Completion summary component for transcription operations."""

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class TranscriptionCompletionSummary(QDialog):
    """Dialog showing detailed completion summary for transcription operations."""

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
        self.performance_label.setStyleSheet("color: #333; line-height: 1.4;")
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
        self.next_steps_label.setStyleSheet("color: #333; line-height: 1.4;")
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

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Cloud Transcription Complete - Summary")
        self.setMinimumSize(600, 400)
        self.setModal(True)

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

        # Next steps for cloud
        next_steps_group = QGroupBox("🚀 What's Next?")
        next_steps_layout = QVBoxLayout(next_steps_group)

        next_steps_text = (
            "Your content has been processed via SkipThePodcast.com's cloud service:\n\n"
            "• Transcripts are automatically saved to your output folder\n"
            "• High-quality summaries have been generated using advanced AI\n"
            "• Visit your SkipThePodcast.com dashboard for additional features\n"
            "• Use the local Summarization tab for further processing"
        )

        next_steps_label = QLabel(next_steps_text)
        next_steps_label.setWordWrap(True)
        next_steps_label.setStyleSheet("color: white; line-height: 1.4;")
        next_steps_layout.addWidget(next_steps_label)

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
    ) -> None:
        """Show cloud transcription summary."""
        total_urls = successful_urls + failed_urls

        # Update title and summary
        if failed_urls == 0:
            self.title_label.setText("🎉 Cloud Transcription Complete!")
            self.title_label.setStyleSheet(
                "color: white; margin-left: 10px; font-weight: bold;"
            )
        else:
            self.title_label.setText("⚠️ Cloud Transcription Complete (with issues)")
            self.title_label.setStyleSheet(
                "color: white; margin-left: 10px; font-weight: bold;"
            )

        # URL processing summary
        self.url_summary.setText(
            f"📊 Successfully processed: {successful_urls} URLs\n"
            f"❌ Failed to process: {failed_urls} URLs\n"
            f"📈 Success rate: {(successful_urls/total_urls*100):.1f}%\n"
            f"⏱️ Total processing time: {self._format_duration(total_processing_time)}"
        )

        # Service information
        self.service_info.setText(
            f"🔗 Service Status: {service_status}\n"
            "⚡ Processing Method: Cloud-based AI transcription\n"
            "🎯 Quality Level: Premium (cloud-optimized models)\n"
            "📁 Output Location: Automatically saved to your output folder"
        )

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
