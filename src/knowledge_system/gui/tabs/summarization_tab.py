"""Summarization tab for document summarization using AI models."""

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


class EnhancedSummarizationWorker(QThread):
    """Enhanced worker thread for summarization with real-time progress dialog."""
    
    progress_updated = pyqtSignal(object)  # SummarizationProgress
    file_completed = pyqtSignal(int, int)  # current, total
    processing_finished = pyqtSignal()
    processing_error = pyqtSignal(str)
    
    def __init__(self, files, settings, gui_settings, parent=None):
        super().__init__(parent)
        self.files = files
        self.settings = settings
        self.gui_settings = gui_settings
        self.progress_dialog = None
        self.should_stop = False
        
    def run(self):
        """Run the summarization process."""
        try:
            from ...processors.summarizer import SummarizerProcessor
            from ...utils.progress import SummarizationProgress
            from ...utils.file_io import overwrite_or_insert_summary_section
            from pathlib import Path
            from datetime import datetime
            
            # Create processor with GUI settings
            processor = SummarizerProcessor(
                provider=self.gui_settings.get('provider', 'openai'),
                model=self.gui_settings.get('model', 'gpt-4o-mini-2024-07-18'),
                max_tokens=self.gui_settings.get('max_tokens', 10000)
            )
            
            # Get output directory (if not updating in-place)
            output_dir = None
            if not self.gui_settings.get('update_in_place', False):
                output_dir = Path(self.gui_settings.get('output_dir', ''))
                if output_dir:
                    output_dir.mkdir(parents=True, exist_ok=True)
            
            for i, file_path in enumerate(self.files):
                if self.should_stop:
                    break
                    
                file_path_obj = Path(file_path)
                
                # Create enhanced progress object
                progress = SummarizationProgress(
                    current_file=file_path,
                    total_files=len(self.files),
                    completed_files=i,
                    current_step=f"Processing {file_path_obj.name}...",
                    percent=(i / len(self.files)) * 100.0,
                    provider=self.gui_settings.get('provider', 'openai'),
                    model_name=self.gui_settings.get('model', 'gpt-4o-mini-2024-07-18')
                )
                
                self.progress_updated.emit(progress)
                
                # Process the file
                result = processor.process(
                    file_path,
                    style=self.gui_settings.get('style', 'general'),
                    prompt_template=self.gui_settings.get('template_path', None) or None,
                    progress_callback=lambda p: self.progress_updated.emit(p)
                )
                
                if result.success:
                    # Save the summary to file
                    try:
                        if self.gui_settings.get('update_in_place', False) and file_path_obj.suffix.lower() == ".md":
                            # Update existing .md file in-place
                            overwrite_or_insert_summary_section(file_path_obj, result.data)
                            self.progress_updated.emit(SummarizationProgress(
                                current_file=file_path,
                                total_files=len(self.files),
                                completed_files=i + 1,
                                current_step=f"✅ Updated summary in-place: {file_path_obj.name}",
                                percent=((i + 1) / len(self.files)) * 100.0,
                                provider=self.gui_settings.get('provider', 'openai'),
                                model_name=self.gui_settings.get('model', 'gpt-4o-mini-2024-07-18')
                            ))
                        else:
                            # Create new summary file
                            if not output_dir:
                                # Fallback: create summary next to original file
                                output_file = file_path_obj.parent / f"{file_path_obj.stem}_summary.md"
                            else:
                                output_file = output_dir / f"{file_path_obj.stem}_summary.md"
                            
                            # Ensure output directory exists
                            output_file.parent.mkdir(parents=True, exist_ok=True)
                            
                            # Write summary with enhanced metadata (like CLI does)
                            metadata = result.metadata or {}
                            
                            with open(output_file, "w", encoding="utf-8") as f:
                                # Basic metadata
                                f.write(f"# Summary of {file_path_obj.name}\n\n")
                                f.write(f"**Source File:** {file_path_obj.name}\n")
                                f.write(f"**Source Path:** {file_path_obj.absolute()}\n")

                                f.write(f"**Model:** {self.gui_settings.get('model', 'gpt-4o-mini-2024-07-18')}\n")
                                f.write(f"**Provider:** {metadata.get('provider', self.gui_settings.get('provider', 'unknown'))}\n")
                                if self.gui_settings.get('template_path'):
                                    f.write(f"**Template:** {self.gui_settings.get('template_path')}\n")
                                f.write("\n")
                                
                                # Performance stats
                                f.write("**Performance:**\n")
                                processing_time = metadata.get('processing_time', 0)
                                f.write(f"- **Processing Time:** {processing_time:.1f}s\n")
                                
                                prompt_tokens = metadata.get('prompt_tokens', 0)
                                completion_tokens = metadata.get('completion_tokens', 0)
                                total_tokens = metadata.get('total_tokens', 0)
                                f.write(f"- **Tokens Used:** {total_tokens:,} total ({prompt_tokens:,} prompt + {completion_tokens:,} completion)\n")
                                
                                tokens_per_second = metadata.get('tokens_per_second', 0)
                                f.write(f"- **Speed:** {tokens_per_second:.1f} tokens/second\n")
                                f.write("\n")
                                
                                # Content analysis
                                f.write("**Content Analysis:**\n")
                                input_length = metadata.get('input_length', 0)
                                summary_length = len(result.data) if result.data else 0
                                f.write(f"- **Input Length:** {input_length:,} characters\n")
                                f.write(f"- **Summary Length:** {summary_length:,} characters\n")
                                
                                compression_ratio = metadata.get('compression_ratio', 0)
                                reduction_percent = (1 - compression_ratio) * 100 if compression_ratio > 0 else 0
                                f.write(f"- **Compression:** {reduction_percent:.1f}% reduction\n")
                                f.write("\n")
                                
                                # Add chunking info if available
                                if metadata.get('chunks_processed'):
                                    f.write("**Processing Details:**\n")
                                    f.write(f"- **Chunks Processed:** {metadata.get('chunks_processed')}\n")
                                    f.write(f"- **Chunking Strategy:** {metadata.get('chunking_summary', 'N/A')}\n")
                                    f.write("\n")
                                
                                f.write(f"**Generated:** {datetime.now().isoformat()}\n\n")
                                f.write("---\n\n")
                                f.write(result.data)
                            
                            self.progress_updated.emit(SummarizationProgress(
                                current_file=file_path,
                                total_files=len(self.files),
                                completed_files=i + 1,
                                current_step=f"✅ Summary saved: {output_file.name}",
                                percent=((i + 1) / len(self.files)) * 100.0,
                                provider=self.gui_settings.get('provider', 'openai'),
                                model_name=self.gui_settings.get('model', 'gpt-4o-mini-2024-07-18')
                            ))
                            
                    except Exception as save_error:
                        self.processing_error.emit(f"Failed to save summary for {file_path_obj.name}: {save_error}")
                        continue
                else:
                    # Handle processing failure
                    error_msg = '; '.join(result.errors) if result.errors else 'Unknown error'
                    self.progress_updated.emit(SummarizationProgress(
                        current_file=file_path,
                        total_files=len(self.files),
                        completed_files=i + 1,
                        current_step=f"❌ Failed: {error_msg}",
                        percent=((i + 1) / len(self.files)) * 100.0,
                        provider=self.gui_settings.get('provider', 'openai'),
                        model_name=self.gui_settings.get('model', 'gpt-4o-mini-2024-07-18')
                    ))
                
                self.file_completed.emit(i + 1, len(self.files))
                
            self.processing_finished.emit()
            
        except Exception as e:
            self.processing_error.emit(str(e))
    
    def stop(self):
        """Stop the summarization process."""
        self.should_stop = True


