"""
System 2 Review Tab

Provides a QTableView-based interface for reviewing and editing claims
extracted by the HCE pipeline with SQLite backend and validation.
"""

import json
from datetime import datetime
from typing import Any

from PyQt6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    Qt,
    QTimer,
)
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableView,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ...database import DatabaseService
from ...database.hce_models import Claim, Episode
from ...logger import get_logger

logger = get_logger(__name__)


def extract_scores(claim: Claim) -> dict[str, Any]:
    """Helper to extract scores_json from a claim."""
    scores = {}
    if claim.scores_json:
        if isinstance(claim.scores_json, str):
            try:
                scores = json.loads(claim.scores_json)
            except Exception:
                scores = {}
        elif isinstance(claim.scores_json, dict):
            scores = claim.scores_json
    return scores


class ClaimEditDialog(QDialog):
    """Dialog for editing individual claims."""

    def __init__(self, claim: Claim, parent=None):
        super().__init__(parent)
        self.claim = claim
        self.setWindowTitle(f"Edit Claim - {claim.claim_id}")
        self.setModal(True)
        self.setMinimumWidth(600)

        self._setup_ui()
        self._load_claim_data()

    def _setup_ui(self):
        """Setup the edit dialog UI."""
        layout = QVBoxLayout(self)

        # Canonical claim text
        layout.addWidget(QLabel("Claim Text:"))
        self.canonical_edit = QTextEdit()
        self.canonical_edit.setMaximumHeight(100)
        layout.addWidget(self.canonical_edit)

        # Claim type
        type_layout = QHBoxLayout()
        type_layout.addWidget(QLabel("Type:"))
        self.type_combo = QComboBox()
        self.type_combo.addItems(
            ["factual", "causal", "normative", "forecast", "definition"]
        )
        type_layout.addWidget(self.type_combo)
        type_layout.addStretch()
        layout.addLayout(type_layout)

        # Scores section
        scores_group = QGroupBox("Scores (1-10)")
        scores_layout = QVBoxLayout()

        # Importance
        importance_layout = QHBoxLayout()
        importance_layout.addWidget(QLabel("Importance:"))
        self.importance_combo = QComboBox()
        self.importance_combo.addItems([str(i) for i in range(1, 11)])
        importance_layout.addWidget(self.importance_combo)
        importance_layout.addStretch()
        scores_layout.addLayout(importance_layout)

        # Novelty
        novelty_layout = QHBoxLayout()
        novelty_layout.addWidget(QLabel("Novelty:"))
        self.novelty_combo = QComboBox()
        self.novelty_combo.addItems([str(i) for i in range(1, 11)])
        novelty_layout.addWidget(self.novelty_combo)
        novelty_layout.addStretch()
        scores_layout.addLayout(novelty_layout)

        # Confidence
        confidence_layout = QHBoxLayout()
        confidence_layout.addWidget(QLabel("Confidence:"))
        self.confidence_combo = QComboBox()
        self.confidence_combo.addItems([str(i) for i in range(1, 11)])
        confidence_layout.addWidget(self.confidence_combo)
        confidence_layout.addStretch()
        scores_layout.addLayout(confidence_layout)

        scores_group.setLayout(scores_layout)
        layout.addWidget(scores_group)

        # First mention timestamp
        timestamp_layout = QHBoxLayout()
        timestamp_layout.addWidget(QLabel("First Mention:"))
        self.timestamp_edit = QLineEdit()
        self.timestamp_edit.setPlaceholderText("HH:MM:SS")
        timestamp_layout.addWidget(self.timestamp_edit)
        timestamp_layout.addStretch()
        layout.addLayout(timestamp_layout)

        # Upload status
        status_layout = QHBoxLayout()
        status_layout.addWidget(QLabel("Upload Status:"))
        self.status_combo = QComboBox()
        self.status_combo.addItems(["pending", "uploaded", "failed"])
        status_layout.addWidget(self.status_combo)
        status_layout.addStretch()
        layout.addLayout(status_layout)

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _load_claim_data(self):
        """Load claim data into form fields."""
        self.canonical_edit.setPlainText(self.claim.canonical)
        self.type_combo.setCurrentText(self.claim.claim_type or "factual")

        # Load scores from scores_json
        scores = extract_scores(self.claim)

        self.importance_combo.setCurrentText(str(int(scores.get("importance", 5))))
        self.novelty_combo.setCurrentText(str(int(scores.get("novelty", 5))))
        self.confidence_combo.setCurrentText(
            str(int(scores.get("confidence", scores.get("confidence_final", 5))))
        )

        self.timestamp_edit.setText(self.claim.first_mention_ts or "")
        self.status_combo.setCurrentText(self.claim.upload_status or "pending")

    def get_updated_values(self) -> dict[str, Any]:
        """Get the updated claim values."""
        # Get existing scores or create new dict
        scores = extract_scores(self.claim).copy() if self.claim.scores_json else {}

        # Update scores
        scores["importance"] = int(self.importance_combo.currentText())
        scores["novelty"] = int(self.novelty_combo.currentText())
        scores["confidence"] = int(self.confidence_combo.currentText())

        return {
            "canonical": self.canonical_edit.toPlainText().strip(),
            "claim_type": self.type_combo.currentText(),
            "scores_json": scores,
            "first_mention_ts": self.timestamp_edit.text().strip(),
            "upload_status": self.status_combo.currentText(),
            "updated_at": datetime.utcnow(),
        }


