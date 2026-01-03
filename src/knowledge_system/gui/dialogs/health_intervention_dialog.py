"""Dialog for creating/editing health interventions."""

import uuid

from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from ...database import DatabaseService, HealthIntervention
from ...logger import get_logger
from ...services.entity_sync import get_entity_sync_service

logger = get_logger(__name__)

# Dropdown options from spreadsheet
BODY_SYSTEMS = [
    "",
    "Skeletal System",
    "Muscular System",
    "Respiratory System",
    "Circulatory System",
    "Digestive System",
    "Nervous System",
    "Endocrine System",
    "Urinary System",
    "Lymphatic System",
    "Integumentary System",
    "Reproductive System",
]

ORGANS = [
    "",
    "Brain",
    "Heart",
    "Lungs",
    "Liver",
    "Kidneys",
    "Stomach",
    "Intestines",
    "Pancreas",
    "Spleen",
    "Gallbladder",
    "Bladder",
    "Skin",
    "Eyes",
    "Ears",
    "Nose",
    "Tongue",
    "Muscles",
    "Bones",
    "Thyroid",
    "Adrenal glands",
]

PETE_ATTIA_CATEGORIES = [
    "",
    "Metabolic dysfunction",
    "Cancer",
    "Cardiovascular disease",
    "Neurodegenerative disease",
]


