"""Dialog for adding evidence to predictions."""

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QTextEdit,
    QVBoxLayout,
)

from ...database.models import Claim, Concept, JargonTerm, Person
from ...database.service import DatabaseService
from ...logger import get_logger
from ...services.prediction_service import PredictionService

logger = get_logger(__name__)


class EvidenceSearchWorker(QThread):
    """Worker thread for searching evidence entities."""

    results_ready = pyqtSignal(list)
    search_error = pyqtSignal(str)

    def __init__(self, entity_type: str, query: str, parent=None):
        super().__init__(parent)
        self.entity_type = entity_type
        self.query = query.lower()
        self.db = DatabaseService()

    def run(self):
        """Search for entities."""
        try:
            results = self._search_entities()
            self.results_ready.emit(results)
        except Exception as e:
            logger.error(f"Search failed: {e}")
            self.search_error.emit(str(e))

    def _search_entities(self) -> list[dict]:
        """Search entities based on type and query."""
        results = []

        try:
            with self.db.get_session() as session:
                if self.entity_type == "claim":
                    entities = session.query(Claim).filter(
                        Claim.canonical.contains(self.query)
                    ).limit(50).all()
                    
                    for entity in entities:
                        results.append({
                            "id": entity.claim_id,
                            "text": f"{entity.canonical[:100]}...",
                            "subtitle": f"Tier: {entity.tier}, Speaker: {entity.speaker or 'Unknown'}",
                        })

                elif self.entity_type == "jargon":
                    entities = session.query(JargonTerm).filter(
                        JargonTerm.term.contains(self.query)
                    ).limit(50).all()
                    
                    for entity in entities:
                        results.append({
                            "id": entity.term_id,
                            "text": entity.term,
                            "subtitle": entity.definition[:100] if entity.definition else "",
                        })

                elif self.entity_type == "person":
                    entities = session.query(Person).filter(
                        Person.name.contains(self.query)
                    ).limit(50).all()
                    
                    for entity in entities:
                        results.append({
                            "id": entity.person_id,
                            "text": entity.name,
                            "subtitle": entity.description[:100] if entity.description else "",
                        })

                elif self.entity_type == "concept":
                    entities = session.query(Concept).filter(
                        Concept.name.contains(self.query)
                    ).limit(50).all()
                    
                    for entity in entities:
                        results.append({
                            "id": entity.concept_id,
                            "text": entity.name,
                            "subtitle": entity.description[:100] if entity.description else "",
                        })

        except Exception as e:
            logger.error(f"Entity search failed: {e}")

        return results