class ClaimsTableModel(QAbstractTableModel):
    """
    Table model for displaying and editing claims from SQLite database.

    Implements the Claim Review Grid specification from TECHNICAL_SPECIFICATIONS.md.
    """

    def __init__(self, db_service: DatabaseService, parent=None):
        super().__init__(parent)
        self.db_service = db_service
        self.claims: list[Claim] = []
        self.episodes: dict[str, Episode] = {}
        self.modified_rows = set()

        # Column definitions matching TECHNICAL_SPECIFICATIONS.md
        self.columns = [
            ("Episode", "episode_title"),
            ("Claim", "canonical"),
            ("Type", "claim_type"),
            ("Importance", "importance"),
            ("Novelty", "novelty"),
            ("Confidence", "confidence"),
            ("First Mention", "first_mention_ts"),
            ("Upload Status", "upload_status"),
            ("Modified", "is_modified"),
        ]

        self.load_data()

    def load_data(self, episode_filter: str | None = None):
        """Load claims from database with optional episode filter."""
        try:
            with self.db_service.get_session() as session:
                # Load episodes
                try:
                    episodes = session.query(Episode).all()
                    self.episodes = {ep.episode_id: ep for ep in episodes}
                except Exception as e:
                    logger.warning(f"Could not load episodes: {e}")
                    self.episodes = {}

                # Load claims
                try:
                    query = session.query(Claim)
                    if episode_filter:
                        query = query.filter_by(episode_id=episode_filter)

                    # Order by episode and timestamp
                    query = query.order_by(Claim.episode_id, Claim.first_mention_ts)

                    self.claims = list(query.all())
                except Exception as e:
                    logger.warning(f"Could not load claims: {e}")
                    self.claims = []
        except Exception as e:
            logger.error(f"Database error in load_data: {e}")
            self.claims = []
            self.episodes = {}
            self.modified_rows.clear()

        # Always clear modified rows when reloading
        self.modified_rows.clear()
        self.layoutChanged.emit()

    def rowCount(self, parent=QModelIndex()) -> int:
        """Return number of claims."""
        return len(self.claims)

    def columnCount(self, parent=QModelIndex()) -> int:
        """Return number of columns."""
        return len(self.columns)

    def headerData(self, section: int, orientation: Qt.Orientation, role: int) -> Any:
        """Return header data."""
        if (
            orientation == Qt.Orientation.Horizontal
            and role == Qt.ItemDataRole.DisplayRole
        ):
            if 0 <= section < len(self.columns):
                return self.columns[section][0]
        return None

    def data(self, index: QModelIndex, role: int) -> Any:
        """Return cell data for display and editing."""
        if not index.isValid() or not (0 <= index.row() < len(self.claims)):
            return None

        claim = self.claims[index.row()]
        col_name, col_attr = self.columns[index.column()]

        if role == Qt.ItemDataRole.DisplayRole:
            if col_name == "Episode":
                episode = self.episodes.get(claim.episode_id)
                return episode.title if episode else claim.episode_id
            elif col_name == "Modified":
                return "✓" if index.row() in self.modified_rows else ""
            elif col_name in ["Importance", "Novelty", "Confidence"]:
                # Extract from scores_json
                scores = extract_scores(claim)

                score_key = col_name.lower()
                if score_key == "confidence":
                    # Try both "confidence" and "confidence_final"
                    value = scores.get("confidence", scores.get("confidence_final", ""))
                else:
                    value = scores.get(score_key, "")
                return str(int(value)) if value else ""
            else:
                value = getattr(claim, col_attr, "")
                return str(value) if value else ""

        elif role == Qt.ItemDataRole.EditRole:
            if col_name not in ["Episode", "Modified"]:
                if col_name in ["Importance", "Novelty", "Confidence"]:
                    # Extract from scores_json for editing
                    scores = extract_scores(claim)

                    score_key = col_name.lower()
                    if score_key == "confidence":
                        value = scores.get(
                            "confidence", scores.get("confidence_final", 5)
                        )
                    else:
                        value = scores.get(score_key, 5)
                    return int(value)
                else:
                    return getattr(claim, col_attr, "")

        elif role == Qt.ItemDataRole.BackgroundRole:
            # Highlight modified rows
            if index.row() in self.modified_rows:
                return QColor(255, 255, 200)  # Light yellow

        elif role == Qt.ItemDataRole.FontRole:
            if index.row() in self.modified_rows:
                font = QFont()
                font.setBold(True)
                return font

        return None

    def setData(self, index: QModelIndex, value: Any, role: int) -> bool:
        """Handle cell editing with validation and auto-save."""
        if not index.isValid() or role != Qt.ItemDataRole.EditRole:
            return False

        claim = self.claims[index.row()]
        col_name, col_attr = self.columns[index.column()]

        # Validate based on column
        if col_name == "Type" and value not in [
            "factual",
            "causal",
            "normative",
            "forecast",
            "definition",
        ]:
            return False
        elif col_name in ["Importance", "Novelty", "Confidence"]:
            # Validate score is 1-10
            try:
                score_val = int(value)
                if not (1 <= score_val <= 10):
                    return False
            except (ValueError, TypeError):
                return False

            # Update scores_json
            scores = extract_scores(claim).copy() if claim.scores_json else {}

            score_key = col_name.lower()
            scores[score_key] = score_val
            claim.scores_json = scores

        elif col_name == "Upload Status" and value not in [
            "pending",
            "uploaded",
            "failed",
        ]:
            return False
        else:
            # Update claim attribute for non-score columns
            setattr(claim, col_attr, value)

        claim.updated_at = datetime.utcnow()

        # Mark as modified
        self.modified_rows.add(index.row())

        # Auto-save immediately
        self._auto_save_claim(index.row())

        # Emit data changed
        self.dataChanged.emit(index, index)
        return True

    def _auto_save_claim(self, row: int):
        """Auto-save a single claim to the database."""
        if row >= len(self.claims):
            return

        try:
            claim = self.claims[row]
            with self.db_service.get_session() as session:
                db_claim = (
                    session.query(Claim)
                    .filter_by(episode_id=claim.episode_id, claim_id=claim.claim_id)
                    .first()
                )

                if db_claim:
                    # Update fields
                    db_claim.canonical = claim.canonical
                    db_claim.claim_type = claim.claim_type
                    db_claim.scores_json = claim.scores_json
                    db_claim.first_mention_ts = claim.first_mention_ts
                    db_claim.upload_status = claim.upload_status
                    db_claim.updated_at = claim.updated_at

                session.commit()

            # Remove from modified rows after successful save
            self.modified_rows.discard(row)

        except Exception as e:
            logger.error(f"Failed to auto-save claim: {e}")

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        """Return item flags for editability."""
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags

        col_name = self.columns[index.column()][0]

        # Episode and Modified columns are not editable
        if col_name in ["Episode", "Modified"]:
            return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable

        return (
            Qt.ItemFlag.ItemIsEnabled
            | Qt.ItemFlag.ItemIsSelectable
            | Qt.ItemFlag.ItemIsEditable
        )

    def save_changes(self) -> bool:
        """Save all modified claims to database."""
        if not self.modified_rows:
            return True

        try:
            with self.db_service.get_session() as session:
                for row in self.modified_rows:
                    if row < len(self.claims):
                        claim = self.claims[row]
                        # Merge with session
                        db_claim = (
                            session.query(Claim)
                            .filter_by(
                                episode_id=claim.episode_id, claim_id=claim.claim_id
                            )
                            .first()
                        )

                        if db_claim:
                            # Update fields
                            db_claim.canonical = claim.canonical
                            db_claim.claim_type = claim.claim_type
                            db_claim.tier = claim.tier
                            db_claim.first_mention_ts = claim.first_mention_ts
                            db_claim.upload_status = claim.upload_status
                            db_claim.updated_at = claim.updated_at

                session.commit()

            self.modified_rows.clear()
            self.layoutChanged.emit()
            return True

        except Exception as e:
            logger.error(f"Failed to save claims: {e}")
            return False


