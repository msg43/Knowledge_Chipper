"""Prediction detail page with evidence, graph, and management controls."""

from datetime import datetime

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ...logger import get_logger
from ...services.prediction_service import PredictionService

logger = get_logger(__name__)


class PredictionDetailPage(QWidget):
    """Detail page for viewing and editing a single prediction."""

    prediction_updated = pyqtSignal()  # Emitted when prediction is updated

    def __init__(self, prediction_id: str, parent=None):
        super().__init__(parent)
        self.prediction_id = prediction_id
        self.service = PredictionService()
        self.prediction_data = None
        
        self.setWindowTitle("Prediction Details")
        self.resize(1000, 800)
        
        self._setup_ui()
        self._load_prediction()

    def _setup_ui(self):
        """Setup the UI."""
        layout = QVBoxLayout(self)

        # Header section
        header_widget = self._create_header_section()
        layout.addWidget(header_widget)

        # Graph section
        graph_widget = self._create_graph_section()
        layout.addWidget(graph_widget)

        # Evidence tabs
        self.evidence_tabs = QTabWidget()
        self.evidence_tabs.addTab(self._create_claims_evidence_tab(), "📋 Claims")
        self.evidence_tabs.addTab(self._create_jargon_evidence_tab(), "📖 Jargon")
        self.evidence_tabs.addTab(self._create_people_evidence_tab(), "👥 People")
        self.evidence_tabs.addTab(self._create_concepts_evidence_tab(), "💡 Concepts")
        layout.addWidget(self.evidence_tabs)

        # User notes section
        notes_group = QGroupBox("User Notes")
        notes_layout = QVBoxLayout(notes_group)
        self.user_notes_edit = QTextEdit()
        self.user_notes_edit.setPlaceholderText("Add your reasoning and thoughts about this prediction...")
        notes_layout.addWidget(self.user_notes_edit)
        
        save_notes_btn = QPushButton("💾 Save Notes")
        save_notes_btn.clicked.connect(self._save_user_notes)
        notes_layout.addWidget(save_notes_btn)
        
        layout.addWidget(notes_group)

        # Action buttons
        action_layout = QHBoxLayout()
        
        self.update_btn = QPushButton("📝 Update Confidence/Deadline")
        self.update_btn.clicked.connect(self._update_confidence_deadline)
        action_layout.addWidget(self.update_btn)
        
        self.add_evidence_btn = QPushButton("➕ Add Evidence")
        self.add_evidence_btn.clicked.connect(self._add_evidence)
        action_layout.addWidget(self.add_evidence_btn)
        
        self.resolve_btn = QPushButton("✅ Mark as Resolved")
        self.resolve_btn.clicked.connect(self._resolve_prediction)
        action_layout.addWidget(self.resolve_btn)
        
        self.delete_btn = QPushButton("🗑️ Delete")
        self.delete_btn.setStyleSheet("QPushButton { background-color: #f44336; color: white; }")
        self.delete_btn.clicked.connect(self._delete_prediction)
        action_layout.addWidget(self.delete_btn)
        
        action_layout.addStretch()
        
        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self.close)
        action_layout.addWidget(self.close_btn)
        
        layout.addLayout(action_layout)

    def _create_header_section(self) -> QWidget:
        """Create header with title, confidence, deadline."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)

        # Title
        self.title_label = QLabel()
        self.title_label.setStyleSheet("font-size: 24px; font-weight: bold;")
        self.title_label.setWordWrap(True)
        layout.addWidget(self.title_label)

        # Description
        self.description_label = QLabel()
        self.description_label.setStyleSheet("font-size: 14px; color: #666; margin-top: 5px;")
        self.description_label.setWordWrap(True)
        layout.addWidget(self.description_label)

        # Metrics row
        metrics_layout = QHBoxLayout()
        
        # Confidence
        confidence_widget = QWidget()
        confidence_layout = QVBoxLayout(confidence_widget)
        confidence_layout.setContentsMargins(0, 0, 0, 0)
        confidence_label = QLabel("Current Confidence")
        confidence_label.setStyleSheet("font-size: 12px; color: #666;")
        self.confidence_value = QLabel()
        self.confidence_value.setStyleSheet("font-size: 36px; font-weight: bold; color: #4CAF50;")
        confidence_layout.addWidget(confidence_label)
        confidence_layout.addWidget(self.confidence_value)
        metrics_layout.addWidget(confidence_widget)

        # Deadline
        deadline_widget = QWidget()
        deadline_layout = QVBoxLayout(deadline_widget)
        deadline_layout.setContentsMargins(0, 0, 0, 0)
        deadline_label = QLabel("Deadline")
        deadline_label.setStyleSheet("font-size: 12px; color: #666;")
        self.deadline_value = QLabel()
        self.deadline_value.setStyleSheet("font-size: 24px; font-weight: bold;")
        deadline_layout.addWidget(deadline_label)
        deadline_layout.addWidget(self.deadline_value)
        metrics_layout.addWidget(deadline_widget)

        # Status
        status_widget = QWidget()
        status_layout = QVBoxLayout(status_widget)
        status_layout.setContentsMargins(0, 0, 0, 0)
        status_label = QLabel("Status")
        status_label.setStyleSheet("font-size: 12px; color: #666;")
        self.status_value = QLabel()
        self.status_value.setStyleSheet("font-size: 18px; font-weight: bold; padding: 8px; border-radius: 4px;")
        status_layout.addWidget(status_label)
        status_layout.addWidget(self.status_value)
        metrics_layout.addWidget(status_widget)

        metrics_layout.addStretch()
        layout.addLayout(metrics_layout)

        return widget

    def _create_graph_section(self) -> QWidget:
        """Create graph section for confidence/deadline history."""
        group = QGroupBox("Confidence & Deadline History")
        layout = QVBoxLayout(group)

        self.graph_placeholder = QLabel("Graph will be displayed here\n(Requires matplotlib)")
        self.graph_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.graph_placeholder.setStyleSheet("padding: 40px; background-color: #f5f5f5; border-radius: 4px;")
        self.graph_placeholder.setMinimumHeight(200)
        layout.addWidget(self.graph_placeholder)

        return group

    def _create_claims_evidence_tab(self) -> QWidget:
        """Create tab for claim evidence."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        info_label = QLabel("Claims linked to this prediction (with Pro/Con/Neutral stance)")
        info_label.setStyleSheet("color: #666; margin-bottom: 10px;")
        layout.addWidget(info_label)

        self.claims_list = QListWidget()
        self.claims_list.itemDoubleClicked.connect(lambda item: self._edit_evidence_stance(item, "claim"))
        layout.addWidget(self.claims_list)

        return widget

    def _create_jargon_evidence_tab(self) -> QWidget:
        """Create tab for jargon evidence."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        info_label = QLabel("Jargon/terminology linked to this prediction")
        info_label.setStyleSheet("color: #666; margin-bottom: 10px;")
        layout.addWidget(info_label)

        self.jargon_list = QListWidget()
        self.jargon_list.itemDoubleClicked.connect(lambda item: self._edit_evidence_stance(item, "jargon"))
        layout.addWidget(self.jargon_list)

        return widget

    def _create_people_evidence_tab(self) -> QWidget:
        """Create tab for people evidence."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        info_label = QLabel("People linked to this prediction")
        info_label.setStyleSheet("color: #666; margin-bottom: 10px;")
        layout.addWidget(info_label)

        self.people_list = QListWidget()
        self.people_list.itemDoubleClicked.connect(lambda item: self._edit_evidence_stance(item, "person"))
        layout.addWidget(self.people_list)

        return widget

    def _create_concepts_evidence_tab(self) -> QWidget:
        """Create tab for concept evidence."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        info_label = QLabel("Mental models/concepts linked to this prediction")
        info_label.setStyleSheet("color: #666; margin-bottom: 10px;")
        layout.addWidget(info_label)

        self.concepts_list = QListWidget()
        self.concepts_list.itemDoubleClicked.connect(lambda item: self._edit_evidence_stance(item, "concept"))
        layout.addWidget(self.concepts_list)

        return widget

    def _load_prediction(self):
        """Load prediction data from database."""
        try:
            self.prediction_data = self.service.get_prediction_with_evidence(self.prediction_id)
            if not self.prediction_data:
                QMessageBox.warning(self, "Error", "Prediction not found")
                self.close()
                return

            self._populate_ui()
        except Exception as e:
            logger.error(f"Failed to load prediction: {e}")
            QMessageBox.critical(self, "Error", f"Failed to load prediction:\n{e}")
            self.close()

    def _populate_ui(self):
        """Populate UI with prediction data."""
        pred = self.prediction_data["prediction"]

        # Header
        self.title_label.setText(pred.title)
        self.description_label.setText(pred.description or "No description")
        
        # Confidence
        confidence_pct = pred.confidence * 100
        self.confidence_value.setText(f"{confidence_pct:.0f}%")
        
        # Deadline
        self.deadline_value.setText(pred.deadline or "No deadline")
        
        # Status
        status_text = pred.resolution_status.title()
        self.status_value.setText(status_text)
        status_colors = {
            "Pending": ("#2196F3", "#E3F2FD"),
            "Correct": ("#4CAF50", "#E8F5E9"),
            "Incorrect": ("#f44336", "#FFEBEE"),
            "Ambiguous": ("#FF9800", "#FFF3E0"),
            "Cancelled": ("#9E9E9E", "#F5F5F5"),
        }
        if status_text in status_colors:
            color, bg = status_colors[status_text]
            self.status_value.setStyleSheet(
                f"font-size: 18px; font-weight: bold; padding: 8px; border-radius: 4px; color: {color}; background-color: {bg};"
            )

        # User notes
        self.user_notes_edit.setPlainText(pred.user_notes or "")

        # Evidence
        self._populate_evidence()

        # Graph
        self._populate_graph()

    def _populate_evidence(self):
        """Populate evidence lists."""
        evidence = self.prediction_data["evidence"]

        # Clear lists
        self.claims_list.clear()
        self.jargon_list.clear()
        self.people_list.clear()
        self.concepts_list.clear()

        for ev in evidence:
            item_text = self._format_evidence_item(ev)
            item = QListWidgetItem(item_text)
            item.setData(Qt.ItemDataRole.UserRole, ev)

            # Add to appropriate list
            if ev["evidence_type"] == "claim":
                self.claims_list.addItem(item)
            elif ev["evidence_type"] == "jargon":
                self.jargon_list.addItem(item)
            elif ev["evidence_type"] == "person":
                self.people_list.addItem(item)
            elif ev["evidence_type"] == "concept":
                self.concepts_list.addItem(item)

    def _format_evidence_item(self, evidence: dict) -> str:
        """Format evidence item for display."""
        stance_emoji = {
            "pro": "✅",
            "con": "❌",
            "neutral": "⚪",
        }
        emoji = stance_emoji.get(evidence["stance"], "⚪")
        
        entity_data = evidence.get("entity_data", {})
        
        if evidence["evidence_type"] == "claim":
            text = entity_data.get("canonical", "Unknown claim")
            speaker = entity_data.get("speaker")
            if speaker:
                text = f"{speaker}: {text}"
        elif evidence["evidence_type"] == "jargon":
            term = entity_data.get("term", "Unknown term")
            definition = entity_data.get("definition", "")
            text = f"{term}: {definition[:100]}" if definition else term
        elif evidence["evidence_type"] == "person":
            text = entity_data.get("name", "Unknown person")
        elif evidence["evidence_type"] == "concept":
            text = entity_data.get("name", "Unknown concept")
        else:
            text = "Unknown evidence"

        return f"{emoji} {text}"

    def _populate_graph(self):
        """Populate confidence/deadline graph."""
        try:
            import matplotlib
            matplotlib.use('Qt5Agg')
            from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
            from matplotlib.figure import Figure
            
            history = self.prediction_data["history"]
            if len(history) < 2:
                self.graph_placeholder.setText("Not enough history data to display graph\n(Need at least 2 updates)")
                return

            # Remove placeholder
            self.graph_placeholder.setParent(None)

            # Create matplotlib figure
            fig = Figure(figsize=(8, 4))
            canvas = FigureCanvasQTAgg(fig)
            
            ax1 = fig.add_subplot(111)
            ax1.set_xlabel("Time")
            ax1.set_ylabel("Confidence", color="tab:blue")
            ax1.tick_params(axis="y", labelcolor="tab:blue")
            
            # Plot confidence
            timestamps = [h["timestamp"] for h in history]
            confidences = [h["confidence"] * 100 for h in history]
            ax1.plot(timestamps, confidences, color="tab:blue", marker="o", label="Confidence")
            ax1.set_ylim(0, 100)
            
            # Add grid
            ax1.grid(True, alpha=0.3)
            
            fig.tight_layout()
            
            # Replace placeholder with canvas
            self.graph_placeholder.parent().layout().addWidget(canvas)
            
        except ImportError:
            self.graph_placeholder.setText("matplotlib not available\nInstall matplotlib to see confidence graph")
        except Exception as e:
            logger.error(f"Failed to create graph: {e}")
            self.graph_placeholder.setText(f"Error creating graph:\n{e}")

    def _save_user_notes(self):
        """Save user notes."""
        try:
            notes = self.user_notes_edit.toPlainText()
            success = self.service.db.update_prediction(
                self.prediction_id,
                user_notes=notes,
            )
            if success:
                QMessageBox.information(self, "Success", "Notes saved successfully")
                self.prediction_updated.emit()
            else:
                QMessageBox.warning(self, "Error", "Failed to save notes")
        except Exception as e:
            logger.error(f"Failed to save notes: {e}")
            QMessageBox.critical(self, "Error", f"Failed to save notes:\n{e}")

    def _update_confidence_deadline(self):
        """Open dialog to update confidence/deadline."""
        from ..dialogs.prediction_update_dialog import PredictionUpdateDialog
        
        dialog = PredictionUpdateDialog(self.prediction_id, self)
        if dialog.exec():
            self._load_prediction()
            self.prediction_updated.emit()

    def _add_evidence(self):
        """Open dialog to add evidence."""
        from ..dialogs.add_evidence_dialog import AddEvidenceDialog
        
        dialog = AddEvidenceDialog(self.prediction_id, self)
        if dialog.exec():
            self._load_prediction()
            self.prediction_updated.emit()

    def _edit_evidence_stance(self, item: QListWidgetItem, evidence_type: str):
        """Edit stance for evidence item."""
        evidence = item.data(Qt.ItemDataRole.UserRole)
        if not evidence:
            return

        # Show dialog to change stance
        from PyQt6.QtWidgets import QDialog, QDialogButtonBox
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Edit Evidence Stance")
        layout = QVBoxLayout(dialog)
        
        layout.addWidget(QLabel("Select stance for this evidence:"))
        
        stance_combo = QComboBox()
        stance_combo.addItems(["pro", "con", "neutral"])
        stance_combo.setCurrentText(evidence["stance"])
        layout.addWidget(stance_combo)
        
        notes_edit = QTextEdit()
        notes_edit.setPlaceholderText("Add notes about why this evidence matters...")
        notes_edit.setPlainText(evidence.get("user_notes", ""))
        notes_edit.setMaximumHeight(100)
        layout.addWidget(notes_edit)
        
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        
        if dialog.exec():
            new_stance = stance_combo.currentText()
            new_notes = notes_edit.toPlainText()
            
            try:
                self.service.update_evidence_stance(evidence["evidence_id"], new_stance)
                # TODO: Add method to update evidence notes
                self._load_prediction()
                self.prediction_updated.emit()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to update evidence:\n{e}")

    def _resolve_prediction(self):
        """Mark prediction as resolved."""
        from PyQt6.QtWidgets import QDialog, QDialogButtonBox
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Resolve Prediction")
        layout = QVBoxLayout(dialog)
        
        layout.addWidget(QLabel("How did this prediction resolve?"))
        
        resolution_combo = QComboBox()
        resolution_combo.addItems(["Correct", "Incorrect", "Ambiguous", "Cancelled"])
        layout.addWidget(resolution_combo)
        
        notes_edit = QTextEdit()
        notes_edit.setPlaceholderText("Add notes about the resolution...")
        notes_edit.setMaximumHeight(100)
        layout.addWidget(notes_edit)
        
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        
        if dialog.exec():
            resolution_status = resolution_combo.currentText().lower()
            notes = notes_edit.toPlainText()
            
            try:
                self.service.resolve_prediction(self.prediction_id, resolution_status, notes)
                self._load_prediction()
                self.prediction_updated.emit()
                QMessageBox.information(self, "Success", "Prediction resolved successfully")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to resolve prediction:\n{e}")

    def _delete_prediction(self):
        """Delete prediction after confirmation."""
        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            "Are you sure you want to delete this prediction? This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                self.service.db.delete_prediction(self.prediction_id)
                self.prediction_updated.emit()
                QMessageBox.information(self, "Success", "Prediction deleted successfully")
                self.close()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to delete prediction:\n{e}")

