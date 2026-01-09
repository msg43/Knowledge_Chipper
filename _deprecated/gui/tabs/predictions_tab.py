"""Predictions tab for personal forecasting system."""

from datetime import datetime

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ...logger import get_logger
from ...services.prediction_service import PredictionService
from ..components.base_tab import BaseTab

logger = get_logger(__name__)


class PredictionLoadWorker(QThread):
    """Worker thread for loading predictions."""

    predictions_loaded = pyqtSignal(list)
    load_error = pyqtSignal(str)

    def __init__(self, privacy_filter: str = None, status_filter: str = None, search_query: str = None, parent=None):
        super().__init__(parent)
        self.privacy_filter = privacy_filter
        self.status_filter = status_filter
        self.search_query = search_query
        self.service = PredictionService()

    def run(self):
        """Load predictions from database."""
        try:
            predictions = self.service.search_predictions(
                query=self.search_query,
                privacy_status=self.privacy_filter if self.privacy_filter != "All" else None,
                resolution_status=self.status_filter if self.status_filter != "All" else None,
            )
            self.predictions_loaded.emit(predictions)
        except Exception as e:
            logger.error(f"Failed to load predictions: {e}")
            self.load_error.emit(str(e))


class PredictionsTab(BaseTab):
    """Tab for viewing and managing predictions."""

    def __init__(self, parent=None):
        self.service = PredictionService()
        self.load_worker = None
        self.current_predictions = []
        self.tab_name = "🔮 Predictions"
        super().__init__(parent)

    def _setup_ui(self):
        """Setup the predictions list UI."""
        layout = QVBoxLayout(self)

        # Title
        title_label = QLabel("Predictions")
        title_label.setStyleSheet("font-size: 20px; font-weight: bold; margin: 10px;")
        layout.addWidget(title_label)

        # Description
        desc_label = QLabel("Track your predictions with confidence levels and deadlines. Link evidence from your knowledge base.")
        desc_label.setStyleSheet("margin: 0px 10px 10px 10px; color: #666;")
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)

        # Filter bar
        filter_layout = QHBoxLayout()
        filter_layout.setContentsMargins(10, 5, 10, 5)

        # Privacy filter
        filter_layout.addWidget(QLabel("Privacy:"))
        self.privacy_filter = QComboBox()
        self.privacy_filter.addItems(["All", "Private", "Public"])
        self.privacy_filter.currentTextChanged.connect(self._refresh_predictions)
        filter_layout.addWidget(self.privacy_filter)

        # Status filter
        filter_layout.addWidget(QLabel("Status:"))
        self.status_filter = QComboBox()
        self.status_filter.addItems(["All", "Pending", "Correct", "Incorrect", "Ambiguous", "Cancelled"])
        self.status_filter.currentTextChanged.connect(self._refresh_predictions)
        filter_layout.addWidget(self.status_filter)

        # Search box
        filter_layout.addWidget(QLabel("Search:"))
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search predictions...")
        self.search_box.textChanged.connect(self._on_search_changed)
        filter_layout.addWidget(self.search_box)

        filter_layout.addStretch()
        layout.addLayout(filter_layout)

        # Action buttons
        button_layout = QHBoxLayout()
        button_layout.setContentsMargins(10, 5, 10, 5)

        self.new_prediction_button = QPushButton("➕ New Prediction")
        self.new_prediction_button.clicked.connect(self._create_new_prediction)
        self.new_prediction_button.setStyleSheet("""
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
        button_layout.addWidget(self.new_prediction_button)

        self.refresh_button = QPushButton("🔄 Refresh")
        self.refresh_button.clicked.connect(self._refresh_predictions)
        button_layout.addWidget(self.refresh_button)

        button_layout.addStretch()
        layout.addLayout(button_layout)

        # Predictions table
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Title", "Confidence", "Deadline", "Status"])
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(1, 120)
        self.table.setColumnWidth(2, 120)
        self.table.setColumnWidth(3, 120)
        self.table.cellDoubleClicked.connect(self._open_prediction_detail)
        self.table.setStyleSheet("""
            QTableWidget {
                border: 1px solid #ddd;
                border-radius: 4px;
            }
            QTableWidget::item {
                padding: 8px;
            }
            QTableWidget::item:selected {
                background-color: #e3f2fd;
            }
        """)
        layout.addWidget(self.table)

        # Status label
        self.status_label = QLabel("No predictions yet. Click 'New Prediction' to create one.")
        self.status_label.setStyleSheet("margin: 10px; color: #666; font-style: italic;")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label)

        # Load initial predictions
        self._refresh_predictions()

    def _on_search_changed(self, text: str):
        """Handle search text change with debouncing."""
        # Simple implementation: refresh immediately
        # Could add debouncing for better performance
        self._refresh_predictions()

    def _refresh_predictions(self):
        """Reload predictions from database."""
        if self.load_worker and self.load_worker.isRunning():
            return

        # Get filter values
        privacy = self.privacy_filter.currentText().lower() if self.privacy_filter.currentText() != "All" else None
        status = self.status_filter.currentText().lower() if self.status_filter.currentText() != "All" else None
        search = self.search_box.text().strip() if self.search_box.text() else None

        # Start worker
        self.load_worker = PredictionLoadWorker(privacy, status, search, self)
        self.load_worker.predictions_loaded.connect(self._on_predictions_loaded)
        self.load_worker.load_error.connect(self._on_load_error)
        self.load_worker.start()

        # Update status
        self.status_label.setText("Loading predictions...")
        self.new_prediction_button.setEnabled(False)
        self.refresh_button.setEnabled(False)

    def _on_predictions_loaded(self, predictions):
        """Handle predictions loaded successfully."""
        self.current_predictions = predictions
        self._populate_table(predictions)

        # Update status
        count = len(predictions)
        if count == 0:
            self.status_label.setText("No predictions found. Click 'New Prediction' to create one.")
        else:
            self.status_label.setText(f"Showing {count} prediction{'s' if count != 1 else ''}")

        self.new_prediction_button.setEnabled(True)
        self.refresh_button.setEnabled(True)

    def _on_load_error(self, error_msg: str):
        """Handle prediction load error."""
        self.status_label.setText(f"Error loading predictions: {error_msg}")
        self.new_prediction_button.setEnabled(True)
        self.refresh_button.setEnabled(True)
        QMessageBox.warning(self, "Load Error", f"Failed to load predictions:\n{error_msg}")

    def _populate_table(self, predictions):
        """Populate table with predictions."""
        self.table.setRowCount(0)

        for prediction in predictions:
            row = self.table.rowCount()
            self.table.insertRow(row)

            # Title (clickable)
            title_item = QTableWidgetItem(prediction.title)
            title_item.setData(Qt.ItemDataRole.UserRole, prediction.prediction_id)
            title_item.setForeground(QColor("#0066cc"))
            title_item.setToolTip("Double-click to open prediction details")
            self.table.setItem(row, 0, title_item)

            # Confidence (formatted as percentage)
            confidence_pct = prediction.confidence * 100
            confidence_item = QTableWidgetItem(f"{confidence_pct:.0f}%")
            confidence_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            
            # Color code by confidence
            if confidence_pct >= 80:
                confidence_item.setForeground(QColor("#4CAF50"))  # Green
            elif confidence_pct >= 50:
                confidence_item.setForeground(QColor("#FF9800"))  # Orange
            else:
                confidence_item.setForeground(QColor("#f44336"))  # Red
            
            self.table.setItem(row, 1, confidence_item)

            # Deadline
            deadline_item = QTableWidgetItem(prediction.deadline or "No deadline")
            deadline_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            
            # Check if deadline is past
            if prediction.deadline and prediction.resolution_status == "pending":
                try:
                    deadline_date = datetime.strptime(prediction.deadline, "%Y-%m-%d").date()
                    if deadline_date < datetime.now().date():
                        deadline_item.setForeground(QColor("#f44336"))  # Red for overdue
                except ValueError:
                    pass
            
            self.table.setItem(row, 2, deadline_item)

            # Status
            status_text = prediction.resolution_status.title()
            status_item = QTableWidgetItem(status_text)
            status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            
            # Color code by status
            status_colors = {
                "Pending": "#2196F3",  # Blue
                "Correct": "#4CAF50",  # Green
                "Incorrect": "#f44336",  # Red
                "Ambiguous": "#FF9800",  # Orange
                "Cancelled": "#9E9E9E",  # Gray
            }
            if status_text in status_colors:
                status_item.setForeground(QColor(status_colors[status_text]))
            
            self.table.setItem(row, 3, status_item)

    def _create_new_prediction(self):
        """Open dialog to create new prediction."""
        from ..dialogs.prediction_creation_dialog import PredictionCreationDialog
        
        dialog = PredictionCreationDialog(self)
        if dialog.exec():
            self._refresh_predictions()

    def _open_prediction_detail(self, row, column):
        """Open detail page for selected prediction."""
        title_item = self.table.item(row, 0)
        if not title_item:
            return
        
        prediction_id = title_item.data(Qt.ItemDataRole.UserRole)
        
        # Import here to avoid circular dependency
        from .prediction_detail_page import PredictionDetailPage
        
        # Open detail page in a new window or tab
        detail_page = PredictionDetailPage(prediction_id, parent=self)
        detail_page.prediction_updated.connect(self._refresh_predictions)
        detail_page.show()

