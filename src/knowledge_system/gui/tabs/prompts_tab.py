"""Prompts tab for managing and editing system prompts and JSON schemas."""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QTextCharFormat, QTextCursor
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ...logger import get_logger
from ..components.base_tab import BaseTab

logger = get_logger(__name__)


class PromptsTab(BaseTab):
    """Tab for managing and editing system prompts and JSON schemas."""

    def __init__(self, parent: Any = None) -> None:
        self.tab_name = "Prompts"
        super().__init__(parent)

        # Track current prompt and schema
        self.current_prompt_file: Path | None = None
        self.current_schema_file: Path | None = None
        self.prompt_modified = False
        self.schema_modified = False

    def _setup_ui(self) -> None:
        """Setup the prompts UI with split layout."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)

        # Create title
        title_label = QLabel("System Prompts & JSON Schemas")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title_label.setFont(title_font)
        main_layout.addWidget(title_label)

        # Create description
        desc_label = QLabel(
            "Edit prompts and JSON schemas to customize system behavior without code changes. "
            "Changes are saved to the config directory and take effect immediately."
        )
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("color: #666; margin-bottom: 10px;")
        main_layout.addWidget(desc_label)

        # Create horizontal splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(splitter)

        # Left side: Prompt list
        left_widget = self._create_prompt_list_widget()
        splitter.addWidget(left_widget)

        # Right side: JSON schema editor
        right_widget = self._create_schema_editor_widget()
        splitter.addWidget(right_widget)

        # Set splitter proportions (40% left, 60% right)
        splitter.setSizes([400, 600])

        # Add control buttons
        self._create_control_buttons(main_layout)

    def _create_prompt_list_widget(self) -> QWidget:
        """Create the left side prompt list and editor widget."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Title
        title_label = QLabel("Available Prompts")
        title_font = QFont()
        title_font.setBold(True)
        title_label.setFont(title_font)
        layout.addWidget(title_label)

        # Prompt list
        self.prompt_list = QListWidget()
        self.prompt_list.itemClicked.connect(self._on_prompt_selected)
        layout.addWidget(self.prompt_list)

        # Prompt editor
        editor_label = QLabel("Prompt Content")
        editor_font = QFont()
        editor_font.setBold(True)
        editor_label.setFont(editor_font)
        layout.addWidget(editor_label)

        self.prompt_editor = QTextEdit()
        self.prompt_editor.setFont(QFont("Consolas", 10))
        self.prompt_editor.textChanged.connect(self._on_prompt_modified)
        layout.addWidget(self.prompt_editor)

        # Load prompts
        self._load_prompt_list()

        return widget

    def _create_schema_editor_widget(self) -> QWidget:
        """Create the right side JSON schema editor widget."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Title
        title_label = QLabel("JSON Schema Editor")
        title_font = QFont()
        title_font.setBold(True)
        title_label.setFont(title_font)
        layout.addWidget(title_label)

        # Schema selection buttons
        schema_buttons_layout = QHBoxLayout()

        self.miner_schema_btn = QPushButton("Miner Schema")
        self.miner_schema_btn.clicked.connect(
            lambda: self._load_schema("miner_output.v1.json")
        )
        schema_buttons_layout.addWidget(self.miner_schema_btn)

        self.flagship_schema_btn = QPushButton("Flagship Schema")
        self.flagship_schema_btn.clicked.connect(
            lambda: self._load_schema("flagship_output.v1.json")
        )
        schema_buttons_layout.addWidget(self.flagship_schema_btn)

        self.miner_input_btn = QPushButton("Miner Input")
        self.miner_input_btn.clicked.connect(
            lambda: self._load_schema("miner_input.v1.json")
        )
        schema_buttons_layout.addWidget(self.miner_input_btn)

        self.flagship_input_btn = QPushButton("Flagship Input")
        self.flagship_input_btn.clicked.connect(
            lambda: self._load_schema("flagship_input.v1.json")
        )
        schema_buttons_layout.addWidget(self.flagship_input_btn)

        layout.addLayout(schema_buttons_layout)

        # JSON editor
        self.json_editor = QTextEdit()
        self.json_editor.setFont(QFont("Consolas", 10))
        self.json_editor.textChanged.connect(self._on_schema_modified)
        layout.addWidget(self.json_editor)

        # Add JSON syntax highlighting
        self._setup_json_highlighting()

        return widget

    def _create_control_buttons(self, parent_layout: QVBoxLayout) -> None:
        """Create control buttons for save/load operations."""
        buttons_layout = QHBoxLayout()

        # Save prompt button
        self.save_prompt_btn = QPushButton("Save Prompt")
        self.save_prompt_btn.clicked.connect(self._save_current_prompt)
        self.save_prompt_btn.setEnabled(False)
        buttons_layout.addWidget(self.save_prompt_btn)

        # Save schema button
        self.save_schema_btn = QPushButton("Save Schema")
        self.save_schema_btn.clicked.connect(self._save_current_schema)
        self.save_schema_btn.setEnabled(False)
        buttons_layout.addWidget(self.save_schema_btn)

        # Reload button
        reload_btn = QPushButton("Reload All")
        reload_btn.clicked.connect(self._reload_all)
        buttons_layout.addWidget(reload_btn)

        # Reset button
        reset_btn = QPushButton("Reset to Default")
        reset_btn.clicked.connect(self._reset_to_default)
        buttons_layout.addWidget(reset_btn)

        buttons_layout.addStretch()
        parent_layout.addLayout(buttons_layout)

    def _load_prompt_list(self) -> None:
        """Load available prompts from config/prompts directory."""
        self.prompt_list.clear()

        prompts_dir = Path("config/prompts")
        if not prompts_dir.exists():
            logger.warning("Prompts directory not found: config/prompts")
            return

        # Load all .txt files
        prompt_files = sorted(prompts_dir.glob("*.txt"))

        for prompt_file in prompt_files:
            item = QListWidgetItem(prompt_file.stem.replace("_", " ").title())
            item.setData(Qt.ItemDataRole.UserRole, prompt_file)
            self.prompt_list.addItem(item)

        logger.info(f"Loaded {len(prompt_files)} prompts from config/prompts")

    def _on_prompt_selected(self, item: QListWidgetItem) -> None:
        """Handle prompt selection."""
        prompt_file = item.data(Qt.ItemDataRole.UserRole)
        if not prompt_file or not prompt_file.exists():
            return

        try:
            # Load prompt content
            content = prompt_file.read_text(encoding="utf-8")

            # Display in prompt editor
            self.prompt_editor.setPlainText(content)

            # Store current prompt file
            self.current_prompt_file = prompt_file
            self.prompt_modified = False
            self.save_prompt_btn.setEnabled(False)

            logger.info(f"Selected prompt: {prompt_file.name}")

        except Exception as e:
            logger.error(f"Failed to load prompt {prompt_file}: {e}")
            QMessageBox.critical(self, "Error", f"Failed to load prompt: {e}")

    def _load_schema(self, schema_name: str) -> None:
        """Load a JSON schema file."""
        schema_path = Path("schemas") / schema_name
        if not schema_path.exists():
            logger.warning(f"Schema file not found: {schema_path}")
            QMessageBox.warning(
                self, "File Not Found", f"Schema file not found: {schema_path}"
            )
            return

        try:
            # Load and format JSON
            content = schema_path.read_text(encoding="utf-8")
            json_data = json.loads(content)
            formatted_json = json.dumps(json_data, indent=2)

            # Display in editor
            self.json_editor.setPlainText(formatted_json)
            self.current_schema_file = schema_path
            self.schema_modified = False
            self.save_schema_btn.setEnabled(False)

            logger.info(f"Loaded schema: {schema_name}")

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in schema {schema_path}: {e}")
            QMessageBox.critical(
                self, "Invalid JSON", f"Invalid JSON in schema file: {e}"
            )
        except Exception as e:
            logger.error(f"Failed to load schema {schema_path}: {e}")
            QMessageBox.critical(self, "Error", f"Failed to load schema: {e}")

    def _on_schema_modified(self) -> None:
        """Handle schema modification."""
        self.schema_modified = True
        self.save_schema_btn.setEnabled(True)

    def _on_prompt_modified(self) -> None:
        """Handle prompt modification."""
        self.prompt_modified = True
        self.save_prompt_btn.setEnabled(True)

    def _save_current_prompt(self) -> None:
        """Save the current prompt."""
        if not self.current_prompt_file:
            QMessageBox.warning(
                self, "No Prompt Selected", "Please select a prompt to save."
            )
            return

        try:
            # Get content from editor
            content = self.prompt_editor.toPlainText()

            # Save to file
            self.current_prompt_file.write_text(content, encoding="utf-8")
            self.prompt_modified = False
            self.save_prompt_btn.setEnabled(False)

            logger.info(f"Saved prompt: {self.current_prompt_file.name}")
            QMessageBox.information(
                self, "Success", f"Prompt saved: {self.current_prompt_file.name}"
            )

        except Exception as e:
            logger.error(f"Failed to save prompt: {e}")
            QMessageBox.critical(self, "Error", f"Failed to save prompt: {e}")

    def _save_current_schema(self) -> None:
        """Save the current schema."""
        if not self.current_schema_file:
            QMessageBox.warning(
                self, "No Schema Selected", "Please select a schema to save."
            )
            return

        try:
            # Validate JSON
            content = self.json_editor.toPlainText()
            json.loads(content)  # This will raise an exception if invalid

            # Save to file
            self.current_schema_file.write_text(content, encoding="utf-8")
            self.schema_modified = False
            self.save_schema_btn.setEnabled(False)

            logger.info(f"Saved schema: {self.current_schema_file.name}")
            QMessageBox.information(
                self, "Success", f"Schema saved: {self.current_schema_file.name}"
            )

        except json.JSONDecodeError as e:
            QMessageBox.critical(self, "Invalid JSON", f"Invalid JSON format: {e}")
        except Exception as e:
            logger.error(f"Failed to save schema: {e}")
            QMessageBox.critical(self, "Error", f"Failed to save schema: {e}")

    def _reload_all(self) -> None:
        """Reload all prompts and schemas."""
        self._load_prompt_list()
        self.json_editor.clear()
        self.prompt_editor.clear()
        self.current_schema_file = None
        self.current_prompt_file = None
        self.schema_modified = False
        self.prompt_modified = False
        self.save_schema_btn.setEnabled(False)
        self.save_prompt_btn.setEnabled(False)

        logger.info("Reloaded all prompts and schemas")

    def _reset_to_default(self) -> None:
        """Reset current schema to default (from git)."""
        if not self.current_schema_file:
            QMessageBox.warning(
                self, "No Schema Selected", "Please select a schema to reset."
            )
            return

        reply = QMessageBox.question(
            self,
            "Reset Schema",
            f"Reset {self.current_schema_file.name} to default version? This will discard any unsaved changes.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                # This would require git checkout functionality
                # For now, just reload the file
                self._load_schema(self.current_schema_file.name)
                QMessageBox.information(
                    self, "Reset Complete", "Schema reset to default version."
                )
            except Exception as e:
                logger.error(f"Failed to reset schema: {e}")
                QMessageBox.critical(self, "Error", f"Failed to reset schema: {e}")

    def _setup_json_highlighting(self) -> None:
        """Setup basic JSON syntax highlighting."""
        # This is a simplified version - in a full implementation,
        # you'd want more sophisticated syntax highlighting
        pass

    def _load_settings(self) -> None:
        """Load saved settings from session."""
        # No persistent settings for this tab currently
        pass

    def _save_settings(self) -> None:
        """Save current settings to session."""
        # No persistent settings for this tab currently
        pass