class SummarizationTab(BaseTab):
    """Tab for document summarization using AI models."""
    
    def __init__(self, parent=None):
        self.summarization_worker = None
        self.gui_settings = get_gui_settings_manager()
        self.tab_name = "Document Summarization"
        super().__init__(parent)
        
    def _setup_ui(self):
        """Setup the summarization UI."""
        layout = QVBoxLayout(self)
        
        # Input section
        input_group = QGroupBox("Input Documents")
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
        clear_btn = QPushButton("🗑️ Clear All Files")
        clear_btn.clicked.connect(self._clear_files)
        clear_btn.setStyleSheet("background-color: #d32f2f; font-weight: bold; color: white;")
        clear_btn.setToolTip("Remove all files from the list (including files from previous sessions)")

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

        # Provider selection (made narrower)
        provider_label = QLabel("Provider:")
        provider_label.setToolTip("Choose AI provider: OpenAI (GPT models), Anthropic (Claude models), or Local (self-hosted models). Requires API keys in Settings.")
        self.provider_combo = QComboBox()
        self.provider_combo.addItems(["openai", "anthropic", "local"])
        self.provider_combo.currentTextChanged.connect(self._update_models)
        self.provider_combo.currentTextChanged.connect(self._on_setting_changed)
        self.provider_combo.setToolTip("Choose AI provider: OpenAI (GPT models), Anthropic (Claude models), or Local (self-hosted models). Requires API keys in Settings.")
        self.provider_combo.setMaximumWidth(120)  # Make provider field narrower
        
        settings_layout.addWidget(provider_label, 0, 0)
        settings_layout.addWidget(self.provider_combo, 0, 1)

        # Model selection (made wider)
        model_label = QLabel("Model:")
        model_label.setToolTip("Select the specific AI model to use for summarization. Different models have different capabilities, costs, and speed.")
        self.model_combo = QComboBox()
        self._update_models()  # Initialize with correct models
        self.model_combo.currentTextChanged.connect(self._on_setting_changed)
        self.model_combo.setToolTip("Select the specific AI model to use for summarization. Different models have different capabilities, costs, and speed.")
        self.model_combo.setMinimumWidth(300)  # Make model field wider to accommodate long model names
        
        settings_layout.addWidget(model_label, 0, 2)
        settings_layout.addWidget(self.model_combo, 0, 3, 1, 2)  # Span 2 columns to make it wider

        # Max tokens
        max_tokens_label = QLabel("Max Tokens:")
        max_tokens_label.setToolTip("Maximum length of generated summary in tokens. Higher values create longer summaries but cost more. 1000 tokens ≈ 750 words.")
        self.max_tokens_spin = QSpinBox()
        self.max_tokens_spin.setRange(100, 100000)
        self.max_tokens_spin.setValue(10000)
        self.max_tokens_spin.setToolTip("Maximum length of generated summary in tokens. Higher values create longer summaries but cost more. 1000 tokens ≈ 750 words.")
        self.max_tokens_spin.valueChanged.connect(self._on_setting_changed)
        self.max_tokens_spin.setMinimumWidth(120)
        self.max_tokens_spin.setToolTip("Maximum length of generated summary in tokens. Higher values create longer summaries but cost more. 1000 tokens ≈ 750 words.")
        
        settings_layout.addWidget(max_tokens_label, 1, 0)
        settings_layout.addWidget(self.max_tokens_spin, 1, 1)



        # Prompt file
        prompt_label = QLabel("Prompt File:")
        prompt_label.setToolTip("Path to custom prompt template file for summarization. Leave empty to use default prompts.")
        self.template_path_edit = QLineEdit("")
        self.template_path_edit.setMinimumWidth(250)
        self.template_path_edit.setToolTip("Path to custom prompt template file for summarization. Leave empty to use default prompts.")
        self.template_path_edit.textChanged.connect(self._on_setting_changed)
        
        settings_layout.addWidget(prompt_label, 1, 2)
        settings_layout.addWidget(self.template_path_edit, 1, 3, 1, 1)  # Adjusted to fit in same row
        browse_template_btn = QPushButton("Browse")
        browse_template_btn.setFixedWidth(80)
        browse_template_btn.clicked.connect(self._select_template)
        settings_layout.addWidget(browse_template_btn, 1, 4)

        # Options
        self.update_md_checkbox = QCheckBox("Update .md files in-place")
        self.update_md_checkbox.setToolTip(
            "If checked, will update the ## Summary section of existing .md files instead of creating new files"
        )
        self.update_md_checkbox.toggled.connect(self._toggle_output_options)
        self.update_md_checkbox.toggled.connect(self._on_setting_changed)
        settings_layout.addWidget(self.update_md_checkbox, 2, 0, 1, 2)

        self.progress_checkbox = QCheckBox("Show progress tracking")
        settings_layout.addWidget(self.progress_checkbox, 2, 2, 1, 2)

        self.resume_checkbox = QCheckBox("Resume from checkpoint")
        self.resume_checkbox.setToolTip(
            "If a previous summarization was interrupted, resume from where it left off using the checkpoint file"
        )
        settings_layout.addWidget(self.resume_checkbox, 3, 0, 1, 2)

        # Output folder (only shown when not updating in-place)
        self.output_label = QLabel("Output:")
        settings_layout.addWidget(self.output_label, 4, 0)
        self.output_edit = QLineEdit()
        self.output_edit.setMinimumWidth(250)
        self.output_edit.textChanged.connect(self._on_setting_changed)
        settings_layout.addWidget(self.output_edit, 4, 1, 1, 3)  # Span 3 columns for consistency
        self.output_btn = QPushButton("Browse")
        self.output_btn.setFixedWidth(80)
        self.output_btn.clicked.connect(self._select_output)
        settings_layout.addWidget(self.output_btn, 4, 4)

        # Initially hide output selector if update in-place is checked
        self._toggle_output_options(self.update_md_checkbox.isChecked())

        settings_group.setLayout(settings_layout)
        layout.addWidget(settings_group)

        # Action buttons
        action_layout = self._create_action_layout()
        layout.addLayout(action_layout)

        # Output section
        output_layout = self._create_output_section()
        layout.addLayout(output_layout)

        layout.addStretch()
        
        # Load saved settings after UI is set up
        self._load_settings()
        
    def _connect_signals(self):
        """Connect internal signals."""
        # Connect any additional signals specific to summarization
        pass
        
    def _get_start_button_text(self) -> str:
        """Get the text for the start button."""
        return "📝 Start Enhanced Summarization"
        
    def _start_processing(self):
        """Start the summarization process."""
        if not self.validate_inputs():
            return
            
        files = self._get_file_list()
        if not files:
            self.show_warning("No Files", "Please add files to summarize.")
            return
            
        # Prepare settings
        gui_settings = {
            'provider': self.provider_combo.currentText(),
            'model': self.model_combo.currentText(),
            'max_tokens': self.max_tokens_spin.value(),
            'template_path': self.template_path_edit.text(),
            'output_dir': self.output_edit.text() if not self.update_md_checkbox.isChecked() else None,
            'update_in_place': self.update_md_checkbox.isChecked()
        }
        
        # Start worker
        self.summarization_worker = EnhancedSummarizationWorker(files, self.settings, gui_settings, self)
        self.summarization_worker.progress_updated.connect(self._on_progress_updated)
        self.summarization_worker.file_completed.connect(self._on_file_completed)
        self.summarization_worker.processing_finished.connect(self._on_processing_finished)
        self.summarization_worker.processing_error.connect(self._on_processing_error)
        
        self.active_workers.append(self.summarization_worker)
        self.set_processing_state(True)
        self.clear_log()
        self.append_log("Starting summarization process...")
        
        self.summarization_worker.start()
        
    def validate_inputs(self) -> bool:
        """Validate inputs before processing."""
        if not self._get_file_list():
            return False
            
        if not self.update_md_checkbox.isChecked() and not self.output_edit.text():
            self.show_warning("No Output Directory", "Please select an output directory or enable in-place updates.")
            return False
            
        return True
        
    def _add_files(self):
        """Add files to the summarization list."""
        files, _ = QFileDialog.getOpenFileNames(
            self, "Select Files to Summarize",
            str(Path.home()),
            "All Supported (*.txt *.md *.pdf *.docx);;Text Files (*.txt);;Markdown Files (*.md);;PDF Files (*.pdf);;Word Documents (*.docx)"
        )
        
        for file_path in files:
            self.file_list.addItem(file_path)
            
    def _add_folder(self):
        """Add all compatible files from a folder."""
        folder_path = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder_path:
            folder = Path(folder_path)
            extensions = ['.txt', '.md', '.pdf', '.docx']
            
            for file_path in folder.rglob('*'):
                if file_path.suffix.lower() in extensions:
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
        
    def _update_models(self):
        """Update the model list based on selected provider."""
        provider = self.provider_combo.currentText()
        self.model_combo.clear()
        
        if provider == "openai":
            models = [
                "gpt-3.5-turbo-0125",
                "gpt-3.5-turbo-1106", 
                "gpt-4-0613",
                "gpt-4-1106-preview",
                "gpt-4-turbo-2024-04-09",
                "gpt-4o-2024-05-13",
                "gpt-4o-2024-08-06",
                "gpt-4o-mini-2024-07-18"
            ]
        elif provider == "anthropic":
            models = [
                "claude-3-haiku-20240307",
                "claude-3-sonnet-20240229", 
                "claude-3-opus-20240229",
                "claude-3-5-sonnet-20240620",
                "claude-3-5-sonnet-20241022",
                "claude-3-5-haiku-20241022"
            ]
        else:  # local
            models = [
                "llama2:7b-chat",
                "llama2:13b-chat", 
                "llama3.1:8b-instruct",
                "llama3.2:3b-instruct",
                "mistral:7b-instruct-v0.2",
                "codellama:7b-instruct",
                "codellama:13b-instruct",
                "phi3:3.8b-mini-instruct",
                "qwen2.5:7b-instruct",
                "qwen2.5:14b-instruct",
                "qwen2.5:32b-instruct",
                "qwen2.5-coder:7b-instruct"
            ]
            
        self.model_combo.addItems(models)
        
        # Set a reasonable default
        if models:
            if provider == "openai":
                self.model_combo.setCurrentText("gpt-4o-mini-2024-07-18")
            elif provider == "anthropic":
                self.model_combo.setCurrentText("claude-3-5-sonnet-20241022")
            else:
                self.model_combo.setCurrentText("qwen2.5-coder:7b-instruct")
        
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
        """Select output directory."""
        folder_path = QFileDialog.getExistingDirectory(self, "Select Output Directory")
        if folder_path:
            self.output_edit.setText(folder_path)
            
    def _toggle_output_options(self, in_place: bool):
        """Toggle output directory visibility based on in-place option."""
        self.output_label.setVisible(not in_place)
        self.output_edit.setVisible(not in_place)
        self.output_btn.setVisible(not in_place)
        
    def _on_progress_updated(self, progress):
        """Handle progress updates with detailed status information."""
        if hasattr(progress, 'current_step') and progress.current_step:
            # Show the detailed progress step
            self.append_log(progress.current_step)
            
        if hasattr(progress, 'percent'):
            # Update any progress bars or percentage displays
            if hasattr(self, 'progress_bar'):
                self.progress_bar.setValue(int(progress.percent))
        
    def _on_file_completed(self, current: int, total: int):
        """Handle file completion with detailed progress."""
        percent = (current / total) * 100 if total > 0 else 0
        self.append_log(f"Progress: {current}/{total} files completed ({percent:.1f}%)")
        
    def _on_processing_finished(self):
        """Handle processing completion with success summary."""
        self.set_processing_state(False)
        self.append_log("\n" + "="*50)
        self.append_log("🎉 SUMMARIZATION COMPLETED SUCCESSFULLY!")
        self.append_log("="*50)
        
        # Show output location information
        if self.update_md_checkbox.isChecked():
            self.append_log("📝 Summary sections have been updated in-place for .md files")
        else:
            output_dir = self.output_edit.text()
            if output_dir:
                self.append_log(f"📁 Summary files saved to: {output_dir}")
            else:
                self.append_log("📁 Summary files saved next to original files")
        
        self.append_log("✅ All files processed successfully!")
        
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
        if self.summarization_worker and self.summarization_worker.isRunning():
            self.summarization_worker.stop()
            self.summarization_worker.wait(3000)
        super().cleanup_workers()
    
    def _load_settings(self):
        """Load saved settings from session."""
        try:
            # Load output directory - use configured summaries path as default
            default_output_dir = str(self.settings.paths.summaries)
            saved_output_dir = self.gui_settings.get_output_directory(
                self.tab_name, 
                default_output_dir
            )
            self.output_edit.setText(saved_output_dir)
            
            # Load provider selection
            saved_provider = self.gui_settings.get_combo_selection(self.tab_name, "provider", "local")
            index = self.provider_combo.findText(saved_provider)
            if index >= 0:
                self.provider_combo.setCurrentIndex(index)
                self._update_models()  # Update models after setting provider
            
            # Load model selection
            saved_model = self.gui_settings.get_combo_selection(self.tab_name, "model", "qwen2.5-coder:7b-instruct")
            index = self.model_combo.findText(saved_model)
            if index >= 0:
                self.model_combo.setCurrentIndex(index)
            
            # Load max tokens
            saved_max_tokens = self.gui_settings.get_spinbox_value(self.tab_name, "max_tokens", 10000)
            self.max_tokens_spin.setValue(saved_max_tokens)
            

            
            # Load template path
            saved_template = self.gui_settings.get_line_edit_text(self.tab_name, "template_path", "")
            self.template_path_edit.setText(saved_template)
            
            # Load checkbox states
            self.update_md_checkbox.setChecked(
                self.gui_settings.get_checkbox_state(self.tab_name, "update_in_place", False)
            )
            
            # Update output visibility based on checkbox state
            self._toggle_output_options(self.update_md_checkbox.isChecked())
            
            logger.debug(f"Loaded settings for {self.tab_name} tab")
        except Exception as e:
            logger.error(f"Failed to load settings for {self.tab_name} tab: {e}")
    
    def _save_settings(self):
        """Save current settings to session."""
        try:
            # Save output directory
            self.gui_settings.set_output_directory(self.tab_name, self.output_edit.text())
            
            # Save combo selections
            self.gui_settings.set_combo_selection(self.tab_name, "provider", self.provider_combo.currentText())
            self.gui_settings.set_combo_selection(self.tab_name, "model", self.model_combo.currentText())
            
            # Save spinbox values
            self.gui_settings.set_spinbox_value(self.tab_name, "max_tokens", self.max_tokens_spin.value())
            
            # Save line edit text
            self.gui_settings.set_line_edit_text(self.tab_name, "template_path", self.template_path_edit.text())
            
            # Save checkbox states
            self.gui_settings.set_checkbox_state(self.tab_name, "update_in_place", self.update_md_checkbox.isChecked())
            
            logger.debug(f"Saved settings for {self.tab_name} tab")
        except Exception as e:
            logger.error(f"Failed to save settings for {self.tab_name} tab: {e}")
    
    def _on_setting_changed(self):
        """Called when any setting changes to automatically save."""
        self._save_settings() 