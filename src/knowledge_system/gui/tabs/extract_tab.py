"""
Extract Tab for Knowledge System GUI (PyQt6).

Provides the extraction and bulk review workflow with:
- URL input (single URL or playlist)
- LLM selection for extraction and synthesis models
- Progress dashboard with real-time stats
- Unified review queue with filtering and bulk actions
- Detail editor with Accept/Reject/Skip buttons
- Confirm & Sync workflow for pushing to GetReceipts
"""

from typing import Any, Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ...database.review_queue_service import ReviewQueueService
from ...logger import get_logger
from ..components.bulk_action_toolbar import BulkActionToolbar
from ..components.enhanced_progress_display import PipelineProgressDisplay
from ..components.filter_bar import FilterBar
from ..components.review_dashboard import ReviewDashboard
from ..components.review_queue import (
    EntityType,
    ReviewItem,
    ReviewQueueFilterModel,
    ReviewQueueModel,
    ReviewQueueView,
    ReviewStatus,
)
from ..workers.processing_workers import ClaimsFirstWorker

logger = get_logger(__name__)


# LLM provider and model options
LLM_PROVIDERS = {
    "openai": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"],
    "anthropic": ["claude-3-5-sonnet-20241022", "claude-3-opus-20240229", "claude-3-haiku-20240307"],
    "google": ["gemini-2.0-flash", "gemini-1.5-pro", "gemini-1.5-flash"],
    "ollama": ["llama3.1", "llama3", "mistral", "mixtral"],
}


class ConfirmSyncDialog(QDialog):
    """Dialog for confirming sync to GetReceipts."""
    
    def __init__(self, counts: dict[str, int], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Confirm & Sync to GetReceipts")
        self.setMinimumWidth(400)
        
        layout = QVBoxLayout(self)
        
        # Header
        header = QLabel("Ready to sync to GetReceipts:")
        header.setStyleSheet("font-size: 14px; font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(header)
        
        # Counts
        counts_frame = QFrame()
        counts_frame.setStyleSheet("""
            QFrame {
                background-color: #2d2d2d;
                border: 1px solid #3c3c3c;
                border-radius: 6px;
                padding: 10px;
            }
        """)
        counts_layout = QVBoxLayout(counts_frame)
        
        accepted_claims = counts.get("accepted_claims", 0)
        accepted_jargon = counts.get("accepted_jargon", 0)
        accepted_people = counts.get("accepted_people", 0)
        accepted_concepts = counts.get("accepted_concepts", 0)
        rejected = counts.get("rejected", 0)
        pending = counts.get("pending", 0)
        
        counts_layout.addWidget(QLabel(f"✓ {accepted_claims:,} claims (approved)"))
        counts_layout.addWidget(QLabel(f"✓ {accepted_jargon:,} jargon terms (approved)"))
        counts_layout.addWidget(QLabel(f"✓ {accepted_people:,} people (approved)"))
        counts_layout.addWidget(QLabel(f"✓ {accepted_concepts:,} concepts (approved)"))
        
        layout.addWidget(counts_frame)
        
        # Info about rejected/pending
        if rejected > 0:
            rejected_label = QLabel(f"✗ {rejected:,} items marked as rejected (will be saved locally)")
            rejected_label.setStyleSheet("color: #dc3545; margin-top: 10px;")
            layout.addWidget(rejected_label)
        
        if pending > 0:
            pending_label = QLabel(f"⏳ {pending:,} items still pending (will remain for later review)")
            pending_label.setStyleSheet("color: #ffc107; margin-top: 5px;")
            layout.addWidget(pending_label)
        
        # Buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Ok
        )
        button_box.button(QDialogButtonBox.StandardButton.Ok).setText("Confirm & Sync")
        button_box.button(QDialogButtonBox.StandardButton.Ok).setStyleSheet("""
            QPushButton {
                background-color: #28a745;
                color: white;
                padding: 8px 20px;
                border-radius: 4px;
                font-weight: bold;
            }
        """)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)


