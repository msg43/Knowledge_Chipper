"""Personal Health Dashboard - standalone window for tracking interventions, metrics, and issues."""

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ...database import (
    DatabaseService,
    HealthIntervention,
    HealthIssue,
    HealthMetric,
)
from ...logger import get_logger
from .health_intervention_dialog import HealthInterventionDialog
from .health_issue_dialog import HealthIssueDialog
from .health_metric_dialog import HealthMetricDialog

logger = get_logger(__name__)


class HealthDataLoader(QThread):
    """Worker thread for loading health tracking data."""

    data_loaded = pyqtSignal(str, list)  # section_type, data
    load_error = pyqtSignal(str)

    def __init__(self, section_type: str, parent=None):
        super().__init__(parent)
        self.section_type = section_type
        self.db = DatabaseService()

    def run(self):
        """Load health tracking data from database."""
        try:
            with self.db.get_session() as session:
                if self.section_type == "interventions":
                    results = session.query(HealthIntervention).order_by(
                        HealthIntervention.active.desc(),
                        HealthIntervention.name
                    ).all()
                elif self.section_type == "metrics":
                    results = session.query(HealthMetric).order_by(
                        HealthMetric.active.desc(),
                        HealthMetric.name
                    ).all()
                elif self.section_type == "issues":
                    results = session.query(HealthIssue).order_by(
                        HealthIssue.active.desc(),
                        HealthIssue.name
                    ).all()
                else:
                    results = []
                
                self.data_loaded.emit(self.section_type, results)
                
        except Exception as e:
            logger.error(f"Failed to load {self.section_type}: {e}")
            self.load_error.emit(str(e))


