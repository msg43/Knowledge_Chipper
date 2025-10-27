#!/usr/bin/env python3
"""
Batch Processing Tab for Skip the Podcast Desktop

Integrates the intelligent batch processing system into the main GUI.
Provides one-button processing for large-scale episode operations.
"""

import asyncio
import time
from collections.abc import Callable
from typing import Any

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ...core.batch_processor import (
    BatchJobStatus,
    IntelligentBatchProcessor,
    start_episode_batch_process,
)
from ...utils.hardware_detection import detect_hardware_specs
from ..components.base_tab import BaseTab


class BatchProcessingWorker(QThread):
    """Worker thread for batch processing operations."""

    progress_updated = pyqtSignal(
        str, int, int, dict
    )  # message, completed, total, metadata
    batch_completed = pyqtSignal(str)  # batch_id
    batch_failed = pyqtSignal(str)  # error_message

    def __init__(
        self,
        batch_name: str,
        urls: list[str],
        hardware_specs: dict[str, Any],
        download_func: Callable,
        mining_func: Callable,
        evaluation_func: Callable,
    ):
        super().__init__()
        self.batch_name = batch_name
        self.urls = urls
        self.hardware_specs = hardware_specs
        self.download_func = download_func
        self.mining_func = mining_func
        self.evaluation_func = evaluation_func
        self.batch_id: str | None = None
        self.is_cancelled = False

    def run(self):
        """Run the batch processing operation."""
        try:
            # Create event loop for async operations
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            # Start batch processing
            self.batch_id = loop.run_until_complete(
                start_episode_batch_process(
                    name=self.batch_name,
                    episode_urls=self.urls,
                    hardware_specs=self.hardware_specs,
                    download_func=self.download_func,
                    mining_func=self.mining_func,
                    evaluation_func=self.evaluation_func,
                    progress_callback=self._progress_callback,
                )
            )

            self.batch_completed.emit(self.batch_id)

        except Exception as e:
            self.batch_failed.emit(str(e))
        finally:
            loop.close()

    def _progress_callback(
        self, message: str, completed: int, total: int, metadata: dict[str, Any]
    ):
        """Progress callback from batch processor."""
        if not self.is_cancelled:
            self.progress_updated.emit(message, completed, total, metadata)

    def cancel(self):
        """Cancel the batch processing operation."""
        self.is_cancelled = True


