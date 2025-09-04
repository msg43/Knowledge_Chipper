"""
Crash Recovery Dialog

Provides a user-friendly interface for handling interrupted processing jobs
and allows users to resume, restart, or delete incomplete checkpoint files.

Features:
- Automatic checkpoint detection on startup
- Job details preview
- Resume/restart/delete options
- Progress estimation
"""

import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import psutil
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QGroupBox, QTextEdit,
    QProgressBar, QMessageBox, QHeaderView, QAbstractItemView
)

from ...logger import get_logger
from ...utils.tracking import ProgressTracker

logger = get_logger(__name__)


class CrashRecoveryDialog(QDialog):
    """Dialog for handling crash recovery and checkpoint management."""
    
    # Signals
    recovery_action_selected = pyqtSignal(str, str)  # action, checkpoint_path
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Processing Recovery")
        self.setModal(True)
        self.resize(800, 600)
        
        # Data
        self.checkpoint_jobs = []
        self.selected_checkpoint = None
        
        self._setup_ui()
        self._scan_for_checkpoints()
        
        # Auto-refresh every 5 seconds
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self._scan_for_checkpoints)
        self.refresh_timer.start(5000)
    
    def _setup_ui(self):
        """Setup the user interface."""
        layout = QVBoxLayout(self)
        
        # Header
        header_label = QLabel("Recovery Manager")
        header_label.setStyleSheet("font-size: 16px; font-weight: bold; padding: 10px;")
        layout.addWidget(header_label)
        
        info_label = QLabel(
            "The following processing jobs were interrupted and can be resumed from their last checkpoint."
        )
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        
        # Jobs table
        jobs_group = QGroupBox("Interrupted Jobs")
        jobs_layout = QVBoxLayout(jobs_group)
        
        self.jobs_table = QTableWidget()
        self.jobs_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.jobs_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.jobs_table.selectionModel().selectionChanged.connect(self._on_selection_changed)
        
        # Table columns
        columns = ["Job Name", "Files", "Progress", "Last Updated", "Status"]
        self.jobs_table.setColumnCount(len(columns))
        self.jobs_table.setHorizontalHeaderLabels(columns)
        
        # Resize columns
        header = self.jobs_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)  # Job Name
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)  # Files
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)  # Progress
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)  # Last Updated
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)  # Status
        
        jobs_layout.addWidget(self.jobs_table)
        layout.addWidget(jobs_group)
        
        # Job details
        details_group = QGroupBox("Job Details")
        details_layout = QVBoxLayout(details_group)
        
        self.details_text = QTextEdit()
        self.details_text.setReadOnly(True)
        self.details_text.setMaximumHeight(150)
        details_layout.addWidget(self.details_text)
        
        layout.addWidget(details_group)
        
        # Action buttons
        button_layout = QHBoxLayout()
        
        self.resume_btn = QPushButton("Resume Processing")
        self.resume_btn.clicked.connect(lambda: self._select_action("resume"))
        self.resume_btn.setEnabled(False)
        button_layout.addWidget(self.resume_btn)
        
        self.restart_btn = QPushButton("Restart from Beginning")
        self.restart_btn.clicked.connect(lambda: self._select_action("restart"))
        self.restart_btn.setEnabled(False)
        button_layout.addWidget(self.restart_btn)
        
        self.delete_btn = QPushButton("Delete Checkpoint")
        self.delete_btn.clicked.connect(lambda: self._select_action("delete"))
        self.delete_btn.setEnabled(False)
        button_layout.addWidget(self.delete_btn)
        
        button_layout.addStretch()
        
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self._scan_for_checkpoints)
        button_layout.addWidget(self.refresh_btn)
        
        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.close_btn)
        
        layout.addLayout(button_layout)
    
    def _scan_for_checkpoints(self):
        """Scan for checkpoint files and populate the table."""
        try:
            # Common checkpoint locations
            checkpoint_locations = [
                Path.home() / ".cache" / "knowledge_chipper" / "checkpoints",
                Path("/tmp"),
                Path.cwd() / "output" / "checkpoints",
                Path.cwd() / "checkpoints"
            ]
            
            self.checkpoint_jobs = []
            
            for location in checkpoint_locations:
                if location.exists():
                    # Look for checkpoint files
                    for checkpoint_file in location.glob("*checkpoint*.json"):
                        try:
                            job_info = self._analyze_checkpoint(checkpoint_file)
                            if job_info:
                                self.checkpoint_jobs.append(job_info)
                        except Exception as e:
                            logger.warning(f"Failed to analyze checkpoint {checkpoint_file}: {e}")
            
            # Also look for temporary checkpoint files
            temp_dir = Path.cwd()
            for checkpoint_file in temp_dir.glob("kc_checkpoint_*.json"):
                try:
                    job_info = self._analyze_checkpoint(checkpoint_file)
                    if job_info:
                        self.checkpoint_jobs.append(job_info)
                except Exception as e:
                    logger.warning(f"Failed to analyze temp checkpoint {checkpoint_file}: {e}")
            
            self._update_table()
            
        except Exception as e:
            logger.error(f"Error scanning for checkpoints: {e}")
    
    def _analyze_checkpoint(self, checkpoint_file: Path) -> Optional[Dict]:
        """Analyze a checkpoint file and extract job information."""
        try:
            with open(checkpoint_file, 'r') as f:
                checkpoint_data = json.load(f)
            
            # Check if this is a valid checkpoint
            if not isinstance(checkpoint_data, dict):
                return None
            
            # Extract job information
            total_files = checkpoint_data.get("total_files", 0)
            completed_files = len(checkpoint_data.get("completed_files", []))
            files_list = checkpoint_data.get("files", [])
            
            if total_files == 0 and len(files_list) > 0:
                total_files = len(files_list)
            
            # Calculate progress
            progress_percent = 0
            if total_files > 0:
                progress_percent = (completed_files / total_files) * 100
            
            # Get file modification time
            mtime = checkpoint_file.stat().st_mtime
            last_updated = datetime.fromtimestamp(mtime)
            
            # Determine status
            status = self._determine_job_status(checkpoint_data, checkpoint_file)
            
            # Create job name from checkpoint file or path
            job_name = checkpoint_data.get("job_name", checkpoint_file.stem)
            if job_name.startswith("kc_checkpoint_"):
                job_name = f"Batch Job {checkpoint_file.stem[-8:]}"  # Last 8 chars of filename
            
            return {
                "checkpoint_file": str(checkpoint_file),
                "job_name": job_name,
                "total_files": total_files,
                "completed_files": completed_files,
                "progress_percent": progress_percent,
                "last_updated": last_updated,
                "status": status,
                "files": files_list,
                "config": checkpoint_data.get("config", {}),
                "results": checkpoint_data.get("results", {}),
                "checkpoint_data": checkpoint_data
            }
            
        except Exception as e:
            logger.warning(f"Failed to analyze checkpoint {checkpoint_file}: {e}")
            return None
    
    def _determine_job_status(self, checkpoint_data: Dict, checkpoint_file: Path) -> str:
        """Determine the status of a checkpoint job."""
        # Check if there's a PID and if the process is still running
        pid = checkpoint_data.get("process_pid")
        if pid:
            try:
                if psutil.pid_exists(pid):
                    process = psutil.Process(pid)
                    if process.is_running():
                        return "Running"
                    else:
                        return "Crashed"
                else:
                    return "Crashed"
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                return "Crashed"
        
        # Check completion status
        total_files = checkpoint_data.get("total_files", 0)
        completed_files = len(checkpoint_data.get("completed_files", []))
        
        if total_files > 0 and completed_files >= total_files:
            return "Completed"
        elif completed_files > 0:
            return "Interrupted"
        else:
            return "Failed"
    
    def _update_table(self):
        """Update the jobs table with current checkpoint data."""
        self.jobs_table.setRowCount(len(self.checkpoint_jobs))
        
        for row, job in enumerate(self.checkpoint_jobs):
            # Job Name
            self.jobs_table.setItem(row, 0, QTableWidgetItem(job["job_name"]))
            
            # Files
            files_text = f"{job['completed_files']}/{job['total_files']}"
            self.jobs_table.setItem(row, 1, QTableWidgetItem(files_text))
            
            # Progress
            progress_text = f"{job['progress_percent']:.1f}%"
            self.jobs_table.setItem(row, 2, QTableWidgetItem(progress_text))
            
            # Last Updated
            time_str = job["last_updated"].strftime("%Y-%m-%d %H:%M:%S")
            self.jobs_table.setItem(row, 3, QTableWidgetItem(time_str))
            
            # Status
            status_item = QTableWidgetItem(job["status"])
            
            # Color code status
            if job["status"] == "Running":
                status_item.setBackground(Qt.GlobalColor.green)
            elif job["status"] == "Crashed":
                status_item.setBackground(Qt.GlobalColor.red)
            elif job["status"] == "Interrupted":
                status_item.setBackground(Qt.GlobalColor.yellow)
            elif job["status"] == "Completed":
                status_item.setBackground(Qt.GlobalColor.lightGray)
            
            self.jobs_table.setItem(row, 4, status_item)
        
        # Update window title with count
        if self.checkpoint_jobs:
            self.setWindowTitle(f"Processing Recovery ({len(self.checkpoint_jobs)} jobs found)")
        else:
            self.setWindowTitle("Processing Recovery (No interrupted jobs)")
    
    def _on_selection_changed(self):
        """Handle table selection changes."""
        selected_rows = self.jobs_table.selectionModel().selectedRows()
        
        if selected_rows:
            row = selected_rows[0].row()
            if 0 <= row < len(self.checkpoint_jobs):
                self.selected_checkpoint = self.checkpoint_jobs[row]
                self._update_details()
                self._update_button_states()
            else:
                self.selected_checkpoint = None
                self._clear_details()
                self._update_button_states()
        else:
            self.selected_checkpoint = None
            self._clear_details()
            self._update_button_states()
    
    def _update_details(self):
        """Update the job details section."""
        if not self.selected_checkpoint:
            self._clear_details()
            return
        
        job = self.selected_checkpoint
        
        details = []
        details.append(f"Job Name: {job['job_name']}")
        details.append(f"Checkpoint File: {job['checkpoint_file']}")
        details.append(f"Status: {job['status']}")
        details.append(f"Progress: {job['completed_files']}/{job['total_files']} files ({job['progress_percent']:.1f}%)")
        details.append(f"Last Updated: {job['last_updated'].strftime('%Y-%m-%d %H:%M:%S')}")
        details.append("")
        
        # Configuration details
        config = job.get("config", {})
        if config:
            details.append("Configuration:")
            details.append(f"  • Transcription: {'Yes' if config.get('transcribe') else 'No'}")
            details.append(f"  • Summarization: {'Yes' if config.get('summarize') else 'No'}")
            details.append(f"  • MOC Generation: {'Yes' if config.get('create_moc') else 'No'}")
            if config.get("transcription_model"):
                details.append(f"  • Transcription Model: {config['transcription_model']}")
            details.append("")
        
        # File list (first few files)
        files = job.get("files", [])
        if files:
            details.append("Files to Process:")
            for i, file_path in enumerate(files[:5]):  # Show first 5 files
                filename = Path(file_path).name
                details.append(f"  • {filename}")
            
            if len(files) > 5:
                details.append(f"  ... and {len(files) - 5} more files")
        
        self.details_text.setText("\n".join(details))
    
    def _clear_details(self):
        """Clear the job details section."""
        self.details_text.setText("Select a job from the table above to view details.")
    
    def _update_button_states(self):
        """Update the state of action buttons based on selection."""
        has_selection = self.selected_checkpoint is not None
        
        if has_selection:
            status = self.selected_checkpoint["status"]
            
            # Resume button: enabled for interrupted/crashed jobs
            self.resume_btn.setEnabled(status in ["Interrupted", "Crashed"])
            
            # Restart button: enabled for any incomplete job
            self.restart_btn.setEnabled(status != "Running")
            
            # Delete button: enabled for any job except running
            self.delete_btn.setEnabled(status != "Running")
        else:
            self.resume_btn.setEnabled(False)
            self.restart_btn.setEnabled(False)
            self.delete_btn.setEnabled(False)
    
    def _select_action(self, action: str):
        """Handle action button clicks."""
        if not self.selected_checkpoint:
            return
        
        checkpoint_path = self.selected_checkpoint["checkpoint_file"]
        
        # Confirm destructive actions
        if action == "delete":
            reply = QMessageBox.question(
                self,
                "Confirm Deletion",
                f"Are you sure you want to delete this checkpoint?\n\n"
                f"Job: {self.selected_checkpoint['job_name']}\n"
                f"This action cannot be undone.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            
            if reply != QMessageBox.StandardButton.Yes:
                return
        
        elif action == "restart":
            reply = QMessageBox.question(
                self,
                "Confirm Restart",
                f"Are you sure you want to restart this job from the beginning?\n\n"
                f"Job: {self.selected_checkpoint['job_name']}\n"
                f"Progress: {self.selected_checkpoint['progress_percent']:.1f}% completed\n\n"
                f"This will discard all current progress.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            
            if reply != QMessageBox.StandardButton.Yes:
                return
        
        # Emit signal and close dialog
        self.recovery_action_selected.emit(action, checkpoint_path)
        self.accept()
    
    def closeEvent(self, event):
        """Handle dialog close event."""
        if hasattr(self, 'refresh_timer'):
            self.refresh_timer.stop()
        super().closeEvent(event)
    
    @staticmethod
    def check_for_checkpoints() -> bool:
        """
        Static method to quickly check if there are any recoverable checkpoints.
        Returns True if checkpoints are found, False otherwise.
        """
        try:
            # Quick check for checkpoint files
            checkpoint_locations = [
                Path.home() / ".cache" / "knowledge_chipper" / "checkpoints",
                Path("/tmp"),
                Path.cwd() / "output" / "checkpoints",
                Path.cwd() / "checkpoints",
                Path.cwd()  # For temp files
            ]
            
            for location in checkpoint_locations:
                if location.exists():
                    # Look for any checkpoint files
                    checkpoint_files = list(location.glob("*checkpoint*.json"))
                    checkpoint_files.extend(list(location.glob("kc_checkpoint_*.json")))
                    
                    if checkpoint_files:
                        return True
            
            return False
            
        except Exception as e:
            logger.warning(f"Error checking for checkpoints: {e}")
            return False


class CrashRecoveryManager:
    """Manager class for handling crash recovery operations."""
    
    def __init__(self, parent=None):
        self.parent = parent
        self.dialog = None
    
    def check_and_show_recovery_dialog(self) -> bool:
        """
        Check for recoverable checkpoints and show recovery dialog if found.
        Returns True if dialog was shown, False otherwise.
        """
        if CrashRecoveryDialog.check_for_checkpoints():
            self.show_recovery_dialog()
            return True
        return False
    
    def show_recovery_dialog(self):
        """Show the crash recovery dialog."""
        if self.dialog is None:
            self.dialog = CrashRecoveryDialog(self.parent)
            self.dialog.recovery_action_selected.connect(self._handle_recovery_action)
        
        self.dialog.exec()
    
    def _handle_recovery_action(self, action: str, checkpoint_path: str):
        """Handle recovery action selection."""
        try:
            if action == "delete":
                # Delete checkpoint file
                Path(checkpoint_path).unlink()
                logger.info(f"Deleted checkpoint: {checkpoint_path}")
                
                QMessageBox.information(
                    self.parent,
                    "Checkpoint Deleted",
                    "The checkpoint has been deleted successfully."
                )
            
            elif action == "restart":
                # Delete checkpoint and restart
                Path(checkpoint_path).unlink()
                logger.info(f"Deleted checkpoint for restart: {checkpoint_path}")
                
                # Load the checkpoint data to get job configuration
                # This would need to be implemented to actually restart the job
                # For now, just show a message
                QMessageBox.information(
                    self.parent,
                    "Job Restart",
                    "The checkpoint has been cleared. You can now start a new job with the same configuration."
                )
            
            elif action == "resume":
                # Resume processing from checkpoint
                logger.info(f"Resuming from checkpoint: {checkpoint_path}")
                
                # This would need to be implemented to actually resume the job
                # For now, just show a message
                QMessageBox.information(
                    self.parent,
                    "Job Resume",
                    "Job resumption is not yet implemented in this version. The checkpoint has been preserved."
                )
            
        except Exception as e:
            logger.error(f"Error handling recovery action {action}: {e}")
            QMessageBox.critical(
                self.parent,
                "Recovery Error",
                f"Failed to {action} checkpoint:\n{str(e)}"
            )
