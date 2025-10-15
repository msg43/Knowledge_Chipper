"""Prompts tab for managing and editing system prompts and JSON schemas."""

import json
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QTextCharFormat, QTextCursor
from PyQt6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ...logger import get_logger
from ..components.base_tab import BaseTab

logger = get_logger(__name__)


# Define pipeline stages and their associated prompt files
PIPELINE_STAGES = {
    "unified_miner": {
        "name": "Unified Miner",
        "description": "Extracts claims, jargon, people, and mental models from content segments",
        "prompt_path": "src/knowledge_system/processors/hce/prompts/unified_miner.txt",
        "default_prompt": "unified_miner.txt",
    },
    "flagship_evaluator": {
        "name": "Flagship Evaluator",
        "description": "Reviews and ranks extracted claims by importance and quality",
        "prompt_path": "src/knowledge_system/processors/hce/prompts/flagship_evaluator.txt",
        "default_prompt": "flagship_evaluator.txt",
    },
    "skim": {
        "name": "Skimmer",
        "description": "Performs high-level overview to identify key milestones",
        "prompt_path": "src/knowledge_system/processors/hce/prompts/skim.txt",
        "default_prompt": "skim.txt",
    },
    "concepts": {
        "name": "Concept Extractor",
        "description": "Detects mental models and conceptual frameworks",
        "prompt_path": "src/knowledge_system/processors/hce/prompts/concepts_detect.txt",
        "default_prompt": "concepts_detect.txt",
    },
    "glossary": {
        "name": "Glossary Builder",
        "description": "Creates definitions for jargon and technical terms",
        "prompt_path": "src/knowledge_system/processors/hce/prompts/glossary_detect.txt",
        "default_prompt": "glossary_detect.txt",
    },
    "people_detect": {
        "name": "People Detector",
        "description": "Identifies people mentioned in content",
        "prompt_path": "src/knowledge_system/processors/hce/prompts/people_detect.txt",
        "default_prompt": "people_detect.txt",
    },
    "people_disambiguate": {
        "name": "People Disambiguator",
        "description": "Resolves ambiguous person references",
        "prompt_path": "src/knowledge_system/processors/hce/prompts/people_disambiguate.txt",
        "default_prompt": "people_disambiguate.txt",
    },
}

logger = get_logger(__name__)


