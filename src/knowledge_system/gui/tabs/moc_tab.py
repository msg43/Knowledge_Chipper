"""Maps of Content (MOC) generation tab for organizing markdown files hierarchically."""

from typing import List, Optional, Dict, Any
from pathlib import Path

from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QGroupBox, QGridLayout,
    QLabel, QPushButton, QLineEdit, QSpinBox, QComboBox,
    QCheckBox, QListWidget, QFileDialog, QMessageBox,
    QTextEdit
)
from PyQt6.QtCore import QTimer, pyqtSignal, QThread

from ..components.base_tab import BaseTab
from ..core.settings_manager import get_gui_settings_manager
from ...logger import get_logger

logger = get_logger(__name__)


class MOCGenerationWorker(QThread):
    """Worker thread for MOC generation."""
    
    progress_updated = pyqtSignal(object)  # MOCProgress
    processing_finished = pyqtSignal(dict)  # results
    processing_error = pyqtSignal(str)
    
    def __init__(self, files, settings, gui_settings, parent=None):
        super().__init__(parent)
        self.files = files
        self.settings = settings
        self.gui_settings = gui_settings
        self.should_stop = False
        
    def run(self):
        """Run the MOC generation process."""
        try:
            from ...processors.moc import MOCProcessor
            from ...utils.progress import MOCProgress
            
            processor = MOCProcessor()
            
            # Create progress object
            progress = MOCProgress(
                percent=0,
                status="Starting MOC generation...",
                current_step="Initializing"
            )
            self.progress_updated.emit(progress)
            
            # Process the files
            result = processor.process(
                self.files,
                depth=self.gui_settings.get('depth', 3),
                title=self.gui_settings.get('title', ''),
                template_path=self.gui_settings.get('template_path', ''),
                output_path=self.gui_settings.get('output_path', ''),
                include_beliefs=self.gui_settings.get('include_beliefs', True)
            )
            
            # Complete
            progress = MOCProgress(
                percent=100,
                status="Completed",
                current_step="Finished"
            )
            self.progress_updated.emit(progress)
            
            self.processing_finished.emit({"result": result})
            
        except Exception as e:
            self.processing_error.emit(str(e))
    
    def stop(self):
        """Stop the MOC generation process."""
        self.should_stop = True


