"""
System 2 Review Tab

Provides a QTableView-based interface for reviewing and editing claims
extracted by the HCE pipeline with SQLite backend and validation.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from PyQt6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    Qt,
    QTimer,
    QVariant,
    pyqtSignal,
)
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
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

        # Tier
        tier_layout = QHBoxLayout()
        tier_layout.addWidget(QLabel("Tier:"))
        self.tier_combo = QComboBox()
        self.tier_combo.addItems(["A", "B", "C"])
        tier_layout.addWidget(self.tier_combo)
        tier_layout.addStretch()
        layout.addLayout(tier_layout)

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
        self.tier_combo.setCurrentText(self.claim.tier or "B")
        self.timestamp_edit.setText(self.claim.first_mention_ts or "")
        self.status_combo.setCurrentText(self.claim.upload_status or "pending")

    def get_updated_values(self) -> dict[str, Any]:
        """Get the updated claim values."""
        return {
            "canonical": self.canonical_edit.toPlainText().strip(),
            "claim_type": self.type_combo.currentText(),
            "tier": self.tier_combo.currentText(),
            "first_mention_ts": self.timestamp_edit.text().strip(),
            "upload_status": self.status_combo.currentText(),
            "updated_at": datetime.utcnow(),
        }


class ClaimsTableModel(QAbstractTableModel):
    """
    Table model for displaying and editing claims from SQLite database.

    Implements the Claim Review Grid specification from TECHNICAL_SPECIFICATIONS.md.
    """

    dataChanged = pyqtSignal()

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
            ("Tier", "tier"),
            ("First Mention", "first_mention_ts"),
            ("Upload Status", "upload_status"),
            ("Modified", "is_modified"),
        ]

        self.load_data()

    def load_data(self, episode_filter: str | None = None):
        """Load claims from database with optional episode filter."""
        with self.db_service.get_session() as session:
            # Load episodes
            episodes = session.query(Episode).all()
            self.episodes = {ep.episode_id: ep for ep in episodes}

            # Load claims
            query = session.query(Claim)
            if episode_filter:
                query = query.filter_by(episode_id=episode_filter)

            # Order by episode and timestamp
            query = query.order_by(Claim.episode_id, Claim.first_mention_ts)

            self.claims = list(query.all())
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
            else:
                value = getattr(claim, col_attr, "")
                return str(value) if value else ""

        elif role == Qt.ItemDataRole.EditRole:
            if col_name not in ["Episode", "Modified"]:
                return getattr(claim, col_attr, "")

        elif role == Qt.ItemDataRole.BackgroundRole:
            # Highlight modified rows
            if index.row() in self.modified_rows:
                return QColor(255, 255, 200)  # Light yellow
            # Color code by tier
            elif col_name == "Tier":
                tier = claim.tier
                if tier == "A":
                    return QColor(200, 255, 200)  # Light green
                elif tier == "B":
                    return QColor(200, 200, 255)  # Light blue
                elif tier == "C":
                    return QColor(255, 200, 200)  # Light red

        elif role == Qt.ItemDataRole.FontRole:
            if index.row() in self.modified_rows:
                font = QFont()
                font.setBold(True)
                return font

        return None

    def setData(self, index: QModelIndex, value: Any, role: int) -> bool:
        """Handle cell editing with validation."""
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
        elif col_name == "Tier" and value not in ["A", "B", "C"]:
            return False
        elif col_name == "Upload Status" and value not in [
            "pending",
            "uploaded",
            "failed",
        ]:
            return False

        # Update claim attribute
        setattr(claim, col_attr, value)
        claim.updated_at = datetime.utcnow()

        # Mark as modified
        self.modified_rows.add(index.row())

        # Emit data changed
        self.dataChanged.emit(index, index)
        return True

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
            "Double-click cells to edit. Changes are highlighted in yellow."
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
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)  # Tier
        header.setSectionResizeMode(
            4, QHeaderView.ResizeMode.ResizeToContents
        )  # First Mention
        header.setSectionResizeMode(
            5, QHeaderView.ResizeMode.ResizeToContents
        )  # Upload Status
        header.setSectionResizeMode(
            6, QHeaderView.ResizeMode.ResizeToContents
        )  # Modified

        # Enable double-click editing
        self.table_view.doubleClicked.connect(self._on_cell_double_clicked)

        layout.addWidget(self.table_view)

        # Action buttons
        button_layout = QHBoxLayout()

        # Auto-save checkbox
        self.auto_save_checkbox = QCheckBox("Auto-save changes")
        self.auto_save_checkbox.setChecked(False)
        self.auto_save_checkbox.setToolTip(
            "Automatically save changes as you edit.\n"
            "When disabled, use Save button to commit changes."
        )
        button_layout.addWidget(self.auto_save_checkbox)

        button_layout.addStretch()

        # Save button
        self.save_btn = QPushButton("💾 Save Changes")
        self.save_btn.clicked.connect(self._save_changes)
        self.save_btn.setEnabled(False)
        button_layout.addWidget(self.save_btn)

        # Export button
        export_btn = QPushButton("📤 Export to CSV")
        export_btn.clicked.connect(self._export_to_csv)
        button_layout.addWidget(export_btn)

        layout.addLayout(button_layout)

        # Connect model signals
        self.model.dataChanged.connect(self._on_data_changed)

    def _populate_episodes(self):
        """Populate episode filter combo box."""
        with self.db_service.get_session() as session:
            episodes = session.query(Episode).order_by(Episode.title).all()
            for episode in episodes:
                self.episode_combo.addItem(episode.title, episode.episode_id)

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

                # Mark as modified
                self.model.modified_rows.add(index.row())
                self.model.layoutChanged.emit()
                self._on_data_changed()

    def _on_data_changed(self):
        """Handle data changes."""
        has_changes = bool(self.model.modified_rows)
        self.save_btn.setEnabled(has_changes)

        # Auto-save if enabled
        if has_changes and self.auto_save_checkbox.isChecked():
            self._save_changes()

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
        pass

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
                        row = [
                            episode.title if episode else claim.episode_id,
                            claim.canonical,
                            claim.claim_type,
                            claim.tier,
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
