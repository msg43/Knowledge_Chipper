"""Dialog for creating new predictions."""

from datetime import datetime, timedelta

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QTextEdit,
    QVBoxLayout,
)

from ...logger import get_logger
from ...services.prediction_service import PredictionService

logger = get_logger(__name__)


class PredictionCreationDialog(QDialog):
    """Dialog for creating a new prediction."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.service = PredictionService()
        
        self.setWindowTitle("Create New Prediction")
        self.setMinimumWidth(600)
        
        self._setup_ui()

    def _setup_ui(self):
        """Setup the UI."""
        layout = QVBoxLayout(self)

        # Title
        title_label = QLabel("Create New Prediction")
        title_label.setStyleSheet("font-size: 18px; font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(title_label)

        # Form
        form_layout = QFormLayout()

        # Title field
        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("e.g., 'Bitcoin will reach $100k by EOY 2026'")
        form_layout.addRow("Title:*", self.title_edit)

        # Description field
        self.description_edit = QTextEdit()
        self.description_edit.setPlaceholderText("Detailed prediction statement...")
        self.description_edit.setMaximumHeight(100)
        form_layout.addRow("Description:", self.description_edit)

        # Confidence field
        self.confidence_spin = QDoubleSpinBox()
        self.confidence_spin.setRange(0.0, 100.0)
        self.confidence_spin.setValue(50.0)
        self.confidence_spin.setSuffix("%")
        self.confidence_spin.setDecimals(0)
        form_layout.addRow("Initial Confidence:*", self.confidence_spin)

        # Deadline field
        self.deadline_edit = QDateEdit()
        self.deadline_edit.setCalendarPopup(True)
        self.deadline_edit.setDate(datetime.now().date() + timedelta(days=365))
        self.deadline_edit.setDisplayFormat("yyyy-MM-dd")
        form_layout.addRow("Deadline:*", self.deadline_edit)

        # Privacy field
        self.privacy_combo = QComboBox()
        self.privacy_combo.addItems(["Private", "Public"])
        form_layout.addRow("Privacy:", self.privacy_combo)

        # User notes
        self.notes_edit = QTextEdit()
        self.notes_edit.setPlaceholderText("Your reasoning and thoughts...")
        self.notes_edit.setMaximumHeight(100)
        form_layout.addRow("Notes:", self.notes_edit)

        layout.addLayout(form_layout)

        # Help text
        help_label = QLabel("* Required fields")
        help_label.setStyleSheet("color: #666; font-size: 12px; font-style: italic;")
        layout.addWidget(help_label)

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._create_prediction)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _create_prediction(self):
        """Validate and create prediction."""
        # Validate required fields
        title = self.title_edit.text().strip()
        if not title:
            QMessageBox.warning(self, "Validation Error", "Title is required")
            return

        # Get form values
        description = self.description_edit.toPlainText().strip() or None
        confidence = self.confidence_spin.value() / 100.0  # Convert to 0.0-1.0
        deadline = self.deadline_edit.date().toString("yyyy-MM-dd")
        privacy = self.privacy_combo.currentText().lower()
        notes = self.notes_edit.toPlainText().strip() or None

        # Create prediction
        try:
            prediction_id = self.service.create_prediction(
                title=title,
                description=description,
                confidence=confidence,
                deadline=deadline,
                privacy_status=privacy,
                user_notes=notes,
            )
            
            logger.info(f"Created prediction: {prediction_id}")
            QMessageBox.information(self, "Success", "Prediction created successfully!")
            self.accept()
            
        except Exception as e:
            logger.error(f"Failed to create prediction: {e}")
            QMessageBox.critical(self, "Error", f"Failed to create prediction:\n{e}")

