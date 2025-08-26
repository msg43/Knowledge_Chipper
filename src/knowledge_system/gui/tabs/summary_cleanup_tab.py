"""
Summary Cleanup Tab for Knowledge System GUI (PyQt6).

Provides interface for reviewing and editing generated summaries,
claims, and extracted entities before finalizing.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime

from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QPushButton, QLabel, QTextEdit, QTreeWidget, QTreeWidgetItem,
    QListWidget, QListWidgetItem, QFileDialog, QMessageBox,
    QComboBox, QSpinBox, QCheckBox, QGroupBox, QTabWidget
)
from PyQt6.QtGui import QTextCharFormat, QColor, QFont

from ...database import DatabaseService
from ...logger import get_logger

logger = get_logger(__name__)


class EntityItem(QListWidgetItem):
    """Custom list item for entities with data storage."""
    
    def __init__(self, entity_type: str, entity_data: Dict[str, Any]):
        super().__init__()
        self.entity_type = entity_type
        self.entity_data = entity_data
        self.update_display()
    
    def update_display(self):
        """Update the display text based on entity type and data."""
        if self.entity_type == "claim":
            self.setText(f"[{self.entity_data.get('tier', 'B')}] {self.entity_data.get('text', '')}")
        elif self.entity_type == "person":
            self.setText(f"👤 {self.entity_data.get('name', '')}")
        elif self.entity_type == "concept":
            self.setText(f"💡 {self.entity_data.get('term', '')}")
        elif self.entity_type == "jargon":
            self.setText(f"📖 {self.entity_data.get('term', '')}")
        else:
            self.setText(str(self.entity_data))


class SummaryCleanupTab(QWidget):
    """Tab for post-summary cleanup and editing."""
    
    status_update = pyqtSignal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.db = DatabaseService()
        self.current_file_path: Optional[Path] = None
        self.original_data: Dict[str, Any] = {}
        self.modified_data: Dict[str, Any] = {}
        self.is_modified = False
        
        self.setup_ui()
    
    def setup_ui(self):
        """Set up the user interface."""
        layout = QVBoxLayout(self)
        
        # Header
        header_layout = QHBoxLayout()
        
        title_label = QLabel("Summary Cleanup & Review")
        title_label.setStyleSheet("font-size: 20px; font-weight: bold;")
        header_layout.addWidget(title_label)
        
        header_layout.addStretch()
        
        # File controls
        self.load_btn = QPushButton("Load Summary")
        self.load_btn.clicked.connect(self.load_summary)
        header_layout.addWidget(self.load_btn)
        
        self.save_btn = QPushButton("Save Changes")
        self.save_btn.clicked.connect(self.save_changes)
        self.save_btn.setEnabled(False)
        header_layout.addWidget(self.save_btn)
        
        self.export_btn = QPushButton("Export Clean")
        self.export_btn.clicked.connect(self.export_clean)
        self.export_btn.setEnabled(False)
        header_layout.addWidget(self.export_btn)
        
        layout.addLayout(header_layout)
        
        # File info
        self.file_label = QLabel("No file loaded")
        self.file_label.setStyleSheet("font-size: 14px; padding: 5px;")
        layout.addWidget(self.file_label)
        
        # Main content area
        content_splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Left: Summary text editor
        self.create_text_editor(content_splitter)
        
        # Right: Entity editor
        self.create_entity_editor(content_splitter)
        
        content_splitter.setSizes([600, 400])
        layout.addWidget(content_splitter)
        
        # Status bar
        self.status_label = QLabel("Ready")
        layout.addWidget(self.status_label)
    
    def create_text_editor(self, parent):
        """Create the summary text editor panel."""
        text_widget = QWidget()
        layout = QVBoxLayout(text_widget)
        
        # Tab widget for different text sections
        self.text_tabs = QTabWidget()
        
        # Summary tab
        self.summary_edit = QTextEdit()
        self.summary_edit.textChanged.connect(self.on_text_changed)
        self.text_tabs.addTab(self.summary_edit, "Summary")
        
        # Key Points tab
        self.keypoints_edit = QTextEdit()
        self.keypoints_edit.textChanged.connect(self.on_text_changed)
        self.text_tabs.addTab(self.keypoints_edit, "Key Points")
        
        # Raw text tab (read-only)
        self.raw_text = QTextEdit()
        self.raw_text.setReadOnly(True)
        self.raw_text.setStyleSheet("background-color: #2b2b2b;")
        self.text_tabs.addTab(self.raw_text, "Original Text")
        
        layout.addWidget(self.text_tabs)
        
        # Text formatting tools
        format_layout = QHBoxLayout()
        
        self.word_count_label = QLabel("Words: 0")
        format_layout.addWidget(self.word_count_label)
        
        format_layout.addStretch()
        
        self.condense_btn = QPushButton("Condense")
        self.condense_btn.clicked.connect(self.condense_text)
        format_layout.addWidget(self.condense_btn)
        
        self.expand_btn = QPushButton("Expand")
        self.expand_btn.clicked.connect(self.expand_text)
        format_layout.addWidget(self.expand_btn)
        
        layout.addLayout(format_layout)
        
        parent.addWidget(text_widget)
    
    def create_entity_editor(self, parent):
        """Create the entity editing panel."""
        entity_widget = QWidget()
        layout = QVBoxLayout(entity_widget)
        
        # Entity tabs
        self.entity_tabs = QTabWidget()
        
        # Claims tab
        claims_widget = self.create_claims_editor()
        self.entity_tabs.addTab(claims_widget, "Claims")
        
        # People tab
        people_widget = self.create_people_editor()
        self.entity_tabs.addTab(people_widget, "People")
        
        # Concepts tab
        concepts_widget = self.create_concepts_editor()
        self.entity_tabs.addTab(concepts_widget, "Concepts")
        
        # Jargon tab
        jargon_widget = self.create_jargon_editor()
        self.entity_tabs.addTab(jargon_widget, "Jargon")
        
        layout.addWidget(self.entity_tabs)
        
        parent.addWidget(entity_widget)
    
    def create_claims_editor(self) -> QWidget:
        """Create the claims editing widget."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Controls
        controls = QHBoxLayout()
        
        self.claim_tier_combo = QComboBox()
        self.claim_tier_combo.addItems(["A", "B", "C"])
        controls.addWidget(QLabel("Tier:"))
        controls.addWidget(self.claim_tier_combo)
        
        self.confidence_spin = QSpinBox()
        self.confidence_spin.setRange(0, 100)
        self.confidence_spin.setSuffix("%")
        controls.addWidget(QLabel("Confidence:"))
        controls.addWidget(self.confidence_spin)
        
        controls.addStretch()
        
        self.add_claim_btn = QPushButton("Add Claim")
        self.add_claim_btn.clicked.connect(self.add_claim)
        controls.addWidget(self.add_claim_btn)
        
        layout.addLayout(controls)
        
        # Claims list
        self.claims_list = QListWidget()
        self.claims_list.itemSelectionChanged.connect(self.on_claim_selected)
        layout.addWidget(self.claims_list)
        
        # Claim editor
        claim_edit_group = QGroupBox("Edit Claim")
        claim_edit_layout = QVBoxLayout(claim_edit_group)
        
        self.claim_text_edit = QTextEdit()
        self.claim_text_edit.setMaximumHeight(100)
        self.claim_text_edit.textChanged.connect(self.on_claim_text_changed)
        claim_edit_layout.addWidget(self.claim_text_edit)
        
        edit_controls = QHBoxLayout()
        
        self.update_claim_btn = QPushButton("Update")
        self.update_claim_btn.clicked.connect(self.update_claim)
        self.update_claim_btn.setEnabled(False)
        edit_controls.addWidget(self.update_claim_btn)
        
        self.delete_claim_btn = QPushButton("Delete")
        self.delete_claim_btn.clicked.connect(self.delete_claim)
        self.delete_claim_btn.setEnabled(False)
        edit_controls.addWidget(self.delete_claim_btn)
        
        claim_edit_layout.addLayout(edit_controls)
        layout.addWidget(claim_edit_group)
        
        return widget
    
    def create_people_editor(self) -> QWidget:
        """Create the people editing widget."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Controls
        controls = QHBoxLayout()
        
        self.add_person_btn = QPushButton("Add Person")
        self.add_person_btn.clicked.connect(self.add_person)
        controls.addWidget(self.add_person_btn)
        
        controls.addStretch()
        layout.addLayout(controls)
        
        # People list
        self.people_list = QListWidget()
        self.people_list.itemDoubleClicked.connect(self.edit_person)
        layout.addWidget(self.people_list)
        
        # Merge controls
        merge_group = QGroupBox("Merge Duplicates")
        merge_layout = QHBoxLayout(merge_group)
        
        self.merge_btn = QPushButton("Merge Selected")
        self.merge_btn.clicked.connect(self.merge_people)
        merge_layout.addWidget(self.merge_btn)
        
        layout.addWidget(merge_group)
        
        return widget
    
    def create_concepts_editor(self) -> QWidget:
        """Create the concepts editing widget."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Similar structure to people editor
        controls = QHBoxLayout()
        
        self.add_concept_btn = QPushButton("Add Concept")
        self.add_concept_btn.clicked.connect(self.add_concept)
        controls.addWidget(self.add_concept_btn)
        
        controls.addStretch()
        layout.addLayout(controls)
        
        self.concepts_list = QListWidget()
        self.concepts_list.itemDoubleClicked.connect(self.edit_concept)
        layout.addWidget(self.concepts_list)
        
        return widget
    
    def create_jargon_editor(self) -> QWidget:
        """Create the jargon editing widget."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        controls = QHBoxLayout()
        
        self.add_jargon_btn = QPushButton("Add Term")
        self.add_jargon_btn.clicked.connect(self.add_jargon)
        controls.addWidget(self.add_jargon_btn)
        
        controls.addStretch()
        layout.addLayout(controls)
        
        self.jargon_list = QListWidget()
        self.jargon_list.itemDoubleClicked.connect(self.edit_jargon)
        layout.addWidget(self.jargon_list)
        
        return widget
    
    def load_summary(self):
        """Load a summary file for cleanup."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Summary File",
            "",
            "Markdown files (*.md);;JSON files (*.json);;All files (*.*)"
        )
        
        if not file_path:
            return
        
        try:
            self.current_file_path = Path(file_path)
            
            # Load data based on file type
            if self.current_file_path.suffix == ".json":
                with open(self.current_file_path, 'r', encoding='utf-8') as f:
                    self.original_data = json.load(f)
            else:
                # Parse markdown file
                self.original_data = self.parse_markdown_summary(self.current_file_path)
            
            # Create working copy
            self.modified_data = json.loads(json.dumps(self.original_data))
            
            # Populate UI
            self.populate_ui()
            
            # Update status
            self.file_label.setText(f"File: {self.current_file_path.name}")
            self.save_btn.setEnabled(True)
            self.export_btn.setEnabled(True)
            self.is_modified = False
            
            self.update_status("Summary loaded successfully")
            
        except Exception as e:
            logger.error(f"Failed to load summary: {e}")
            QMessageBox.critical(self, "Error", f"Failed to load summary: {str(e)}")
    
    def parse_markdown_summary(self, file_path: Path) -> Dict[str, Any]:
        """Parse a markdown summary file into structured data."""
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Basic parsing - this would be more sophisticated in production
        data = {
            "summary": "",
            "key_points": [],
            "claims": [],
            "people": [],
            "concepts": [],
            "jargon": [],
            "original_text": ""
        }
        
        # Extract sections
        sections = content.split("\n## ")
        for section in sections:
            if section.startswith("Summary"):
                data["summary"] = section.split("\n", 1)[1].strip()
            elif section.startswith("Key Points"):
                points = section.split("\n", 1)[1].strip().split("\n- ")
                data["key_points"] = [p.strip() for p in points if p.strip()]
        
        return data
    
    def populate_ui(self):
        """Populate the UI with loaded data."""
        # Summary text
        self.summary_edit.setText(self.modified_data.get("summary", ""))
        
        # Key points
        key_points_text = "\n".join(f"- {point}" for point in self.modified_data.get("key_points", []))
        self.keypoints_edit.setText(key_points_text)
        
        # Original text
        self.raw_text.setText(self.modified_data.get("original_text", ""))
        
        # Claims
        self.claims_list.clear()
        for claim in self.modified_data.get("claims", []):
            item = EntityItem("claim", claim)
            self.claims_list.addItem(item)
        
        # People
        self.people_list.clear()
        for person in self.modified_data.get("people", []):
            item = EntityItem("person", person)
            self.people_list.addItem(item)
        
        # Concepts
        self.concepts_list.clear()
        for concept in self.modified_data.get("concepts", []):
            item = EntityItem("concept", concept)
            self.concepts_list.addItem(item)
        
        # Jargon
        self.jargon_list.clear()
        for term in self.modified_data.get("jargon", []):
            item = EntityItem("jargon", term)
            self.jargon_list.addItem(item)
        
        self.update_word_count()
    
    def on_text_changed(self):
        """Handle text changes."""
        self.is_modified = True
        self.update_word_count()
        
        # Update modified data
        self.modified_data["summary"] = self.summary_edit.toPlainText()
        
        # Parse key points
        key_points_text = self.keypoints_edit.toPlainText()
        self.modified_data["key_points"] = [
            point.strip().lstrip("- ")
            for point in key_points_text.split("\n")
            if point.strip()
        ]
    
    def update_word_count(self):
        """Update the word count display."""
        text = self.summary_edit.toPlainText()
        word_count = len(text.split())
        self.word_count_label.setText(f"Words: {word_count}")
    
    def on_claim_selected(self):
        """Handle claim selection."""
        selected = self.claims_list.selectedItems()
        if selected:
            item = selected[0]
            if isinstance(item, EntityItem):
                self.claim_text_edit.setText(item.entity_data.get("text", ""))
                self.claim_tier_combo.setCurrentText(item.entity_data.get("tier", "B"))
                self.confidence_spin.setValue(int(item.entity_data.get("confidence", 0.5) * 100))
                
                self.update_claim_btn.setEnabled(True)
                self.delete_claim_btn.setEnabled(True)
        else:
            self.update_claim_btn.setEnabled(False)
            self.delete_claim_btn.setEnabled(False)
    
    def on_claim_text_changed(self):
        """Handle claim text changes."""
        self.update_claim_btn.setEnabled(bool(self.claims_list.selectedItems()))
    
    def add_claim(self):
        """Add a new claim."""
        new_claim = {
            "text": "New claim",
            "tier": self.claim_tier_combo.currentText(),
            "confidence": self.confidence_spin.value() / 100.0
        }
        
        item = EntityItem("claim", new_claim)
        self.claims_list.addItem(item)
        
        # Update data
        if "claims" not in self.modified_data:
            self.modified_data["claims"] = []
        self.modified_data["claims"].append(new_claim)
        
        self.is_modified = True
        self.claims_list.setCurrentItem(item)
    
    def update_claim(self):
        """Update the selected claim."""
        selected = self.claims_list.selectedItems()
        if selected:
            item = selected[0]
            if isinstance(item, EntityItem):
                # Update data
                item.entity_data["text"] = self.claim_text_edit.toPlainText()
                item.entity_data["tier"] = self.claim_tier_combo.currentText()
                item.entity_data["confidence"] = self.confidence_spin.value() / 100.0
                
                # Update display
                item.update_display()
                
                # Update modified data
                index = self.claims_list.row(item)
                if index < len(self.modified_data.get("claims", [])):
                    self.modified_data["claims"][index] = item.entity_data
                
                self.is_modified = True
    
    def delete_claim(self):
        """Delete the selected claim."""
        selected = self.claims_list.selectedItems()
        if selected:
            item = selected[0]
            index = self.claims_list.row(item)
            
            # Remove from list
            self.claims_list.takeItem(index)
            
            # Remove from data
            if index < len(self.modified_data.get("claims", [])):
                self.modified_data["claims"].pop(index)
            
            self.is_modified = True
    
    def add_person(self):
        """Add a new person."""
        name, ok = QMessageBox.getText(self, "Add Person", "Enter person name:")
        if ok and name:
            new_person = {"name": name}
            item = EntityItem("person", new_person)
            self.people_list.addItem(item)
            
            if "people" not in self.modified_data:
                self.modified_data["people"] = []
            self.modified_data["people"].append(new_person)
            
            self.is_modified = True
    
    def edit_person(self, item):
        """Edit a person's name."""
        if isinstance(item, EntityItem):
            name, ok = QMessageBox.getText(
                self, "Edit Person", "Enter new name:",
                text=item.entity_data.get("name", "")
            )
            if ok and name:
                item.entity_data["name"] = name
                item.update_display()
                self.is_modified = True
    
    def merge_people(self):
        """Merge selected people into one."""
        selected = self.people_list.selectedItems()
        if len(selected) < 2:
            QMessageBox.warning(self, "Merge People", "Select at least 2 people to merge")
            return
        
        # Get primary name
        names = [item.entity_data.get("name", "") for item in selected if isinstance(item, EntityItem)]
        primary_name, ok = QMessageBox.getItem(
            self, "Merge People", "Select primary name:", names, 0, False
        )
        
        if ok:
            # Keep first item, update with primary name
            primary_item = selected[0]
            if isinstance(primary_item, EntityItem):
                primary_item.entity_data["name"] = primary_name
                primary_item.update_display()
            
            # Remove others
            for item in selected[1:]:
                index = self.people_list.row(item)
                self.people_list.takeItem(index)
            
            # Update data
            self.modified_data["people"] = []
            for i in range(self.people_list.count()):
                item = self.people_list.item(i)
                if isinstance(item, EntityItem):
                    self.modified_data["people"].append(item.entity_data)
            
            self.is_modified = True
    
    def add_concept(self):
        """Add a new concept."""
        term, ok = QMessageBox.getText(self, "Add Concept", "Enter concept term:")
        if ok and term:
            new_concept = {"term": term}
            item = EntityItem("concept", new_concept)
            self.concepts_list.addItem(item)
            
            if "concepts" not in self.modified_data:
                self.modified_data["concepts"] = []
            self.modified_data["concepts"].append(new_concept)
            
            self.is_modified = True
    
    def edit_concept(self, item):
        """Edit a concept."""
        if isinstance(item, EntityItem):
            term, ok = QMessageBox.getText(
                self, "Edit Concept", "Enter new term:",
                text=item.entity_data.get("term", "")
            )
            if ok and term:
                item.entity_data["term"] = term
                item.update_display()
                self.is_modified = True
    
    def add_jargon(self):
        """Add a new jargon term."""
        term, ok = QMessageBox.getText(self, "Add Jargon", "Enter jargon term:")
        if ok and term:
            new_jargon = {"term": term}
            item = EntityItem("jargon", new_jargon)
            self.jargon_list.addItem(item)
            
            if "jargon" not in self.modified_data:
                self.modified_data["jargon"] = []
            self.modified_data["jargon"].append(new_jargon)
            
            self.is_modified = True
    
    def edit_jargon(self, item):
        """Edit a jargon term."""
        if isinstance(item, EntityItem):
            term, ok = QMessageBox.getText(
                self, "Edit Jargon", "Enter new term:",
                text=item.entity_data.get("term", "")
            )
            if ok and term:
                item.entity_data["term"] = term
                item.update_display()
                self.is_modified = True
    
    def condense_text(self):
        """AI-powered text condensing (placeholder)."""
        QMessageBox.information(
            self, "Condense", 
            "AI-powered text condensing would reduce the summary length while preserving key information."
        )
    
    def expand_text(self):
        """AI-powered text expansion (placeholder)."""
        QMessageBox.information(
            self, "Expand",
            "AI-powered text expansion would add more detail and context to the summary."
        )
    
    def save_changes(self):
        """Save changes back to file."""
        if not self.current_file_path or not self.is_modified:
            return
        
        try:
            # Create backup
            backup_path = self.current_file_path.with_suffix(
                self.current_file_path.suffix + ".backup"
            )
            import shutil
            shutil.copy2(self.current_file_path, backup_path)
            
            # Save based on file type
            if self.current_file_path.suffix == ".json":
                with open(self.current_file_path, 'w', encoding='utf-8') as f:
                    json.dump(self.modified_data, f, indent=2)
            else:
                # Convert back to markdown
                self.save_as_markdown(self.current_file_path)
            
            self.is_modified = False
            self.update_status(f"Saved changes to {self.current_file_path.name}")
            
        except Exception as e:
            logger.error(f"Failed to save changes: {e}")
            QMessageBox.critical(self, "Error", f"Failed to save: {str(e)}")
    
    def export_clean(self):
        """Export cleaned version to new file."""
        if not self.current_file_path:
            return
        
        # Suggest filename
        suggested_name = self.current_file_path.stem + "_cleaned" + self.current_file_path.suffix
        
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Cleaned Summary",
            str(self.current_file_path.parent / suggested_name),
            "Markdown files (*.md);;JSON files (*.json);;All files (*.*)"
        )
        
        if not file_path:
            return
        
        try:
            output_path = Path(file_path)
            
            if output_path.suffix == ".json":
                with open(output_path, 'w', encoding='utf-8') as f:
                    json.dump(self.modified_data, f, indent=2)
            else:
                self.save_as_markdown(output_path)
            
            self.update_status(f"Exported to {output_path.name}")
            
        except Exception as e:
            logger.error(f"Failed to export: {e}")
            QMessageBox.critical(self, "Error", f"Failed to export: {str(e)}")
    
    def save_as_markdown(self, file_path: Path):
        """Save data as markdown file."""
        with open(file_path, 'w', encoding='utf-8') as f:
            # Title
            f.write(f"# {self.modified_data.get('title', 'Summary')}\n\n")
            
            # Metadata
            if self.modified_data.get("date"):
                f.write(f"Date: {self.modified_data['date']}\n")
            if self.modified_data.get("authors"):
                f.write(f"Authors: {', '.join(self.modified_data['authors'])}\n")
            f.write("\n")
            
            # Summary
            f.write("## Summary\n\n")
            f.write(self.modified_data.get("summary", "") + "\n\n")
            
            # Key Points
            if self.modified_data.get("key_points"):
                f.write("## Key Points\n\n")
                for point in self.modified_data["key_points"]:
                    f.write(f"- {point}\n")
                f.write("\n")
            
            # Claims
            if self.modified_data.get("claims"):
                f.write("## Claims\n\n")
                for claim in self.modified_data["claims"]:
                    tier = claim.get("tier", "B")
                    text = claim.get("text", "")
                    f.write(f"- [{tier}] {text}\n")
                f.write("\n")
            
            # People
            if self.modified_data.get("people"):
                f.write("## People Mentioned\n\n")
                for person in self.modified_data["people"]:
                    f.write(f"- {person.get('name', '')}\n")
                f.write("\n")
            
            # Concepts
            if self.modified_data.get("concepts"):
                f.write("## Key Concepts\n\n")
                for concept in self.modified_data["concepts"]:
                    f.write(f"- {concept.get('term', '')}\n")
                f.write("\n")
            
            # Jargon
            if self.modified_data.get("jargon"):
                f.write("## Technical Terms\n\n")
                for term in self.modified_data["jargon"]:
                    f.write(f"- {term.get('term', '')}\n")
                f.write("\n")
    
    def update_status(self, message: str):
        """Update the status bar."""
        self.status_label.setText(message)
        self.status_update.emit(message)
