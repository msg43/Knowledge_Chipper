"""
Import Transcripts Tab

GUI tab for importing PDF transcripts with automatic YouTube video matching.
"""

import asyncio
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QLineEdit,
    QCheckBox,
    QFileDialog,
    QTableWidget,
    QTableWidgetItem,
    QProgressBar,
    QTextEdit,
    QGroupBox,
    QHeaderView,
)

from ...database import DatabaseService
from ...logger import get_logger
from ...processors.pdf_transcript_processor import PDFTranscriptProcessor
from ...services.youtube_video_matcher import YouTubeVideoMatcher
from ...services.transcript_manager import TranscriptManager

logger = get_logger(__name__)


class ImportTranscriptWorker(QThread):
    """
    Background worker for PDF transcript import.
    """
    
    # Signals
    matching_started = pyqtSignal()
    matching_progress = pyqtSignal(int, int)  # current, total
    match_found = pyqtSignal(str, str, float)  # pdf_path, video_id, confidence
    match_failed = pyqtSignal(str, str)  # pdf_path, reason
    import_completed = pyqtSignal(dict)  # stats
    log_message = pyqtSignal(str)  # log message
    
    def __init__(
        self,
        pdf_files: list[Path],
        auto_match: bool = False,
        confidence_threshold: float = 0.8
    ):
        super().__init__()
        self.pdf_files = pdf_files
        self.auto_match = auto_match
        self.confidence_threshold = confidence_threshold
        
        self.db_service = DatabaseService()
        self.pdf_processor = PDFTranscriptProcessor(db_service=self.db_service)
        self.transcript_manager = TranscriptManager(db_service=self.db_service)
        
        if auto_match:
            self.video_matcher = YouTubeVideoMatcher(
                db_service=self.db_service,
                headless=True,
                confidence_threshold=confidence_threshold
            )
        else:
            self.video_matcher = None
    
    def run(self):
        """Run import process."""
        try:
            self.matching_started.emit()
            
            stats = {
                "total": len(self.pdf_files),
                "imported": 0,
                "failed": 0,
                "matched": 0,
                "unmatched": 0,
            }
            
            for i, pdf_file in enumerate(self.pdf_files):
                self.matching_progress.emit(i + 1, len(self.pdf_files))
                self.log_message.emit(f"Processing: {pdf_file.name}")
                
                try:
                    # Process PDF
                    result = self.pdf_processor.process(pdf_file)
                    
                    if not result.success:
                        self.log_message.emit(f"❌ Failed: {result.errors}")
                        self.match_failed.emit(str(pdf_file), str(result.errors))
                        stats["failed"] += 1
                        continue
                    
                    source_id = result.data["source_id"]
                    pdf_metadata = result.data["metadata"]
                    
                    # Try auto-match if enabled
                    if self.auto_match and self.video_matcher:
                        self.log_message.emit("🔍 Searching for YouTube match...")
                        
                        pdf_text_preview = result.data["text"][:2000]
                        
                        # Run async matching in sync context
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        video_id, confidence, method = loop.run_until_complete(
                            self.video_matcher.find_youtube_video(
                                pdf_metadata,
                                pdf_text_preview
                            )
                        )
                        loop.close()
                        
                        if video_id and confidence >= self.confidence_threshold:
                            self.log_message.emit(
                                f"✅ Matched: {video_id} (confidence: {confidence:.2f})"
                            )
                            self.match_found.emit(str(pdf_file), video_id, confidence)
                            stats["matched"] += 1
                        else:
                            self.log_message.emit("❌ No match found")
                            stats["unmatched"] += 1
                    
                    stats["imported"] += 1
                    self.log_message.emit(
                        f"✅ Imported: {pdf_file.name} (quality: {result.data['quality_score']:.2f})"
                    )
                
                except Exception as e:
                    logger.error(f"Failed to process {pdf_file.name}: {e}")
                    self.log_message.emit(f"❌ Error: {str(e)}")
                    self.match_failed.emit(str(pdf_file), str(e))
                    stats["failed"] += 1
            
            self.import_completed.emit(stats)
        
        except Exception as e:
            logger.error(f"Worker thread failed: {e}")
            self.log_message.emit(f"❌ Worker error: {str(e)}")