class PromptsTab(BaseTab):
    """Tab for managing and editing system prompts and JSON schemas."""

    def __init__(self, parent: Any = None) -> None:
        # Initialize attributes BEFORE calling super().__init__()
        # because super().__init__() calls _setup_ui() which needs these
        self.tab_name = "Prompts"

        # Track current prompt and schema
        self.current_prompt_file: Path | None = None
        self.current_schema_file: Path | None = None
        self.prompt_modified = False
        self.schema_modified = False

        # Track pipeline stage assignments
        self.stage_prompt_combos: dict[str, QComboBox] = {}

        # Now call parent init which will trigger _setup_ui()
        super().__init__(parent)

    def _setup_ui(self) -> None:
        """Setup the prompts UI with enhanced management features."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)

        # Create title
        title_label = QLabel("Prompt Management & Pipeline Configuration")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title_label.setFont(title_font)
        main_layout.addWidget(title_label)

        # Create description
        desc_label = QLabel(
            "Manage system prompts and configure which prompts are used at each pipeline stage. "
            "Import new prompts, edit existing ones, and assign them to different processing stages."
        )
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("color: #666; margin-bottom: 10px;")
        main_layout.addWidget(desc_label)

        # Create horizontal splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(splitter, stretch=1)

        # Left side: Pipeline stage assignments
        left_widget = self._create_pipeline_assignments_widget()
        splitter.addWidget(left_widget)

        # Right side: Prompt editor
        right_widget = self._create_prompt_editor_widget()
        splitter.addWidget(right_widget)

        # Set splitter proportions (35% left, 65% right)
        splitter.setSizes([350, 650])

    def _create_pipeline_assignments_widget(self) -> QWidget:
        """Create the left side pipeline stage assignments widget."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)

        # Title
        title_label = QLabel("Pipeline Stage Assignments")
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(12)
        title_label.setFont(title_font)
        layout.addWidget(title_label)

        # Info label
        info_label = QLabel(
            "Configure which prompt is used at each stage of the processing pipeline:"
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: #666; margin-bottom: 10px; font-size: 10pt;")
        layout.addWidget(info_label)

        # Create scroll area for stage assignments
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        scroll_layout.setContentsMargins(5, 5, 5, 5)

        # Create group box for each pipeline stage
        for stage_id, stage_info in PIPELINE_STAGES.items():
            group = QGroupBox(stage_info["name"])
            group_layout = QVBoxLayout()

            # Description
            desc_label = QLabel(stage_info["description"])
            desc_label.setWordWrap(True)
            desc_label.setStyleSheet("color: #555; font-size: 9pt;")
            group_layout.addWidget(desc_label)

            # Combo box for prompt selection
            combo_layout = QHBoxLayout()
            combo_label = QLabel("Prompt:")
            combo = QComboBox()
            combo.setMinimumWidth(200)
            combo.currentTextChanged.connect(
                lambda text, sid=stage_id: self._on_stage_assignment_changed(sid, text)
            )
            self.stage_prompt_combos[stage_id] = combo

            combo_layout.addWidget(combo_label)
            combo_layout.addWidget(combo, stretch=1)
            group_layout.addLayout(combo_layout)

            # View/Edit button
            view_btn = QPushButton("View Assigned Prompt")
            view_btn.clicked.connect(
                lambda checked, sid=stage_id: self._view_stage_prompt(sid)
            )
            group_layout.addWidget(view_btn)

            group.setLayout(group_layout)
            scroll_layout.addWidget(group)

        scroll_layout.addStretch()
        scroll.setWidget(scroll_widget)
        layout.addWidget(scroll, stretch=1)

        # Refresh assignments button
        refresh_btn = QPushButton("🔄 Refresh Assignments")
        refresh_btn.clicked.connect(self._refresh_pipeline_assignments)
        layout.addWidget(refresh_btn)

        # Load initial assignments
        self._refresh_pipeline_assignments()

        return widget

    def _create_prompt_editor_widget(self) -> QWidget:
        """Create the right side prompt management and editor widget."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)

        # Title and management buttons
        header_layout = QHBoxLayout()

        title_label = QLabel("Prompt Library & Editor")
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(12)
        title_label.setFont(title_font)
        header_layout.addWidget(title_label)

        header_layout.addStretch()

        # Import prompt button
        import_btn = QPushButton("📥 Import Prompt")
        import_btn.clicked.connect(self._import_prompt)
        import_btn.setToolTip("Import a new prompt file from your computer")
        header_layout.addWidget(import_btn)

        # Delete prompt button
        self.delete_btn = QPushButton("🗑️ Delete Prompt")
        self.delete_btn.clicked.connect(self._delete_current_prompt)
        self.delete_btn.setEnabled(False)
        self.delete_btn.setToolTip("Delete the currently selected prompt")
        header_layout.addWidget(self.delete_btn)

        layout.addLayout(header_layout)

        # Prompt list section
        list_label = QLabel("Available Prompts:")
        list_label.setStyleSheet("font-weight: bold; margin-top: 10px;")
        layout.addWidget(list_label)

        # Prompt list with search/filter
        self.prompt_list = QListWidget()
        self.prompt_list.setMaximumHeight(150)
        self.prompt_list.itemClicked.connect(self._on_prompt_selected)
        layout.addWidget(self.prompt_list)

        # Current prompt info
        self.prompt_info_label = QLabel("Select a prompt to view and edit")
        self.prompt_info_label.setStyleSheet(
            "color: #666; font-style: italic; margin-top: 5px; padding: 5px; "
            "background-color: #f0f0f0; border-radius: 3px;"
        )
        layout.addWidget(self.prompt_info_label)

        # Prompt editor
        editor_label = QLabel("Prompt Content:")
        editor_label.setStyleSheet("font-weight: bold; margin-top: 10px;")
        layout.addWidget(editor_label)

        self.prompt_editor = QTextEdit()
        self.prompt_editor.setFont(QFont("Consolas", 10))
        self.prompt_editor.textChanged.connect(self._on_prompt_modified)
        self.prompt_editor.setPlaceholderText(
            "Select a prompt from the list above to view and edit its content..."
        )
        layout.addWidget(self.prompt_editor, stretch=1)

        # Editor control buttons
        editor_buttons_layout = QHBoxLayout()

        self.save_prompt_btn = QPushButton("💾 Save Changes")
        self.save_prompt_btn.clicked.connect(self._save_current_prompt)
        self.save_prompt_btn.setEnabled(False)
        self.save_prompt_btn.setStyleSheet("font-weight: bold;")
        editor_buttons_layout.addWidget(self.save_prompt_btn)

        self.revert_btn = QPushButton("↩️ Revert Changes")
        self.revert_btn.clicked.connect(self._revert_prompt_changes)
        self.revert_btn.setEnabled(False)
        editor_buttons_layout.addWidget(self.revert_btn)

        editor_buttons_layout.addStretch()

        layout.addLayout(editor_buttons_layout)

        # Load prompts
        self._load_prompt_list()

        return widget

    def _get_all_prompt_files(self) -> list[Path]:
        """Get all prompt files from both HCE prompts and config/prompts directories."""
        prompt_files = []

        # HCE prompts directory
        hce_prompts_dir = Path("src/knowledge_system/processors/hce/prompts")
        if hce_prompts_dir.exists():
            prompt_files.extend(sorted(hce_prompts_dir.glob("*.txt")))

        # Config prompts directory
        config_prompts_dir = Path("config/prompts")
        if config_prompts_dir.exists():
            prompt_files.extend(sorted(config_prompts_dir.glob("*.txt")))

        return prompt_files

    def _load_prompt_list(self) -> None:
        """Load available prompts from all prompt directories."""
        self.prompt_list.clear()

        prompt_files = self._get_all_prompt_files()

        for prompt_file in prompt_files:
            # Create display name with directory indicator
            if "hce/prompts" in str(prompt_file):
                display_name = f"⚙️ {prompt_file.stem}"
            else:
                display_name = f"📄 {prompt_file.stem}"

            item = QListWidgetItem(display_name)
            item.setData(Qt.ItemDataRole.UserRole, prompt_file)
            self.prompt_list.addItem(item)

        logger.info(f"Loaded {len(prompt_files)} prompts from all directories")

    def _refresh_pipeline_assignments(self) -> None:
        """Refresh the prompt dropdowns for all pipeline stages."""
        # Get all available prompts
        prompt_files = self._get_all_prompt_files()
        prompt_names = [p.stem for p in prompt_files]

        # Update each combo box
        for stage_id, combo in self.stage_prompt_combos.items():
            # Block signals while updating
            combo.blockSignals(True)
            combo.clear()
            combo.addItems(prompt_names)

            # Set current assignment based on what file exists at the stage path
            stage_info = PIPELINE_STAGES[stage_id]
            stage_path = Path(stage_info["prompt_path"])

            if stage_path.exists():
                # Try to find which prompt matches the current content
                current_content = stage_path.read_text(encoding="utf-8")
                matched = False

                for prompt_file in prompt_files:
                    try:
                        if prompt_file.read_text(encoding="utf-8") == current_content:
                            combo.setCurrentText(prompt_file.stem)
                            matched = True
                            break
                    except Exception:
                        continue

                if not matched:
                    # If no match, use the default prompt name
                    default_name = stage_info["default_prompt"].replace(".txt", "")
                    idx = combo.findText(default_name)
                    if idx >= 0:
                        combo.setCurrentIndex(idx)

            combo.blockSignals(False)

        logger.info("Refreshed pipeline stage assignments")

    def _on_prompt_selected(self, item: QListWidgetItem) -> None:
        """Handle prompt selection."""
        prompt_file = item.data(Qt.ItemDataRole.UserRole)
        if not prompt_file or not prompt_file.exists():
            return

        try:
            # Load prompt content
            content = prompt_file.read_text(encoding="utf-8")

            # Block signals to prevent triggering modification
            self.prompt_editor.blockSignals(True)
            self.prompt_editor.setPlainText(content)
            self.prompt_editor.blockSignals(False)

            # Store current prompt file
            self.current_prompt_file = prompt_file
            self.prompt_modified = False
            self.save_prompt_btn.setEnabled(False)
            self.revert_btn.setEnabled(False)
            self.delete_btn.setEnabled(True)

            # Update info label
            # Check if this prompt is used by any pipeline stage
            used_by = []
            for stage_id, stage_info in PIPELINE_STAGES.items():
                stage_path = Path(stage_info["prompt_path"])
                if stage_path.exists():
                    try:
                        stage_content = stage_path.read_text(encoding="utf-8")
                        if stage_content == content:
                            used_by.append(stage_info["name"])
                    except Exception:
                        pass

            if used_by:
                usage_text = f"Used by: {', '.join(used_by)}"
                self.prompt_info_label.setStyleSheet(
                    "color: #007acc; font-style: italic; margin-top: 5px; padding: 5px; "
                    "background-color: #e6f2ff; border-radius: 3px; font-weight: bold;"
                )
            else:
                usage_text = "Not currently assigned to any pipeline stage"
                self.prompt_info_label.setStyleSheet(
                    "color: #666; font-style: italic; margin-top: 5px; padding: 5px; "
                    "background-color: #f0f0f0; border-radius: 3px;"
                )

            self.prompt_info_label.setText(f"📝 {prompt_file.name} | {usage_text}")

            logger.info(f"Selected prompt: {prompt_file.name}")

        except Exception as e:
            logger.error(f"Failed to load prompt {prompt_file}: {e}")
            QMessageBox.critical(self, "Error", f"Failed to load prompt: {e}")

    def _on_prompt_modified(self) -> None:
        """Handle prompt modification."""
        if not self.current_prompt_file:
            return
        self.prompt_modified = True
        self.save_prompt_btn.setEnabled(True)
        self.revert_btn.setEnabled(True)

    def _on_stage_assignment_changed(self, stage_id: str, prompt_name: str) -> None:
        """Handle pipeline stage prompt assignment change."""
        if not prompt_name:
            return

        try:
            stage_info = PIPELINE_STAGES[stage_id]
            stage_path = Path(stage_info["prompt_path"])

            # Find the prompt file
            prompt_files = self._get_all_prompt_files()
            selected_prompt = None
            for pf in prompt_files:
                if pf.stem == prompt_name:
                    selected_prompt = pf
                    break

            if not selected_prompt or not selected_prompt.exists():
                logger.warning(f"Could not find prompt: {prompt_name}")
                return

            # Copy the prompt content to the stage location
            prompt_content = selected_prompt.read_text(encoding="utf-8")
            stage_path.parent.mkdir(parents=True, exist_ok=True)
            stage_path.write_text(prompt_content, encoding="utf-8")

            logger.info(f"Assigned '{prompt_name}' to {stage_info['name']}")
            QMessageBox.information(
                self,
                "Assignment Updated",
                f"Successfully assigned '{prompt_name}' to {stage_info['name']}\n\n"
                f"This prompt will now be used for {stage_info['description'].lower()}",
            )

        except Exception as e:
            logger.error(f"Failed to assign prompt to stage: {e}")
            QMessageBox.critical(
                self, "Assignment Failed", f"Failed to assign prompt: {e}"
            )

    def _view_stage_prompt(self, stage_id: str) -> None:
        """View the prompt currently assigned to a pipeline stage."""
        try:
            stage_info = PIPELINE_STAGES[stage_id]
            stage_path = Path(stage_info["prompt_path"])

            if not stage_path.exists():
                QMessageBox.warning(
                    self, "No Prompt Assigned", f"No prompt file found at {stage_path}"
                )
                return

            # Load the stage's prompt
            content = stage_path.read_text(encoding="utf-8")

            # Find matching prompt in list
            prompt_files = self._get_all_prompt_files()
            for pf in prompt_files:
                try:
                    if pf.read_text(encoding="utf-8") == content:
                        # Select this prompt in the list
                        for i in range(self.prompt_list.count()):
                            item = self.prompt_list.item(i)
                            if (
                                item is not None
                                and item.data(Qt.ItemDataRole.UserRole) == pf
                            ):
                                self.prompt_list.setCurrentItem(item)
                                self._on_prompt_selected(item)
                                return
                except Exception:
                    continue

            # If no match found, just display the content
            self.prompt_editor.blockSignals(True)
            self.prompt_editor.setPlainText(content)
            self.prompt_editor.blockSignals(False)
            self.current_prompt_file = stage_path
            self.prompt_info_label.setText(
                f"📝 {stage_info['name']} (direct from pipeline)"
            )

        except Exception as e:
            logger.error(f"Failed to view stage prompt: {e}")
            QMessageBox.critical(self, "Error", f"Failed to view prompt: {e}")

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
            self.revert_btn.setEnabled(False)

            logger.info(f"Saved prompt: {self.current_prompt_file.name}")

            # Check if this affects any pipeline stages
            affected_stages = []
            for stage_id, stage_info in PIPELINE_STAGES.items():
                stage_path = Path(stage_info["prompt_path"])
                if stage_path.exists() and stage_path.samefile(
                    self.current_prompt_file
                ):
                    affected_stages.append(stage_info["name"])

            if affected_stages:
                msg = (
                    f"Prompt saved: {self.current_prompt_file.name}\n\n"
                    f"⚠️ This prompt is used by: {', '.join(affected_stages)}\n"
                    f"Changes will take effect on the next processing run."
                )
            else:
                msg = f"Prompt saved: {self.current_prompt_file.name}"

            QMessageBox.information(self, "Saved", msg)

            # Refresh the assignments display
            self._refresh_pipeline_assignments()

        except Exception as e:
            logger.error(f"Failed to save prompt: {e}")
            QMessageBox.critical(self, "Error", f"Failed to save prompt: {e}")

    def _revert_prompt_changes(self) -> None:
        """Revert unsaved changes to the current prompt."""
        if not self.current_prompt_file:
            return

        reply = QMessageBox.question(
            self,
            "Revert Changes",
            "Discard all unsaved changes to this prompt?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                # Reload from file
                content = self.current_prompt_file.read_text(encoding="utf-8")
                self.prompt_editor.blockSignals(True)
                self.prompt_editor.setPlainText(content)
                self.prompt_editor.blockSignals(False)

                self.prompt_modified = False
                self.save_prompt_btn.setEnabled(False)
                self.revert_btn.setEnabled(False)

                logger.info(f"Reverted changes to: {self.current_prompt_file.name}")

            except Exception as e:
                logger.error(f"Failed to revert prompt: {e}")
                QMessageBox.critical(self, "Error", f"Failed to revert: {e}")

    def _import_prompt(self) -> None:
        """Import a new prompt file from the file system."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Import Prompt File", "", "Text Files (*.txt);;All Files (*)"
        )

        if not file_path:
            return

        try:
            source_path = Path(file_path)

            # Ask where to save it
            reply = QMessageBox.question(
                self,
                "Import Location",
                f"Import '{source_path.name}' to:\n\n"
                "• HCE Prompts (for pipeline use)\n"
                "• Config Prompts (for general use)\n\n"
                "Choose 'Yes' for HCE Prompts, 'No' for Config Prompts",
                QMessageBox.StandardButton.Yes
                | QMessageBox.StandardButton.No
                | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Yes,
            )

            if reply == QMessageBox.StandardButton.Cancel:
                return

            if reply == QMessageBox.StandardButton.Yes:
                target_dir = Path("src/knowledge_system/processors/hce/prompts")
            else:
                target_dir = Path("config/prompts")

            target_dir.mkdir(parents=True, exist_ok=True)
            target_path = target_dir / source_path.name

            # Check if file already exists
            if target_path.exists():
                overwrite = QMessageBox.question(
                    self,
                    "File Exists",
                    f"A prompt named '{source_path.name}' already exists. Overwrite?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                if overwrite != QMessageBox.StandardButton.Yes:
                    return

            # Copy the file
            shutil.copy2(source_path, target_path)

            logger.info(f"Imported prompt: {source_path.name} to {target_dir}")
            QMessageBox.information(
                self,
                "Import Successful",
                f"Successfully imported '{source_path.name}'\n\n"
                f"Location: {target_path}",
            )

            # Reload prompt list and refresh assignments
            self._load_prompt_list()
            self._refresh_pipeline_assignments()

        except Exception as e:
            logger.error(f"Failed to import prompt: {e}")
            QMessageBox.critical(self, "Import Failed", f"Failed to import prompt: {e}")

    def _delete_current_prompt(self) -> None:
        """Delete the currently selected prompt."""
        if not self.current_prompt_file:
            return

        # Check if this prompt is currently used by any pipeline stage
        used_by = []
        for stage_id, stage_info in PIPELINE_STAGES.items():
            stage_path = Path(stage_info["prompt_path"])
            if stage_path.exists():
                try:
                    if stage_path.samefile(self.current_prompt_file):
                        used_by.append(stage_info["name"])
                except Exception:
                    pass

        if used_by:
            QMessageBox.warning(
                self,
                "Cannot Delete",
                f"Cannot delete this prompt because it is currently used by:\n\n"
                f"• {chr(10).join(used_by)}\n\n"
                f"Please assign different prompts to these stages first.",
            )
            return

        reply = QMessageBox.question(
            self,
            "Delete Prompt",
            f"Are you sure you want to delete '{self.current_prompt_file.name}'?\n\n"
            f"This action cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                prompt_name = self.current_prompt_file.name
                self.current_prompt_file.unlink()

                logger.info(f"Deleted prompt: {prompt_name}")

                # Clear editor and reload list
                self.prompt_editor.clear()
                self.prompt_info_label.setText("Prompt deleted")
                self.current_prompt_file = None
                self.prompt_modified = False
                self.save_prompt_btn.setEnabled(False)
                self.revert_btn.setEnabled(False)
                self.delete_btn.setEnabled(False)

                self._load_prompt_list()
                self._refresh_pipeline_assignments()

                QMessageBox.information(
                    self, "Deleted", f"Successfully deleted '{prompt_name}'"
                )

            except Exception as e:
                logger.error(f"Failed to delete prompt: {e}")
                QMessageBox.critical(
                    self, "Delete Failed", f"Failed to delete prompt: {e}"
                )

    def _load_settings(self) -> None:
        """Load saved settings from session."""
        # No persistent settings for this tab currently
        pass

    def _save_settings(self) -> None:
        """Save current settings to session."""
        # No persistent settings for this tab currently
        pass
