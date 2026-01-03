"""Dialog for updating prediction confidence and deadline."""

from datetime import datetime

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
)

from ...logger import get_logger
from ...services.prediction_service import PredictionService

logger = get_logger(__name__)


class PredictionUpdateDialog(QDialog):
    """Dialog for updating prediction confidence and/or deadline."""

    def __init__(self, prediction_id: str, parent=None):
        super().__init__(parent)
        self.prediction_id = prediction_id
        self.service = PredictionService()
        
        self.setWindowTitle("Update Prediction")
        self.setMinimumWidth(500)
        
        self._load_prediction()
        self._setup_ui()

    def _load_prediction(self):
        """Load current prediction data."""
        try:
            self.prediction = self.service.db.get_prediction(self.prediction_id)
            if not self.prediction:
                raise ValueError(f"Prediction {self.prediction_id} not found")
        except Exception as e:
            logger.error(f"Failed to load prediction: {e}")
            QMessageBox.critical(None, "Error", f"Failed to load prediction:\n{e}")
            raise

    def _setup_ui(self):
        """Setup the UI."""
        layout = QVBoxLayout(self)

        # Title
        title_label = QLabel(f"Update: {self.prediction.title}")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold; margin-bottom: 10px;")
        title_label.setWordWrap(True)
        layout.addWidget(title_label)

        # Form
        form_layout = QFormLayout()

        # Current confidence
        current_conf = self.prediction.confidence * 100
        current_label = QLabel(f"Current: {current_conf:.0f}%")
        current_label.setStyleSheet("color: #666;")
        
        self.confidence_spin = QDoubleSpinBox()
        self.confidence_spin.setRange(0.0, 100.0)
        self.confidence_spin.setValue(current_conf)
        self.confidence_spin.setSuffix("%")
        self.confidence_spin.setDecimals(0)
        
        conf_widget = QVBoxLayout()
        conf_widget.addWidget(current_label)
        conf_widget.addWidget(self.confidence_spin)
        form_layout.addRow("New Confidence:", conf_widget)

        # Current deadline
        deadline_current_label = QLabel(f"Current: {self.prediction.deadline}")
        deadline_current_label.setStyleSheet("color: #666;")
        
        self.deadline_edit = QDateEdit()
        self.deadline_edit.setCalendarPopup(True)
        self.deadline_edit.setDisplayFormat("yyyy-MM-dd")
        if self.prediction.deadline:
            try:
                deadline_date = datetime.strptime(self.prediction.deadline, "%Y-%m-%d").date()
                self.deadline_edit.setDate(deadline_date)
            except ValueError:
                pass
        
        deadline_widget = QVBoxLayout()
        deadline_widget.addWidget(deadline_current_label)
        deadline_widget.addWidget(self.deadline_edit)
        form_layout.addRow("New Deadline:", deadline_widget)

        # Change reason
        self.reason_edit = QLineEdit()
        self.reason_edit.setPlaceholderText("Why are you updating? (optional)")
        form_layout.addRow("Reason for change:", self.reason_edit)

        layout.addLayout(form_layout)

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._update_prediction)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _update_prediction(self):
        """Update prediction."""
        try:
            new_confidence = self.confidence_spin.value() / 100.0
            new_deadline = self.deadline_edit.date().toString("yyyy-MM-dd")
            reason = self.reason_edit.text().strip() or None

            # Check if anything changed
            if (new_confidence == self.prediction.confidence and 
                new_deadline == self.prediction.deadline):
                QMessageBox.information(self, "No Changes", "No changes were made")
                self.reject()
                return

            # Update
            success = self.service.db.update_prediction(
                self.prediction_id,
                confidence=new_confidence,
                deadline=new_deadline,
                change_reason=reason,
            )

            if success:
                QMessageBox.information(self, "Success", "Prediction updated successfully!")
                self.accept()
            else:
                QMessageBox.warning(self, "Error", "Failed to update prediction")

        except Exception as e:
            logger.error(f"Failed to update prediction: {e}")
            QMessageBox.critical(self, "Error", f"Failed to update prediction:\n{e}")

