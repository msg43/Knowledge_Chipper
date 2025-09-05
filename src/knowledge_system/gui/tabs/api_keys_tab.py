"""API Keys configuration tab for managing all API credentials."""

from pathlib import Path
from typing import Any

from PyQt6.QtCore import QTimer, pyqtSignal, Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QVBoxLayout,
    QLayout,
)

from ...logger import get_logger
from ..components.base_tab import BaseTab
from ..workers.ffmpeg_installer import FFmpegInstaller, FFmpegRelease
from ..workers.dmg_update_worker import DMGUpdateWorker

logger = get_logger(__name__)


class APIKeysTab(BaseTab):
    """Tab for API keys configuration."""

    # Signals for settings changes
    settings_saved = pyqtSignal()

    def __init__(self, parent: Any = None) -> None:
        # Initialize _actual_api_keys before calling super().__init__
        self._actual_api_keys: dict[str, str] = {}
        self.update_worker: UpdateWorker | None = None
        self.update_progress_dialog: QProgressDialog | None = None
        self._update_log_buffer: list[str] = []
        self.ffmpeg_worker: FFmpegInstaller | None = None
        self.update_btn: QPushButton | None = None
        self.admin_install_btn: QPushButton | None = None

        # Initialize settings manager for session persistence
        from ..core.settings_manager import get_gui_settings_manager

        self.gui_settings = get_gui_settings_manager()
        self.tab_name = "⚙️ Settings"

        super().__init__(parent)

    def _setup_ui(self) -> None:
        """Setup the API keys UI."""
        main_layout = QVBoxLayout(self)

        # Instructions section with dark background - moved to top
        instructions_group = QGroupBox("Instructions")
        instructions_layout = QVBoxLayout()

        instructions_text = QLabel(
            """
            🔑 API Key Configuration Guide:

• Bright Data API Key: Required for YouTube access. Uses pay-per-request model with residential proxies.
  Sign up at: https://brightdata.com/

• OpenAI API Key: Required for GPT-based summarization.
  Get your key at: https://platform.openai.com/api-keys

• Anthropic API Key: Required for Claude-based summarization.
  Get your key at: https://console.anthropic.com/

• HuggingFace Token: Required for speaker diarization (separating different speakers in audio).
  Get your free token at: https://huggingface.co/settings/tokens
            """
        )
        instructions_text.setWordWrap(True)
        # Dark background with light text for better readability
        instructions_text.setStyleSheet(
            """
            background-color: #2b2b2b;
            color: #ffffff;
            padding: 15px;
            border: 1px solid #555;
            border-radius: 5px;
        """
        )
        instructions_layout.addWidget(instructions_text)

        instructions_group.setLayout(instructions_layout)
        main_layout.addWidget(instructions_group)

        # API Key Input Fields - moved below instructions
        layout = QGridLayout()
        layout.addWidget(QLabel("🗝️ API Keys"), 0, 0, 1, 2)
        layout.addWidget(QFrame(), 1, 0, 1, 2)  # Separator

        # OpenAI API Key
        self.openai_key_edit = QLineEdit()
        self.openai_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.openai_key_edit.setPlaceholderText("sk-...")
        self._add_field_with_info(
            layout,
            "OpenAI API Key:",
            self.openai_key_edit,
            "Your OpenAI API key for GPT models (required for AI summarization).\n"
            "• Get your key at: https://platform.openai.com/api-keys\n"
            "• Format: sk-proj-... or sk-...\n"
            "• Used for: Document summarization, knowledge extraction, and analysis\n"
            "• Cost: Pay-per-token usage based on model and content length",
            2,
            0,
        )

        # Anthropic API Key
        self.anthropic_key_edit = QLineEdit()
        self.anthropic_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.anthropic_key_edit.setPlaceholderText("sk-ant-api03-...")
        self._add_field_with_info(
            layout,
            "Anthropic API Key:",
            self.anthropic_key_edit,
            "Your Anthropic API key for Claude models (alternative to OpenAI).\n"
            "• Get your key at: https://console.anthropic.com/\n"
            "• Format: sk-ant-api03-...\n"
            "• Used for: Document analysis with Claude's excellent reasoning capabilities\n"
            "• Cost: Competitive pricing with different token limits per model",
            3,
            0,
        )

        # HuggingFace Token
        self.huggingface_token_edit = QLineEdit()
        self.huggingface_token_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.huggingface_token_edit.setPlaceholderText("hf_...")
        self._add_field_with_info(
            layout,
            "HuggingFace Token:",
            self.huggingface_token_edit,
            "Your HuggingFace access token (optional, for speaker diarization).\n"
            "• Get your token at: https://huggingface.co/settings/tokens\n"
            "• Format: hf_...\n"
            "• Used for: Speaker diarization (identifying different speakers in audio)\n"
            "• Cost: Free for most models, some premium models may require subscription\n"
            "• Note: Only needed if you want to identify different speakers in transcriptions",
            4,
            0,
        )

        # Bright Data API Key
        self.bright_data_api_key_edit = QLineEdit()
        self.bright_data_api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.bright_data_api_key_edit.setPlaceholderText(
            "bd_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
        )
        self._add_field_with_info(
            layout,
            "Bright Data API Key:",
            self.bright_data_api_key_edit,
            "Your Bright Data API key for YouTube processing.\n"
            "• Sign up at: https://brightdata.com/\n"
            "• Used for: YouTube metadata, transcripts, and audio downloads\n"
            "• Why needed: Pay-per-request model with residential proxies\n"
            "• Cost: More cost-effective than monthly proxy subscriptions\n"
            "• Benefits: Direct JSON responses, automatic IP rotation, reliable access\n"
            "• Format: Starts with 'bd_' followed by alphanumeric characters",
            5,
            0,
        )



        # Load existing values and set up change handlers
        self._load_existing_values()
        self._setup_change_handlers()

        # Load session settings after UI is set up
        self._load_settings()

        # Save button (moved to top for better visibility)
        save_btn = QPushButton("💾 Save API Keys")
        save_btn.clicked.connect(self._save_settings)
        save_btn.setStyleSheet(
            "background-color: #4caf50; font-weight: bold; padding: 10px; font-size: 14px;"
        )
        save_btn.setToolTip(
            "Save all API keys and credentials securely.\n"
            "• Keys are encrypted and stored locally\n"
            "• Required before using AI features\n"
            "• You can save partial configurations (some keys can be empty)\n"
            "• Changes take effect immediately after saving"
        )
        main_layout.addWidget(save_btn)

        # Add the layout to a group and then to main layout
        api_group = QGroupBox("API Keys Configuration")
        api_group.setLayout(layout)
        main_layout.addWidget(api_group)

        # Button layout
        button_layout = QHBoxLayout()

        # Add spacer
        button_layout.addStretch()

        # Update section layout
        update_section = QVBoxLayout()

        # Update button
        self.update_btn = QPushButton("🔄 Check for Updates")
        self.update_btn.clicked.connect(self._check_for_updates)
        self.update_btn.setStyleSheet(
            """
            QPushButton {
                background-color: #2196F3;
                color: white;
                font-weight: bold;
                padding: 10px;
                font-size: 14px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
            QPushButton:pressed {
                background-color: #0D47A1;
            }
        """
        )
        self.update_btn.setToolTip(
            "Check for and install the latest version.\n"
            "• Pulls latest code from GitHub\n"
            "• Updates the app bundle\n"
            "• Preserves your settings and configuration\n"
            "• Requires an active internet connection"
        )
        update_section.addWidget(self.update_btn)

        # FFmpeg section
        ffmpeg_btn = QPushButton("📥 Install/Update FFmpeg")
        ffmpeg_btn.clicked.connect(self._install_ffmpeg)
        ffmpeg_btn.setToolTip(
            "Install FFmpeg for YouTube transcription features (no admin privileges required).\n\n"
            "✅ Features enabled with FFmpeg:\n"
            "• YouTube video downloads and transcription\n"
            "• Audio format conversions (MP3, WAV, etc.)\n"
            "• Video file audio extraction\n"
            "• Audio metadata and duration detection\n\n"
            "⚠️ Available without FFmpeg:\n"
            "• PDF processing and summarization\n"
            "• Text file processing\n"
            "• Local transcription (compatible formats)\n"
            "• All MOC generation features\n\n"
            "Safe to install - creates a user-space binary that doesn't affect your system."
        )
        update_section.addWidget(ffmpeg_btn)

        # Auto-update checkbox
        self.auto_update_checkbox = QCheckBox("Automatically check for updates on app launch")
        self.auto_update_checkbox.setToolTip(
            "When enabled, Knowledge Chipper will automatically check for new versions\n"
            "when you launch the app. Updates use fast DMG downloads (~2-3 minutes)\n"
            "and preserve all your data and settings in their standard macOS locations.\n\n"
            "• Checks: GitHub releases for newer versions\n"
            "• Downloads: Pre-built DMG files (no rebuilding required)\n"
            "• Preserves: All data, settings, and preferences\n"
            "• Restarts: Automatically to new version after update"
        )
        # Use consistent styling similar to other checkboxes in the app
        self.auto_update_checkbox.setStyleSheet(
            """
            QCheckBox {
                font-size: 12px;
                color: #333;
                font-weight: normal;
                padding: 4px;
            }
            QCheckBox:hover {
                color: #2196F3;
            }
            QCheckBox:checked {
                color: #1976d2;
            }
        """
        )
        # Load saved preference from app config (with GUI fallback for migration)
        from ...config import get_settings
        settings = get_settings()
        
        # Check both new app config and legacy GUI setting
        auto_update_enabled = (
            settings.app.auto_check_updates or 
            self.gui_settings.get_value(self.tab_name, "auto_update_enabled", False)
        )
        self.auto_update_checkbox.setChecked(auto_update_enabled)
        self.auto_update_checkbox.stateChanged.connect(self._on_auto_update_changed)
        update_section.addWidget(self.auto_update_checkbox)
        

        button_layout.addLayout(update_section)

        main_layout.addLayout(button_layout)

        # Status label
        self.status_label = QLabel("")
        main_layout.addWidget(self.status_label)

        # Admin Install link (lower right)
        admin_row = QHBoxLayout()
        admin_row.addStretch()
        self.admin_install_btn = QPushButton("Admin Install")
        self.admin_install_btn.setFlat(True)
        self.admin_install_btn.setStyleSheet(
            "QPushButton { color: #2196F3; background: transparent; border: none; font-weight: bold; }\n"
            "QPushButton:hover { text-decoration: underline; }"
        )
        self.admin_install_btn.setToolTip(
            "Install to /Applications (requires admin). Your macOS password will be requested in Terminal."
        )
        self.admin_install_btn.clicked.connect(self._admin_install)
        admin_row.addWidget(self.admin_install_btn)
        main_layout.addLayout(admin_row)

        main_layout.addStretch()

    def _load_existing_values(self) -> None:
        """Load existing API key values from settings."""
        # Load OpenAI key
        if self.settings.api_keys.openai_api_key:
            self._actual_api_keys["openai_api_key"] = (
                self.settings.api_keys.openai_api_key
            )
            self.openai_key_edit.setText(
                "••••••••••••••••••••••••••••••••••••••••••••••••••••"
            )

        # Load Anthropic key
        if self.settings.api_keys.anthropic_api_key:
            self._actual_api_keys["anthropic_api_key"] = (
                self.settings.api_keys.anthropic_api_key
            )
            self.anthropic_key_edit.setText(
                "••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••"
            )

        # Load HuggingFace token
        if self.settings.api_keys.huggingface_token:
            self._actual_api_keys["huggingface_token"] = (
                self.settings.api_keys.huggingface_token
            )
            self.huggingface_token_edit.setText(
                "••••••••••••••••••••••••••••••••••••••••••••••••••••"
            )

        # Load Bright Data API key
        if (
            hasattr(self.settings.api_keys, "bright_data_api_key")
            and self.settings.api_keys.bright_data_api_key
        ):
            self._actual_api_keys["bright_data_api_key"] = (
                self.settings.api_keys.bright_data_api_key
            )
            self.bright_data_api_key_edit.setText(
                "••••••••••••••••••••••••••••••••••••••••••••••••••••"
            )



    def _setup_change_handlers(self) -> None:
        """Set up change handlers for password/key fields."""
        self.openai_key_edit.textChanged.connect(
            lambda text: self._handle_key_change("openai_api_key", text)
        )
        self.anthropic_key_edit.textChanged.connect(
            lambda text: self._handle_key_change("anthropic_api_key", text)
        )
        self.huggingface_token_edit.textChanged.connect(
            lambda text: self._handle_key_change("huggingface_token", text)
        )
        self.bright_data_api_key_edit.textChanged.connect(
            lambda text: self._handle_key_change("bright_data_api_key", text)
        )

    def _handle_key_change(self, key_name: str, new_text: str) -> None:
        """Handle changes to API key fields."""
        # If user types new content (not just the obscured dots), update the actual key
        if new_text and not new_text.startswith("••"):
            self._actual_api_keys[key_name] = new_text
            self._on_setting_changed()

    def _handle_password_change(self, key_name: str, new_text: str) -> None:
        """Handle changes to password fields."""
        # If user types new content (not just the obscured dots), update the actual password
        if new_text and not new_text.startswith("••"):
            self._actual_api_keys[key_name] = new_text
            self._on_setting_changed()

    def _on_setting_changed(self) -> None:
        """Called when any setting changes to automatically save to session."""
        try:
            # Save masked indicators for fields that have actual keys stored
            for key_name in self._actual_api_keys:
                if key_name == "openai_api_key":
                    self.gui_settings.set_line_edit_text(
                        self.tab_name,
                        "openai_key_masked",
                        "••••••••••••••••••••••••••••••••••••••••••••••••••••",
                    )
                elif key_name == "anthropic_api_key":
                    self.gui_settings.set_line_edit_text(
                        self.tab_name,
                        "anthropic_key_masked",
                        "••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••",
                    )
                elif key_name == "huggingface_token":
                    self.gui_settings.set_line_edit_text(
                        self.tab_name,
                        "huggingface_token_masked",
                        "••••••••••••••••••••••••••••••••••••••••••••••••••••",
                    )

            # Save the session
            self.gui_settings.save()

        except Exception as e:
            logger.error(f"Failed to save API keys session data: {e}")

    def _load_settings(self) -> None:
        """Load saved settings from session and existing credential files."""
        try:
            # First load from the credential files (like the existing _load_existing_values)
            self._load_existing_values()



            # Note: We don't restore actual API keys from session for security,
            # only restore the masked display indicators to show fields that were previously filled

            logger.debug(f"Loaded settings for {self.tab_name} tab")
        except Exception as e:
            logger.error(f"Failed to load settings for {self.tab_name} tab: {e}")

    def _get_start_button_text(self) -> str:
        """Get the text for the start button."""
        return "Save API Keys"

    def _start_processing(self) -> None:
        """Save settings when start button is pressed."""
        self._save_settings()

    def _save_settings(self) -> None:
        """Save API key settings and update environment variables."""
        try:
            logger.info("🔧 DEBUG: _save_settings() called")
            self.append_log("🔧 DEBUG: Save button clicked - starting save process...")

            # For password/key fields, use actual stored values if available, otherwise use form input

            openai_key = self._actual_api_keys.get(
                "openai_api_key", self.openai_key_edit.text().strip()
            )
            if not openai_key.startswith("••"):
                self.settings.api_keys.openai_api_key = openai_key

            anthropic_key = self._actual_api_keys.get(
                "anthropic_api_key", self.anthropic_key_edit.text().strip()
            )
            if not anthropic_key.startswith("••"):
                self.settings.api_keys.anthropic_api_key = anthropic_key

            huggingface_token = self._actual_api_keys.get(
                "huggingface_token", self.huggingface_token_edit.text().strip()
            )
            if not huggingface_token.startswith("••"):
                self.settings.api_keys.huggingface_token = huggingface_token

            bright_data_api_key = self._actual_api_keys.get(
                "bright_data_api_key", self.bright_data_api_key_edit.text().strip()
            )
            if not bright_data_api_key.startswith("••"):
                self.settings.api_keys.bright_data_api_key = bright_data_api_key

            # PERSISTENT STORAGE: Save credentials to YAML file for persistence across sessions
            self._save_credentials_to_file()

            # Update environment variables immediately
            self._load_api_keys_to_environment()

            # Save to session
            self._save_session()

            # Show success message
            self.status_label.setText("✅ API keys saved successfully!")
            self.status_label.setStyleSheet("color: #4caf50; font-weight: bold;")

            # Clear success message after 3 seconds
            QTimer.singleShot(3000, lambda: self.status_label.setText(""))

            self.append_log("API keys saved and environment variables updated")
            self.settings_saved.emit()

        except Exception as e:
            error_msg = f"Failed to save API keys: {e}"
            self.status_label.setText(f"❌ {error_msg}")
            self.status_label.setStyleSheet("color: #f44336; font-weight: bold;")
            self.append_log(error_msg)

    def _save_credentials_to_file(self) -> None:
        """Save API credentials to persistent YAML file."""
        try:
            logger.info("🔧 DEBUG: _save_credentials_to_file() called")
            self.append_log("🔧 DEBUG: Starting credential file save process...")

            from pathlib import Path

            import yaml  # type: ignore

            # Create credentials data structure using correct field names (Pydantic aliases)
            credentials_data = {
                "api_keys": {
                    "openai": self.settings.api_keys.openai_api_key
                    or "",  # Use alias 'openai'
                    "anthropic": self.settings.api_keys.anthropic_api_key
                    or "",  # Use alias 'anthropic'
                    "hf_token": self.settings.api_keys.huggingface_token
                    or "",  # Use alias 'hf_token'
                    # Persist Bright Data API key so it survives app restarts
                    "bright_data_api_key": getattr(
                        self.settings.api_keys, "bright_data_api_key", ""
                    )
                    or "",
                }
            }

            logger.info(
                f"🔧 DEBUG: credentials_data before filtering = {credentials_data}"
            )

            # Remove empty credentials to keep file clean
            credentials_data["api_keys"] = {
                k: v
                for k, v in credentials_data["api_keys"].items()
                if v and v.strip() and not v.startswith("••")
            }

            logger.info(
                f"🔧 DEBUG: credentials_data after filtering = {credentials_data}"
            )

            if not credentials_data["api_keys"]:
                logger.warning("🔧 DEBUG: No credentials to save after filtering!")
                self.append_log("⚠️ No credentials to save (all were empty or masked)")
                return

            # Determine save path - prefer config/credentials.yaml, handle running from src/ directory
            config_dir = Path("config")
            if not config_dir.exists():
                config_dir = Path("../config")

            config_dir.mkdir(exist_ok=True)
            credentials_path = config_dir / "credentials.yaml"

            logger.info(f"🔧 DEBUG: Saving to {credentials_path}")

            # Save to file with secure permissions
            with open(credentials_path, "w", encoding="utf-8") as f:
                f.write("# API Credentials - Auto-generated by Knowledge Workflow\n")
                f.write("# This file is excluded from git for security\n\n")
                yaml.dump(credentials_data, f, default_flow_style=False, indent=2)

            # Set restrictive file permissions (readable only by owner)
            import stat

            credentials_path.chmod(stat.S_IRUSR | stat.S_IWUSR)  # 600 permissions

            logger.info(f"✅ Credentials saved to {credentials_path}")
            self.append_log(f"💾 Credentials saved to {credentials_path}")

        except Exception as e:
            logger.error(f"Failed to save credentials file: {e}")
            self.append_log(f"❌ Failed to save credentials file: {e}")
            import traceback

            logger.error(f"Full traceback: {traceback.format_exc()}")

    def _load_api_keys_to_environment(self) -> None:
        """Load API keys to environment variables - stub method."""
        # This method should be connected to the main window's implementation
        parent = self.parent()
        if parent and hasattr(parent, "_load_api_keys_to_environment"):
            parent._load_api_keys_to_environment()

    def _save_session(self) -> None:
        """Save session data - stub method."""
        # This method should be connected to the main window's implementation
        parent = self.parent()
        if parent and hasattr(parent, "_save_session"):
            parent._save_session()

    def validate_inputs(self) -> bool:
        """Validate API key inputs."""
        # All API keys are optional, so always valid
        return True

    def _on_auto_update_changed(self, state: int) -> None:
        """Handle auto-update checkbox state change."""
        is_enabled = bool(state)
        
        # Save to both app config and GUI settings (for backward compatibility)
        from ...config import get_settings
        settings = get_settings()
        
        # Update app config (this will be saved to settings.yaml)
        settings.app.auto_check_updates = is_enabled
        
        # Also save to GUI settings for backward compatibility
        self.gui_settings.set_value(self.tab_name, "auto_update_enabled", is_enabled)
        self.gui_settings.save()
        
        # Save the app config to file
        try:
            from ...utils.macos_paths import get_config_dir
            config_file = get_config_dir() / "settings.yaml"
            settings.to_yaml(config_file)
            self.append_log(f"✅ {'Enabled' if is_enabled else 'Disabled'} automatic update checking on launch")
        except Exception as e:
            self.append_log(f"⚠️ Setting changed but couldn't save to config file: {e}")
            # Still update the runtime setting even if file save fails
            self.append_log(f"{'Enabled' if is_enabled else 'Disabled'} automatic update checking (runtime only)")

    def check_for_updates_on_launch(self) -> None:
        """Check for updates if auto-update is enabled."""
        from ...config import get_settings
        settings = get_settings()
        
        # Check app config first, fallback to GUI settings for migration
        auto_update_enabled = (
            settings.app.auto_check_updates or 
            self.gui_settings.get_value(self.tab_name, "auto_update_enabled", False)
        )
        
        if auto_update_enabled:
            self._check_for_updates(is_auto=True)

    def _check_for_updates(self, is_auto: bool = False) -> None:
        """Check for and install updates."""
        try:
            # If a previous worker exists
            if self.update_worker:
                # If it's still running, do not start another
                if self.update_worker.isRunning():
                    self.append_log("An update is already in progress…")
                    return
                # If it's finished or was cancelled, discard and create a fresh worker
                self.update_worker = None

            # Always create a fresh worker instance to avoid restarting finished QThreads
            self.update_worker = DMGUpdateWorker()
            self.update_worker.update_progress.connect(self._handle_update_progress)
            # New: determinate progress support
            try:
                self.update_worker.update_progress_percent.connect(self._handle_update_progress_percent)  # type: ignore[attr-defined]
            except Exception:
                pass
            self.update_worker.update_finished.connect(self._handle_update_finished)
            self.update_worker.update_error.connect(self._handle_update_error)
            
            # Initialize completion tracking
            self._update_completed = False
            
            # Add worker failure detection
            self.update_worker.finished.connect(self._on_worker_finished)

            # Create and show progress dialog
            self.update_progress_dialog = QProgressDialog(
                "Checking for updates...", "Cancel", 0, 0, self
            )
            self.update_progress_dialog.setWindowTitle("Skip the Podcast Desktop Update")
            self.update_progress_dialog.setModal(True)
            self.update_progress_dialog.setMinimumDuration(
                0 if is_auto else 500
            )  # Show immediately for auto-updates
            self.update_progress_dialog.canceled.connect(self._cancel_update)
            self.update_progress_dialog.setAutoClose(False)
            # Lock dialog size to prevent jumpy resizing
            self.update_progress_dialog.setMinimumWidth(520)
            self.update_progress_dialog.setMaximumWidth(520)
            self.update_progress_dialog.setFixedHeight(160)
            try:
                # Prevent layout from recalculating size on label changes
                if self.update_progress_dialog.layout():
                    self.update_progress_dialog.layout().setSizeConstraint(
                        QLayout.SizeConstraint.SetFixedSize
                    )
            except Exception:
                pass
            self.update_progress_dialog.setSizeGripEnabled(False)
            # Subtle styling and monospace label for better readability of logs
            self.update_progress_dialog.setStyleSheet(
                "QProgressDialog QLabel { font-family: Menlo, Monaco, monospace; font-size: 12px; }"
            )
            self.update_progress_dialog.show()

            # Start update process
            self.update_worker.start()

        except Exception as e:
            self._handle_update_error(str(e))

    def _cancel_update(self) -> None:
        """Cancel the update process."""
        if self.update_worker:
            try:
                if self.update_worker.isRunning():
                    self.update_worker.terminate()
                    self.update_worker.wait(1000)
            finally:
                self.update_worker = None
        if self.update_progress_dialog:
            self.update_progress_dialog.close()
            self.update_progress_dialog = None
        self.status_label.setText("Update cancelled")
        self.status_label.setStyleSheet("color: #666; font-weight: bold;")
        self.append_log("Update cancelled by user")

    def _handle_update_progress(self, message: str) -> None:
        """Handle update progress messages."""
        # Keep a rolling buffer of the last few lines for later inspection if needed
        self._update_log_buffer.append(message)
        if len(self._update_log_buffer) > 200:
            self._update_log_buffer = self._update_log_buffer[-200:]

        # Show only the last line, trimmed, to avoid an overly long progress label
        last_line = (message or "").splitlines()[-1].strip()
        if len(last_line) > 140:
            last_line = "…" + last_line[-140:]

        if self.update_progress_dialog:
            self._set_update_dialog_text(last_line)
        self.status_label.setText(message)
        self.status_label.setStyleSheet("color: #2196F3; font-weight: bold;")
        self.append_log(message)

    def _handle_update_progress_percent(self, percent: int, message: str) -> None:
        """Handle determinate progress updates."""
        if self.update_progress_dialog:
            # Switch from indeterminate to determinate on first percent
            if self.update_progress_dialog.maximum() == 0:
                self.update_progress_dialog.setMaximum(100)
            self.update_progress_dialog.setValue(max(0, min(100, int(percent))))
            if message:
                self._set_update_dialog_text(message)
        # Mirror to status label/log
        self.status_label.setText(f"{message} ({percent}%)" if message else f"{percent}%")
        self.status_label.setStyleSheet("color: #2196F3; font-weight: bold;")
        self.append_log(f"{percent}% - {message}" if message else f"{percent}%")

    def _handle_update_finished(self, success: bool, message: str) -> None:
        """Handle update completion."""
        # Mark update as completed to prevent false crash detection
        self._update_completed = True
        
        # Close progress dialog
        if self.update_progress_dialog:
            self.update_progress_dialog.close()
            self.update_progress_dialog = None

        if success:
            self.status_label.setText("✨ Update completed! Please restart the app.")
            self.status_label.setStyleSheet("color: #4caf50; font-weight: bold;")

            # Show restart dialog with auto-restart option
            from PyQt6.QtWidgets import QMessageBox, QPushButton
            
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle("Update Complete")
            msg_box.setText("The app has been updated successfully!")
            msg_box.setInformativeText(
                f"{message}\n\n"
                "The new version has been installed to /Applications.\n"
                "Your settings and data are preserved in their standard locations."
            )
            msg_box.setIcon(QMessageBox.Icon.Information)
            
            # Add custom buttons
            restart_button = msg_box.addButton("Restart Now", QMessageBox.ButtonRole.AcceptRole)
            later_button = msg_box.addButton("Restart Later", QMessageBox.ButtonRole.RejectRole)
            msg_box.setDefaultButton(restart_button)
            
            # Show the dialog and handle response
            msg_box.exec()
            
            if msg_box.clickedButton() == restart_button:
                self._restart_application()
            else:
                # Just close the dialog - user will restart manually later
                pass
        else:
            self.status_label.setText(f"❌ Update failed: {message}")
            self.status_label.setStyleSheet("color: #f44336; font-weight: bold;")

            # Show error dialog
            QMessageBox.warning(
                self,
                "Update Failed",
                f"Failed to update Knowledge Chipper:\n\n{message}",
                QMessageBox.StandardButton.Ok,
            )

        self.append_log(message)
        self.update_worker = None

    def _restart_application(self) -> None:
        """Restart the application after an update."""
        import sys
        import os
        from PyQt6.QtWidgets import QApplication
        
        try:
            # Get the current application path
            if getattr(sys, 'frozen', False):
                # Running as packaged app
                app_path = sys.executable
            else:
                # Running from source - find the app bundle or start script
                app_bundle_path = "/Applications/Knowledge_Chipper.app"
                user_app_path = os.path.expanduser("~/Applications/Knowledge_Chipper.app")
                
                if os.path.exists(app_bundle_path):
                    app_path = app_bundle_path
                elif os.path.exists(user_app_path):
                    app_path = user_app_path
                else:
                    # Fallback to running from source
                    app_path = sys.executable + " -m knowledge_system.gui.__main__"
            
            self.append_log("🔄 Restarting application...")
            
            # Close current application and start new one
            QApplication.quit()
            
            # Use subprocess to start the new instance
            import subprocess
            if app_path.endswith(".app"):
                subprocess.Popen(["open", app_path])
            else:
                subprocess.Popen(app_path.split())
                
        except Exception as e:
            self.append_log(f"❌ Failed to restart automatically: {e}")
            self.append_log("Please restart Knowledge Chipper manually.")

    def _on_worker_finished(self) -> None:
        """Handle worker thread finishing (for crash detection)."""
        if self.update_worker:
            # Check if worker finished without calling our completion handlers
            # This indicates the worker crashed or was terminated unexpectedly
            if (not hasattr(self, '_update_completed') or not self._update_completed) and self.update_worker.isFinished():
                self.append_log("⚠️  Update worker finished unexpectedly")
                if self.update_progress_dialog:
                    self.update_progress_dialog.close()
                    self.update_progress_dialog = None
                
                # Offer fallback option
                from PyQt6.QtWidgets import QMessageBox
                reply = QMessageBox.question(
                    self,
                    "Update Issue",
                    "The update process encountered an issue. Would you like to try the fallback update method?\n\n"
                    "This will open Terminal where you can run the update manually.",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.Yes
                )
                
                if reply == QMessageBox.StandardButton.Yes:
                    self._fallback_update()

    def _fallback_update(self) -> None:
        """Fallback update method using Terminal."""
        try:
            import subprocess
            from pathlib import Path
            
            # Find the script
            script_path = Path.home() / "Projects" / "Knowledge_Chipper" / "scripts" / "build_macos_app.sh"
            if not script_path.exists():
                self.append_log("❌ Could not find build script for fallback update")
                return
            
            # Open Terminal and run the original script
            script_dir = str(script_path.parent)
            script_name = script_path.name
            
            apple_script = f"""
tell application "Terminal"
  activate
  do script "cd {script_dir}; echo '🏗️ Running fallback updater…'; bash {script_name}; echo ''; echo '✅ Update finished. Please restart Knowledge Chipper and close this window.'"
end tell
"""
            
            subprocess.run(["osascript", "-e", apple_script], check=True)
            self.append_log("🔄 Opened Terminal for fallback update")
            self.append_log("Please follow the prompts in Terminal, then restart the app")
            
        except Exception as e:
            self.append_log(f"❌ Fallback update failed: {e}")
            self.append_log("Please run 'bash scripts/build_macos_app.sh' manually from Terminal")

    def _admin_install(self) -> None:
        """Perform an admin install to /Applications via Terminal, removing user-space copy first.
        This will prompt for the macOS password in Terminal (not inside the app)."""
        try:
            import subprocess
            from pathlib import Path

            script_path = Path.home() / "Projects" / "Knowledge_Chipper" / "scripts" / "build_macos_app.sh"
            if not script_path.exists():
                self.append_log("❌ Could not find build script for admin install")
                QMessageBox.critical(self, "Admin Install", "Build script not found. Ensure the repository exists at ~/Projects/Knowledge_Chipper.")
                return

            script_dir = str(script_path.parent)
            script_name = script_path.name

            self.append_log("🔐 Admin install requested. A Terminal window will open and may prompt for your macOS password.")

            # Disable update actions during admin install to avoid conflicts
            self._set_admin_install_in_progress(True)

            apple_script = f"""
tell application "Terminal"
  activate
  do script "cd {script_dir}; echo '🧹 Removing user-space copy (if any)...'; rm -rf \"$HOME/Applications/Knowledge_Chipper.app\"; echo '🏗️ Running admin installer to /Applications...'; bash {script_name}; echo ''; echo '✅ Admin install complete. You can close this window.'"
end tell
"""

            subprocess.run(["osascript", "-e", apple_script], check=True)
            self.append_log("🔄 Opened Terminal for admin install")
        except Exception as e:
            self.append_log(f"❌ Admin install failed to launch: {e}")
            QMessageBox.critical(self, "Admin Install", f"Failed to start admin install: {e}")
            # Re-enable on failure to launch
            self._set_admin_install_in_progress(False)

    def _set_admin_install_in_progress(self, in_progress: bool) -> None:
        """Enable/disable update controls while admin install runs externally."""
        try:
            if self.admin_install_btn:
                self.admin_install_btn.setEnabled(not in_progress)
                self.admin_install_btn.setToolTip(
                    "Admin install in progress…" if in_progress else
                    "Install to /Applications (requires admin). Your macOS password will be requested in Terminal."
                )
            if self.update_btn:
                self.update_btn.setEnabled(not in_progress)
                self.update_btn.setToolTip(
                    "Disabled during Admin Install" if in_progress else
                    "Check for and install the latest version.\n• Pulls latest code from GitHub\n• Updates the app bundle\n• Preserves your settings and configuration\n• Requires an active internet connection"
                )
        except Exception:
            pass

    def _handle_update_error(self, error: str) -> None:
        """Handle update errors."""
        # Mark update as completed (even though failed) to prevent false crash detection
        self._update_completed = True
        
        # Close progress dialog
        if self.update_progress_dialog:
            self.update_progress_dialog.close()
            self.update_progress_dialog = None

        self.status_label.setText(f"❌ Update error: {error}")
        self.status_label.setStyleSheet("color: #f44336; font-weight: bold;")
        self.append_log(f"Update error: {error}")

        # Show error dialog
        QMessageBox.critical(
            self,
            "Update Error",
            f"An error occurred while updating Knowledge Chipper:\n\n{error}",
            QMessageBox.StandardButton.Ok,
        )

        self.update_worker = None

    def _install_ffmpeg(self) -> None:
        """Start FFmpeg installation in background."""
        try:
            # Fast path: if ffmpeg already exists on PATH, configure and return
            import shutil as _shutil
            existing = _shutil.which("ffmpeg")
            if existing:
                import os as _os
                _os.environ["FFMPEG_PATH"] = existing
                ffprobe_existing = _shutil.which("ffprobe")
                if ffprobe_existing:
                    _os.environ["FFPROBE_PATH"] = ffprobe_existing
                self.status_label.setText("✅ FFmpeg already installed and configured")
                self.status_label.setStyleSheet("color: #4caf50; font-weight: bold;")
                self.append_log(f"Using existing ffmpeg at: {existing}")
                return
            # Probe common install paths when PATH is not inherited in GUI env
            for candidate in ("/opt/homebrew/bin/ffmpeg", "/usr/local/bin/ffmpeg"):
                try:
                    from pathlib import Path as _Path
                    if _Path(candidate).exists() and _Path(candidate).is_file():
                        import os as _os
                        _os.environ["FFMPEG_PATH"] = candidate
                        # Also set PATH for this process so shutil.which will work later
                        current_path = _os.environ.get("PATH", "")
                        bin_dir = str(_Path(candidate).parent)
                        if bin_dir not in current_path:
                            _os.environ["PATH"] = f"{bin_dir}:{current_path}" if current_path else bin_dir
                        # Try ffprobe next to it
                        probe = _Path(candidate).parent / "ffprobe"
                        if probe.exists():
                            _os.environ["FFPROBE_PATH"] = str(probe)
                        self.status_label.setText("✅ FFmpeg already installed and configured")
                        self.status_label.setStyleSheet("color: #4caf50; font-weight: bold;")
                        self.append_log(f"Using existing ffmpeg at: {candidate}")
                        return
                except Exception:
                    pass

            # Use the same arch-aware default selection as the first-run installer
            from ..workers.ffmpeg_installer import get_default_ffmpeg_release
            release = get_default_ffmpeg_release()

            self.ffmpeg_worker = FFmpegInstaller(release)
            self.ffmpeg_worker.progress.connect(self._handle_ffmpeg_progress)
            self.ffmpeg_worker.finished.connect(self._handle_ffmpeg_finished)

            self.update_progress_dialog = QProgressDialog(
                "Installing FFmpeg…", "Cancel", 0, 0, self
            )
            # Non-modal so the rest of the app remains responsive
            self.update_progress_dialog.setModal(False)
            self.update_progress_dialog.setMinimumDuration(0)
            self.update_progress_dialog.setMinimumWidth(520)
            self.update_progress_dialog.setStyleSheet(
                "QProgressDialog QLabel { font-family: Menlo, Monaco, monospace; font-size: 12px; }"
            )
            self.update_progress_dialog.canceled.connect(self._cancel_ffmpeg_install)
            self.update_progress_dialog.show()

            self.ffmpeg_worker.start()
        except Exception as e:
            self._handle_update_error(str(e))

    def _cancel_ffmpeg_install(self) -> None:
        if self.ffmpeg_worker:
            self.ffmpeg_worker.terminate()
            self.ffmpeg_worker = None
        if self.update_progress_dialog:
            self.update_progress_dialog.close()
            self.update_progress_dialog = None
        self.append_log("FFmpeg installation cancelled")

    def _handle_ffmpeg_progress(self, message: str) -> None:
        if self.update_progress_dialog:
            self._set_update_dialog_text(message)
        self.append_log(message)

    def _set_update_dialog_text(self, text: str) -> None:
        """Set progress dialog label text without resizing the dialog.

        - Replaces newlines with spaces
        - Elides text in the middle to fit the fixed dialog width
        """
        try:
            if not self.update_progress_dialog:
                return
            clean = (text or "").replace("\n", " ").strip()
            # Find the internal QLabel and set elided text
            label = self.update_progress_dialog.findChild(QLabel)
            if label is None:
                # Fallback to dialog API
                self.update_progress_dialog.setLabelText(clean)
                return
            fm = label.fontMetrics()
            # Approximate available width inside dialog (account for margins)
            available = max(100, self.update_progress_dialog.width() - 60)
            elided = fm.elidedText(clean, Qt.TextElideMode.ElideMiddle, available)
            label.setText(elided)
        except Exception:
            # Safe fallback
            try:
                if self.update_progress_dialog:
                    self.update_progress_dialog.setLabelText(clean)
            except Exception:
                pass

    def _handle_ffmpeg_finished(
        self, success: bool, message: str, installed_path: str
    ) -> None:
        if self.update_progress_dialog:
            self.update_progress_dialog.close()
            self.update_progress_dialog = None
        if success:
            # Persist the path in the process environment for this app run
            import os

            os.environ["FFMPEG_PATH"] = installed_path
            # Also try to set FFPROBE_PATH next to it
            ffprobe_candidate = installed_path.replace("ffmpeg", "ffprobe")
            if Path(ffprobe_candidate).exists():
                os.environ["FFPROBE_PATH"] = ffprobe_candidate
            self.status_label.setText("✅ FFmpeg installed and configured")
            self.status_label.setStyleSheet("color: #4caf50; font-weight: bold;")
        else:
            self.status_label.setText(f"❌ FFmpeg install failed: {message}")
            self.status_label.setStyleSheet("color: #f44336; font-weight: bold;")
        self.append_log(message)