class MOCTab(BaseTab):
    """Tab for Maps of Content generation."""
    
    def __init__(self, parent=None):
        self.moc_worker = None
        self.gui_settings = get_gui_settings_manager()
        self.tab_name = "Maps of Content"
        super().__init__(parent)
        
    def _setup_ui(self):
        """Setup the MOC generation UI."""
        layout = QVBoxLayout(self)
        
        # Input section
        input_group = QGroupBox("Input Markdown Files")
        input_layout = QVBoxLayout()

        # File list
        self.file_list = QListWidget()
        self.file_list.setMinimumHeight(150)
        input_layout.addWidget(self.file_list)

        # File buttons
        button_layout = QHBoxLayout()
        add_files_btn = QPushButton("Add Files")
        add_files_btn.clicked.connect(self._add_files)
        add_folder_btn = QPushButton("Add Folder")
        add_folder_btn.clicked.connect(self._add_folder)
        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self._clear_files)
        clear_btn.setStyleSheet("background-color: #d32f2f;")

        button_layout.addWidget(add_files_btn)
        button_layout.addWidget(add_folder_btn)
        button_layout.addWidget(clear_btn)
        button_layout.addStretch()
        input_layout.addLayout(button_layout)

        input_group.setLayout(input_layout)
        layout.addWidget(input_group)

        # Settings section
        settings_group = QGroupBox("Settings")
        settings_layout = QGridLayout()

        # Depth selection
        depth_label = QLabel("Depth:")
        depth_label.setToolTip(
            "Controls how many levels deep the hierarchical organization should go (1-5)"
        )
        settings_layout.addWidget(depth_label, 0, 0)
        self.depth_spin = QSpinBox()
        self.depth_spin.setMinimum(1)
        self.depth_spin.setMaximum(5)
        self.depth_spin.setValue(3)
        self.depth_spin.valueChanged.connect(self._on_setting_changed)
        settings_layout.addWidget(self.depth_spin, 0, 1)

        # Title
        title_label = QLabel("Title:")
        title_label.setToolTip(
            "Optional: Custom title for the Map of Content. If left blank, an auto-generated title will be used."
        )
        settings_layout.addWidget(title_label, 0, 2)
        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("e.g., 'Machine Learning Research Notes'")
        self.title_edit.textChanged.connect(self._on_setting_changed)
        settings_layout.addWidget(self.title_edit, 0, 3)

        # Prompt file
        settings_layout.addWidget(QLabel("Prompt File:"), 1, 0)
        self.template_path_edit = QLineEdit("")
        self.template_path_edit.setMinimumWidth(250)
        self.template_path_edit.textChanged.connect(self._on_setting_changed)
        settings_layout.addWidget(self.template_path_edit, 1, 1, 1, 2)
        browse_template_btn = QPushButton("Browse")
        browse_template_btn.setFixedWidth(80)
        browse_template_btn.clicked.connect(self._select_template)
        settings_layout.addWidget(browse_template_btn, 1, 3)

        # Custom output
        settings_layout.addWidget(QLabel("Output:"), 2, 0)
        self.output_path_edit = QLineEdit()
        self.output_path_edit.setPlaceholderText("Click Browse to select output file path (required)")
        self.output_path_edit.setMinimumWidth(250)
        self.output_path_edit.textChanged.connect(self._on_setting_changed)
        settings_layout.addWidget(self.output_path_edit, 2, 1, 1, 2)
        browse_output_btn = QPushButton("Browse")
        browse_output_btn.setFixedWidth(80)
        browse_output_btn.clicked.connect(self._select_output)
        settings_layout.addWidget(browse_output_btn, 2, 3)

        # Options
        self.beliefs_checkbox = QCheckBox("Include belief extraction")
        self.beliefs_checkbox.setToolTip(
            "Extract and organize beliefs, assumptions, and key insights from the content into a separate section"
        )
        self.beliefs_checkbox.setChecked(True)
        self.beliefs_checkbox.toggled.connect(self._on_setting_changed)
        settings_layout.addWidget(self.beliefs_checkbox, 3, 0, 1, 4)

        settings_group.setLayout(settings_layout)
        layout.addWidget(settings_group)

        # Action buttons
        action_layout = self._create_action_layout()
        
        # Add dry run button
        dry_run_btn = QPushButton("Dry Run")
        dry_run_btn.clicked.connect(self._dry_run)
        action_layout.insertWidget(1, dry_run_btn)
        
        layout.addLayout(action_layout)

        # Output section
        output_layout = self._create_output_section()
        layout.addLayout(output_layout, 1)  # Give stretch factor of 1 to allow expansion
        
        # Load saved settings after UI is set up
        self._load_settings()
        
    def _connect_signals(self):
        """Connect internal signals."""
        # Connect any additional signals specific to MOC generation
        pass
        
    def _get_start_button_text(self) -> str:
        """Get the text for the start button."""
        return "Start MOC Generation"
        
    def _start_processing(self):
        """Start the MOC generation process."""
        if not self.validate_inputs():
            return
            
        files = self._get_file_list()
        if not files:
            self.show_warning("No Files", "Please add markdown files to generate MOC.")
            return
            
        # Prepare settings
        gui_settings = {
            'depth': self.depth_spin.value(),
            'title': self.title_edit.text(),
            'template_path': self.template_path_edit.text(),
            'output_path': self.output_path_edit.text(),
            'include_beliefs': self.beliefs_checkbox.isChecked()
        }
        
        # Start worker
        self.moc_worker = MOCGenerationWorker(files, self.settings, gui_settings, self)
        self.moc_worker.progress_updated.connect(self._on_progress_updated)
        self.moc_worker.processing_finished.connect(self._on_processing_finished)
        self.moc_worker.processing_error.connect(self._on_processing_error)
        
        self.active_workers.append(self.moc_worker)
        self.set_processing_state(True)
        self.clear_log()
        self.append_log("Starting MOC generation...")
        
        self.moc_worker.start()
        
    def _dry_run(self):
        """Perform a dry run of the MOC generation."""
        files = self._get_file_list()
        if not files:
            self.show_warning("No Files", "Please add markdown files for dry run.")
            return
            
        self.clear_log()
        self.append_log("Dry run - would process the following files:")
        for i, file_path in enumerate(files, 1):
            self.append_log(f"{i}. {file_path}")
            
        self.append_log(f"\nSettings:")
        self.append_log(f"  Depth: {self.depth_spin.value()}")
        self.append_log(f"  Title: {self.title_edit.text() or 'Auto-generated'}")
        self.append_log(f"  Template: {self.template_path_edit.text() or 'Default'}")
        self.append_log(f"  Output: {self.output_path_edit.text() or 'Default location'}")
        self.append_log(f"  Include beliefs: {self.beliefs_checkbox.isChecked()}")
        
    def validate_inputs(self) -> bool:
        """Validate inputs before processing."""
        files = self._get_file_list()
        if not files:
            return False
            
        # Check if files are markdown files
        for file_path in files:
            if not file_path.lower().endswith('.md'):
                self.show_warning("Invalid File Type", f"File is not a markdown file: {file_path}")
                return False
        
        # Check if output path is specified
        output_path = self.output_path_edit.text().strip()
        if not output_path:
            self.show_warning("No Output Path", "Please select an output file path for the MOC.")
            return False
            
        # Check if output directory exists
        output_dir = Path(output_path).parent
        if not output_dir.exists():
            self.show_warning("Invalid Output Directory", f"Output directory does not exist: {output_dir}")
            return False
                
        return True
        
    def _add_files(self):
        """Add markdown files to the MOC list."""
        files, _ = QFileDialog.getOpenFileNames(
            self, "Select Markdown Files",
            str(Path.home()),
            "Markdown Files (*.md);;All Files (*)"
        )
        
        for file_path in files:
            self.file_list.addItem(file_path)
            
    def _add_folder(self):
        """Add all markdown files from a folder."""
        folder_path = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder_path:
            folder = Path(folder_path)
            
            for file_path in folder.rglob('*.md'):
                self.file_list.addItem(str(file_path))
                    
    def _clear_files(self):
        """Clear all files from the list."""
        self.file_list.clear()
        
    def _get_file_list(self) -> List[str]:
        """Get the list of files to process."""
        files = []
        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            if item:
                files.append(item.text())
        return files
        
    def _select_template(self):
        """Select a template file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Template File",
            str(Path.home()),
            "Text Files (*.txt);;All Files (*)"
        )
        if file_path:
            self.template_path_edit.setText(file_path)
            
    def _select_output(self):
        """Select output file path."""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save MOC As",
            str(Path.home() / "MOC.md"),
            "Markdown Files (*.md);;All Files (*)"
        )
        if file_path:
            self.output_path_edit.setText(file_path)
        
    def _on_progress_updated(self, progress):
        """Handle progress updates."""
        if hasattr(progress, 'current_step') and progress.current_step:
            self.append_log(f"Step: {progress.current_step}")
        if hasattr(progress, 'status'):
            self.append_log(f"Status: {progress.status}")
        
    def _on_processing_finished(self, result):
        """Handle processing completion."""
        self.set_processing_state(False)
        self.append_log("MOC generation completed successfully!")
        
        # Enable report button if available
        if hasattr(self, 'report_btn'):
            self.report_btn.setEnabled(True)
            
    def _on_processing_error(self, error: str):
        """Handle processing errors."""
        self.set_processing_state(False)
        self.append_log(f"Error: {error}")
        self.show_error("Processing Error", error)
        
    def cleanup_workers(self):
        """Clean up worker threads."""
        if self.moc_worker and self.moc_worker.isRunning():
            self.moc_worker.stop()
            self.moc_worker.wait(3000)
        super().cleanup_workers()
    
    def _load_settings(self):
        """Load saved settings from session."""
        try:
            # Load spinbox values
            saved_depth = self.gui_settings.get_spinbox_value(self.tab_name, "depth", 3)
            self.depth_spin.setValue(saved_depth)
            
            # Load line edit text
            saved_title = self.gui_settings.get_line_edit_text(self.tab_name, "title", "")
            self.title_edit.setText(saved_title)
            
            saved_template = self.gui_settings.get_line_edit_text(self.tab_name, "template_path", "")
            self.template_path_edit.setText(saved_template)
            
            saved_output = self.gui_settings.get_line_edit_text(self.tab_name, "output_path", "")
            self.output_path_edit.setText(saved_output)
            
            # Load checkbox states
            self.beliefs_checkbox.setChecked(
                self.gui_settings.get_checkbox_state(self.tab_name, "include_beliefs", True)
            )
            
            logger.debug(f"Loaded settings for {self.tab_name} tab")
        except Exception as e:
            logger.error(f"Failed to load settings for {self.tab_name} tab: {e}")
    
    def _save_settings(self):
        """Save current settings to session."""
        try:
            # Save spinbox values
            self.gui_settings.set_spinbox_value(self.tab_name, "depth", self.depth_spin.value())
            
            # Save line edit text
            self.gui_settings.set_line_edit_text(self.tab_name, "title", self.title_edit.text())
            self.gui_settings.set_line_edit_text(self.tab_name, "template_path", self.template_path_edit.text())
            self.gui_settings.set_line_edit_text(self.tab_name, "output_path", self.output_path_edit.text())
            
            # Save checkbox states
            self.gui_settings.set_checkbox_state(self.tab_name, "include_beliefs", self.beliefs_checkbox.isChecked())
            
            logger.debug(f"Saved settings for {self.tab_name} tab")
        except Exception as e:
            logger.error(f"Failed to save settings for {self.tab_name} tab: {e}")
    
    def _on_setting_changed(self):
        """Called when any setting changes to automatically save."""
        self._save_settings() 