class HealthInterventionDialog(QDialog):
    """Dialog for creating or editing a health intervention."""

    def __init__(self, intervention: HealthIntervention = None, parent=None):
        super().__init__(parent)
        self.intervention = intervention
        self.db = DatabaseService()
        
        self.setWindowTitle("Edit Intervention" if intervention else "New Intervention")
        self.setMinimumWidth(600)
        
        self._setup_ui()
        
        if intervention:
            self._load_intervention_data()

    def _setup_ui(self):
        """Setup the dialog UI."""
        layout = QVBoxLayout(self)

        # Form layout for fields
        form_layout = QFormLayout()

        # Active checkbox
        self.active_checkbox = QCheckBox("Active")
        self.active_checkbox.setChecked(True)
        form_layout.addRow("Status:", self.active_checkbox)

        # Name field (required)
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("e.g., Red Light Therapy Cap")
        form_layout.addRow("Name:*", self.name_edit)

        # Body System dropdown
        self.body_system_combo = QComboBox()
        self.body_system_combo.addItems(BODY_SYSTEMS)
        self.body_system_combo.setEditable(True)
        form_layout.addRow("Body System:", self.body_system_combo)

        # Organs dropdown
        self.organs_combo = QComboBox()
        self.organs_combo.addItems(ORGANS)
        self.organs_combo.setEditable(True)
        form_layout.addRow("Organs:", self.organs_combo)

        # Author field
        self.author_edit = QLineEdit()
        self.author_edit.setPlaceholderText("e.g., Peter Attia")
        form_layout.addRow("Author:", self.author_edit)

        # Frequency field
        self.frequency_edit = QLineEdit()
        self.frequency_edit.setPlaceholderText("e.g., 1 x Day, 2 x Week")
        form_layout.addRow("Frequency:", self.frequency_edit)

        # Metric field
        self.metric_edit = QLineEdit()
        self.metric_edit.setPlaceholderText("How to measure effectiveness")
        form_layout.addRow("Metric:", self.metric_edit)

        # Pete Attia Category dropdown
        self.pete_attia_category_combo = QComboBox()
        self.pete_attia_category_combo.addItems(PETE_ATTIA_CATEGORIES)
        self.pete_attia_category_combo.setEditable(True)
        form_layout.addRow("Pete Attia Category:", self.pete_attia_category_combo)

        # PA Subcategory field
        self.pa_subcategory_edit = QLineEdit()
        form_layout.addRow("PA Subcategory:", self.pa_subcategory_edit)

        # Source 1 field
        self.source_1_edit = QLineEdit()
        self.source_1_edit.setPlaceholderText("Reference or source")
        form_layout.addRow("Source 1:", self.source_1_edit)

        # Source 2 field
        self.source_2_edit = QLineEdit()
        form_layout.addRow("Source 2:", self.source_2_edit)

        # Source 3 field
        self.source_3_edit = QLineEdit()
        form_layout.addRow("Source 3:", self.source_3_edit)

        layout.addLayout(form_layout)

        # Matt Notes text area
        notes_label = QLabel("Matt Notes:")
        layout.addWidget(notes_label)
        
        self.matt_notes_edit = QTextEdit()
        self.matt_notes_edit.setPlaceholderText("Personal notes and observations...")
        self.matt_notes_edit.setMaximumHeight(100)
        layout.addWidget(self.matt_notes_edit)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)

        self.save_button = QPushButton("Save")
        self.save_button.setDefault(True)
        self.save_button.clicked.connect(self._save_intervention)
        self.save_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                padding: 8px 16px;
                border: none;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        button_layout.addWidget(self.save_button)

        layout.addLayout(button_layout)

    def _load_intervention_data(self):
        """Load existing intervention data into form."""
        if not self.intervention:
            return

        self.active_checkbox.setChecked(self.intervention.active)
        self.name_edit.setText(self.intervention.name or "")
        self.body_system_combo.setCurrentText(self.intervention.body_system or "")
        self.organs_combo.setCurrentText(self.intervention.organs or "")
        self.author_edit.setText(self.intervention.author or "")
        self.frequency_edit.setText(self.intervention.frequency or "")
        self.metric_edit.setText(self.intervention.metric or "")
        self.pete_attia_category_combo.setCurrentText(self.intervention.pete_attia_category or "")
        self.pa_subcategory_edit.setText(self.intervention.pa_subcategory or "")
        self.source_1_edit.setText(self.intervention.source_1 or "")
        self.source_2_edit.setText(self.intervention.source_2 or "")
        self.source_3_edit.setText(self.intervention.source_3 or "")
        self.matt_notes_edit.setPlainText(self.intervention.matt_notes or "")

    def _save_intervention(self):
        """Save the intervention to database."""
        # Validate required fields
        if not self.name_edit.text().strip():
            logger.warning("Intervention name is required")
            return

        try:
            with self.db.get_session() as session:
                if self.intervention:
                    # Update existing
                    intervention = session.query(HealthIntervention).filter_by(
                        intervention_id=self.intervention.intervention_id
                    ).first()
                else:
                    # Create new
                    intervention = HealthIntervention()
                    intervention.intervention_id = str(uuid.uuid4())
                    session.add(intervention)

                # Update fields
                intervention.active = self.active_checkbox.isChecked()
                intervention.name = self.name_edit.text().strip()
                intervention.body_system = self.body_system_combo.currentText().strip() or None
                intervention.organs = self.organs_combo.currentText().strip() or None
                intervention.author = self.author_edit.text().strip() or None
                intervention.frequency = self.frequency_edit.text().strip() or None
                intervention.metric = self.metric_edit.text().strip() or None
                intervention.pete_attia_category = self.pete_attia_category_combo.currentText().strip() or None
                intervention.pa_subcategory = self.pa_subcategory_edit.text().strip() or None
                intervention.source_1 = self.source_1_edit.text().strip() or None
                intervention.source_2 = self.source_2_edit.text().strip() or None
                intervention.source_3 = self.source_3_edit.text().strip() or None
                intervention.matt_notes = self.matt_notes_edit.toPlainText().strip() or None

                session.commit()
                intervention_id = intervention.intervention_id
                logger.info(f"Saved intervention: {intervention.name}")
                
                # Auto-sync to web (unified sync service)
                sync_service = get_entity_sync_service()
                if sync_service.is_sync_enabled():
                    logger.info(f"Auto-syncing intervention {intervention_id} to GetReceipts...")
                    sync_result = sync_service.sync_health_intervention(intervention_id)
                    if sync_result.get("success"):
                        logger.info(f"✅ Intervention synced to web")
                    else:
                        logger.warning(f"⚠️ Intervention not synced: {sync_result.get('reason')}")
                
                self.accept()

        except Exception as e:
            logger.error(f"Failed to save intervention: {e}")
            # Could show error dialog here