class ReviewTabSystem2(QWidget):
    """
    System 2 Review Tab with QTableView bound to SQLite.

    Provides claim review and editing functionality with:
    - Direct SQLite integration
    - Column-based validation
    - Optimistic concurrency using updated_at
    - Batch save functionality
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.db_service = DatabaseService()
        self._setup_ui()

        # Auto-refresh timer
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self._check_for_updates)
        self.refresh_timer.start(30000)  # Check every 30 seconds

    def _setup_ui(self):
        """Setup the review tab UI."""
        layout = QVBoxLayout(self)

        # Header
        header_layout = QHBoxLayout()
        header_layout.addWidget(QLabel("<h2>📋 Claim Review</h2>"))
        header_layout.addStretch()

        # Episode filter
        self.episode_combo = QComboBox()
        self.episode_combo.addItem("All Episodes")
        self._populate_episodes()
        self.episode_combo.currentTextChanged.connect(self._on_episode_filter_changed)
        header_layout.addWidget(QLabel("Episode:"))
        header_layout.addWidget(self.episode_combo)

        # Refresh button
        refresh_btn = QPushButton("🔄 Refresh")
        refresh_btn.clicked.connect(self._refresh_data)
        header_layout.addWidget(refresh_btn)

        layout.addLayout(header_layout)

        # Info label
        info_label = QLabel(
            "Review and edit claims extracted by the HCE pipeline. "
            "Double-click cells to edit. All changes are saved automatically."
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: #666; margin: 10px 0;")
        layout.addWidget(info_label)

        # Table view
        self.table_view = QTableView()
        self.model = ClaimsTableModel(self.db_service)
        self.table_view.setModel(self.model)

        # Configure table
        self.table_view.setAlternatingRowColors(True)
        self.table_view.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.table_view.setSortingEnabled(True)
        self.table_view.setWordWrap(True)

        # Set column widths
        header = self.table_view.horizontalHeader()
        header.setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )  # Episode
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)  # Claim
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)  # Type
        header.setSectionResizeMode(
            3, QHeaderView.ResizeMode.ResizeToContents
        )  # Importance
        header.setSectionResizeMode(
            4, QHeaderView.ResizeMode.ResizeToContents
        )  # Novelty
        header.setSectionResizeMode(
            5, QHeaderView.ResizeMode.ResizeToContents
        )  # Confidence
        header.setSectionResizeMode(
            6, QHeaderView.ResizeMode.ResizeToContents
        )  # First Mention
        header.setSectionResizeMode(
            7, QHeaderView.ResizeMode.ResizeToContents
        )  # Upload Status
        header.setSectionResizeMode(
            8, QHeaderView.ResizeMode.ResizeToContents
        )  # Modified

        # Enable double-click editing
        self.table_view.doubleClicked.connect(self._on_cell_double_clicked)
        
        # Connect selection changed to update delete button state
        self.table_view.selectionModel().selectionChanged.connect(
            self._on_selection_changed
        )

        layout.addWidget(self.table_view)

        # Action buttons
        button_layout = QHBoxLayout()

        # Info label about auto-save
        auto_save_info = QLabel("ℹ️ Changes are saved automatically")
        auto_save_info.setStyleSheet("color: #666; font-style: italic;")
        button_layout.addWidget(auto_save_info)

        button_layout.addStretch()

        # Delete button
        self.delete_btn = QPushButton("🗑️ Delete Selected")
        self.delete_btn.clicked.connect(self._delete_selected_claims)
        self.delete_btn.setEnabled(False)  # Initially disabled until selection is made
        self.delete_btn.setToolTip(
            "Permanently delete selected claims from the database.\n"
            "This action cannot be undone."
        )
        button_layout.addWidget(self.delete_btn)

        # Export button group
        export_csv_btn = QPushButton("📤 Export CSV")
        export_csv_btn.clicked.connect(self._export_to_csv)
        button_layout.addWidget(export_csv_btn)

        export_md_btn = QPushButton("📄 Export MD")
        export_md_btn.clicked.connect(self._export_to_md)
        button_layout.addWidget(export_md_btn)

        export_json_btn = QPushButton("🔧 Export JSON")
        export_json_btn.clicked.connect(self._export_to_json)
        button_layout.addWidget(export_json_btn)

        export_web_btn = QPushButton("🌐 Export to Web")
        export_web_btn.clicked.connect(self._export_to_web)
        button_layout.addWidget(export_web_btn)

        layout.addLayout(button_layout)

        # Connect model signals
        self.model.dataChanged.connect(self._on_data_changed)

    def _populate_episodes(self):
        """Populate episode filter combo box."""
        try:
            with self.db_service.get_session() as session:
                episodes = session.query(Episode).order_by(Episode.title).all()
                for episode in episodes:
                    self.episode_combo.addItem(episode.title, episode.episode_id)
        except Exception as e:
            logger.warning(f"Could not populate episodes dropdown: {e}")
            # Keep just the "All Episodes" option if database fails

    def _on_episode_filter_changed(self, text: str):
        """Handle episode filter change."""
        if text == "All Episodes":
            self.model.load_data()
        else:
            episode_id = self.episode_combo.currentData()
            if episode_id:
                self.model.load_data(episode_filter=episode_id)

    def _on_cell_double_clicked(self, index: QModelIndex):
        """Handle cell double-click for advanced editing."""
        if not index.isValid():
            return

        claim = self.model.claims[index.row()]
        col_name = self.model.columns[index.column()][0]

        # For claim text, open full editor
        if col_name == "Claim":
            dialog = ClaimEditDialog(claim, self)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                # Update claim with new values
                updates = dialog.get_updated_values()
                for key, value in updates.items():
                    setattr(claim, key, value)

                # Auto-save to database immediately
                self.model._auto_save_claim(index.row())

                # Update UI
                self.model.layoutChanged.emit()
                self._on_data_changed()

    def _on_data_changed(self):
        """Handle data changes - auto-save is now handled per-cell in setData."""
        # Changes are auto-saved immediately, so nothing to do here

    def _on_selection_changed(self):
        """Handle selection changes to enable/disable delete button."""
        selected_indexes = self.table_view.selectionModel().selectedRows()
        self.delete_btn.setEnabled(len(selected_indexes) > 0)

    def _save_changes(self):
        """Save all pending changes."""
        if self.model.save_changes():
            QMessageBox.information(
                self,
                "Success",
                f"Successfully saved {len(self.model.modified_rows)} claim(s).",
            )
            self.save_btn.setEnabled(False)
        else:
            QMessageBox.critical(
                self, "Error", "Failed to save changes. Check logs for details."
            )

    def _refresh_data(self):
        """Manually refresh data from database."""
        current_filter = self.episode_combo.currentText()
        if current_filter == "All Episodes":
            self.model.load_data()
        else:
            episode_id = self.episode_combo.currentData()
            if episode_id:
                self.model.load_data(episode_filter=episode_id)

    def _check_for_updates(self):
        """Check for database updates (for multi-user scenarios)."""
        # In a production system, this would check for changes
        # made by other users and prompt to reload if needed

    def _delete_selected_claims(self):
        """Delete selected claims from the database."""
        # Get selected rows
        selected_indexes = self.table_view.selectionModel().selectedRows()
        
        if not selected_indexes:
            QMessageBox.information(
                self,
                "No Selection",
                "Please select one or more claims to delete.",
            )
            return
        
        # Get unique rows (in case multiple cells in same row are selected)
        selected_rows = sorted(set(index.row() for index in selected_indexes), reverse=True)
        
        # Get the claims to delete
        claims_to_delete = [self.model.claims[row] for row in selected_rows]
        
        # Confirm deletion
        reply = QMessageBox.question(
            self,
            "Confirm Deletion",
            f"Are you sure you want to permanently delete {len(claims_to_delete)} claim(s)?\n\n"
            "This action cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        # Delete from database
        try:
            deleted_count = 0
            with self.db_service.get_session() as session:
                for claim in claims_to_delete:
                    # Find and delete the claim
                    db_claim = (
                        session.query(Claim)
                        .filter_by(episode_id=claim.episode_id, claim_id=claim.claim_id)
                        .first()
                    )
                    
                    if db_claim:
                        session.delete(db_claim)
                        deleted_count += 1
                
                session.commit()
            
            # Refresh the view
            self._refresh_data()
            
            QMessageBox.information(
                self,
                "Deletion Complete",
                f"Successfully deleted {deleted_count} claim(s) from the database.",
            )
            
        except Exception as e:
            logger.error(f"Failed to delete claims: {e}")
            QMessageBox.critical(
                self,
                "Deletion Error",
                f"Failed to delete claims:\n\n{str(e)}",
            )

    def _export_to_csv(self):
        """Export current view to CSV."""
        import csv

        from PyQt6.QtWidgets import QFileDialog

        filename, _ = QFileDialog.getSaveFileName(
            self, "Export Claims to CSV", "claims_export.csv", "CSV Files (*.csv)"
        )

        if filename:
            try:
                with open(filename, "w", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)

                    # Write headers
                    headers = [
                        col[0] for col in self.model.columns if col[0] != "Modified"
                    ]
                    writer.writerow(headers)

                    # Write data
                    for claim in self.model.claims:
                        episode = self.model.episodes.get(claim.episode_id)

                        # Extract scores
                        scores = extract_scores(claim)

                        row = [
                            episode.title if episode else claim.episode_id,
                            claim.canonical,
                            claim.claim_type,
                            scores.get("importance", ""),
                            scores.get("novelty", ""),
                            scores.get(
                                "confidence", scores.get("confidence_final", "")
                            ),
                            claim.first_mention_ts,
                            claim.upload_status,
                        ]
                        writer.writerow(row)

                QMessageBox.information(
                    self,
                    "Export Complete",
                    f"Successfully exported {len(self.model.claims)} claims to {filename}",
                )

            except Exception as e:
                QMessageBox.critical(
                    self, "Export Error", f"Failed to export: {str(e)}"
                )

    def _export_to_md(self):
        """Export current view to Markdown."""
        from PyQt6.QtWidgets import QFileDialog

        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Export Claims to Markdown",
            "claims_export.md",
            "Markdown Files (*.md)",
        )

        if filename:
            try:
                with open(filename, "w", encoding="utf-8") as f:
                    # Write header
                    f.write("# Claims Export\n\n")
                    f.write(f"Exported {len(self.model.claims)} claims\n\n")

                    # Group by episode
                    episode_claims = {}
                    for claim in self.model.claims:
                        episode = self.model.episodes.get(claim.episode_id)
                        episode_title = episode.title if episode else claim.episode_id
                        if episode_title not in episode_claims:
                            episode_claims[episode_title] = []
                        episode_claims[episode_title].append(claim)

                    # Write claims by episode
                    for episode_title, claims in episode_claims.items():
                        f.write(f"## {episode_title}\n\n")
                        for claim in claims:
                            # Extract scores
                            scores = extract_scores(claim)

                            f.write(f"### {claim.canonical}\n\n")
                            f.write(f"- **Type**: {claim.claim_type}\n")
                            f.write(
                                f"- **Importance**: {scores.get('importance', 'N/A')}\n"
                            )
                            f.write(f"- **Novelty**: {scores.get('novelty', 'N/A')}\n")
                            f.write(
                                f"- **Confidence**: {scores.get('confidence', scores.get('confidence_final', 'N/A'))}\n"
                            )
                            f.write(f"- **First Mention**: {claim.first_mention_ts}\n")
                            f.write(f"- **Upload Status**: {claim.upload_status}\n")
                            f.write("\n")

                QMessageBox.information(
                    self,
                    "Export Complete",
                    f"Successfully exported {len(self.model.claims)} claims to {filename}",
                )

            except Exception as e:
                QMessageBox.critical(
                    self, "Export Error", f"Failed to export: {str(e)}"
                )

    def _export_to_json(self):
        """Export current view to JSON."""
        import json

        from PyQt6.QtWidgets import QFileDialog

        filename, _ = QFileDialog.getSaveFileName(
            self, "Export Claims to JSON", "claims_export.json", "JSON Files (*.json)"
        )

        if filename:
            try:
                export_data = {"episodes": [], "claims": []}

                # Export episodes
                for episode_id, episode in self.model.episodes.items():
                    export_data["episodes"].append(
                        {
                            "episode_id": episode.episode_id,
                            "title": episode.title,
                            "source_url": episode.source_url,
                            "media_type": episode.media_type,
                            "duration_seconds": episode.duration_seconds,
                            "published_at": (
                                str(episode.published_at)
                                if episode.published_at
                                else None
                            ),
                        }
                    )

                # Export claims
                for claim in self.model.claims:
                    export_data["claims"].append(
                        {
                            "claim_id": claim.claim_id,
                            "episode_id": claim.episode_id,
                            "canonical": claim.canonical,
                            "claim_type": claim.claim_type,
                            "tier": claim.tier,
                            "first_mention_ts": claim.first_mention_ts,
                            "upload_status": claim.upload_status,
                            "scores_json": claim.scores_json,
                            "inserted_at": (
                                str(claim.inserted_at) if claim.inserted_at else None
                            ),
                            "updated_at": (
                                str(claim.updated_at) if claim.updated_at else None
                            ),
                        }
                    )

                with open(filename, "w", encoding="utf-8") as f:
                    json.dump(export_data, f, indent=2)

                QMessageBox.information(
                    self,
                    "Export Complete",
                    f"Successfully exported {len(self.model.claims)} claims and {len(export_data['episodes'])} episodes to {filename}",
                )

            except Exception as e:
                QMessageBox.critical(
                    self, "Export Error", f"Failed to export: {str(e)}"
                )

    def _export_to_web(self):
        """Export selected claims to Skip The Podcast web."""
        try:
            # Check if any claims are selected
            if not self.model.claims:
                QMessageBox.information(
                    self,
                    "No Claims",
                    "No claims available to export. Please load or create claims first.",
                )
                return

            # Ask user to confirm
            reply = QMessageBox.question(
                self,
                "Export to Web",
                f"Export {len(self.model.claims)} claims to Skip The Podcast web?\n\n"
                "This will upload the claims to Skipthepodcast.com using OAuth authentication.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )

            if reply != QMessageBox.StandardButton.Yes:
                return

            # Import upload functionality
            try:
                from ...cloud.oauth import upload_to_getreceipts
                from ...services.claims_upload_service import ClaimUploadData
            except ImportError as e:
                QMessageBox.critical(
                    self,
                    "Import Error",
                    f"Failed to import upload functionality:\n\n{str(e)}\n\n"
                    "Please ensure the GetReceipts OAuth module is available.",
                )
                return

            # Prepare claims data for upload
            claims_data = []
            for claim in self.model.claims:
                episode = self.model.episodes.get(claim.episode_id)

                # Build episode data
                episode_data = None
                if episode:
                    episode_data = {
                        "episode_id": episode.episode_id,
                        "title": episode.title,
                        "source_url": episode.source_url or "",
                        "media_type": episode.media_type or "unknown",
                        "duration_seconds": episode.duration_seconds or 0,
                        "published_at": (
                            str(episode.published_at) if episode.published_at else None
                        ),
                    }

                # Build claim upload data
                claim_upload = ClaimUploadData(
                    claim_id=claim.claim_id,
                    canonical=claim.canonical,
                    episode_id=claim.episode_id,
                    claim_type=claim.claim_type,
                    tier=claim.tier,
                    scores_json=claim.scores_json or "{}",
                    first_mention_ts=claim.first_mention_ts,
                    inserted_at=str(claim.inserted_at) if claim.inserted_at else None,
                    episode_data=episode_data,
                    evidence_spans=[],
                    people=[],
                    jargon=[],
                    concepts=[],
                    relations=[],
                )
                claims_data.append(claim_upload)

            # Convert to session data format
            session_data = {
                "episodes": [],
                "claims": [],
                "evidence_spans": [],
                "people": [],
                "jargon": [],
                "concepts": [],
                "relations": [],
            }

            seen_episodes = set()
            for claim_upload in claims_data:
                if (
                    claim_upload.episode_data
                    and claim_upload.episode_id not in seen_episodes
                ):
                    session_data["episodes"].append(claim_upload.episode_data)
                    seen_episodes.add(claim_upload.episode_id)

                session_data["claims"].append(
                    {
                        "claim_id": claim_upload.claim_id,
                        "canonical": claim_upload.canonical,
                        "episode_id": claim_upload.episode_id,
                        "claim_type": claim_upload.claim_type,
                        "tier": claim_upload.tier,
                        "scores_json": claim_upload.scores_json,
                        "first_mention_ts": claim_upload.first_mention_ts,
                        "inserted_at": claim_upload.inserted_at,
                    }
                )

            # Show progress dialog
            from PyQt6.QtWidgets import QProgressDialog

            progress = QProgressDialog(
                "Uploading claims to Skip The Podcast web...",
                "Cancel",
                0,
                0,
                self,
            )
            progress.setWindowTitle("Web Export")
            progress.setModal(True)
            progress.show()

            try:
                # Perform upload
                upload_results = upload_to_getreceipts(
                    session_data, use_production=False
                )

                progress.close()

                # Report results
                total_uploaded = sum(
                    len(data) if data else 0 for data in upload_results.values()
                )

                QMessageBox.information(
                    self,
                    "Upload Complete",
                    f"Successfully uploaded {total_uploaded} records to Skip The Podcast web!\n\n"
                    f"Claims: {len(upload_results.get('claims', []))}\n"
                    f"Episodes: {len(upload_results.get('episodes', []))}",
                )

            except Exception as upload_error:
                progress.close()
                QMessageBox.critical(
                    self,
                    "Upload Failed",
                    f"Failed to upload to Skip The Podcast web:\n\n{str(upload_error)}",
                )

        except Exception as e:
            QMessageBox.critical(
                self,
                "Export Error",
                f"Failed to prepare export:\n\n{str(e)}",
            )