class ImportTranscriptsTab(QWidget):
    """Import Transcripts tab for PDF transcript import."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.db_service = DatabaseService()
        self.worker: Optional[ImportTranscriptWorker] = None
        self.init_ui()
    
    def init_ui(self):
        """Initialize UI components."""
        layout = QVBoxLayout()
        
        # Title
        title = QLabel("Import PDF Transcripts")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(title)
        
        # Single PDF Import section
        single_group = self._create_single_import_section()
        layout.addWidget(single_group)
        
        # Batch Import section
        batch_group = self._create_batch_import_section()
        layout.addWidget(batch_group)
        
        # Results section
        results_group = self._create_results_section()
        layout.addWidget(results_group)
        
        # Progress section
        progress_group = self._create_progress_section()
        layout.addWidget(progress_group)
        
        layout.addStretch()
        self.setLayout(layout)
    
    def _create_single_import_section(self) -> QGroupBox:
        """Create single PDF import section."""
        group = QGroupBox("Single PDF Import")
        layout = QVBoxLayout()
        
        # File selection
        file_layout = QHBoxLayout()
        self.file_path_edit = QLineEdit()
        self.file_path_edit.setPlaceholderText("Select PDF file...")
        browse_btn = QPushButton("Browse")
        browse_btn.clicked.connect(self.browse_single_file)
        file_layout.addWidget(self.file_path_edit)
        file_layout.addWidget(browse_btn)
        layout.addLayout(file_layout)
        
        # YouTube URL (optional)
        url_layout = QHBoxLayout()
        url_label = QLabel("YouTube URL (optional):")
        self.youtube_url_edit = QLineEdit()
        self.youtube_url_edit.setPlaceholderText("https://www.youtube.com/watch?v=...")
        url_layout.addWidget(url_label)
        url_layout.addWidget(self.youtube_url_edit)
        layout.addLayout(url_layout)
        
        # Auto-match checkbox
        self.auto_match_single = QCheckBox("Auto-match if URL not provided")
        self.auto_match_single.setChecked(True)
        layout.addWidget(self.auto_match_single)
        
        # Import button
        import_btn = QPushButton("Import PDF")
        import_btn.clicked.connect(self.import_single_pdf)
        layout.addWidget(import_btn)
        
        group.setLayout(layout)
        return group
    
    def _create_batch_import_section(self) -> QGroupBox:
        """Create batch import section."""
        group = QGroupBox("Batch Import")
        layout = QVBoxLayout()
        
        # Folder selection
        folder_layout = QHBoxLayout()
        self.folder_path_edit = QLineEdit()
        self.folder_path_edit.setPlaceholderText("Select folder containing PDFs...")
        browse_folder_btn = QPushButton("Browse Folder")
        browse_folder_btn.clicked.connect(self.browse_folder)
        folder_layout.addWidget(self.folder_path_edit)
        folder_layout.addWidget(browse_folder_btn)
        layout.addLayout(folder_layout)
        
        # Auto-match settings
        self.auto_match_batch = QCheckBox("Enable automatic YouTube matching")
        self.auto_match_batch.setChecked(True)
        layout.addWidget(self.auto_match_batch)
        
        # Confidence threshold
        threshold_layout = QHBoxLayout()
        threshold_label = QLabel("Confidence threshold:")
        self.confidence_threshold_edit = QLineEdit("0.8")
        self.confidence_threshold_edit.setMaximumWidth(100)
        threshold_layout.addWidget(threshold_label)
        threshold_layout.addWidget(self.confidence_threshold_edit)
        threshold_layout.addStretch()
        layout.addLayout(threshold_layout)
        
        # Scan button
        scan_btn = QPushButton("Scan Folder")
        scan_btn.clicked.connect(self.scan_folder)
        layout.addWidget(scan_btn)
        
        group.setLayout(layout)
        return group
    
    def _create_results_section(self) -> QGroupBox:
        """Create results display section."""
        group = QGroupBox("Matching Results")
        layout = QVBoxLayout()
        
        # Results table
        self.results_table = QTableWidget()
        self.results_table.setColumnCount(4)
        self.results_table.setHorizontalHeaderLabels([
            "PDF File", "Match Status", "Confidence", "Video ID"
        ])
        self.results_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.results_table)
        
        # Action buttons
        button_layout = QHBoxLayout()
        import_matched_btn = QPushButton("Import Matched")
        import_matched_btn.clicked.connect(self.import_matched)
        review_btn = QPushButton("Review Unmatched")
        review_btn.clicked.connect(self.review_unmatched)
        button_layout.addWidget(import_matched_btn)
        button_layout.addWidget(review_btn)
        button_layout.addStretch()
        layout.addLayout(button_layout)
        
        group.setLayout(layout)
        return group
    
    def _create_progress_section(self) -> QGroupBox:
        """Create progress display section."""
        group = QGroupBox("Progress")
        layout = QVBoxLayout()
        
        # Progress bar
        self.progress_bar = QProgressBar()
        layout.addWidget(self.progress_bar)
        
        # Log display
        self.log_display = QTextEdit()
        self.log_display.setReadOnly(True)
        self.log_display.setMaximumHeight(150)
        layout.addWidget(self.log_display)
        
        group.setLayout(layout)
        return group
    
    def browse_single_file(self):
        """Browse for single PDF file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select PDF Transcript",
            "",
            "PDF Files (*.pdf)"
        )
        if file_path:
            self.file_path_edit.setText(file_path)
    
    def browse_folder(self):
        """Browse for folder containing PDFs."""
        folder_path = QFileDialog.getExistingDirectory(
            self,
            "Select Folder Containing PDFs"
        )
        if folder_path:
            self.folder_path_edit.setText(folder_path)
    
    def import_single_pdf(self):
        """Import single PDF file."""
        file_path = self.file_path_edit.text()
        if not file_path:
            self.log_display.append("❌ Please select a PDF file")
            return
        
        youtube_url = self.youtube_url_edit.text() or None
        auto_match = self.auto_match_single.isChecked() and not youtube_url
        
        self.log_display.append(f"Importing: {Path(file_path).name}")
        
        # Start worker
        self.worker = ImportTranscriptWorker(
            [Path(file_path)],
            auto_match=auto_match,
            confidence_threshold=0.8
        )
        self.worker.log_message.connect(self.log_display.append)
        self.worker.import_completed.connect(self.on_import_completed)
        self.worker.start()
    
    def scan_folder(self):
        """Scan folder for PDFs and start import."""
        folder_path = self.folder_path_edit.text()
        if not folder_path:
            self.log_display.append("❌ Please select a folder")
            return
        
        folder = Path(folder_path)
        pdf_files = list(folder.glob("*.pdf"))
        
        if not pdf_files:
            self.log_display.append("❌ No PDF files found in folder")
            return
        
        self.log_display.append(f"Found {len(pdf_files)} PDF files")
        
        # Get settings
        auto_match = self.auto_match_batch.isChecked()
        try:
            confidence_threshold = float(self.confidence_threshold_edit.text())
        except ValueError:
            confidence_threshold = 0.8
        
        # Start worker
        self.worker = ImportTranscriptWorker(
            pdf_files,
            auto_match=auto_match,
            confidence_threshold=confidence_threshold
        )
        self.worker.matching_progress.connect(self.on_progress)
        self.worker.match_found.connect(self.on_match_found)
        self.worker.match_failed.connect(self.on_match_failed)
        self.worker.log_message.connect(self.log_display.append)
        self.worker.import_completed.connect(self.on_import_completed)
        self.worker.start()
    
    def on_progress(self, current: int, total: int):
        """Update progress bar."""
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(current)
    
    def on_match_found(self, pdf_path: str, video_id: str, confidence: float):
        """Handle successful match."""
        row = self.results_table.rowCount()
        self.results_table.insertRow(row)
        
        self.results_table.setItem(row, 0, QTableWidgetItem(Path(pdf_path).name))
        self.results_table.setItem(row, 1, QTableWidgetItem("✓ Matched"))
        self.results_table.setItem(row, 2, QTableWidgetItem(f"{confidence:.2f}"))
        self.results_table.setItem(row, 3, QTableWidgetItem(video_id))
    
    def on_match_failed(self, pdf_path: str, reason: str):
        """Handle failed match."""
        row = self.results_table.rowCount()
        self.results_table.insertRow(row)
        
        self.results_table.setItem(row, 0, QTableWidgetItem(Path(pdf_path).name))
        self.results_table.setItem(row, 1, QTableWidgetItem("✗ Failed"))
        self.results_table.setItem(row, 2, QTableWidgetItem("-"))
        self.results_table.setItem(row, 3, QTableWidgetItem(reason[:50]))
    
    def on_import_completed(self, stats: dict):
        """Handle import completion."""
        self.log_display.append("\n" + "="*60)
        self.log_display.append("IMPORT SUMMARY")
        self.log_display.append("="*60)
        self.log_display.append(f"Total PDFs:      {stats['total']}")
        self.log_display.append(f"Imported:        {stats['imported']}")
        self.log_display.append(f"Failed:          {stats['failed']}")
        self.log_display.append(f"Matched:         {stats['matched']}")
        self.log_display.append(f"Unmatched:       {stats['unmatched']}")
        self.log_display.append("="*60)
    
    def import_matched(self):
        """Import matched PDFs."""
        self.log_display.append("Import matched functionality not yet implemented")
    
    def review_unmatched(self):
        """Review unmatched PDFs."""
        self.log_display.append("Review unmatched functionality not yet implemented")