class AddEvidenceDialog(QDialog):
    """Dialog for searching and adding evidence to prediction."""

    def __init__(self, prediction_id: str, parent=None):
        super().__init__(parent)
        self.prediction_id = prediction_id
        self.service = PredictionService()
        self.search_worker = None
        self.selected_entity = None
        
        self.setWindowTitle("Add Evidence")
        self.setMinimumSize(700, 500)
        
        self._setup_ui()

    def _setup_ui(self):
        """Setup the UI."""
        layout = QVBoxLayout(self)

        # Title
        title_label = QLabel("Add Evidence to Prediction")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(title_label)

        # Entity type selector
        type_layout = QFormLayout()
        self.entity_type_combo = QComboBox()
        self.entity_type_combo.addItems(["Claim", "Jargon", "Person", "Concept"])
        self.entity_type_combo.currentTextChanged.connect(self._on_type_changed)
        type_layout.addRow("Evidence Type:", self.entity_type_combo)
        layout.addLayout(type_layout)

        # Search box
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search for claims, jargon, people, or concepts...")
        self.search_box.textChanged.connect(self._on_search_changed)
        layout.addWidget(self.search_box)

        # Results list
        results_label = QLabel("Search Results:")
        results_label.setStyleSheet("margin-top: 10px; font-weight: bold;")
        layout.addWidget(results_label)

        self.results_list = QListWidget()
        self.results_list.itemClicked.connect(self._on_item_selected)
        layout.addWidget(self.results_list)

        # Stance selector
        stance_layout = QFormLayout()
        self.stance_combo = QComboBox()
        self.stance_combo.addItems(["Pro", "Con", "Neutral"])
        self.stance_combo.setCurrentText("Neutral")
        stance_layout.addRow("Stance:", self.stance_combo)
        layout.addLayout(stance_layout)

        # Notes
        notes_label = QLabel("Notes (why this evidence matters):")
        layout.addWidget(notes_label)
        
        self.notes_edit = QTextEdit()
        self.notes_edit.setPlaceholderText("Explain why this evidence supports or contradicts your prediction...")
        self.notes_edit.setMaximumHeight(100)
        layout.addWidget(self.notes_edit)

        # Status
        self.status_label = QLabel("Enter search term to find evidence")
        self.status_label.setStyleSheet("color: #666; font-style: italic;")
        layout.addWidget(self.status_label)

        # Buttons
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
        self.buttons.accepted.connect(self._add_evidence)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

    def _on_type_changed(self, text: str):
        """Handle entity type change."""
        self.results_list.clear()
        self.selected_entity = None
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
        self.status_label.setText(f"Search for {text.lower()}...")

    def _on_search_changed(self, text: str):
        """Handle search text change."""
        if len(text) < 2:
            self.results_list.clear()
            self.status_label.setText("Enter at least 2 characters to search")
            return

        # Start search
        self._search_evidence()

    def _search_evidence(self):
        """Start evidence search."""
        if self.search_worker and self.search_worker.isRunning():
            return

        entity_type = self.entity_type_combo.currentText().lower()
        query = self.search_box.text().strip()

        self.status_label.setText("Searching...")
        self.results_list.clear()

        self.search_worker = EvidenceSearchWorker(entity_type, query, self)
        self.search_worker.results_ready.connect(self._on_results_ready)
        self.search_worker.search_error.connect(self._on_search_error)
        self.search_worker.start()

    def _on_results_ready(self, results: list[dict]):
        """Handle search results."""
        self.results_list.clear()

        if not results:
            self.status_label.setText("No results found")
            return

        for result in results:
            item = QListWidgetItem(f"{result['text']}\n  {result['subtitle']}")
            item.setData(Qt.ItemDataRole.UserRole, result)
            self.results_list.addItem(item)

        self.status_label.setText(f"Found {len(results)} result{'s' if len(results) != 1 else ''}")

    def _on_search_error(self, error_msg: str):
        """Handle search error."""
        self.status_label.setText(f"Search error: {error_msg}")
        QMessageBox.warning(self, "Search Error", f"Failed to search:\n{error_msg}")

    def _on_item_selected(self, item: QListWidgetItem):
        """Handle item selection."""
        self.selected_entity = item.data(Qt.ItemDataRole.UserRole)
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(True)
        self.status_label.setText("Ready to add evidence")

    def _add_evidence(self):
        """Add selected evidence to prediction."""
        if not self.selected_entity:
            QMessageBox.warning(self, "No Selection", "Please select an evidence item")
            return

        entity_type = self.entity_type_combo.currentText().lower()
        entity_id = self.selected_entity["id"]
        stance = self.stance_combo.currentText().lower()
        notes = self.notes_edit.toPlainText().strip() or None

        try:
            evidence_id = self.service.add_evidence(
                prediction_id=self.prediction_id,
                evidence_type=entity_type,
                entity_id=entity_id,
                stance=stance,
                notes=notes,
            )

            if evidence_id:
                QMessageBox.information(self, "Success", "Evidence added successfully!")
                self.accept()
            else:
                QMessageBox.warning(self, "Error", "Failed to add evidence")

        except ValueError as e:
            # Entity already added or validation error
            QMessageBox.warning(self, "Validation Error", str(e))
        except Exception as e:
            logger.error(f"Failed to add evidence: {e}")
            QMessageBox.critical(self, "Error", f"Failed to add evidence:\n{e}")