class BatchProcessingTab(BaseTab):
    """
    Batch Processing Tab for large-scale episode processing.

    Features:
    - One-button processing for 5000+ episodes
    - Intelligent resume from interruptions
    - Dynamic parallelization with resource monitoring
    - Real-time progress tracking
    - Hardware-optimized settings
    """

    def __init__(self, main_window):
        super().__init__(main_window)
        self.hardware_specs = detect_hardware_specs()
        self.batch_worker: BatchProcessingWorker | None = None
        self.processor: IntelligentBatchProcessor | None = None

        self._setup_ui()
        self._update_hardware_info()
        self._load_existing_batches()

    def _setup_ui(self):
        """Setup the user interface."""
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # Title
        title_label = QLabel("🚀 Batch Processing")
        title_label.setStyleSheet(
            "font-size: 18px; font-weight: bold; margin-bottom: 10px;"
        )
        layout.addWidget(title_label)

        # Create main splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter)

        # Left panel - Configuration and Controls
        left_panel = self._create_left_panel()
        splitter.addWidget(left_panel)

        # Right panel - Progress and Results
        right_panel = self._create_right_panel()
        splitter.addWidget(right_panel)

        # Set splitter proportions
        splitter.setSizes([400, 600])

    def _create_left_panel(self) -> QWidget:
        """Create the left configuration panel."""
        panel = QWidget()
        layout = QVBoxLayout(panel)

        # Hardware Info Section
        hw_group = QGroupBox("🖥️ Hardware Optimization")
        hw_layout = QVBoxLayout(hw_group)

        self.hardware_info_label = QLabel()
        self.hardware_info_label.setWordWrap(True)
        self.hardware_info_label.setStyleSheet(
            "background-color: #f0f0f0; padding: 10px; border-radius: 5px;"
        )
        hw_layout.addWidget(self.hardware_info_label)

        layout.addWidget(hw_group)

        # Batch Configuration Section
        config_group = QGroupBox("⚙️ Batch Configuration")
        config_layout = QGridLayout(config_group)

        # Batch name
        config_layout.addWidget(QLabel("Batch Name:"), 0, 0)
        self.batch_name_input = QTextEdit()
        self.batch_name_input.setMaximumHeight(30)
        self.batch_name_input.setPlainText("Episode Batch Processing")
        config_layout.addWidget(self.batch_name_input, 0, 1)

        # Parallel processing settings
        config_layout.addWidget(QLabel("Max Parallel Downloads:"), 1, 0)
        self.max_downloads_spin = QSpinBox()
        self.max_downloads_spin.setRange(1, 8)
        self.max_downloads_spin.setValue(4)
        config_layout.addWidget(self.max_downloads_spin, 1, 1)

        config_layout.addWidget(QLabel("Max Parallel Mining:"), 2, 0)
        self.max_mining_spin = QSpinBox()
        self.max_mining_spin.setRange(1, 16)
        self.max_mining_spin.setValue(8)
        config_layout.addWidget(self.max_mining_spin, 2, 1)

        config_layout.addWidget(QLabel("Max Parallel Evaluation:"), 3, 0)
        self.max_evaluation_spin = QSpinBox()
        self.max_evaluation_spin.setRange(1, 12)
        self.max_evaluation_spin.setValue(6)
        config_layout.addWidget(self.max_evaluation_spin, 3, 1)

        # Resume option
        self.resume_checkbox = QCheckBox("Enable intelligent resume from interruptions")
        self.resume_checkbox.setChecked(True)
        config_layout.addWidget(self.resume_checkbox, 4, 0, 1, 2)

        layout.addWidget(config_group)

        # URL Input Section
        url_group = QGroupBox("📋 Episode URLs")
        url_layout = QVBoxLayout(url_group)

        # URL input buttons
        url_button_layout = QHBoxLayout()

        load_file_btn = QPushButton("📁 Load from File")
        load_file_btn.clicked.connect(self._load_urls_from_file)
        url_button_layout.addWidget(load_file_btn)

        paste_btn = QPushButton("📋 Paste URLs")
        paste_btn.clicked.connect(self._show_paste_dialog)
        url_button_layout.addWidget(paste_btn)

        url_layout.addLayout(url_button_layout)

        # URL list
        self.url_tree = QTreeWidget()
        self.url_tree.setHeaderLabels(["#", "Episode URL", "Status"])
        self.url_tree.setMaximumHeight(150)
        url_layout.addWidget(self.url_tree)

        # URL count
        self.url_count_label = QLabel("0 episodes")
        url_layout.addWidget(self.url_count_label)

        layout.addWidget(url_group)

        # Control Buttons Section
        control_group = QGroupBox("🎮 Controls")
        control_layout = QVBoxLayout(control_group)

        # Main processing button
        self.start_button = QPushButton("🚀 Start Batch Processing")
        self.start_button.setStyleSheet(
            """
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
                padding: 10px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
        """
        )
        self.start_button.clicked.connect(self._start_batch_processing)
        control_layout.addWidget(self.start_button)

        # Stop button
        self.stop_button = QPushButton("⏹️ Stop Processing")
        self.stop_button.setEnabled(False)
        self.stop_button.setStyleSheet(
            """
            QPushButton {
                background-color: #f44336;
                color: white;
                font-weight: bold;
                padding: 8px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #da190b;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
        """
        )
        self.stop_button.clicked.connect(self._stop_batch_processing)
        control_layout.addWidget(self.stop_button)

        # Resume button
        self.resume_button = QPushButton("🔄 Resume Interrupted")
        self.resume_button.clicked.connect(self._show_resume_dialog)
        control_layout.addWidget(self.resume_button)

        layout.addWidget(control_group)

        # Batch History Section
        history_group = QGroupBox("📊 Batch History")
        history_layout = QVBoxLayout(history_group)

        self.batch_history_tree = QTreeWidget()
        self.batch_history_tree.setHeaderLabels(
            ["Batch Name", "Status", "Progress", "Created"]
        )
        self.batch_history_tree.setMaximumHeight(120)
        history_layout.addWidget(self.batch_history_tree)

        view_history_btn = QPushButton("📈 View All Batches")
        view_history_btn.clicked.connect(self._show_batch_history)
        history_layout.addWidget(view_history_btn)

        layout.addWidget(history_group)

        return panel

    def _create_right_panel(self) -> QWidget:
        """Create the right progress and results panel."""
        panel = QWidget()
        layout = QVBoxLayout(panel)

        # Progress Section
        progress_group = QGroupBox("📊 Progress Monitoring")
        progress_layout = QVBoxLayout(progress_group)

        # Overall progress
        progress_layout.addWidget(QLabel("Overall Progress:"))
        self.overall_progress = QProgressBar()
        self.overall_progress.setRange(0, 100)
        progress_layout.addWidget(self.overall_progress)

        # Current phase
        self.current_phase_label = QLabel("Ready to start")
        self.current_phase_label.setStyleSheet("font-weight: bold; color: #333;")
        progress_layout.addWidget(self.current_phase_label)

        # Detailed progress
        self.detailed_progress_label = QLabel("")
        progress_layout.addWidget(self.detailed_progress_label)

        # Resource usage
        resource_frame = QFrame()
        resource_layout = QHBoxLayout(resource_frame)

        self.resource_usage_label = QLabel("CPU: 0% | RAM: 0%")
        resource_layout.addWidget(self.resource_usage_label)

        progress_layout.addWidget(resource_frame)

        layout.addWidget(progress_group)

        # Results Section
        results_group = QGroupBox("📋 Results & Logs")
        results_layout = QVBoxLayout(results_group)

        self.results_text = QTextEdit()
        self.results_text.setReadOnly(True)
        self.results_text.setStyleSheet(
            """
            QTextEdit {
                background-color: #f8f8f8;
                border: 1px solid #ddd;
                border-radius: 5px;
                font-family: 'Courier New', monospace;
                font-size: 11px;
            }
        """
        )
        results_layout.addWidget(self.results_text)

        layout.addWidget(results_group)

        return panel

    def _update_hardware_info(self):
        """Update hardware information display."""
        memory_gb = self.hardware_specs.get("memory_gb", 16)
        cpu_cores = self.hardware_specs.get("cpu_cores", 8)
        chip_type = self.hardware_specs.get("chip_type", "Unknown")

        # Determine optimization level
        if memory_gb >= 64 and (
            "ultra" in chip_type.lower() or "max" in chip_type.lower()
        ):
            optimization_level = "Maximum"
            model_type = "Qwen2.5-14B-instruct FP16"
            parallelization_level = "Aggressive (8+ parallel workers)"
            recommended_downloads = 4
            recommended_mining = 8
            recommended_evaluation = 6
        elif memory_gb >= 32 and (
            "max" in chip_type.lower() or "pro" in chip_type.lower()
        ):
            optimization_level = "High"
            model_type = "Qwen2.5-14B-instruct FP16"
            parallelization_level = "Moderate (6 parallel workers)"
            recommended_downloads = 3
            recommended_mining = 6
            recommended_evaluation = 4
        elif memory_gb >= 16:
            optimization_level = "Balanced"
            model_type = "Qwen2.5-7b-instruct"
            parallelization_level = "Conservative (4 parallel workers)"
            recommended_downloads = 2
            recommended_mining = 4
            recommended_evaluation = 3
        else:
            optimization_level = "Basic"
            model_type = "Qwen2.5-3b-instruct"
            parallelization_level = "Minimal (2 parallel workers)"
            recommended_downloads = 1
            recommended_mining = 2
            recommended_evaluation = 2

        # Update spinbox values with recommendations
        self.max_downloads_spin.setValue(recommended_downloads)
        self.max_mining_spin.setValue(recommended_mining)
        self.max_evaluation_spin.setValue(recommended_evaluation)

        hardware_info = f"""Hardware: {chip_type} with {memory_gb}GB RAM, {cpu_cores} cores
Optimization Level: {optimization_level}
Model: {model_type}
Parallelization: {parallelization_level}
Dynamic Scaling: Enabled with real-time resource monitoring

Recommended Settings:
• Downloads: {recommended_downloads} parallel
• Mining: {recommended_mining} parallel
• Evaluation: {recommended_evaluation} parallel"""

        self.hardware_info_label.setText(hardware_info)

    def _load_urls_from_file(self):
        """Load URLs from a text file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select URL file", "", "Text files (*.txt);;All files (*.*)"
        )

        if file_path:
            try:
                with open(file_path) as f:
                    urls = [line.strip() for line in f if line.strip()]
                self._add_urls(urls)
                self._log_result(f"Loaded {len(urls)} URLs from file")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to load URLs: {e}")

    def _show_paste_dialog(self):
        """Show dialog for pasting URLs."""
        from PyQt6.QtWidgets import QDialog, QDialogButtonBox

        dialog = QDialog(self)
        dialog.setWindowTitle("Paste Episode URLs")
        dialog.setModal(True)
        dialog.resize(600, 400)

        layout = QVBoxLayout(dialog)

        layout.addWidget(QLabel("Paste episode URLs (one per line):"))

        url_text = QTextEdit()
        url_text.setPlaceholderText("Paste your episode URLs here, one per line...")
        layout.addWidget(url_text)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            urls = [
                line.strip()
                for line in url_text.toPlainText().split("\n")
                if line.strip()
            ]
            if urls:
                self._add_urls(urls)
                self._log_result(f"Added {len(urls)} URLs from paste")

    def _add_urls(self, urls: list[str]):
        """Add URLs to the tree."""
        # Clear existing URLs
        self.url_tree.clear()

        # Add new URLs
        for i, url in enumerate(urls, 1):
            item = QTreeWidgetItem([str(i), url, "Pending"])
            self.url_tree.addTopLevelItem(item)

        self.url_count_label.setText(f"{len(urls)} episodes")

    def _get_urls(self) -> list[str]:
        """Get all URLs from the tree."""
        urls = []
        for i in range(self.url_tree.topLevelItemCount()):
            item = self.url_tree.topLevelItem(i)
            if item:
                urls.append(item.text(1))
        return urls

    def _start_batch_processing(self):
        """Start batch processing."""
        urls = self._get_urls()
        if not urls:
            QMessageBox.warning(self, "Warning", "Please add episode URLs first")
            return

        batch_name = self.batch_name_input.toPlainText().strip()
        if not batch_name:
            batch_name = f"Episode Batch {int(time.time())}"

        # Get processing functions from main window
        # These would need to be implemented based on your existing functions
        download_func = self._get_download_function()
        mining_func = self._get_mining_function()
        evaluation_func = self._get_evaluation_function()

        if not all([download_func, mining_func, evaluation_func]):
            QMessageBox.warning(self, "Warning", "Processing functions not available")
            return

        # Update UI state
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)

        # Create and start worker
        self.batch_worker = BatchProcessingWorker(
            batch_name,
            urls,
            self.hardware_specs,
            download_func,
            mining_func,
            evaluation_func,
        )

        self.batch_worker.progress_updated.connect(self._update_progress)
        self.batch_worker.batch_completed.connect(self._batch_completed)
        self.batch_worker.batch_failed.connect(self._batch_failed)

        self.batch_worker.start()

        self._log_result(
            f"Started batch processing: {batch_name} ({len(urls)} episodes)"
        )

    def _stop_batch_processing(self):
        """Stop batch processing."""
        if self.batch_worker and self.batch_worker.isRunning():
            self.batch_worker.cancel()
            self.batch_worker.wait(5000)  # Wait up to 5 seconds

            self.start_button.setEnabled(True)
            self.stop_button.setEnabled(False)

            self._log_result("Batch processing stopped by user")

    def _update_progress(
        self, message: str, completed: int, total: int, metadata: dict[str, Any]
    ):
        """Update progress display."""
        # Update progress bar
        progress_percent = (completed / total) * 100 if total > 0 else 0
        self.overall_progress.setValue(int(progress_percent))

        # Update phase label
        phase = metadata.get("phase", "processing")
        self.current_phase_label.setText(f"{phase.title()}: {message}")

        # Update detailed progress
        self.detailed_progress_label.setText(
            f"Completed: {completed}/{total} ({progress_percent:.1f}%)"
        )

        # Update resource usage (this would need to be implemented with actual monitoring)
        self.resource_usage_label.setText("CPU: 45% | RAM: 62%")  # Placeholder

    def _batch_completed(self, batch_id: str):
        """Handle batch completion."""
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)

        self._log_result(f"✅ Batch processing completed successfully!")
        self._log_result(f"Batch ID: {batch_id}")

        # Refresh batch history
        self._load_existing_batches()

    def _batch_failed(self, error_message: str):
        """Handle batch failure."""
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)

        self._log_result(f"❌ Batch processing failed: {error_message}")

        QMessageBox.critical(
            self,
            "Batch Processing Failed",
            f"Batch processing failed:\n{error_message}",
        )

    def _show_resume_dialog(self):
        """Show dialog for resuming interrupted batches."""
        if not self.processor:
            self.processor = IntelligentBatchProcessor(self.hardware_specs)

        # Get interrupted batches
        batches = self.processor.list_batches(BatchJobStatus.IN_PROGRESS)

        if not batches:
            QMessageBox.information(self, "Info", "No interrupted batches found")
            return

        # Show selection dialog (simplified for now)
        QMessageBox.information(
            self,
            "Resume Feature",
            f"Found {len(batches)} interrupted batch(es).\n"
            f"Resume functionality will be fully implemented in the next update.",
        )

    def _show_batch_history(self):
        """Show detailed batch history."""
        if not self.processor:
            self.processor = IntelligentBatchProcessor(self.hardware_specs)

        batches = self.processor.list_batches()

        # Create history dialog (simplified for now)
        QMessageBox.information(
            self,
            "Batch History",
            f"Found {len(batches)} batch(es) in history.\n"
            f"Detailed history view will be implemented in the next update.",
        )

    def _load_existing_batches(self):
        """Load existing batches into history tree."""
        try:
            if not self.processor:
                self.processor = IntelligentBatchProcessor(self.hardware_specs)

            batches = self.processor.list_batches()

            # Clear existing items
            self.batch_history_tree.clear()

            # Add batches to tree
            for batch in batches[:10]:  # Show last 10 batches
                created_text = time.strftime(
                    "%m/%d %H:%M", time.localtime(batch["created_at"])
                )
                progress_text = f"{batch['jobs_completed']}/{batch['total_jobs']}"

                item = QTreeWidgetItem(
                    [batch["name"], batch["status"], progress_text, created_text]
                )
                self.batch_history_tree.addTopLevelItem(item)

        except Exception as e:
            self._log_result(f"Error loading batch history: {e}")

    def _get_download_function(self) -> Callable | None:
        """Get the download function from main window."""
        # This would need to be implemented based on your existing download functionality
        # For now, return a placeholder
        return None

    def _get_mining_function(self) -> Callable | None:
        """Get the mining function from main window."""
        # This would need to be implemented based on your existing mining functionality
        return None

    def _get_evaluation_function(self) -> Callable | None:
        """Get the evaluation function from main window."""
        # This would need to be implemented based on your existing evaluation functionality
        return None

    def _log_result(self, message: str):
        """Log a result message."""
        timestamp = time.strftime("%H:%M:%S")

        # Check if we should auto-scroll BEFORE appending
        scrollbar = self.results_text.verticalScrollBar()
        should_scroll = False
        if scrollbar:
            should_scroll = scrollbar.value() >= scrollbar.maximum() - 10

        self.results_text.append(f"[{timestamp}] {message}")

        # Only auto-scroll if user was already at the bottom
        if should_scroll and scrollbar:
            scrollbar.setValue(scrollbar.maximum())
