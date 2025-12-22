"""
Extract Tab for Knowledge System GUI (PyQt6).

Provides the claims-first extraction interface with:
- URL input (single URL or playlist)
- LLM selection for mining and evaluation stages
- Multi-stage progress display
- Two-pane results editor (list on left, details on right)
- Quality assessment with Whisper fallback option
"""

from pathlib import Path
from typing import Any, Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QComboBox,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ...logger import get_logger
from ..components.enhanced_progress_display import PipelineProgressDisplay
from ..workers.processing_workers import ClaimsFirstWorker

logger = get_logger(__name__)


# LLM provider and model options
LLM_PROVIDERS = {
    "openai": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"],
    "anthropic": ["claude-3-5-sonnet-20241022", "claude-3-opus-20240229", "claude-3-haiku-20240307"],
    "google": ["gemini-2.0-flash", "gemini-1.5-pro", "gemini-1.5-flash"],
    "ollama": ["llama3.1", "llama3", "mistral", "mixtral"],
}


class ClaimItem(QListWidgetItem):
    """Custom list item for claims with data storage."""

    def __init__(self, claim_data: dict[str, Any], is_rejected: bool = False):
        super().__init__()
        self.claim_data = claim_data
        self.is_rejected = is_rejected
        self.update_display()

    def update_display(self):
        """Update the display text based on claim data."""
        tier = self.claim_data.get("tier", "C")
        text = self.claim_data.get("claim_text", self.claim_data.get("canonical", ""))[:80]
        importance = self.claim_data.get("importance", 0)
        
        if self.is_rejected:
            self.setText(f"❌ [{tier}] {text}...")
        else:
            self.setText(f"[{tier}:{importance:.0f}] {text}...")


class EntityItem(QListWidgetItem):
    """Custom list item for jargon/people/concepts with data storage."""

    def __init__(self, entity_type: str, entity_data: dict[str, Any]):
        super().__init__()
        self.entity_type = entity_type
        self.entity_data = entity_data
        self.update_display()

    def update_display(self):
        """Update the display text based on entity type."""
        if self.entity_type == "jargon":
            term = self.entity_data.get("term", "Unknown")
            self.setText(f"📖 {term}")
        elif self.entity_type == "person":
            name = self.entity_data.get("name", "Unknown")
            self.setText(f"👤 {name}")
        elif self.entity_type == "concept":
            name = self.entity_data.get("name", self.entity_data.get("term", "Unknown"))
            self.setText(f"💡 {name}")
        else:
            self.setText(str(self.entity_data))


