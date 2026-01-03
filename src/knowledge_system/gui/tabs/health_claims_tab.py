"""Health Claims tab - filtered view of health-related knowledge."""

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ...database import (
    Claim,
    Concept,
    DatabaseService,
    JargonTerm,
    Person,
)
from ...logger import get_logger
from ..components.base_tab import BaseTab

logger = get_logger(__name__)


class HealthDataLoader(QThread):
    """Worker thread for loading health-related entities."""

    data_loaded = pyqtSignal(str, list)  # entity_type, data
    load_error = pyqtSignal(str)

    def __init__(self, entity_type: str, tier_filter: str = None, search_query: str = None, parent=None):
        super().__init__(parent)
        self.entity_type = entity_type
        self.tier_filter = tier_filter
        self.search_query = search_query
        self.db = DatabaseService()

    def run(self):
        """Load health entities from database."""
        try:
            health_domains = ['health', 'medicine', 'longevity', 'nutrition', 'fitness', 'wellness']
            
            with self.db.get_session() as session:
                if self.entity_type == "Claims":
                    query = session.query(Claim).filter(
                        Claim.domain.in_(health_domains)
                    )
                    
                    # Apply tier filter
                    if self.tier_filter and self.tier_filter != "All":
                        if self.tier_filter == "A":
                            query = query.filter(Claim.tier == "A")
                        elif self.tier_filter == "B":
                            query = query.filter(Claim.tier.in_(["A", "B"]))
                    
                    # Apply search filter
                    if self.search_query:
                        query = query.filter(Claim.canonical.contains(self.search_query))
                    
                    results = query.order_by(Claim.tier, Claim.importance_score.desc()).all()
                    
                elif self.entity_type == "People":
                    # Get people who have made health claims
                    query = session.query(Person).join(Claim, Person.person_id == Claim.speaker).filter(
                        Claim.domain.in_(health_domains)
                    ).distinct()
                    
                    if self.search_query:
                        query = query.filter(Person.name.contains(self.search_query))
                    
                    results = query.order_by(Person.name).all()
                    
                elif self.entity_type == "Jargon":
                    query = session.query(JargonTerm).filter(
                        JargonTerm.domain.in_(health_domains)
                    )
                    
                    if self.search_query:
                        query = query.filter(JargonTerm.term.contains(self.search_query))
                    
                    results = query.order_by(JargonTerm.term).all()
                    
                elif self.entity_type == "Concepts":
                    query = session.query(Concept).filter(
                        Concept.domain.in_(health_domains)
                    )
                    
                    if self.search_query:
                        query = query.filter(Concept.name.contains(self.search_query))
                    
                    results = query.order_by(Concept.name).all()
                    
                else:
                    results = []
                
                self.data_loaded.emit(self.entity_type, results)
                
        except Exception as e:
            logger.error(f"Failed to load health {self.entity_type}: {e}")
            self.load_error.emit(str(e))


