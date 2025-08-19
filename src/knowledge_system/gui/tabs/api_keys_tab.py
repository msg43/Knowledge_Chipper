""" API Keys configuration tab for managing all API credentials."""

from pathlib import Path
from typing import Any

from PyQt6.QtCore import QTimer, pyqtSignal
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
)

from ...logger import get_logger
from ..components.base_tab import BaseTab
from ..workers.ffmpeg_installer import FFmpegInstaller, FFmpegRelease
from ..workers.update_worker import UpdateWorker

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

• WebShare Proxy: Required for YouTube access. The system uses only WebShare rotating residential proxies.
  Sign up at: https://www.webshare.io/

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

        # WebShare Proxy Credentials (DEPRECATED - use Bright Data instead)
        webshare_header = QLabel("⚠️ WebShare Proxy Credentials (DEPRECATED)")
        webshare_header.setStyleSheet(
            "color: #FFA500; font-weight: bold;"
        )  # Orange warning color
        layout.addWidget(webshare_header, 6, 0, 1, 2)

        # WebShare Username
        self.webshare_username_edit = QLineEdit()
        self.webshare_username_edit.setPlaceholderText("username")
        self._add_field_with_info(
            layout,
            "WebShare Username:",
            self.webshare_username_edit,
            "⚠️ DEPRECATED: Use Bright Data API Key instead (see above).\n"
            "• WebShare will be removed in a future version\n"
            "• Bright Data offers better cost efficiency (pay-per-request)\n"
            "• Still supported for backward compatibility\n"
            "• Sign up at: https://www.webshare.io/ (if still needed)\n"
            "• Note: Only required if you plan to process YouTube content",
            7,
            0,
        )

        # WebShare Password
        self.webshare_password_edit = QLineEdit()
        self.webshare_password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.webshare_password_edit.setPlaceholderText("password")
        self._add_field_with_info(
            layout,
            "WebShare Password:",
            self.webshare_password_edit,
            "⚠️ DEPRECATED: Use Bright Data API Key instead (see above).\n"
            "• WebShare will be removed in a future version\n"
            "• Bright Data is more cost-effective and reliable\n"
            "• Still supported for backward compatibility\n"
            "• Tip: Use a dedicated password for API services",
            8,
            0,
        )

        # Load existing values and set up change handlers
        self._load_existing_values()
        self._setup_change_handlers()

        # Load session settings after UI is set up
        self._load_settings()

        # Add the layout to a group and then to main layout
        api_group = QGroupBox("API Keys Configuration")
        api_group.setLayout(layout)
        main_layout.addWidget(api_group)

        # Button layout
        button_layout = QHBoxLayout()

        # Save button
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
        button_layout.addWidget(save_btn)

        # Add spacer
        button_layout.addStretch()

        # Update section layout
        update_section = QVBoxLayout()

        # Update button
        update_btn = QPushButton("🔄 Check for Updates")
        update_btn.clicked.connect(self._check_for_updates)
        update_btn.setStyleSheet(
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
        update_btn.setToolTip(
            "Check for and install the latest version.\n"
            "• Pulls latest code from GitHub\n"
            "• Updates the app bundle\n"
            "• Preserves your settings and configuration\n"
            "• Requires an active internet connection"
        )
        update_section.addWidget(update_btn)

        # FFmpeg section
        ffmpeg_btn = QPushButton("📥 Install/Update FFmpeg")
        ffmpeg_btn.clicked.connect(self._install_ffmpeg)
        ffmpeg_btn.setToolTip(
            "Install FFmpeg for video/audio processing (no admin privileges required). "
            "FFmpeg is needed for: YouTube video downloads, audio format conversions, "
            "and video file transcription. If FFmpeg is already installed system-wide, "
            "that version will be used unless you install this managed version. "
            "Safe to install - creates a user-space binary that doesn't affect your system."
        )
        update_section.addWidget(ffmpeg_btn)

        # Auto-update checkbox
        self.auto_update_checkbox = QCheckBox("Check for New Updates Upon Launch")
        self.auto_update_checkbox.setToolTip(
            "When enabled, Knowledge Chipper will automatically check for\n"
            "updates each time you launch the application."
        )
        self.auto_update_checkbox.setStyleSheet(
            """
            QCheckBox {
                font-size: 12px;
                color: #666;
            }
            QCheckBox:hover {
                color: #2196F3;
            }
        """
        )
        # Load saved preference
        self.auto_update_checkbox.setChecked(
            self.gui_settings.get_value(self.tab_name, "auto_update_enabled", False)
        )
        self.auto_update_checkbox.stateChanged.connect(self._on_auto_update_changed)
        update_section.addWidget(self.auto_update_checkbox)

        button_layout.addLayout(update_section)

        main_layout.addLayout(button_layout)

        # Status label
        self.status_label = QLabel("")
        main_layout.addWidget(self.status_label)

        main_layout.addStretch()

    def _load_existing_values(self) -> None:
        """Load existing API key values from settings."""
        # Load OpenAI key
        if self.settings.api_keys.openai_api_key:
            self._actual_api_keys[
                "openai_api_key"
            ] = self.settings.api_keys.openai_api_key
            self.openai_key_edit.setText(
                "••••••••••••••••••••••••••••••••••••••••••••••••••••"
            )

        # Load Anthropic key
        if self.settings.api_keys.anthropic_api_key:
            self._actual_api_keys[
                "anthropic_api_key"
            ] = self.settings.api_keys.anthropic_api_key
            self.anthropic_key_edit.setText(
                "••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••"
            )

        # Load HuggingFace token
        if self.settings.api_keys.huggingface_token:
            self._actual_api_keys[
                "huggingface_token"
            ] = self.settings.api_keys.huggingface_token
            self.huggingface_token_edit.setText(
                "••••••••••••••••••••••••••••••••••••••••••••••••••••"
            )

        # Load Bright Data API key
        if (
            hasattr(self.settings.api_keys, "bright_data_api_key")
            and self.settings.api_keys.bright_data_api_key
        ):
            self._actual_api_keys[
                "bright_data_api_key"
            ] = self.settings.api_keys.bright_data_api_key
            self.bright_data_api_key_edit.setText(
                "••••••••••••••••••••••••••••••••••••••••••••••••••••"
            )

        # Load WebShare credentials
        if self.settings.api_keys.webshare_username:
            self.webshare_username_edit.setText(
                self.settings.api_keys.webshare_username
            )

        if self.settings.api_keys.webshare_password:
            self._actual_api_keys[
                "webshare_password"
            ] = self.settings.api_keys.webshare_password
            self.webshare_password_edit.setText("••••••••••••••••")

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
        self.webshare_password_edit.textChanged.connect(
            lambda text: self._handle_password_change("webshare_password", text)
        )
        self.webshare_username_edit.textChanged.connect(self._on_setting_changed)

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
            # Save to GUI session (for UI state persistence)
            self.gui_settings.set_line_edit_text(
                self.tab_name, "webshare_username", self.webshare_username_edit.text()
            )

            # Save masked indicators for fields that have actual keys stored
            for key_name in self._actual_api_keys:
                if key_name == "webshare_password":
                    self.gui_settings.set_line_edit_text(
                        self.tab_name, "webshare_password_masked", "••••••••••••••••"
                    )
                elif key_name == "openai_api_key":
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

            # Then overlay any session-specific UI state
            saved_username = self.gui_settings.get_line_edit_text(
                self.tab_name, "webshare_username", ""
            )
            if saved_username and not self.webshare_username_edit.text():
                self.webshare_username_edit.setText(saved_username)

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

            # DEBUG: Show current state
            username_text = self.webshare_username_edit.text().strip()
            password_text = self.webshare_password_edit.text().strip()
            actual_password = self._actual_api_keys.get("webshare_password", "NOT_SET")

            debug_msg = f"""🔧 DEBUG STATE:
Username field: '{username_text}'
Password field: '{password_text}'
Actual password stored: '{actual_password}'
_actual_api_keys keys: {list(self._actual_api_keys.keys())}"""

            self.append_log(debug_msg)
            logger.info(debug_msg)
            # Update settings object with actual values or form values
            self.settings.api_keys.webshare_username = (
                self.webshare_username_edit.text().strip()
            )

            # For password/key fields, use actual stored values if available, otherwise use form input
            webshare_password = self._actual_api_keys.get(
                "webshare_password", self.webshare_password_edit.text().strip()
            )
            if not webshare_password.startswith("••"):
                self.settings.api_keys.webshare_password = webshare_password

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

            # Debug: Log current settings values
            logger.info(
                f"🔧 DEBUG: webshare_username = '{self.settings.api_keys.webshare_username}'"
            )
            logger.info(
                f"🔧 DEBUG: webshare_password = {'*' * len(self.settings.api_keys.webshare_password) if self.settings.api_keys.webshare_password else 'None'}"
            )

            # Create credentials data structure using correct field names (Pydantic aliases)
            credentials_data = {
                "api_keys": {
                    "webshare_username": self.settings.api_keys.webshare_username or "",
                    "webshare_password": self.settings.api_keys.webshare_password or "",
                    "openai": self.settings.api_keys.openai_api_key
                    or "",  # Use alias 'openai'
                    "anthropic": self.settings.api_keys.anthropic_api_key
                    or "",  # Use alias 'anthropic'
                    "hf_token": self.settings.api_keys.huggingface_token
                    or "",  # Use alias 'hf_token'
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
        self.gui_settings.set_value(self.tab_name, "auto_update_enabled", is_enabled)
        self.gui_settings.save()
        self.append_log(
            f"{'Enabled' if is_enabled else 'Disabled'} automatic update checking on launch"
        )

    def check_for_updates_on_launch(self) -> None:
        """Check for updates if auto-update is enabled."""
        if self.gui_settings.get_value(self.tab_name, "auto_update_enabled", False):
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
            self.update_worker = UpdateWorker()
            self.update_worker.update_progress.connect(self._handle_update_progress)
            self.update_worker.update_finished.connect(self._handle_update_finished)
            self.update_worker.update_error.connect(self._handle_update_error)

            # Create and show progress dialog
            self.update_progress_dialog = QProgressDialog(
                "Checking for updates...", "Cancel", 0, 0, self
            )
            self.update_progress_dialog.setWindowTitle("Knowledge Chipper Update")
            self.update_progress_dialog.setModal(True)
            self.update_progress_dialog.setMinimumDuration(
                0 if is_auto else 500
            )  # Show immediately for auto-updates
            self.update_progress_dialog.canceled.connect(self._cancel_update)
            self.update_progress_dialog.setAutoClose(False)
            self.update_progress_dialog.setMinimumWidth(520)
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
            self.update_progress_dialog.setLabelText(last_line)
        self.status_label.setText(message)
        self.status_label.setStyleSheet("color: #2196F3; font-weight: bold;")
        self.append_log(message)

    def _handle_update_finished(self, success: bool, message: str) -> None:
        """Handle update completion."""
        # Close progress dialog
        if self.update_progress_dialog:
            self.update_progress_dialog.close()
            self.update_progress_dialog = None

        if success:
            self.status_label.setText("✨ Update completed! Please restart the app.")
            self.status_label.setStyleSheet("color: #4caf50; font-weight: bold;")

            # Show restart dialog
            QMessageBox.information(
                self,
                "Update Complete",
                "The app has been updated successfully!\n\nPlease restart Knowledge Chipper to use the new version.",
                QMessageBox.StandardButton.Ok,
            )
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

    def _handle_update_error(self, error: str) -> None:
        """Handle update errors."""
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
            # Static build vetted source and checksum
            # Reference: https://www.osxexperts.net/ffmpeg711arm.zip
            release = FFmpegRelease(
                url="https://www.osxexperts.net/ffmpeg711arm.zip",
                sha256="011221d75eae36943b5a6a28f70e25928cfb5602fe616d06da0a3b9b55ff6b75",
                ffmpeg_name="ffmpeg",
                ffprobe_name="ffprobe",
            )

            self.ffmpeg_worker = FFmpegInstaller(release)
            self.ffmpeg_worker.progress.connect(self._handle_ffmpeg_progress)
            self.ffmpeg_worker.finished.connect(self._handle_ffmpeg_finished)

            self.update_progress_dialog = QProgressDialog(
                "Installing FFmpeg…", "Cancel", 0, 0, self
            )
            self.update_progress_dialog.setModal(True)
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
            self.update_progress_dialog.setLabelText(message)
        self.append_log(message)

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