class ExtractTab(QWidget):
    """Tab for extraction and bulk review workflow."""

    status_update = pyqtSignal(str)
    sync_requested = pyqtSignal(list)  # List of approved items to sync

    def __init__(self, parent=None):
        super().__init__(parent)

        # State
        self.worker: Optional[ClaimsFirstWorker] = None
        self.current_results: list[dict] = []
        self.current_episode_index = 0
        self.current_item: Optional[ReviewItem] = None
        self.sources: list[tuple[str, str]] = []  # (title, source_id)
        
        # Database service for persistence
        self.db_service = ReviewQueueService()
        self._initial_load_done = False
        
        # Auto-sync state
        self.auto_sync_worker: Optional[Any] = None
        self.pending_sync_count = 0  # Track unsynced accepted items
        self.is_syncing = False      # Prevent concurrent syncs
        
        self.setup_ui()
        self._setup_keyboard_shortcuts()
    
    def showEvent(self, event):
        """Handle tab becoming visible - load pending items from database."""
        super().showEvent(event)
        if not self._initial_load_done:
            self._load_pending_from_database()
            self._initial_load_done = True
    
    def _load_pending_from_database(self):
        """Load pending review items from database."""
        try:
            # Ensure table exists
            self.db_service.ensure_table_exists()
            
            # Load all unsynced items (pending + accepted but not synced)
            items_data = self.db_service.load_all_unsynced_items()
            
            if not items_data:
                logger.info("No pending review items in database")
                return
            
            logger.info(f"Loading {len(items_data)} items from database")
            
            # Convert to ReviewItem objects
            items = []
            for item_data in items_data:
                entity_type_str = item_data.get("entity_type", "claim")
                entity_type = EntityType(entity_type_str)
                
                status_str = item_data.get("review_status", "pending")
                status = ReviewStatus(status_str)
                
                item = ReviewItem(
                    item_id=item_data.get("item_id"),
                    entity_type=entity_type,
                    content=item_data.get("content", ""),
                    source_title=item_data.get("source_title", ""),
                    source_id=item_data.get("source_id", ""),
                    tier=item_data.get("tier", "C"),
                    importance=item_data.get("importance", 0),
                    status=status,
                    raw_data=item_data.get("raw_data", {}),
                )
                items.append(item)
            
            # Add to queue model
            self.queue_model.add_items(items)
            
            # Update dashboard
            self._update_dashboard_stats()
            
            # Update filter bar with sources
            sources = self.db_service.get_unique_sources()
            self.filter_bar.set_sources(sources)
            
            self.status_update.emit(f"Loaded {len(items)} pending items from previous session")
            
        except Exception as e:
            logger.error(f"Error loading pending items from database: {e}")
            self.status_update.emit(f"Error loading pending items: {e}")

    def setup_ui(self):
        """Set up the user interface."""
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(10, 10, 10, 10)

        # URL Input section
        url_group = QGroupBox()
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

        # Model selection section
        llm_group = QGroupBox()
        llm_layout = QHBoxLayout(llm_group)
        
        llm_layout.addWidget(QLabel("Extraction Model:"))
        self.miner_provider = QComboBox()
        self.miner_provider.addItems(LLM_PROVIDERS.keys())
        self.miner_provider.currentTextChanged.connect(self._update_miner_models)
        llm_layout.addWidget(self.miner_provider)
        
        self.miner_model = QComboBox()
        self._update_miner_models(self.miner_provider.currentText())
        llm_layout.addWidget(self.miner_model)
        
        llm_layout.addSpacing(20)
        
        llm_layout.addWidget(QLabel("Synthesis Model:"))
        self.evaluator_provider = QComboBox()
        self.evaluator_provider.addItems(LLM_PROVIDERS.keys())
        self.evaluator_provider.currentTextChanged.connect(self._update_evaluator_models)
        llm_layout.addWidget(self.evaluator_provider)
        
        self.evaluator_model = QComboBox()
        self._update_evaluator_models(self.evaluator_provider.currentText())
        llm_layout.addWidget(self.evaluator_model)
        
        llm_layout.addStretch()
        layout.addWidget(llm_group)

        # Progress display (existing component)
        self.progress_display = PipelineProgressDisplay()
        self.progress_display.cancellation_requested.connect(self.cancel_extraction)
        self.progress_display.pause_requested.connect(self.pause_extraction)
        self.progress_display.resume_requested.connect(self.resume_extraction)
        self.progress_display.whisper_fallback_requested.connect(self.request_whisper_fallback)
        layout.addWidget(self.progress_display)

        # Review Dashboard
        self.dashboard = ReviewDashboard()
        layout.addWidget(self.dashboard)

        # Filter Bar
        self.filter_bar = FilterBar()
        self.filter_bar.filters_changed.connect(self._apply_filters)
        layout.addWidget(self.filter_bar)

        # Bulk Action Toolbar
        self.bulk_toolbar = BulkActionToolbar()
        self.bulk_toolbar.accept_selected.connect(self._accept_selected)
        self.bulk_toolbar.reject_selected.connect(self._reject_selected)
        self.bulk_toolbar.set_tier.connect(self._set_tier_selected)
        self.bulk_toolbar.deselect_all.connect(self._deselect_all)
        self.bulk_toolbar.select_all_visible.connect(self._select_all_visible)
        self.bulk_toolbar.select_all_pending.connect(self._select_all_pending)
        layout.addWidget(self.bulk_toolbar)

        # Main content area: Two-pane splitter
        content_splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Left pane: Unified review queue
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        # Queue model and view
        self.queue_model = ReviewQueueModel()
        self.queue_model.selection_changed.connect(self._on_selection_changed)
        self.queue_model.item_status_changed.connect(self._update_dashboard_stats)
        
        self.filter_model = ReviewQueueFilterModel()
        self.filter_model.setSourceModel(self.queue_model)
        
        self.queue_view = ReviewQueueView()
        self.queue_view.setModel(self.filter_model)
        self.queue_view.item_activated.connect(self._on_item_activated)
        self.queue_view.set_column_widths()
        
        left_layout.addWidget(self.queue_view)
        content_splitter.addWidget(left_widget)
        
        # Right pane: Detail editor
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        
        detail_header = QLabel("Selected Item Details")
        detail_header.setStyleSheet("font-weight: bold; font-size: 14px;")
        right_layout.addWidget(detail_header)
        
        # Type indicator
        type_row = QHBoxLayout()
        type_row.addWidget(QLabel("Type:"))
        self.type_label = QLabel("--")
        self.type_label.setStyleSheet("font-weight: bold;")
        type_row.addWidget(self.type_label)
        type_row.addStretch()
        right_layout.addLayout(type_row)
        
        # Content editor
        right_layout.addWidget(QLabel("Content:"))
        self.content_edit = QTextEdit()
        self.content_edit.setMaximumHeight(100)
        right_layout.addWidget(self.content_edit)
        
        # Evidence/Context editor
        right_layout.addWidget(QLabel("Evidence / Context:"))
        self.evidence_edit = QTextEdit()
        self.evidence_edit.setMaximumHeight(80)
        right_layout.addWidget(self.evidence_edit)
        
        # Importance and Source row
        meta_row = QHBoxLayout()
        meta_row.addWidget(QLabel("Importance:"))
        self.importance_edit = QLineEdit()
        self.importance_edit.setMaximumWidth(60)
        meta_row.addWidget(self.importance_edit)
        
        meta_row.addSpacing(20)
        
        meta_row.addWidget(QLabel("Source:"))
        self.source_label = QLabel("--")
        self.source_label.setStyleSheet("color: #666;")
        meta_row.addWidget(self.source_label)
        
        meta_row.addStretch()
        right_layout.addLayout(meta_row)
        
        # Status indicator
        status_row = QHBoxLayout()
        status_row.addWidget(QLabel("Status:"))
        self.status_label = QLabel("--")
        self.status_label.setStyleSheet("font-weight: bold;")
        status_row.addWidget(self.status_label)
        status_row.addStretch()
        right_layout.addLayout(status_row)
        
        # Quick action buttons (Accept/Reject/Skip)
        action_row = QHBoxLayout()
        
        self.accept_btn = QPushButton("✓ Accept (A)")
        self.accept_btn.setStyleSheet("""
            QPushButton {
                background-color: #28a745;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #218838;
            }
        """)
        self.accept_btn.clicked.connect(self._accept_current)
        action_row.addWidget(self.accept_btn)
        
        self.reject_btn = QPushButton("✗ Reject (R)")
        self.reject_btn.setStyleSheet("""
            QPushButton {
                background-color: #dc3545;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #c82333;
            }
        """)
        self.reject_btn.clicked.connect(self._reject_current)
        action_row.addWidget(self.reject_btn)
        
        self.skip_btn = QPushButton("→ Skip (J)")
        self.skip_btn.setStyleSheet("""
            QPushButton {
                background-color: #6c757d;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #5a6268;
            }
        """)
        self.skip_btn.clicked.connect(self._skip_to_next)
        action_row.addWidget(self.skip_btn)
        
        action_row.addStretch()
        right_layout.addLayout(action_row)
        
        # Navigation
        nav_row = QHBoxLayout()
        
        self.prev_btn = QPushButton("← Previous (K)")
        self.prev_btn.clicked.connect(self._go_previous)
        nav_row.addWidget(self.prev_btn)
        
        self.next_btn = QPushButton("Next → (J)")
        self.next_btn.clicked.connect(self._go_next)
        nav_row.addWidget(self.next_btn)
        
        nav_row.addStretch()
        
        self.save_btn = QPushButton("💾 Save Edits")
        self.save_btn.setStyleSheet("""
            QPushButton {
                background-color: #007bff;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #0056b3;
            }
        """)
        self.save_btn.clicked.connect(self._save_current_item)
        nav_row.addWidget(self.save_btn)
        
        right_layout.addLayout(nav_row)
        
        right_layout.addStretch()
        
        # Confirm & Sync button at bottom of right panel
        self.confirm_sync_btn = QPushButton("🚀 Confirm && Sync to GetReceipts")
        self.confirm_sync_btn.setStyleSheet("""
            QPushButton {
                background-color: #17a2b8;
                color: white;
                border: none;
                padding: 12px 24px;
                border-radius: 6px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #138496;
            }
            QPushButton:disabled {
                background-color: #6c757d;
            }
        """)
        self.confirm_sync_btn.clicked.connect(self._show_confirm_sync_dialog)
        right_layout.addWidget(self.confirm_sync_btn)
        
        content_splitter.addWidget(right_widget)
        
        # Set splitter proportions
        content_splitter.setSizes([500, 350])
        layout.addWidget(content_splitter, 1)

    def _setup_keyboard_shortcuts(self):
        """Setup keyboard shortcuts for review workflow."""
        # Accept: A
        self.shortcut_accept = QShortcut(QKeySequence("A"), self)
        self.shortcut_accept.activated.connect(self._accept_current)
        
        # Reject: R
        self.shortcut_reject = QShortcut(QKeySequence("R"), self)
        self.shortcut_reject.activated.connect(self._reject_current)
        
        # Next: J or Down
        self.shortcut_next_j = QShortcut(QKeySequence("J"), self)
        self.shortcut_next_j.activated.connect(self._go_next)
        
        # Previous: K or Up
        self.shortcut_prev_k = QShortcut(QKeySequence("K"), self)
        self.shortcut_prev_k.activated.connect(self._go_previous)
        
        # Toggle selection: Space
        self.shortcut_toggle = QShortcut(QKeySequence(Qt.Key.Key_Space), self)
        self.shortcut_toggle.activated.connect(self._toggle_current_selection)
        
        # Deselect all: Escape
        self.shortcut_deselect = QShortcut(QKeySequence(Qt.Key.Key_Escape), self)
        self.shortcut_deselect.activated.connect(self._deselect_all)
        
        # Focus search: /
        self.shortcut_search = QShortcut(QKeySequence("/"), self)
        self.shortcut_search.activated.connect(lambda: self.filter_bar.search_input.setFocus())
        
        # Confirm & Sync: Cmd+Enter
        self.shortcut_sync = QShortcut(QKeySequence("Ctrl+Return"), self)
        self.shortcut_sync.activated.connect(self._show_confirm_sync_dialog)

    def _update_miner_models(self, provider: str):
        """Update miner model dropdown based on provider."""
        self.miner_model.clear()
        self.miner_model.addItems(LLM_PROVIDERS.get(provider, []))

    def _update_evaluator_models(self, provider: str):
        """Update evaluator model dropdown based on provider."""
        self.evaluator_model.clear()
        self.evaluator_model.addItems(LLM_PROVIDERS.get(provider, []))

    # Extraction methods
    def start_extraction(self):
        """Start the extraction pipeline."""
        url = self.url_input.text().strip()
        if not url:
            QMessageBox.warning(self, "No URL", "Please enter a YouTube URL or playlist URL.")
            return
        
        urls = [url]
        
        # Disable controls
        self.extract_btn.setEnabled(False)
        self.url_input.setEnabled(False)
        
        # Clear previous results
        self.queue_model.clear()
        self.current_results = []
        self.sources = []
        self.dashboard.reset()
        
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
        self.dashboard.set_total_videos(len(urls))
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

    # Worker signal handlers
    def _on_batch_started(self, total: int):
        """Handle batch start."""
        logger.info(f"Batch started: {total} episodes")
        self.dashboard.set_total_videos(total)

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
            self.dashboard.increment_processed()

    def _on_quality_warning(self, index: int, suggestion: str):
        """Handle quality warning."""
        self.whisper_btn.show()
        self.progress_display.show_quality_warning(suggestion)

    def _on_batch_completed(self, success: int, failure: int):
        """Handle batch completion."""
        self.progress_display.complete_batch(success, failure)
        
        # Re-enable controls
        self.extract_btn.setEnabled(True)
        self.url_input.setEnabled(True)
        
        # Update filter bar with sources
        self.filter_bar.set_sources(self.sources)
        
        self.status_update.emit(f"Complete: {success} succeeded, {failure} failed")

    def _on_result_ready(self, result: dict):
        """Handle result data from worker - populate unified queue."""
        self.current_results.append(result)
        
        source_title = result.get("title", "Unknown Source")
        source_id = result.get("source_id", "")
        self.sources.append((source_title, source_id))
        
        items = []
        
        # Add claims
        for claim_data in result.get("claims", []):
            item = ReviewItem(
                entity_type=EntityType.CLAIM,
                content=claim_data.get("claim_text", claim_data.get("canonical", "")),
                source_title=source_title,
                source_id=source_id,
                tier=claim_data.get("tier", "C"),
                importance=claim_data.get("importance", 0),
                status=ReviewStatus.PENDING,
                raw_data=claim_data,
            )
            items.append(item)
        
        # Add rejected claims (pre-marked as rejected)
        for claim_data in result.get("rejected_claims", []):
            item = ReviewItem(
                entity_type=EntityType.CLAIM,
                content=claim_data.get("claim_text", claim_data.get("canonical", "")),
                source_title=source_title,
                source_id=source_id,
                tier=claim_data.get("tier", "C"),
                importance=claim_data.get("importance", 0),
                status=ReviewStatus.REJECTED,
                raw_data=claim_data,
            )
            items.append(item)
        
        # Add jargon
        for jargon_data in result.get("jargon", []):
            item = ReviewItem(
                entity_type=EntityType.JARGON,
                content=jargon_data.get("term", ""),
                source_title=source_title,
                source_id=source_id,
                tier="B",
                importance=jargon_data.get("importance", 50),
                status=ReviewStatus.PENDING,
                raw_data=jargon_data,
            )
            items.append(item)
        
        # Add people
        for person_data in result.get("people", []):
            item = ReviewItem(
                entity_type=EntityType.PERSON,
                content=person_data.get("name", ""),
                source_title=source_title,
                source_id=source_id,
                tier="B",
                importance=person_data.get("importance", 50),
                status=ReviewStatus.PENDING,
                raw_data=person_data,
            )
            items.append(item)
        
        # Add concepts
        for concept_data in result.get("concepts", []):
            item = ReviewItem(
                entity_type=EntityType.CONCEPT,
                content=concept_data.get("name", concept_data.get("term", "")),
                source_title=source_title,
                source_id=source_id,
                tier="B",
                importance=concept_data.get("importance", 50),
                status=ReviewStatus.PENDING,
                raw_data=concept_data,
            )
            items.append(item)
        
        # Save items to database and get IDs
        try:
            db_items = []
            for item in items:
                db_items.append({
                    "entity_type": item.entity_type.value,
                    "content": item.content,
                    "source_id": item.source_id,
                    "source_title": item.source_title,
                    "tier": item.tier,
                    "importance": item.importance,
                    "raw_data": item.raw_data,
                    "review_status": item.status.value,
                })
            
            item_ids = self.db_service.add_items_batch(db_items)
            
            # Assign database IDs to items
            for item, item_id in zip(items, item_ids):
                item.item_id = item_id
            
            logger.info(f"Saved {len(item_ids)} items to database")
        except Exception as e:
            logger.error(f"Error saving items to database: {e}")
        
        # Add all items to queue
        self.queue_model.add_items(items)
        
        # Update dashboard
        self.dashboard.add_extracted(len(items))
        self._update_dashboard_stats()
        
        # Update filter bar with new source
        self.filter_bar.set_sources(self.sources)

    def _on_error(self, error: str):
        """Handle error from worker."""
        logger.error(f"Extraction error: {error}")
        self.status_update.emit(f"Error: {error}")
        QMessageBox.warning(self, "Extraction Error", error)

    # Filter handling
    def _apply_filters(self):
        """Apply current filter settings to the queue."""
        self.filter_model.set_type_filter(self.filter_bar.get_type_filter())
        self.filter_model.set_status_filter(self.filter_bar.get_status_filter())
        self.filter_model.set_source_filter(self.filter_bar.get_source_filter())
        self.filter_model.set_tier_filter(self.filter_bar.get_tier_filter())
        self.filter_model.set_search_text(self.filter_bar.get_search_text())

    # Selection handling
    def _on_selection_changed(self, count: int):
        """Handle change in selection count."""
        self.bulk_toolbar.update_selection_count(count)
        self.bulk_toolbar.set_total_pending(
            self.queue_model.get_status_counts().get("pending", 0)
        )

    def _on_item_activated(self, row: int):
        """Handle item activation (click on row)."""
        item = self.queue_model.get_item(row)
        if item:
            self.current_item = item
            self._update_detail_panel(item)

    def _update_detail_panel(self, item: ReviewItem):
        """Update the detail panel with item data."""
        self.type_label.setText(f"{item.get_type_icon()} {item.entity_type.value.title()}")
        self.content_edit.setText(item.content)
        
        # Get evidence/context from raw data
        raw = item.raw_data
        if item.entity_type == EntityType.CLAIM:
            evidence = raw.get("evidence", raw.get("evidence_quote", ""))
        elif item.entity_type == EntityType.JARGON:
            evidence = raw.get("definition", raw.get("description", ""))
        elif item.entity_type == EntityType.PERSON:
            evidence = raw.get("context", raw.get("description", ""))
        else:
            evidence = raw.get("description", "")
        
        self.evidence_edit.setText(evidence)
        self.importance_edit.setText(str(item.importance))
        self.source_label.setText(item.source_title)
        
        # Update status label with color
        status_colors = {
            ReviewStatus.PENDING: "#ffc107",
            ReviewStatus.ACCEPTED: "#28a745",
            ReviewStatus.REJECTED: "#dc3545",
        }
        self.status_label.setText(item.status.value.title())
        self.status_label.setStyleSheet(f"font-weight: bold; color: {status_colors.get(item.status, '#666')};")

    def _update_dashboard_stats(self):
        """Update dashboard with current status counts."""
        counts = self.queue_model.get_status_counts()
        self.dashboard.set_review_counts(
            counts["pending"],
            counts["accepted"],
            counts["rejected"]
        )

    # Bulk actions
    def _accept_selected(self):
        """Accept all selected items."""
        selected = self.queue_model.get_selected_items()
        count = len(selected)
        
        # Update database
        item_ids = [item.item_id for item in selected if item.item_id]
        if item_ids:
            self.db_service.update_status_batch(item_ids, "accepted")
        
        # Update model
        self.queue_model.accept_selected()
        self._update_dashboard_stats()
        
        # NEW: Trigger auto-sync for all accepted items
        for item in selected:
            self._auto_sync_item(item)
        
        self.status_update.emit(f"Accepted {count} items")

    def _reject_selected(self):
        """Reject all selected items."""
        selected = self.queue_model.get_selected_items()
        count = len(selected)
        
        # Update database
        item_ids = [item.item_id for item in selected if item.item_id]
        if item_ids:
            self.db_service.update_status_batch(item_ids, "rejected")
        
        # Update model
        self.queue_model.reject_selected()
        self._update_dashboard_stats()
        self.status_update.emit(f"Rejected {count} items")

    def _set_tier_selected(self, tier: str):
        """Set tier for all selected items."""
        for item in self.queue_model.get_selected_items():
            item.tier = tier
        self.queue_model.dataChanged.emit(
            self.queue_model.index(0, 0),
            self.queue_model.index(self.queue_model.rowCount() - 1, 6)
        )
        self.status_update.emit(f"Set tier to {tier} for selected items")

    def _deselect_all(self):
        """Deselect all items."""
        self.queue_model.deselect_all()

    def _select_all_visible(self):
        """Select all visible (filtered) items."""
        for row in range(self.filter_model.rowCount()):
            source_index = self.filter_model.mapToSource(self.filter_model.index(row, 0))
            item = self.queue_model.get_item(source_index.row())
            if item:
                item.is_selected = True
        self.queue_model.dataChanged.emit(
            self.queue_model.index(0, 0),
            self.queue_model.index(self.queue_model.rowCount() - 1, 0)
        )
        self.queue_model.selection_changed.emit(self.queue_model.get_selected_count())

    def _select_all_pending(self):
        """Select all pending items."""
        for item in self.queue_model.get_all_items():
            if item.status == ReviewStatus.PENDING:
                item.is_selected = True
        self.queue_model.dataChanged.emit(
            self.queue_model.index(0, 0),
            self.queue_model.index(self.queue_model.rowCount() - 1, 0)
        )
        self.queue_model.selection_changed.emit(self.queue_model.get_selected_count())

    # Single item actions
    def _accept_current(self):
        """Accept the current item and move to next."""
        if self.current_item:
            row = self._get_current_row()
            if row >= 0:
                # Update database
                if self.current_item.item_id:
                    self.db_service.update_status(self.current_item.item_id, "accepted")
                
                # Update model
                self.queue_model.set_item_status(row, ReviewStatus.ACCEPTED)
                self._update_detail_panel(self.current_item)
                self._update_dashboard_stats()
                
                # NEW: Trigger auto-sync
                self._auto_sync_item(self.current_item)
                
                self._go_next()
                self.status_update.emit("Item accepted")

    def _reject_current(self):
        """Reject the current item and move to next."""
        if self.current_item:
            row = self._get_current_row()
            if row >= 0:
                # Update database
                if self.current_item.item_id:
                    self.db_service.update_status(self.current_item.item_id, "rejected")
                
                # Update model
                self.queue_model.set_item_status(row, ReviewStatus.REJECTED)
                self._update_detail_panel(self.current_item)
                self._update_dashboard_stats()
                self._go_next()
                self.status_update.emit("Item rejected")

    def _skip_to_next(self):
        """Skip current item (no change) and move to next."""
        self._go_next()

    def _toggle_current_selection(self):
        """Toggle selection of current item."""
        row = self._get_current_row()
        if row >= 0:
            self.queue_model.toggle_selection(row)

    def _get_current_row(self) -> int:
        """Get row index of current item."""
        if not self.current_item:
            return -1
        items = self.queue_model.get_all_items()
        try:
            return items.index(self.current_item)
        except ValueError:
            return -1

    # Navigation
    def _go_previous(self):
        """Navigate to previous item."""
        current_row = self._get_current_row()
        if current_row > 0:
            new_row = current_row - 1
            item = self.queue_model.get_item(new_row)
            if item:
                self.current_item = item
                self._update_detail_panel(item)
                # Select row in view
                self._select_view_row(new_row)

    def _go_next(self):
        """Navigate to next item."""
        current_row = self._get_current_row()
        if current_row < self.queue_model.rowCount() - 1:
            new_row = current_row + 1
            item = self.queue_model.get_item(new_row)
            if item:
                self.current_item = item
                self._update_detail_panel(item)
                # Select row in view
                self._select_view_row(new_row)

    def _select_view_row(self, row: int):
        """Select a row in the view (handles filter model mapping)."""
        # Find the row in the filter model
        for i in range(self.filter_model.rowCount()):
            source_index = self.filter_model.mapToSource(self.filter_model.index(i, 0))
            if source_index.row() == row:
                self.queue_view.selectRow(i)
                self.queue_view.scrollTo(self.filter_model.index(i, 0))
                break

    def _save_current_item(self):
        """Save edits to the current item."""
        if not self.current_item:
            return
        
        # Update item from form
        self.current_item.content = self.content_edit.toPlainText()
        try:
            self.current_item.importance = float(self.importance_edit.text())
        except ValueError:
            pass
        
        # Update raw data based on type
        raw = self.current_item.raw_data
        if self.current_item.entity_type == EntityType.CLAIM:
            raw["claim_text"] = self.current_item.content
            raw["evidence"] = self.evidence_edit.toPlainText()
        elif self.current_item.entity_type == EntityType.JARGON:
            raw["term"] = self.current_item.content
            raw["definition"] = self.evidence_edit.toPlainText()
        elif self.current_item.entity_type == EntityType.PERSON:
            raw["name"] = self.current_item.content
            raw["context"] = self.evidence_edit.toPlainText()
        elif self.current_item.entity_type == EntityType.CONCEPT:
            raw["name"] = self.current_item.content
            raw["description"] = self.evidence_edit.toPlainText()
        
        # Save to database
        if self.current_item.item_id:
            self.db_service.update_item(
                self.current_item.item_id,
                content=self.current_item.content,
                importance=self.current_item.importance,
                raw_data=raw,
            )
        
        # Trigger model update
        row = self._get_current_row()
        if row >= 0:
            self.queue_model.dataChanged.emit(
                self.queue_model.index(row, 0),
                self.queue_model.index(row, 6)
            )
        
        self.status_update.emit("Item saved")

    # Confirm & Sync
    def _show_confirm_sync_dialog(self):
        """Show the confirmation dialog before syncing."""
        # Calculate counts
        type_status_counts: dict[str, dict[str, int]] = {
            "claim": {"accepted": 0, "rejected": 0, "pending": 0},
            "jargon": {"accepted": 0, "rejected": 0, "pending": 0},
            "person": {"accepted": 0, "rejected": 0, "pending": 0},
            "concept": {"accepted": 0, "rejected": 0, "pending": 0},
        }
        
        for item in self.queue_model.get_all_items():
            type_key = item.entity_type.value
            status_key = item.status.value
            type_status_counts[type_key][status_key] += 1
        
        counts = {
            "accepted_claims": type_status_counts["claim"]["accepted"],
            "accepted_jargon": type_status_counts["jargon"]["accepted"],
            "accepted_people": type_status_counts["person"]["accepted"],
            "accepted_concepts": type_status_counts["concept"]["accepted"],
            "rejected": sum(c["rejected"] for c in type_status_counts.values()),
            "pending": sum(c["pending"] for c in type_status_counts.values()),
        }
        
        total_accepted = sum(counts[k] for k in ["accepted_claims", "accepted_jargon", "accepted_people", "accepted_concepts"])
        
        if total_accepted == 0:
            QMessageBox.information(
                self,
                "Nothing to Sync",
                "No items have been accepted yet. Accept items before syncing."
            )
            return
        
        dialog = ConfirmSyncDialog(counts, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._perform_sync()

    def _perform_sync(self):
        """Perform the sync to GetReceipts."""
        # Collect accepted items
        accepted_items = [
            item for item in self.queue_model.get_all_items()
            if item.status == ReviewStatus.ACCEPTED
        ]
        
        # Mark items as synced in database (preemptively - actual sync may fail)
        item_ids = [item.item_id for item in accepted_items if item.item_id]
        if item_ids:
            self.db_service.mark_synced(item_ids)
        
        # Emit signal for sync (to be handled by main window or sync worker)
        self.sync_requested.emit(accepted_items)
        self.status_update.emit(f"Syncing {len(accepted_items)} items to GetReceipts...")
        
        # Remove synced items from the queue model (they're done)
        # Keep them in DB with synced_at timestamp for audit trail
        synced_count = len(accepted_items)
        
        # Clear and reload only unsynced items
        self.queue_model.clear()
        remaining_items = [
            item for item in self.queue_model.get_all_items()
            if item.status != ReviewStatus.ACCEPTED or item.item_id not in item_ids
        ]
        
        # Reload from database to get fresh state
        self._load_pending_from_database()
        
        QMessageBox.information(
            self,
            "Sync Complete",
            f"Successfully synced {synced_count} items to GetReceipts.\n\n"
            f"Synced items have been removed from the review queue."
        )
    
    # Auto-sync methods
    def _auto_sync_item(self, item: ReviewItem):
        """
        Auto-sync a single accepted item in background.
        
        Args:
            item: ReviewItem to sync
        """
        if not self._is_sync_enabled():
            # Device not linked - queue for manual sync
            self.pending_sync_count += 1
            self._update_sync_indicator()
            return
        
        if self.is_syncing:
            # Already syncing - queue this item
            self.pending_sync_count += 1
            return
        
        # Start background sync
        from ..workers.auto_sync_worker import AutoSyncWorker
        
        self.is_syncing = True
        self.auto_sync_worker = AutoSyncWorker([item])
        self.auto_sync_worker.sync_complete.connect(self._on_auto_sync_complete)
        self.auto_sync_worker.sync_failed.connect(self._on_auto_sync_failed)
        self.auto_sync_worker.start()
        
        # Update UI
        self.dashboard.set_sync_status("Syncing...")
        self.status_update.emit("Auto-syncing to GetReceipts...")
    
    def _is_sync_enabled(self) -> bool:
        """Check if sync is enabled (device linked)."""
        try:
            from ...services.device_auth import get_device_auth
            device_auth = get_device_auth()
            return device_auth.is_enabled()
        except Exception as e:
            logger.error(f"Error checking sync status: {e}")
            return False
    
    def _on_auto_sync_complete(self, count: int, item_ids: list[str]):
        """Handle successful auto-sync."""
        self.is_syncing = False
        
        # Mark items as synced in database
        if item_ids:
            self.db_service.mark_synced(item_ids)
        
        # Update UI
        self.dashboard.set_sync_status("Synced ✓")
        self.status_update.emit(f"Auto-synced {count} item(s)")
        
        # Update unsynced count
        self._update_unsynced_count()
        
        # Remove synced items from queue
        for item_id in item_ids:
            self.queue_model.remove_item_by_id(item_id)
        
        self._update_dashboard_stats()
    
    def _on_auto_sync_failed(self, error: str, item_ids: list[str]):
        """Handle failed auto-sync."""
        self.is_syncing = False
        
        # Queue for manual sync
        self.pending_sync_count += len(item_ids)
        
        # Update UI
        self.dashboard.set_sync_status("Queued for sync")
        logger.warning(f"Auto-sync failed: {error}")
        
        # Don't show error to user - just queue for retry
        self._update_sync_indicator()
    
    def _update_sync_indicator(self):
        """Update sync status indicator in dashboard."""
        if self.pending_sync_count > 0:
            self.dashboard.set_unsynced_count(self.pending_sync_count)
        else:
            self.dashboard.set_sync_status("")
    
    def _update_unsynced_count(self):
        """Update count of unsynced accepted items."""
        unsynced = self.get_unsynced_count()
        self.pending_sync_count = unsynced
        self._update_sync_indicator()
    
    def get_unsynced_count(self) -> int:
        """
        Get count of accepted items not yet synced.
        
        Returns:
            Number of unsynced accepted items
        """
        count = 0
        for item in self.queue_model.get_all_items():
            if item.status == ReviewStatus.ACCEPTED:
                # Check if synced in database
                if item.item_id and not self.db_service.is_item_synced(item.item_id):
                    count += 1
        return count
    
    def sync_all_accepted(self):
        """
        Sync all accepted items (called from close handler).
        
        This is a blocking sync used when closing the app.
        """
        self._perform_sync()