class ExtractTab(QWidget):
    """Tab for claims-first extraction with two-pane editor."""

    status_update = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

        # State
        self.worker: Optional[ClaimsFirstWorker] = None
        self.current_results: list[dict] = []
        self.current_episode_index = 0
        
        self.setup_ui()

    def setup_ui(self):
        """Set up the user interface."""
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(10, 10, 10, 10)

        # Header
        header = QLabel("Claims-First Extraction")
        header.setStyleSheet("font-size: 18px; font-weight: bold; color: #2c3e50;")
        layout.addWidget(header)

        # URL Input section
        url_group = QGroupBox("Source URL")
        url_layout = QHBoxLayout(url_group)
        
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("Enter YouTube URL or playlist URL...")
        self.url_input.returnPressed.connect(self.start_extraction)
        url_layout.addWidget(self.url_input, 1)
        
        self.extract_btn = QPushButton("🚀 Extract")
        self.extract_btn.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                border: none;
                padding: 8px 20px;
                border-radius: 4px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #2ecc71;
            }
            QPushButton:disabled {
                background-color: #95a5a6;
            }
        """)
        self.extract_btn.clicked.connect(self.start_extraction)
        url_layout.addWidget(self.extract_btn)
        
        self.whisper_btn = QPushButton("🔄 Re-run with Whisper")
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
        self.whisper_btn.clicked.connect(self.request_whisper_fallback)
        self.whisper_btn.hide()
        url_layout.addWidget(self.whisper_btn)
        
        layout.addWidget(url_group)

        # LLM Settings section
        llm_group = QGroupBox("LLM Settings")
        llm_layout = QHBoxLayout(llm_group)
        
        # Stage 1: Miner
        llm_layout.addWidget(QLabel("Stage 1 (Miner):"))
        self.miner_provider = QComboBox()
        self.miner_provider.addItems(LLM_PROVIDERS.keys())
        self.miner_provider.currentTextChanged.connect(self._update_miner_models)
        llm_layout.addWidget(self.miner_provider)
        
        self.miner_model = QComboBox()
        self._update_miner_models(self.miner_provider.currentText())
        llm_layout.addWidget(self.miner_model)
        
        llm_layout.addSpacing(20)
        
        # Stage 2: Evaluator
        llm_layout.addWidget(QLabel("Stage 2 (Evaluator):"))
        self.evaluator_provider = QComboBox()
        self.evaluator_provider.addItems(LLM_PROVIDERS.keys())
        self.evaluator_provider.currentTextChanged.connect(self._update_evaluator_models)
        llm_layout.addWidget(self.evaluator_provider)
        
        self.evaluator_model = QComboBox()
        self._update_evaluator_models(self.evaluator_provider.currentText())
        llm_layout.addWidget(self.evaluator_model)
        
        llm_layout.addStretch()
        layout.addWidget(llm_group)

        # Progress display
        self.progress_display = PipelineProgressDisplay()
        self.progress_display.cancellation_requested.connect(self.cancel_extraction)
        self.progress_display.pause_requested.connect(self.pause_extraction)
        self.progress_display.resume_requested.connect(self.resume_extraction)
        self.progress_display.whisper_fallback_requested.connect(self.request_whisper_fallback)
        layout.addWidget(self.progress_display)

        # Quality assessment panel
        self.quality_panel = QFrame()
        self.quality_panel.setStyleSheet("""
            QFrame {
                background-color: #f8f9fa;
                border: 1px solid #dee2e6;
                border-radius: 6px;
                padding: 8px;
            }
        """)
        quality_layout = QHBoxLayout(self.quality_panel)
        
        self.quality_status = QLabel("Status: --")
        self.quality_status.setStyleSheet("font-weight: bold;")
        quality_layout.addWidget(self.quality_status)
        
        self.acceptance_label = QLabel("Acceptance: --")
        quality_layout.addWidget(self.acceptance_label)
        
        self.transcript_quality_label = QLabel("Transcript: --")
        quality_layout.addWidget(self.transcript_quality_label)
        
        self.suggestion_label = QLabel("")
        self.suggestion_label.setStyleSheet("color: #e67e22; font-style: italic;")
        quality_layout.addWidget(self.suggestion_label)
        
        quality_layout.addStretch()
        self.quality_panel.hide()
        layout.addWidget(self.quality_panel)

        # Main content area: Two-pane splitter
        content_splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Left pane: Results tabs
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        self.results_tabs = QTabWidget()
        
        # Claims tab
        self.claims_list = QListWidget()
        self.claims_list.itemClicked.connect(self._on_claim_selected)
        self.results_tabs.addTab(self.claims_list, "Claims")
        
        # Jargon tab
        self.jargon_list = QListWidget()
        self.jargon_list.itemClicked.connect(self._on_entity_selected)
        self.results_tabs.addTab(self.jargon_list, "Jargon")
        
        # People tab
        self.people_list = QListWidget()
        self.people_list.itemClicked.connect(self._on_entity_selected)
        self.results_tabs.addTab(self.people_list, "People")
        
        # Concepts tab
        self.concepts_list = QListWidget()
        self.concepts_list.itemClicked.connect(self._on_entity_selected)
        self.results_tabs.addTab(self.concepts_list, "Concepts")
        
        # Rejected tab
        self.rejected_list = QListWidget()
        self.rejected_list.itemClicked.connect(self._on_rejected_selected)
        self.results_tabs.addTab(self.rejected_list, "Rejected")
        
        left_layout.addWidget(self.results_tabs)
        content_splitter.addWidget(left_widget)
        
        # Right pane: Detail editor
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        
        detail_header = QLabel("Selected Item Details")
        detail_header.setStyleSheet("font-weight: bold; font-size: 14px;")
        right_layout.addWidget(detail_header)
        
        # Claim text editor
        right_layout.addWidget(QLabel("Claim Text:"))
        self.claim_text_edit = QTextEdit()
        self.claim_text_edit.setMaximumHeight(80)
        right_layout.addWidget(self.claim_text_edit)
        
        # Evidence editor
        right_layout.addWidget(QLabel("Evidence:"))
        self.evidence_edit = QTextEdit()
        self.evidence_edit.setMaximumHeight(60)
        right_layout.addWidget(self.evidence_edit)
        
        # Tier and importance row
        tier_row = QHBoxLayout()
        tier_row.addWidget(QLabel("Tier:"))
        self.tier_combo = QComboBox()
        self.tier_combo.addItems(["A", "B", "C", "D"])
        tier_row.addWidget(self.tier_combo)
        
        tier_row.addWidget(QLabel("Importance:"))
        self.importance_edit = QLineEdit()
        self.importance_edit.setMaximumWidth(50)
        tier_row.addWidget(self.importance_edit)
        tier_row.addStretch()
        right_layout.addLayout(tier_row)
        
        # Speaker editor
        speaker_row = QHBoxLayout()
        speaker_row.addWidget(QLabel("Speaker:"))
        self.speaker_edit = QLineEdit()
        speaker_row.addWidget(self.speaker_edit)
        right_layout.addLayout(speaker_row)
        
        # Timestamp row
        timestamp_row = QHBoxLayout()
        timestamp_row.addWidget(QLabel("Timestamp:"))
        self.timestamp_start_edit = QLineEdit()
        self.timestamp_start_edit.setMaximumWidth(80)
        self.timestamp_start_edit.setPlaceholderText("Start")
        timestamp_row.addWidget(self.timestamp_start_edit)
        timestamp_row.addWidget(QLabel("to"))
        self.timestamp_end_edit = QLineEdit()
        self.timestamp_end_edit.setMaximumWidth(80)
        self.timestamp_end_edit.setPlaceholderText("End")
        timestamp_row.addWidget(self.timestamp_end_edit)
        timestamp_row.addStretch()
        right_layout.addLayout(timestamp_row)
        
        # Action buttons
        btn_row = QHBoxLayout()
        
        self.save_item_btn = QPushButton("💾 Save")
        self.save_item_btn.clicked.connect(self._save_current_item)
        self.save_item_btn.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #2ecc71;
            }
        """)
        btn_row.addWidget(self.save_item_btn)
        
        self.revert_btn = QPushButton("↩ Revert")
        self.revert_btn.clicked.connect(self._revert_current_item)
        btn_row.addWidget(self.revert_btn)
        
        self.delete_btn = QPushButton("🗑 Delete")
        self.delete_btn.clicked.connect(self._delete_current_item)
        self.delete_btn.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #c0392b;
            }
        """)
        btn_row.addWidget(self.delete_btn)
        
        self.promote_btn = QPushButton("⬆ Promote")
        self.promote_btn.clicked.connect(self._promote_rejected_claim)
        self.promote_btn.setStyleSheet("""
            QPushButton {
                background-color: #9b59b6;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #8e44ad;
            }
        """)
        self.promote_btn.hide()
        btn_row.addWidget(self.promote_btn)
        
        btn_row.addStretch()
        right_layout.addLayout(btn_row)
        
        right_layout.addStretch()
        content_splitter.addWidget(right_widget)
        
        # Set splitter proportions
        content_splitter.setSizes([400, 300])
        layout.addWidget(content_splitter, 1)

    def _update_miner_models(self, provider: str):
        """Update miner model dropdown based on provider."""
        self.miner_model.clear()
        self.miner_model.addItems(LLM_PROVIDERS.get(provider, []))

    def _update_evaluator_models(self, provider: str):
        """Update evaluator model dropdown based on provider."""
        self.evaluator_model.clear()
        self.evaluator_model.addItems(LLM_PROVIDERS.get(provider, []))

    def start_extraction(self):
        """Start the claims-first extraction pipeline."""
        url = self.url_input.text().strip()
        if not url:
            QMessageBox.warning(self, "No URL", "Please enter a YouTube URL or playlist URL.")
            return
        
        # Parse URL(s)
        urls = [url]  # For now, single URL. Playlist parsing would go here.
        
        # Disable controls
        self.extract_btn.setEnabled(False)
        self.url_input.setEnabled(False)
        
        # Clear previous results
        self.claims_list.clear()
        self.jargon_list.clear()
        self.people_list.clear()
        self.concepts_list.clear()
        self.rejected_list.clear()
        self.current_results = []
        
        # Create worker
        self.worker = ClaimsFirstWorker(
            urls=urls,
            miner_provider=self.miner_provider.currentText(),
            miner_model=self.miner_model.currentText(),
            evaluator_provider=self.evaluator_provider.currentText(),
            evaluator_model=self.evaluator_model.currentText(),
        )
        
        # Connect signals
        self.worker.batch_started.connect(self._on_batch_started)
        self.worker.episode_started.connect(self._on_episode_started)
        self.worker.stage_started.connect(self._on_stage_started)
        self.worker.stage_progress.connect(self._on_stage_progress)
        self.worker.stage_completed.connect(self._on_stage_completed)
        self.worker.episode_completed.connect(self._on_episode_completed)
        self.worker.episode_quality_warning.connect(self._on_quality_warning)
        self.worker.batch_completed.connect(self._on_batch_completed)
        self.worker.result_ready.connect(self._on_result_ready)
        self.worker.error_signal.connect(self._on_error)
        
        # Start
        self.progress_display.start_batch(len(urls))
        self.worker.start()
        
        self.status_update.emit("Extraction started...")

    def cancel_extraction(self):
        """Cancel the extraction process."""
        if self.worker:
            self.worker.cancel()
            self.status_update.emit("Cancelling...")

    def pause_extraction(self):
        """Pause the extraction process."""
        if self.worker:
            self.worker.pause()
            self.status_update.emit("Paused")

    def resume_extraction(self):
        """Resume the extraction process."""
        if self.worker:
            self.worker.resume()
            self.status_update.emit("Resumed")

    def request_whisper_fallback(self):
        """Request re-extraction with Whisper transcription."""
        if self.worker and self.current_episode_index >= 0:
            self.worker.request_whisper_fallback(self.current_episode_index)
            self.status_update.emit("Whisper fallback requested")

    # Signal handlers
    def _on_batch_started(self, total: int):
        """Handle batch start."""
        logger.info(f"Batch started: {total} episodes")

    def _on_episode_started(self, index: int, title: str):
        """Handle episode start."""
        self.current_episode_index = index
        self.progress_display.start_episode(index, title)

    def _on_stage_started(self, stage_id: str, stage_name: str):
        """Handle stage start."""
        self.progress_display.update_stage(stage_id, 0, f"{stage_name}...")

    def _on_stage_progress(self, stage_id: str, progress: int, status: str):
        """Handle stage progress update."""
        self.progress_display.update_stage(stage_id, progress, status)

    def _on_stage_completed(self, stage_id: str):
        """Handle stage completion."""
        self.progress_display.complete_stage(stage_id)

    def _on_episode_completed(self, index: int, success: bool, summary: dict):
        """Handle episode completion."""
        self.progress_display.complete_episode(success)
        
        if success:
            # Update quality panel
            self.quality_panel.show()
            status = summary.get("quality_status", "Unknown")
            self.quality_status.setText(f"Status: {status}")
            
            acceptance = summary.get("acceptance_rate", 0)
            self.acceptance_label.setText(f"Acceptance: {acceptance:.1%}")
            
            quality = summary.get("transcript_quality", 0)
            self.transcript_quality_label.setText(f"Transcript: {quality:.2f}")

    def _on_quality_warning(self, index: int, suggestion: str):
        """Handle quality warning."""
        self.suggestion_label.setText(suggestion)
        self.whisper_btn.show()
        self.progress_display.show_quality_warning(suggestion)

    def _on_batch_completed(self, success: int, failure: int):
        """Handle batch completion."""
        self.progress_display.complete_batch(success, failure)
        
        # Re-enable controls
        self.extract_btn.setEnabled(True)
        self.url_input.setEnabled(True)
        
        self.status_update.emit(f"Complete: {success} succeeded, {failure} failed")

    def _on_result_ready(self, result: dict):
        """Handle result data from worker."""
        self.current_results.append(result)
        
        # Populate claims list
        for claim_data in result.get("claims", []):
            item = ClaimItem(claim_data, is_rejected=False)
            self.claims_list.addItem(item)
        
        # Populate rejected list
        for claim_data in result.get("rejected_claims", []):
            item = ClaimItem(claim_data, is_rejected=True)
            self.rejected_list.addItem(item)
        
        # Populate jargon
        for jargon in result.get("jargon", []):
            item = EntityItem("jargon", jargon)
            self.jargon_list.addItem(item)
        
        # Populate people
        for person in result.get("people", []):
            item = EntityItem("person", person)
            self.people_list.addItem(item)
        
        # Populate concepts
        for concept in result.get("concepts", []):
            item = EntityItem("concept", concept)
            self.concepts_list.addItem(item)

    def _on_error(self, error: str):
        """Handle error from worker."""
        logger.error(f"Extraction error: {error}")
        self.status_update.emit(f"Error: {error}")
        QMessageBox.warning(self, "Extraction Error", error)

    # Item selection handlers
    def _on_claim_selected(self, item: ClaimItem):
        """Handle claim selection."""
        self.promote_btn.hide()
        self.delete_btn.show()
        
        data = item.claim_data
        self.claim_text_edit.setText(data.get("claim_text", data.get("canonical", "")))
        self.evidence_edit.setText(data.get("evidence", data.get("evidence_quote", "")))
        self.tier_combo.setCurrentText(data.get("tier", "C"))
        self.importance_edit.setText(str(data.get("importance", 0)))
        self.speaker_edit.setText(data.get("speaker", "") or "")
        
        ts_start = data.get("timestamp_start")
        ts_end = data.get("timestamp_end")
        self.timestamp_start_edit.setText(str(ts_start) if ts_start else "")
        self.timestamp_end_edit.setText(str(ts_end) if ts_end else "")

    def _on_rejected_selected(self, item: ClaimItem):
        """Handle rejected claim selection."""
        self.promote_btn.show()
        self.delete_btn.hide()
        
        data = item.claim_data
        self.claim_text_edit.setText(data.get("claim_text", data.get("canonical", "")))
        self.evidence_edit.setText(data.get("evidence", data.get("evidence_quote", "")))
        self.tier_combo.setCurrentText(data.get("tier", "C"))
        self.importance_edit.setText(str(data.get("importance", 0)))
        self.speaker_edit.setText(data.get("speaker", "") or "")
        self.timestamp_start_edit.setText("")
        self.timestamp_end_edit.setText("")

    def _on_entity_selected(self, item: EntityItem):
        """Handle entity selection."""
        self.promote_btn.hide()
        self.delete_btn.show()
        
        data = item.entity_data
        entity_type = item.entity_type
        
        if entity_type == "jargon":
            self.claim_text_edit.setText(data.get("term", ""))
            self.evidence_edit.setText(data.get("definition", data.get("description", "")))
        elif entity_type == "person":
            self.claim_text_edit.setText(data.get("name", ""))
            self.evidence_edit.setText(data.get("context", data.get("description", "")))
        elif entity_type == "concept":
            self.claim_text_edit.setText(data.get("name", data.get("term", "")))
            self.evidence_edit.setText(data.get("description", ""))
        
        # Clear claim-specific fields
        self.tier_combo.setCurrentText("C")
        self.importance_edit.setText("")
        self.speaker_edit.setText("")
        self.timestamp_start_edit.setText("")
        self.timestamp_end_edit.setText("")

    # Action handlers
    def _save_current_item(self):
        """Save changes to the currently selected item."""
        current_tab = self.results_tabs.currentIndex()
        
        if current_tab == 0:  # Claims
            item = self.claims_list.currentItem()
            if item and isinstance(item, ClaimItem):
                item.claim_data["claim_text"] = self.claim_text_edit.toPlainText()
                item.claim_data["evidence"] = self.evidence_edit.toPlainText()
                item.claim_data["tier"] = self.tier_combo.currentText()
                try:
                    item.claim_data["importance"] = float(self.importance_edit.text())
                except ValueError:
                    pass
                item.claim_data["speaker"] = self.speaker_edit.text()
                item.update_display()
                self.status_update.emit("Claim saved")
        
        elif current_tab == 4:  # Rejected
            item = self.rejected_list.currentItem()
            if item and isinstance(item, ClaimItem):
                item.claim_data["claim_text"] = self.claim_text_edit.toPlainText()
                item.claim_data["evidence"] = self.evidence_edit.toPlainText()
                item.update_display()
                self.status_update.emit("Rejected claim saved")
        
        else:  # Entity tabs
            lists = [None, self.jargon_list, self.people_list, self.concepts_list]
            if current_tab < len(lists) and lists[current_tab]:
                item = lists[current_tab].currentItem()
                if item and isinstance(item, EntityItem):
                    if item.entity_type == "jargon":
                        item.entity_data["term"] = self.claim_text_edit.toPlainText()
                        item.entity_data["definition"] = self.evidence_edit.toPlainText()
                    elif item.entity_type == "person":
                        item.entity_data["name"] = self.claim_text_edit.toPlainText()
                        item.entity_data["context"] = self.evidence_edit.toPlainText()
                    elif item.entity_type == "concept":
                        item.entity_data["name"] = self.claim_text_edit.toPlainText()
                        item.entity_data["description"] = self.evidence_edit.toPlainText()
                    item.update_display()
                    self.status_update.emit("Entity saved")

    def _revert_current_item(self):
        """Revert changes to the currently selected item."""
        current_tab = self.results_tabs.currentIndex()
        
        if current_tab == 0:
            item = self.claims_list.currentItem()
            if item:
                self._on_claim_selected(item)
        elif current_tab == 4:
            item = self.rejected_list.currentItem()
            if item:
                self._on_rejected_selected(item)
        else:
            lists = [None, self.jargon_list, self.people_list, self.concepts_list]
            if current_tab < len(lists) and lists[current_tab]:
                item = lists[current_tab].currentItem()
                if item:
                    self._on_entity_selected(item)
        
        self.status_update.emit("Changes reverted")

    def _delete_current_item(self):
        """Delete the currently selected item."""
        current_tab = self.results_tabs.currentIndex()
        
        if current_tab == 0:
            row = self.claims_list.currentRow()
            if row >= 0:
                self.claims_list.takeItem(row)
                self.status_update.emit("Claim deleted")
        elif current_tab == 1:
            row = self.jargon_list.currentRow()
            if row >= 0:
                self.jargon_list.takeItem(row)
                self.status_update.emit("Jargon deleted")
        elif current_tab == 2:
            row = self.people_list.currentRow()
            if row >= 0:
                self.people_list.takeItem(row)
                self.status_update.emit("Person deleted")
        elif current_tab == 3:
            row = self.concepts_list.currentRow()
            if row >= 0:
                self.concepts_list.takeItem(row)
                self.status_update.emit("Concept deleted")

    def _promote_rejected_claim(self):
        """Promote a rejected claim back to accepted."""
        row = self.rejected_list.currentRow()
        if row < 0:
            return
        
        # Remove from rejected
        item = self.rejected_list.takeItem(row)
        if not isinstance(item, ClaimItem):
            return
        
        # Add to claims with updated data
        item.is_rejected = False
        item.update_display()
        self.claims_list.addItem(item)
        
        self.status_update.emit("Claim promoted to accepted")
        
        # Hide promote button since we moved it
        self.promote_btn.hide()
        self.delete_btn.show()