class HealthDashboardWindow(QMainWindow):
    """Standalone window for personal health tracking."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.db = DatabaseService()
        self.load_workers = {}
        
        self.setWindowTitle("Personal Health Dashboard")
        self.setMinimumSize(1200, 800)
        
        self._setup_ui()
        self._load_all_data()

    def _setup_ui(self):
        """Setup the dashboard UI."""
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # Title
        title_label = QLabel("Personal Health Dashboard")
        title_label.setStyleSheet("font-size: 24px; font-weight: bold; margin: 10px;")
        main_layout.addWidget(title_label)

        # Description
        desc_label = QLabel(
            "Track your health interventions, metrics, and issues. All data stored locally."
        )
        desc_label.setStyleSheet("margin: 0px 10px 10px 10px; color: #666;")
        main_layout.addWidget(desc_label)

        # Splitter for 3 sections
        splitter = QSplitter(Qt.Orientation.Vertical)
        main_layout.addWidget(splitter)

        # Section 1: Interventions
        interventions_widget = self._create_section(
            "Interventions",
            "Things you're doing or considering (supplements, therapies, exercises)",
            self._create_interventions_table,
            self._add_intervention
        )
        splitter.addWidget(interventions_widget)

        # Section 2: Metrics
        metrics_widget = self._create_section(
            "Metrics",
            "Health measurements and test results (VO2 Max, BMI, blood tests)",
            self._create_metrics_table,
            self._add_metric
        )
        splitter.addWidget(metrics_widget)

        # Section 3: Health Issues
        issues_widget = self._create_section(
            "Health Issues",
            "Conditions being monitored or treated",
            self._create_issues_table,
            self._add_issue
        )
        splitter.addWidget(issues_widget)

        # Set initial sizes (equal)
        splitter.setSizes([300, 300, 300])

    def _create_section(self, title: str, description: str, create_table_func, add_func):
        """Create a section widget with table and buttons."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(5, 5, 5, 5)

        # Header
        header_layout = QHBoxLayout()
        
        title_label = QLabel(title)
        title_label.setStyleSheet("font-size: 18px; font-weight: bold;")
        header_layout.addWidget(title_label)
        
        header_layout.addStretch()
        
        # Add New button
        add_button = QPushButton(f"➕ Add {title[:-1]}")  # Remove 's' from title
        add_button.clicked.connect(add_func)
        add_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                padding: 6px 12px;
                border: none;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        header_layout.addWidget(add_button)
        
        layout.addLayout(header_layout)

        # Description
        desc_label = QLabel(description)
        desc_label.setStyleSheet("color: #666; font-size: 12px;")
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)

        # Table
        table = create_table_func()
        layout.addWidget(table)

        return widget

    def _create_interventions_table(self):
        """Create interventions table."""
        self.interventions_table = QTableWidget()
        self.interventions_table.setColumnCount(7)
        self.interventions_table.setHorizontalHeaderLabels([
            "Active", "Name", "Body System", "Frequency", "Pete Attia Category", "Author", "Notes"
        ])
        self.interventions_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.interventions_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.interventions_table.doubleClicked.connect(self._edit_intervention)
        
        # Set column widths
        header = self.interventions_table.horizontalHeader()
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.interventions_table.setColumnWidth(0, 60)
        
        return self.interventions_table

    def _create_metrics_table(self):
        """Create metrics table."""
        self.metrics_table = QTableWidget()
        self.metrics_table.setColumnCount(6)
        self.metrics_table.setHorizontalHeaderLabels([
            "Active", "Name", "Body System", "Frequency", "Pete Attia Category", "Author"
        ])
        self.metrics_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.metrics_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.metrics_table.doubleClicked.connect(self._edit_metric)
        
        header = self.metrics_table.horizontalHeader()
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.metrics_table.setColumnWidth(0, 60)
        
        return self.metrics_table

    def _create_issues_table(self):
        """Create health issues table."""
        self.issues_table = QTableWidget()
        self.issues_table.setColumnCount(7)
        self.issues_table.setHorizontalHeaderLabels([
            "Active", "Name", "Body System", "Organs", "Pete Attia Category", "Author", "Notes"
        ])
        self.issues_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.issues_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.issues_table.doubleClicked.connect(self._edit_issue)
        
        header = self.issues_table.horizontalHeader()
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.issues_table.setColumnWidth(0, 60)
        
        return self.issues_table

    def _load_all_data(self):
        """Load all health tracking data."""
        self._load_interventions()
        self._load_metrics()
        self._load_issues()

    def _load_interventions(self):
        """Load interventions data."""
        if "interventions" in self.load_workers and self.load_workers["interventions"].isRunning():
            return

        worker = HealthDataLoader("interventions")
        worker.data_loaded.connect(self._on_data_loaded)
        worker.load_error.connect(self._on_load_error)
        worker.start()
        self.load_workers["interventions"] = worker

    def _load_metrics(self):
        """Load metrics data."""
        if "metrics" in self.load_workers and self.load_workers["metrics"].isRunning():
            return

        worker = HealthDataLoader("metrics")
        worker.data_loaded.connect(self._on_data_loaded)
        worker.load_error.connect(self._on_load_error)
        worker.start()
        self.load_workers["metrics"] = worker

    def _load_issues(self):
        """Load health issues data."""
        if "issues" in self.load_workers and self.load_workers["issues"].isRunning():
            return

        worker = HealthDataLoader("issues")
        worker.data_loaded.connect(self._on_data_loaded)
        worker.load_error.connect(self._on_load_error)
        worker.start()
        self.load_workers["issues"] = worker

    def _on_data_loaded(self, section_type: str, data: list):
        """Handle loaded data."""
        if section_type == "interventions":
            self._populate_interventions_table(data)
        elif section_type == "metrics":
            self._populate_metrics_table(data)
        elif section_type == "issues":
            self._populate_issues_table(data)

    def _on_load_error(self, error: str):
        """Handle load error."""
        logger.error(f"Health data load error: {error}")

    def _populate_interventions_table(self, interventions: list):
        """Populate interventions table."""
        self.interventions_table.setRowCount(len(interventions))
        
        for row, intervention in enumerate(interventions):
            # Store intervention object as item data
            self.interventions_table.setItem(row, 0, QTableWidgetItem())
            self.interventions_table.item(row, 0).setData(Qt.ItemDataRole.UserRole, intervention)
            
            # Active checkbox
            active_item = QTableWidgetItem("✓" if intervention.active else "")
            active_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            active_item.setFlags(active_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.interventions_table.setItem(row, 0, active_item)
            
            # Name
            name_item = QTableWidgetItem(intervention.name)
            name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.interventions_table.setItem(row, 1, name_item)
            
            # Body System
            bs_item = QTableWidgetItem(intervention.body_system or "")
            bs_item.setFlags(bs_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.interventions_table.setItem(row, 2, bs_item)
            
            # Frequency
            freq_item = QTableWidgetItem(intervention.frequency or "")
            freq_item.setFlags(freq_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.interventions_table.setItem(row, 3, freq_item)
            
            # Pete Attia Category
            cat_item = QTableWidgetItem(intervention.pete_attia_category or "")
            cat_item.setFlags(cat_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.interventions_table.setItem(row, 4, cat_item)
            
            # Author
            author_item = QTableWidgetItem(intervention.author or "")
            author_item.setFlags(author_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.interventions_table.setItem(row, 5, author_item)
            
            # Notes (preview)
            notes_preview = (intervention.matt_notes or "")[:50]
            if len(intervention.matt_notes or "") > 50:
                notes_preview += "..."
            notes_item = QTableWidgetItem(notes_preview)
            notes_item.setFlags(notes_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.interventions_table.setItem(row, 6, notes_item)

    def _populate_metrics_table(self, metrics: list):
        """Populate metrics table."""
        self.metrics_table.setRowCount(len(metrics))
        
        for row, metric in enumerate(metrics):
            # Store metric object
            self.metrics_table.setItem(row, 0, QTableWidgetItem())
            self.metrics_table.item(row, 0).setData(Qt.ItemDataRole.UserRole, metric)
            
            # Active
            active_item = QTableWidgetItem("✓" if metric.active else "")
            active_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            active_item.setFlags(active_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.metrics_table.setItem(row, 0, active_item)
            
            # Name
            name_item = QTableWidgetItem(metric.name)
            name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.metrics_table.setItem(row, 1, name_item)
            
            # Body System
            bs_item = QTableWidgetItem(metric.body_system or "")
            bs_item.setFlags(bs_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.metrics_table.setItem(row, 2, bs_item)
            
            # Frequency
            freq_item = QTableWidgetItem(metric.frequency or "")
            freq_item.setFlags(freq_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.metrics_table.setItem(row, 3, freq_item)
            
            # Pete Attia Category
            cat_item = QTableWidgetItem(metric.pete_attia_category or "")
            cat_item.setFlags(cat_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.metrics_table.setItem(row, 4, cat_item)
            
            # Author
            author_item = QTableWidgetItem(metric.author or "")
            author_item.setFlags(author_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.metrics_table.setItem(row, 5, author_item)

    def _populate_issues_table(self, issues: list):
        """Populate health issues table."""
        self.issues_table.setRowCount(len(issues))
        
        for row, issue in enumerate(issues):
            # Store issue object
            self.issues_table.setItem(row, 0, QTableWidgetItem())
            self.issues_table.item(row, 0).setData(Qt.ItemDataRole.UserRole, issue)
            
            # Active
            active_item = QTableWidgetItem("✓" if issue.active else "")
            active_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            active_item.setFlags(active_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.issues_table.setItem(row, 0, active_item)
            
            # Name
            name_item = QTableWidgetItem(issue.name)
            name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.issues_table.setItem(row, 1, name_item)
            
            # Body System
            bs_item = QTableWidgetItem(issue.body_system or "")
            bs_item.setFlags(bs_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.issues_table.setItem(row, 2, bs_item)
            
            # Organs
            organs_item = QTableWidgetItem(issue.organs or "")
            organs_item.setFlags(organs_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.issues_table.setItem(row, 3, organs_item)
            
            # Pete Attia Category
            cat_item = QTableWidgetItem(issue.pete_attia_category or "")
            cat_item.setFlags(cat_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.issues_table.setItem(row, 4, cat_item)
            
            # Author
            author_item = QTableWidgetItem(issue.author or "")
            author_item.setFlags(author_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.issues_table.setItem(row, 5, author_item)
            
            # Notes (preview)
            notes_preview = (issue.matt_notes or "")[:50]
            if len(issue.matt_notes or "") > 50:
                notes_preview += "..."
            notes_item = QTableWidgetItem(notes_preview)
            notes_item.setFlags(notes_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.issues_table.setItem(row, 6, notes_item)

    def _add_intervention(self):
        """Add new intervention."""
        dialog = HealthInterventionDialog(parent=self)
        if dialog.exec():
            self._load_interventions()

    def _add_metric(self):
        """Add new metric."""
        dialog = HealthMetricDialog(parent=self)
        if dialog.exec():
            self._load_metrics()

    def _add_issue(self):
        """Add new health issue."""
        dialog = HealthIssueDialog(parent=self)
        if dialog.exec():
            self._load_issues()

    def _edit_intervention(self):
        """Edit selected intervention."""
        current_row = self.interventions_table.currentRow()
        if current_row < 0:
            return
        
        intervention = self.interventions_table.item(current_row, 0).data(Qt.ItemDataRole.UserRole)
        if intervention:
            dialog = HealthInterventionDialog(intervention=intervention, parent=self)
            if dialog.exec():
                self._load_interventions()

    def _edit_metric(self):
        """Edit selected metric."""
        current_row = self.metrics_table.currentRow()
        if current_row < 0:
            return
        
        metric = self.metrics_table.item(current_row, 0).data(Qt.ItemDataRole.UserRole)
        if metric:
            dialog = HealthMetricDialog(metric=metric, parent=self)
            if dialog.exec():
                self._load_metrics()

    def _edit_issue(self):
        """Edit selected health issue."""
        current_row = self.issues_table.currentRow()
        if current_row < 0:
            return
        
        issue = self.issues_table.item(current_row, 0).data(Qt.ItemDataRole.UserRole)
        if issue:
            dialog = HealthIssueDialog(issue=issue, parent=self)
            if dialog.exec():
                self._load_issues()