class HealthClaimsTab(BaseTab):
    """Tab for viewing health-specific claims, people, jargon, and concepts."""

    def __init__(self, parent=None):
        self.db = DatabaseService()
        self.load_worker = None
        self.current_entity_type = "Claims"
        self.tab_name = "🏥 Health"
        super().__init__(parent)

    def _setup_ui(self):
        """Setup the health claims UI."""
        layout = QVBoxLayout(self)

        # Title
        title_label = QLabel("Health & Longevity Knowledge")
        title_label.setStyleSheet("font-size: 20px; font-weight: bold; margin: 10px;")
        layout.addWidget(title_label)

        # Description
        desc_label = QLabel(
            "All health-related claims, people, jargon, and concepts from your knowledge base."
        )
        desc_label.setStyleSheet("margin: 0px 10px 10px 10px; color: #666;")
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)

        # Filter bar
        filter_layout = QHBoxLayout()
        filter_layout.setContentsMargins(10, 5, 10, 5)

        # Tier filter (for claims only)
        filter_layout.addWidget(QLabel("Tier:"))
        self.tier_filter = QComboBox()
        self.tier_filter.addItems(["All", "A", "B", "C"])
        self.tier_filter.currentTextChanged.connect(self._on_filter_changed)
        filter_layout.addWidget(self.tier_filter)

        # Search box
        filter_layout.addWidget(QLabel("Search:"))
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search health knowledge...")
        self.search_box.textChanged.connect(self._on_search_changed)
        filter_layout.addWidget(self.search_box)

        # Refresh button
        self.refresh_button = QPushButton("🔄 Refresh")
        self.refresh_button.clicked.connect(self._refresh_data)
        filter_layout.addWidget(self.refresh_button)

        filter_layout.addStretch()
        layout.addLayout(filter_layout)

        # Tab widget for different entity types
        self.tabs = QTabWidget()
        self.tabs.currentChanged.connect(self._on_tab_changed)
        layout.addWidget(self.tabs)

        # Claims tab
        self.claims_table = QTableWidget()
        self.claims_table.setColumnCount(4)
        self.claims_table.setHorizontalHeaderLabels(["Claim", "Tier", "Importance", "Speaker"])
        self.claims_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tabs.addTab(self.claims_table, "Claims")

        # People tab
        self.people_table = QTableWidget()
        self.people_table.setColumnCount(3)
        self.people_table.setHorizontalHeaderLabels(["Name", "Description", "Affiliation"])
        self.people_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tabs.addTab(self.people_table, "People")

        # Jargon tab
        self.jargon_table = QTableWidget()
        self.jargon_table.setColumnCount(2)
        self.jargon_table.setHorizontalHeaderLabels(["Term", "Definition"])
        self.jargon_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tabs.addTab(self.jargon_table, "Jargon")

        # Concepts tab
        self.concepts_table = QTableWidget()
        self.concepts_table.setColumnCount(2)
        self.concepts_table.setHorizontalHeaderLabels(["Concept", "Description"])
        self.concepts_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tabs.addTab(self.concepts_table, "Concepts")

        # Initial load
        self._refresh_data()

    def _on_tab_changed(self, index: int):
        """Handle tab change."""
        tab_names = ["Claims", "People", "Jargon", "Concepts"]
        self.current_entity_type = tab_names[index]
        
        # Tier filter only applies to claims
        self.tier_filter.setEnabled(self.current_entity_type == "Claims")
        
        self._refresh_data()

    def _on_filter_changed(self):
        """Handle filter change."""
        self._refresh_data()

    def _on_search_changed(self):
        """Handle search query change (with debouncing)."""
        # Simple refresh without debouncing for now
        self._refresh_data()

    def _refresh_data(self):
        """Refresh health data."""
        if self.load_worker and self.load_worker.isRunning():
            return

        tier_filter = self.tier_filter.currentText() if self.current_entity_type == "Claims" else None
        search_query = self.search_box.text() if self.search_box.text() else None

        self.load_worker = HealthDataLoader(
            self.current_entity_type,
            tier_filter=tier_filter,
            search_query=search_query
        )
        self.load_worker.data_loaded.connect(self._on_data_loaded)
        self.load_worker.load_error.connect(self._on_load_error)
        self.load_worker.start()

        # Disable refresh button while loading
        self.refresh_button.setEnabled(False)
        self.refresh_button.setText("Loading...")

    def _on_data_loaded(self, entity_type: str, data: list):
        """Handle loaded data."""
        self.refresh_button.setEnabled(True)
        self.refresh_button.setText("🔄 Refresh")

        if entity_type == "Claims":
            self._populate_claims_table(data)
        elif entity_type == "People":
            self._populate_people_table(data)
        elif entity_type == "Jargon":
            self._populate_jargon_table(data)
        elif entity_type == "Concepts":
            self._populate_concepts_table(data)

    def _on_load_error(self, error: str):
        """Handle load error."""
        self.refresh_button.setEnabled(True)
        self.refresh_button.setText("🔄 Refresh")
        logger.error(f"Health data load error: {error}")

    def _populate_claims_table(self, claims: list):
        """Populate claims table."""
        self.claims_table.setRowCount(len(claims))
        
        for row, claim in enumerate(claims):
            # Claim text
            claim_item = QTableWidgetItem(claim.canonical)
            claim_item.setFlags(claim_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.claims_table.setItem(row, 0, claim_item)
            
            # Tier
            tier_item = QTableWidgetItem(claim.tier or "C")
            tier_item.setFlags(tier_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.claims_table.setItem(row, 1, tier_item)
            
            # Importance score
            try:
                scores = claim.scores_json if hasattr(claim, 'scores_json') else {}
                importance = scores.get('importance', 0) if scores else 0
                importance_text = f"{importance:.2f}"
            except:
                importance_text = "N/A"
            
            importance_item = QTableWidgetItem(importance_text)
            importance_item.setFlags(importance_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.claims_table.setItem(row, 2, importance_item)
            
            # Speaker
            speaker_item = QTableWidgetItem(claim.speaker or "")
            speaker_item.setFlags(speaker_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.claims_table.setItem(row, 3, speaker_item)
        
        self.claims_table.resizeColumnsToContents()
        self.claims_table.setColumnWidth(0, 400)  # Wider for claim text

    def _populate_people_table(self, people: list):
        """Populate people table."""
        self.people_table.setRowCount(len(people))
        
        for row, person in enumerate(people):
            # Name
            name_item = QTableWidgetItem(person.name)
            name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.people_table.setItem(row, 0, name_item)
            
            # Description
            desc_item = QTableWidgetItem(person.description or "")
            desc_item.setFlags(desc_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.people_table.setItem(row, 1, desc_item)
            
            # Affiliation
            affil_item = QTableWidgetItem(person.affiliation or "")
            affil_item.setFlags(affil_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.people_table.setItem(row, 2, affil_item)
        
        self.people_table.resizeColumnsToContents()

    def _populate_jargon_table(self, jargon: list):
        """Populate jargon table."""
        self.jargon_table.setRowCount(len(jargon))
        
        for row, term in enumerate(jargon):
            # Term
            term_item = QTableWidgetItem(term.term)
            term_item.setFlags(term_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.jargon_table.setItem(row, 0, term_item)
            
            # Definition
            def_item = QTableWidgetItem(term.definition or "")
            def_item.setFlags(def_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.jargon_table.setItem(row, 1, def_item)
        
        self.jargon_table.resizeColumnsToContents()
        self.jargon_table.setColumnWidth(1, 500)  # Wider for definition

    def _populate_concepts_table(self, concepts: list):
        """Populate concepts table."""
        self.concepts_table.setRowCount(len(concepts))
        
        for row, concept in enumerate(concepts):
            # Name
            name_item = QTableWidgetItem(concept.name)
            name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.concepts_table.setItem(row, 0, name_item)
            
            # Description
            desc_item = QTableWidgetItem(concept.description or "")
            desc_item.setFlags(desc_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.concepts_table.setItem(row, 1, desc_item)
        
        self.concepts_table.resizeColumnsToContents()
        self.concepts_table.setColumnWidth(1, 500)  # Wider for description

