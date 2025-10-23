"""API Keys configuration tab for managing all API credentials."""

from pathlib import Path
from typing import Any

from PyQt6.QtCore import Qt, QTimer, QUrl, pyqtSignal
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QCheckBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLayout,
    QLineEdit,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ...logger import get_logger
from ..components.base_tab import BaseTab
from ..workers.dmg_update_worker import DMGUpdateWorker
from ..workers.ffmpeg_installer import FFmpegInstaller
from ..workers.update_worker import UpdateWorker

logger = get_logger(__name__)


class APIKeysTab(BaseTab):
    """Tab for API keys configuration."""

    # Signals for settings changes
    settings_saved = pyqtSignal()

    def __init__(self, parent: Any = None) -> None:
        """Initialize the API keys tab."""
        # Initialize _actual_api_keys before calling super().__init__
        self._actual_api_keys: dict[str, str] = {}
        self.update_worker: UpdateWorker | None = None
        self.update_progress_dialog: QProgressDialog | None = None
        self._update_log_buffer: list[str] = []
        self.ffmpeg_worker: FFmpegInstaller | None = None
        self.update_btn: QPushButton | None = None
        self.admin_install_btn: QPushButton | None = None

        # Test execution tracking
        self.test_process: Any = None
        self.test_monitor_timer: QTimer | None = None
        self.current_test_name: str = ""

        # Update progress tracking
        self._current_update_is_auto: bool = False

        # Track app launch time to prevent confusing auto-update checks
        import time

        self._app_launch_time = time.time()

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
            """🔑 API Key Configuration Guide:

• PacketStream Credentials: Alternative for YouTube access with residential proxies.
  Sign up at: https://packetstream.io (Username + Auth Key required)

• OpenAI API Key: Required for GPT-based summarization.
  Get your key at: https://platform.openai.com/api-keys

• Anthropic API Key: Required for Claude-based summarization.
  Get your key at: https://console.anthropic.com/

• HuggingFace Token: Required for speaker diarization (separating different speakers in audio).
  Get your free token at: https://huggingface.co/settings/tokens"""
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
        # Keep inputs full-width and remove inter-column gaps so trailing widgets sit flush
        try:
            layout.setHorizontalSpacing(0)
        except Exception:
            pass
        try:
            layout.setColumnStretch(0, 0)
            layout.setColumnStretch(1, 1)
            layout.setColumnStretch(2, 0)
        except Exception:
            pass
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

        # Create help button
        self.hf_token_help_btn = QPushButton("Help me get HF Token")
        self.hf_token_help_btn.setToolTip(
            "Show step-by-step instructions and open the Hugging Face sign-up page"
        )
        self.hf_token_help_btn.setStyleSheet(
            """
            QPushButton {
                background-color: #2196F3;
                color: white;
                font-weight: bold;
                padding: 6px 10px;
                font-size: 12px;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #1976D2; }
            QPushButton:pressed { background-color: #0D47A1; }
            """
        )
        self.hf_token_help_btn.clicked.connect(self._show_hf_token_help)

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
            trailing_widgets=[self.hf_token_help_btn],
        )

        # Bright Data API Key (hidden in UI)
        self.bright_data_api_key_edit = QLineEdit()
        self.bright_data_api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.bright_data_api_key_edit.setPlaceholderText(
            "bd_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
        )

        # PacketStream Username
        self.packetstream_username_edit = QLineEdit()
        self.packetstream_username_edit.setPlaceholderText("your_username")
        self._add_field_with_info(
            layout,
            "PacketStream Username:",
            self.packetstream_username_edit,
            "Your PacketStream username for residential proxy access.\n"
            "• Sign up at: https://packetstream.io\n"
            "• Used for: YouTube metadata extraction with residential proxies\n"
            "• Why needed: Avoids bot detection and rate limiting at scale\n"
            "• Cost: Pay-per-GB pricing model\n"
            "• Benefits: Residential IPs, sticky sessions, automatic rotation\n"
            "• Alternative to: Bright Data for reliable YouTube access",
            5,
            0,
        )

        # PacketStream Auth Key
        self.packetstream_auth_key_edit = QLineEdit()
        self.packetstream_auth_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.packetstream_auth_key_edit.setPlaceholderText("your_auth_key")
        self._add_field_with_info(
            layout,
            "PacketStream Auth Key:",
            self.packetstream_auth_key_edit,
            "Your PacketStream authentication key for proxy access.\n"
            "• Found in your PacketStream dashboard\n"
            "• Used with: Username to authenticate proxy connections\n"
            "• Security: Stored securely in local credentials file\n"
            "• Format: Alphanumeric string provided by PacketStream\n"
            "• Required for: All PacketStream proxy operations",
            6,
            0,
        )

        # Add spacing between PacketStream fields and proxy strict mode
        from PyQt6.QtWidgets import QSpacerItem, QSizePolicy
        layout.addItem(QSpacerItem(20, 10, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed), 7, 0, 1, 2)

        # Proxy Strict Mode checkbox
        self.proxy_strict_mode_checkbox = QCheckBox("🛡️ Proxy Strict Mode (RECOMMENDED)")
        self.proxy_strict_mode_checkbox.setChecked(True)  # Default to enabled for safety
        self.proxy_strict_mode_checkbox.setStyleSheet("font-weight: bold;")
        
        proxy_strict_info = (
            "Block YouTube operations when proxy fails to protect your IP address.\n\n"
            "ENABLED (Recommended):\n"
            "• Blocks all YouTube downloads if proxy fails\n"
            "• Protects your IP from rate limits and bans\n"
            "• Requires PacketStream to be working properly\n"
            "• Safest option for your account\n\n"
            "DISABLED (Risky):\n"
            "• Falls back to direct connection if proxy fails\n"
            "• Exposes your personal IP to YouTube\n"
            "• May trigger rate limits or account bans\n"
            "• Only use if you understand the risks"
        )
        
        self._add_field_with_info(
            layout,
            "",  # No label needed, checkbox has its own text
            self.proxy_strict_mode_checkbox,
            proxy_strict_info,
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

        # Save button (moved below API Keys Configuration box) - aligned with API key input fields
        save_layout = QGridLayout()
        save_layout.setColumnStretch(0, 0)  # Label column doesn't stretch
        save_layout.setColumnStretch(
            1, 1
        )  # Input column stretches to match API keys layout

        # Add empty label to match API keys layout structure
        save_layout.addWidget(QLabel(), 0, 0)

        # Create horizontal layout matching the API key field structure
        save_widget_layout = QHBoxLayout()
        save_widget_layout.setContentsMargins(0, 0, 0, 0)
        save_widget_layout.setSpacing(8)

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
        save_widget_layout.addWidget(save_btn)

        # Add spacing to match the info icon (16px) + spacing (8px) = 24px total
        save_widget_layout.addSpacing(24)
        save_widget_layout.addStretch()  # Push everything to the left, matching API key field layout

        # Create container widget matching API key field structure
        save_container = QWidget()
        save_container.setLayout(save_widget_layout)
        save_layout.addWidget(save_container, 0, 1)

        main_layout.addLayout(save_layout)

        # Button layout - using grid layout to match API keys alignment
        button_layout = QGridLayout()
        button_layout.setColumnStretch(0, 0)  # Label column doesn't stretch
        button_layout.setColumnStretch(
            1, 1
        )  # Input column stretches to match API keys layout

        # Add empty label to match API keys layout structure
        button_layout.addWidget(QLabel(), 0, 0)

        # Create horizontal layout matching the API key field structure
        button_widget_layout = QHBoxLayout()
        button_widget_layout.setContentsMargins(0, 0, 0, 0)
        button_widget_layout.setSpacing(8)

        # Update section layout - stack buttons vertically in a container
        update_section = QVBoxLayout()
        update_section.setSpacing(8)

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

        # FFmpeg installation section removed per user request

        # Auto-update checkbox
        self.auto_update_checkbox = QCheckBox(
            "Automatically check for updates on app launch"
        )
        self.auto_update_checkbox.setToolTip(
            "When enabled, Skip the Podcast Desktop will automatically check for new versions\n"
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
            settings.app.auto_check_updates
            or self.gui_settings.get_value(self.tab_name, "auto_update_enabled", False)
        )
        self.auto_update_checkbox.setChecked(auto_update_enabled)
        self.auto_update_checkbox.stateChanged.connect(self._on_auto_update_changed)

        update_section.addWidget(self.auto_update_checkbox)

        # Add the update section to the horizontal layout
        button_widget_layout.addLayout(update_section)

        # Add spacing to match the info icon (16px) + spacing (8px) = 24px total
        button_widget_layout.addSpacing(24)
        button_widget_layout.addStretch()  # Push everything to the left, matching API key field layout

        # Create container widget matching API key field structure
        button_container = QWidget()
        button_container.setLayout(button_widget_layout)
        button_layout.addWidget(button_container, 0, 1)
        main_layout.addLayout(button_layout)

        # Status label
        self.status_label = QLabel("")
        main_layout.addWidget(self.status_label)

        # Sign In section - authentication for Skip The Podcast Web
        auth_section = self._create_web_auth_section()
        main_layout.addWidget(auth_section)

        # Settings Tests section removed per user request

        # Hardware Recommendations section - moved from Local Transcription tab
        # Hardware recommendations removed - now handled automatically during installation

        main_layout.addStretch()

    def _create_web_auth_section(self) -> QGroupBox:
        """Create authentication section for Skip The Podcast Web."""
        group = QGroupBox("Skip The Podcast Web Sign In")
        layout = QVBoxLayout(group)

        # Auth status
        self.web_auth_status_label = QLabel("Not signed in")
        self.web_auth_status_label.setStyleSheet("color: #666; font-style: italic;")
        layout.addWidget(self.web_auth_status_label)

        # Info text about OAuth flow
        info_text = QLabel(
            "🔐 Sign in via Skipthepodcast.com to enable web export functionality.\n"
            "This will open your browser for secure authentication."
        )
        info_text.setWordWrap(True)
        info_text.setStyleSheet(
            "color: #666; font-style: italic; margin: 8px; padding: 8px; "
            "background-color: #f5f5f5; border-radius: 4px;"
        )
        layout.addWidget(info_text)

        # Button layout
        button_layout = QHBoxLayout()

        # OAuth authentication button
        self.web_oauth_btn = QPushButton("🌐 Sign In via Skipthepodcast.com")
        self.web_oauth_btn.setStyleSheet(
            "QPushButton { padding: 10px; font-size: 14px; background-color: #2196F3; color: white; border: none; border-radius: 6px; }"
            "QPushButton:hover { background-color: #1976D2; }"
            "QPushButton:disabled { background-color: #cccccc; }"
        )
        self.web_oauth_btn.clicked.connect(self._web_sign_in_with_oauth)
        button_layout.addWidget(self.web_oauth_btn)

        # Sign out button
        self.web_logout_btn = QPushButton("Sign Out")
        self.web_logout_btn.setEnabled(False)
        self.web_logout_btn.clicked.connect(self._web_sign_out)
        button_layout.addWidget(self.web_logout_btn)

        button_layout.addStretch()
        layout.addLayout(button_layout)

        # Initialize OAuth state
        self._web_auth_user = None
        self._web_uploader = None

        # Note: OAuth authentication is handled in the Cloud Uploads tab
        # This section is a placeholder for future direct OAuth integration
        logger.info("Web auth UI initialized - OAuth handled via Cloud Uploads tab")
        self.web_oauth_btn.setEnabled(False)
        self.web_auth_status_label.setText("Use Cloud Uploads tab for authentication")

        return group

    def _refresh_web_auth_ui(self):
        """Refresh web auth UI based on current auth state."""
        # OAuth authentication is handled in the Cloud Uploads tab
        # This is a placeholder for future direct integration
        self.web_auth_status_label.setText("Use Cloud Uploads tab for authentication")
        self.web_auth_status_label.setStyleSheet("color: #666; font-style: italic;")

    def _web_sign_in_with_oauth(self):
        """Sign in using OAuth flow."""
        # OAuth authentication is handled in the Cloud Uploads tab
        QMessageBox.information(
            self,
            "OAuth Authentication",
            "Please use the 'Cloud Uploads' tab for OAuth authentication with Skipthepodcast.com.\n\n"
            "The Cloud Uploads tab provides full OAuth sign-in and upload functionality.",
        )

    def _web_sign_out(self):
        """Sign out of Skip The Podcast Web."""
        # OAuth authentication is handled in the Cloud Uploads tab
        QMessageBox.information(
            self,
            "OAuth Sign Out",
            "Please use the 'Cloud Uploads' tab to sign out of Skipthepodcast.com.",
        )

    def _show_hf_token_help(self) -> None:
        """Show a popup with instructions to obtain a free Hugging Face token."""
        try:
            msg = QMessageBox(self)
            msg.setWindowTitle("Hugging Face Token Setup")
            msg.setIcon(QMessageBox.Icon.Information)

            # Plain text instructions + URLs (easy to copy)
            message = (
                "Get a free Hugging Face token in three steps:\n\n"
                "1) Create a free account: https://huggingface.co/join\n"
                "2) Generate a token: https://huggingface.co/settings/tokens (New token → Read)\n"
                "3) Paste the token (starts with 'hf_') into Settings → HuggingFace Token and click Save.\n\n"
                "Tip: For diarization, you may need to accept access to the pyannote model:\n"
                "https://huggingface.co/pyannote/speaker-diarization-3.1"
            )
            msg.setText(message)

            # Add action buttons to open URLs directly
            open_signup_btn = msg.addButton(
                "Open Sign‑Up Page", QMessageBox.ButtonRole.ActionRole
            )
            open_tokens_btn = msg.addButton(
                "Open Token Page", QMessageBox.ButtonRole.ActionRole
            )
            msg.addButton(QMessageBox.StandardButton.Ok)

            msg.exec()

            clicked = msg.clickedButton()
            if clicked == open_signup_btn:
                QDesktopServices.openUrl(QUrl("https://huggingface.co/join"))
            elif clicked == open_tokens_btn:
                QDesktopServices.openUrl(QUrl("https://huggingface.co/settings/tokens"))
        except Exception as e:
            # Non-fatal UI error; log and continue
            logger.error(f"Failed to show HF token help dialog: {e}")

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

        # Load PacketStream username
        if (
            hasattr(self.settings.api_keys, "packetstream_username")
            and self.settings.api_keys.packetstream_username
        ):
            self._actual_api_keys[
                "packetstream_username"
            ] = self.settings.api_keys.packetstream_username
            self.packetstream_username_edit.setText(
                self.settings.api_keys.packetstream_username
            )

        # Load PacketStream auth key
        if (
            hasattr(self.settings.api_keys, "packetstream_auth_key")
            and self.settings.api_keys.packetstream_auth_key
        ):
            self._actual_api_keys[
                "packetstream_auth_key"
            ] = self.settings.api_keys.packetstream_auth_key
            self.packetstream_auth_key_edit.setText(
                "••••••••••••••••••••••••••••••••••••••••••••••••••••"
            )

        # Load Proxy Strict Mode setting
        if (
            hasattr(self.settings, "youtube_processing")
            and hasattr(self.settings.youtube_processing, "proxy_strict_mode")
        ):
            self.proxy_strict_mode_checkbox.setChecked(
                self.settings.youtube_processing.proxy_strict_mode
            )
        else:
            # Default to True for safety
            self.proxy_strict_mode_checkbox.setChecked(True)

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
        self.packetstream_username_edit.textChanged.connect(
            lambda text: self._handle_key_change("packetstream_username", text)
        )
        self.packetstream_auth_key_edit.textChanged.connect(
            lambda text: self._handle_key_change("packetstream_auth_key", text)
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

            # PacketStream credentials
            packetstream_username = self._actual_api_keys.get(
                "packetstream_username", self.packetstream_username_edit.text().strip()
            )
            if packetstream_username:
                self.settings.api_keys.packetstream_username = packetstream_username

            packetstream_auth_key = self._actual_api_keys.get(
                "packetstream_auth_key", self.packetstream_auth_key_edit.text().strip()
            )
            if not packetstream_auth_key.startswith("••"):
                self.settings.api_keys.packetstream_auth_key = packetstream_auth_key

            # Save Proxy Strict Mode setting
            strict_mode_enabled = self.proxy_strict_mode_checkbox.isChecked()
            self.settings.youtube_processing.proxy_strict_mode = strict_mode_enabled
            logger.info(f"Proxy strict mode set to: {strict_mode_enabled}")

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
                    # Persist PacketStream credentials for residential proxy access
                    "packetstream_username": getattr(
                        self.settings.api_keys, "packetstream_username", ""
                    )
                    or "",
                    "packetstream_auth_key": getattr(
                        self.settings.api_keys, "packetstream_auth_key", ""
                    )
                    or "",
                },
                # Persist YouTube processing settings
                "youtube_processing": {
                    "proxy_strict_mode": getattr(
                        self.settings.youtube_processing, "proxy_strict_mode", True
                    )
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
            self.append_log(
                f"✅ {'Enabled' if is_enabled else 'Disabled'} automatic update checking on launch"
            )
        except Exception as e:
            self.append_log(f"⚠️ Setting changed but couldn't save to config file: {e}")
            # Still update the runtime setting even if file save fails
            self.append_log(
                f"{'Enabled' if is_enabled else 'Disabled'} automatic update checking (runtime only)"
            )

    def check_for_updates_on_launch(self) -> None:
        """Check for updates if auto-update is enabled."""
        from pathlib import Path

        from ...config import get_settings

        # Check for fresh install markers that should disable auto-update
        fresh_install_markers = [
            Path.home() / ".skip_the_podcast_desktop_installed",
            Path.home() / ".skip_the_podcast_desktop_authorized",
        ]

        # Skip auto-update if this is a fresh install
        for marker in fresh_install_markers:
            if marker.exists():
                logger.info(
                    f"Skipping auto-update for fresh install (marker: {marker})"
                )
                return

        settings = get_settings()

        # Check app config first, fallback to GUI settings for migration
        auto_update_enabled = (
            settings.app.auto_check_updates
            or self.gui_settings.get_value(self.tab_name, "auto_update_enabled", False)
        )

        if auto_update_enabled:
            # Additional check: don't auto-update to the same version
            from ... import __version__

            logger.info(f"Auto-update check for current version: {__version__}")
            self._check_for_updates(is_auto=True)
        else:
            logger.debug("Auto-update disabled in settings")

    def _check_for_updates(self, is_auto: bool = False) -> None:
        """Check for and install updates."""
        try:
            # CRITICAL: Thread safety check - ensure we're on the main thread
            from PyQt6.QtCore import QThread
            from PyQt6.QtWidgets import QApplication

            if QThread.currentThread() != QApplication.instance().thread():
                logger.error(
                    "🚨 CRITICAL: _check_for_updates called from background thread - BLOCKED!"
                )
                logger.error(f"Current thread: {QThread.currentThread()}")
                logger.error(f"Main thread: {QApplication.instance().thread()}")
                return

            # For auto-updates, skip if too soon after app launch to avoid confusion
            if is_auto:
                import time

                current_time = time.time()
                if current_time - self._app_launch_time < 30:  # 30 seconds
                    logger.info(
                        "Skipping auto-update check - too soon after app launch"
                    )
                    return

            # If a previous worker exists
            if self.update_worker:
                # If it's still running, do not start another
                if self.update_worker.isRunning():
                    self.append_log("An update is already in progress…")
                    return
                # If it's finished or was cancelled, discard and create a fresh worker
                self.update_worker = None

            # Always create a fresh worker instance to avoid restarting finished QThreads
            # Uses PKG-based updater (class name retained for compatibility)
            self.update_worker = DMGUpdateWorker(is_auto=is_auto)
            # Track if this is an auto update for silent progress handling
            self._current_update_is_auto = is_auto
            self.update_worker.update_progress.connect(self._handle_update_progress)
            # New: determinate progress support
            try:
                self.update_worker.update_progress_percent.connect(self._handle_update_progress_percent)  # type: ignore[attr-defined]
            except AttributeError:
                # Optional signal, not available in all worker versions
                logger.debug("update_progress_percent signal not available")
            self.update_worker.update_finished.connect(self._handle_update_finished)
            self.update_worker.update_error.connect(self._handle_update_error)

            # Initialize completion tracking
            self._update_completed = False

            # Add worker failure detection
            self.update_worker.finished.connect(self._on_worker_finished)

            # Only show progress dialog for manual updates, not auto checks
            if not is_auto:
                # Create and show progress dialog (with additional thread safety check)
                if QThread.currentThread() != QApplication.instance().thread():
                    logger.error(
                        "🚨 CRITICAL: QProgressDialog creation attempted from background thread - BLOCKED!"
                    )
                    return

                self.update_progress_dialog = QProgressDialog(
                    "Checking for updates...", "Cancel", 0, 0, self
                )
                self.update_progress_dialog.setWindowTitle(
                    "Skip the Podcast Desktop Update"
                )
                self.update_progress_dialog.setModal(True)
                self.update_progress_dialog.setMinimumDuration(500)
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
                except (AttributeError, RuntimeError):
                    # Layout constraint not supported in this PyQt version
                    logger.debug("Layout size constraint not available")
                self.update_progress_dialog.setSizeGripEnabled(False)
                # Subtle styling and monospace label for better readability of logs
                self.update_progress_dialog.setStyleSheet(
                    "QProgressDialog QLabel { font-family: 'Courier New', monospace; font-size: 12px; }"
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

        # For auto updates, only log without updating UI
        if self._current_update_is_auto:
            self.append_log(message)
            return

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
        # For auto updates, only log without updating UI
        if self._current_update_is_auto:
            self.append_log(f"{percent}% - {message}" if message else f"{percent}%")
            return

        if self.update_progress_dialog:
            # Switch from indeterminate to determinate on first percent
            if self.update_progress_dialog.maximum() == 0:
                self.update_progress_dialog.setMaximum(100)
            self.update_progress_dialog.setValue(max(0, min(100, int(percent))))
            if message:
                self._set_update_dialog_text(message)
        # Mirror to status label/log
        self.status_label.setText(
            f"{message} ({percent}%)" if message else f"{percent}%"
        )
        self.status_label.setStyleSheet("color: #2196F3; font-weight: bold;")
        self.append_log(f"{message}" if message else f"{percent}%")

    def _handle_update_finished(
        self, success: bool, message: str, silent: bool = False
    ) -> None:
        """Handle update completion."""
        # Mark update as completed to prevent false crash detection
        self._update_completed = True

        # Reset auto update tracking
        self._current_update_is_auto
        self._current_update_is_auto = False

        # Close progress dialog
        if self.update_progress_dialog:
            self.update_progress_dialog.close()
            self.update_progress_dialog = None

        # For silent updates (auto-checks when already up to date), only log and return
        if silent:
            logger.info(f"Silent update check completed: {message}")
            return

        if success:
            # Check if this is "already on latest version" vs actual update completion
            if "Already on latest version" in message:
                # Show positive status for being up to date (message already has checkmark)
                self.status_label.setText(message)
                self.status_label.setStyleSheet("color: #4caf50; font-weight: bold;")
                self.append_log(message)

                # Clear status after 10 seconds
                from PyQt6.QtCore import QTimer

                QTimer.singleShot(10000, lambda: self.status_label.setText(""))
            else:
                # This is an actual update completion
                if "Update downloaded successfully" in message:
                    # New flow: app will quit and install automatically
                    self.status_label.setText(
                        "🚀 Update ready! App will restart automatically..."
                    )
                    self.status_label.setStyleSheet(
                        "color: #4caf50; font-weight: bold;"
                    )

                    # Show info dialog and then quit the app
                    from PyQt6.QtWidgets import QMessageBox

                    msg_box = QMessageBox(self)
                    msg_box.setWindowTitle("Update Ready")
                    msg_box.setText("Update downloaded successfully!")
                    msg_box.setInformativeText(
                        f"{message}\n\n"
                        "The app will now quit and install the update automatically.\n"
                        "The new version will launch when installation is complete.\n\n"
                        "Note: The app may take a moment to launch after installation."
                    )
                    msg_box.setIcon(QMessageBox.Icon.Information)
                    msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
                    msg_box.exec()

                    # Quit the app to allow PKG installation
                    self._quit_for_update()
                else:
                    # Legacy flow: manual restart required
                    self.status_label.setText(
                        "✨ Update completed! Please restart the app."
                    )
                    self.status_label.setStyleSheet(
                        "color: #4caf50; font-weight: bold;"
                    )

                    # Show restart dialog with auto-restart option
                    from PyQt6.QtWidgets import QMessageBox

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
                    restart_button = msg_box.addButton(
                        "Restart Now", QMessageBox.ButtonRole.AcceptRole
                    )
                    _later_button = msg_box.addButton(
                        "Restart Later", QMessageBox.ButtonRole.RejectRole
                    )
                    msg_box.setDefaultButton(restart_button)

                    # Show the dialog and handle response
                    msg_box.exec()

                    if msg_box.clickedButton() == restart_button:
                        self._restart_application()
                    else:
                        # Just close the dialog - user will restart manually later
                        pass
        else:
            # Check if this is "No updates available" or "Already on latest version" - these are not errors
            if (
                "No updates available" in message
                or "Already on latest version" in message
            ):
                # Show positive status for being up to date
                from knowledge_system import __version__

                self.status_label.setText(
                    f"✅ You're on the latest version ({__version__})"
                )
                self.status_label.setStyleSheet("color: #4caf50; font-weight: bold;")
                self.append_log(f"✅ You're on the latest version ({__version__})")

                # Clear status after 10 seconds
                from PyQt6.QtCore import QTimer

                QTimer.singleShot(10000, lambda: self.status_label.setText(""))
            else:
                # This is an actual error
                self.status_label.setText(f"❌ Update failed: {message}")
                self.status_label.setStyleSheet("color: #f44336; font-weight: bold;")

                # Show error dialog only for actual errors
                from PyQt6.QtWidgets import QMessageBox

                QMessageBox.warning(
                    self,
                    "Update Failed",
                    f"Failed to update Skip the Podcast Desktop:\n\n{message}",
                    QMessageBox.StandardButton.Ok,
                )

        self.append_log(message)
        self.update_worker = None

    def _run_quick_tests(self) -> None:
        """Run quick tests (smoke tests)."""
        self._run_test_suite("smoke", "Quick Tests")

    def _run_regular_tests(self) -> None:
        """Run regular tests (comprehensive tests)."""
        self._run_test_suite("comprehensive", "Regular Tests")

    def _run_extended_tests(self) -> None:
        """Run extended tests (stress tests)."""
        self._run_test_suite("stress", "Extended Tests")

    def _run_test_suite(self, test_mode: str, test_name: str) -> None:
        """Run a test suite using the comprehensive testing framework."""
        # Check if a test is already running
        if self.test_process and self.test_process.poll() is None:
            QMessageBox.warning(
                self,
                "Test Already Running",
                f"A test is already running: {self.current_test_name}\n\n"
                "Please wait for it to complete or cancel it first.",
            )
            return

        try:
            import subprocess  # nosec B404  # noqa: F401 # Required for test execution

            # Find the test runner script using dynamic project root detection
            from ...utils.file_io import find_project_root

            project_root = find_project_root()
            test_script = (
                project_root / "tests" / "gui_comprehensive" / "main_test_runner.py"
            )
            venv_python = project_root / "venv" / "bin" / "python3"

            if not test_script.exists():
                self.status_label.setText("❌ Test script not found")
                self.status_label.setStyleSheet("color: #f44336; font-weight: bold;")

                # Provide detailed troubleshooting information
                error_msg = (
                    f"Test script not found at:\n{test_script}\n\n"
                    f"Project root detected as: {project_root}\n\n"
                    "Troubleshooting steps:\n"
                    "1. If running from app bundle, ensure the source code is in a standard location\n"
                    "2. Check that the project was cloned/installed completely\n"
                    "3. Verify tests/gui_comprehensive/ directory exists\n"
                    "4. Try setting KNOWLEDGE_CHIPPER_ROOT environment variable to the source directory\n\n"
                    "Expected project structure:\n"
                    "- pyproject.toml (project root marker)\n"
                    "- tests/gui_comprehensive/main_test_runner.py\n"
                    "- venv/ (virtual environment)"
                )

                QMessageBox.critical(
                    self,
                    "Test Script Not Found",
                    error_msg,
                )
                return

            if not venv_python.exists():
                self.status_label.setText("❌ Virtual environment not found")
                self.status_label.setStyleSheet("color: #f44336; font-weight: bold;")

                # Check for alternative Python locations
                alternative_pythons = [
                    project_root / "venv" / "bin" / "python",
                    project_root / ".venv" / "bin" / "python3",
                    project_root / ".venv" / "bin" / "python",
                ]

                found_alternatives = [p for p in alternative_pythons if p.exists()]

                error_msg = (
                    f"Virtual environment Python not found at:\n{venv_python}\n\n"
                    f"Project root: {project_root}\n\n"
                    "Troubleshooting steps:\n"
                    "1. Run setup script: 'bash scripts/setup.sh'\n"
                    "2. Create virtual environment: 'python3 -m venv venv'\n"
                    "3. Install dependencies: 'venv/bin/pip install -r requirements.txt'\n"
                    "4. Check that virtual environment is in project root\n\n"
                )

                if found_alternatives:
                    error_msg += f"Found alternative Python installations:\n"
                    for alt in found_alternatives:
                        error_msg += f"- {alt}\n"
                else:
                    error_msg += "No alternative Python installations found in project directory."

                QMessageBox.critical(
                    self,
                    "Virtual Environment Not Found",
                    error_msg,
                )
                return

            # Confirm test execution
            reply = QMessageBox.question(
                self,
                f"Run {test_name}",
                f"This will run {test_name} which may take some time:\n\n"
                "• Quick Tests: 5-10 minutes\n"
                "• Regular Tests: 1-2 hours\n"
                "• Extended Tests: 2+ hours\n\n"
                "The test will run in the background without blocking the app.\n"
                "Use the Cancel Test button to stop if needed.\n\n"
                f"Continue with {test_name}?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )

            if reply != QMessageBox.StandardButton.Yes:
                return

            # Start test in background process
            self._start_background_test(
                test_mode, test_name, project_root, venv_python, test_script
            )

        except Exception as e:
            error_msg = f"Failed to start {test_name}: {e}"
            self.append_log(f"❌ {error_msg}")
            self.status_label.setText(f"❌ {error_msg}")
            self.status_label.setStyleSheet("color: #f44336; font-weight: bold;")
            QMessageBox.critical(
                self,
                "Test Error",
                f"Failed to start {test_name}:\n\n{e}",
            )

    def _start_background_test(
        self,
        test_mode: str,
        test_name: str,
        project_root: Path,
        venv_python: Path,
        test_script: Path,
    ) -> None:
        """Start test in background without blocking the app."""
        try:
            import subprocess  # nosec B404 # Required for test execution

            self.current_test_name = test_name
            self.append_log(f"🧪 Starting {test_name} in background...")
            self.status_label.setText(f"🧪 Running {test_name}...")
            self.status_label.setStyleSheet("color: #2196F3; font-weight: bold;")

            # Show cancel button and disable test buttons
            self.cancel_test_btn.setVisible(True)
            self.quick_test_btn.setEnabled(False)
            self.regular_test_btn.setEnabled(False)
            self.extended_test_btn.setEnabled(False)

            # Prepare command
            cmd = [str(venv_python), str(test_script), test_mode, "--no-gui-launch"]

            # Start process in background with proper working directory
            self.test_process = (
                subprocess.Popen(  # nosec B603 # Controlled command execution
                    cmd,
                    cwd=str(project_root),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    bufsize=1,
                    universal_newlines=True,
                )
            )

            # Start monitoring timer
            self.test_monitor_timer = QTimer()
            self.test_monitor_timer.timeout.connect(self._monitor_test_progress)
            self.test_monitor_timer.start(2000)  # Check every 2 seconds

            self.append_log(
                f"✅ {test_name} started successfully (PID: {self.test_process.pid})"
            )
            self.append_log("💡 Use Cancel Test button to stop the test gracefully")

        except Exception as e:
            self._handle_test_error(f"Failed to start background test: {e}")

    def _monitor_test_progress(self) -> None:
        """Monitor test progress and handle completion."""
        if not self.test_process:
            return

        # Check if process is still running
        poll_result = self.test_process.poll()

        if poll_result is not None:
            # Process has finished
            self._handle_test_completion(poll_result)
        else:
            # Process is still running - update status
            getattr(self, "_test_start_time", 0)
            if hasattr(self, "_test_start_time"):
                import time

                elapsed_mins = int((time.time() - self._test_start_time) / 60)
                self.status_label.setText(
                    f"🧪 Running {self.current_test_name} ({elapsed_mins} min elapsed)..."
                )
            else:
                import time

                self._test_start_time = time.time()

    def _handle_test_completion(self, return_code: int) -> None:
        """Handle test completion."""
        if self.test_monitor_timer:
            self.test_monitor_timer.stop()
            self.test_monitor_timer = None

        # Re-enable buttons and hide cancel
        self.quick_test_btn.setEnabled(True)
        self.regular_test_btn.setEnabled(True)
        self.extended_test_btn.setEnabled(True)
        self.cancel_test_btn.setVisible(False)

        if return_code == 0:
            self.status_label.setText(
                f"✅ {self.current_test_name} completed successfully!"
            )
            self.status_label.setStyleSheet("color: #4caf50; font-weight: bold;")
            self.append_log(f"✅ {self.current_test_name} completed successfully")
        else:
            self.status_label.setText(
                f"⚠️ {self.current_test_name} completed with warnings (code: {return_code})"
            )
            self.status_label.setStyleSheet("color: #ff9800; font-weight: bold;")
            self.append_log(
                f"⚠️ {self.current_test_name} completed with return code: {return_code}"
            )

        # Clear status after 10 seconds
        QTimer.singleShot(10000, lambda: self.status_label.setText(""))

        # Clean up
        self.test_process = None
        self.current_test_name = ""
        if hasattr(self, "_test_start_time"):
            delattr(self, "_test_start_time")

    def _cancel_test(self) -> None:
        """Cancel the currently running test."""
        if not self.test_process or self.test_process.poll() is not None:
            QMessageBox.information(
                self,
                "No Test Running",
                "No test is currently running to cancel.",
            )
            return

        reply = QMessageBox.question(
            self,
            "Cancel Test",
            f"Are you sure you want to cancel {self.current_test_name}?\n\n"
            "This will terminate the test process gracefully.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            # Gracefully terminate the process
            self.test_process.terminate()

            # Wait a bit for graceful shutdown
            import subprocess  # nosec B404 # Required for test execution

            try:
                self.test_process.wait(timeout=5)
            except subprocess.TimeoutExpired:  # type: ignore
                # Force kill if it doesn't respond
                self.test_process.kill()
                self.test_process.wait()

            self.append_log(f"❌ {self.current_test_name} cancelled by user")
            self.status_label.setText(f"❌ {self.current_test_name} cancelled")
            self.status_label.setStyleSheet("color: #f44336; font-weight: bold;")

            # Clean up immediately
            if self.test_monitor_timer:
                self.test_monitor_timer.stop()
                self.test_monitor_timer = None

            self.quick_test_btn.setEnabled(True)
            self.regular_test_btn.setEnabled(True)
            self.extended_test_btn.setEnabled(True)
            self.cancel_test_btn.setVisible(False)

            self.test_process = None
            self.current_test_name = ""
            if hasattr(self, "_test_start_time"):
                delattr(self, "_test_start_time")

            # Clear status after 5 seconds
            QTimer.singleShot(5000, lambda: self.status_label.setText(""))

        except Exception as e:
            self._handle_test_error(f"Failed to cancel test: {e}")

    def _handle_test_error(self, error_msg: str) -> None:
        """Handle test execution errors."""
        self.append_log(f"❌ {error_msg}")
        self.status_label.setText("❌ Test error")
        self.status_label.setStyleSheet("color: #f44336; font-weight: bold;")

        # Clean up on error
        if self.test_monitor_timer:
            self.test_monitor_timer.stop()
            self.test_monitor_timer = None

        self.quick_test_btn.setEnabled(True)
        self.regular_test_btn.setEnabled(True)
        self.extended_test_btn.setEnabled(True)
        self.cancel_test_btn.setVisible(False)

        self.test_process = None
        self.current_test_name = ""
        if hasattr(self, "_test_start_time"):
            delattr(self, "_test_start_time")

        QMessageBox.critical(
            self,
            "Test Error",
            error_msg,
        )

    def _restart_application(self) -> None:
        """Restart the application after an update."""
        import os
        import sys

        from PyQt6.QtWidgets import QApplication

        try:
            # Get the current application path
            if getattr(sys, "frozen", False):
                # Running as packaged app
                app_path = sys.executable
            else:
                # Running from source - find the app bundle or start script
                app_bundle_path = "/Applications/Skip the Podcast Desktop.app"
                user_app_path = os.path.expanduser(
                    "~/Applications/Skip the Podcast Desktop.app"
                )

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
            import subprocess  # nosec B404 # Required for app restart functionality

            if app_path.endswith(".app"):
                subprocess.Popen(  # nosec B603,B607 # Trusted system operation
                    ["open", app_path]
                )
            else:
                subprocess.Popen(app_path.split())  # nosec B603 # Trusted app path

        except Exception as e:
            self.append_log(f"❌ Failed to restart automatically: {e}")
            self.append_log("Please restart Skip the Podcast Desktop manually.")

    def _quit_for_update(self) -> None:
        """Quit the application to allow PKG installation."""
        from PyQt6.QtWidgets import QApplication

        try:
            self.append_log("🚀 Quitting app for update installation...")

            # Give a moment for the log to be written
            from PyQt6.QtCore import QTimer

            QTimer.singleShot(1000, QApplication.quit)

        except Exception as e:
            self.append_log(f"❌ Failed to quit for update: {e}")
            # Force quit as fallback
            QApplication.quit()

    def _on_worker_finished(self) -> None:
        """Handle worker thread finishing (for crash detection)."""
        if self.update_worker:
            # Check if worker finished without calling our completion handlers
            # This indicates the worker crashed or was terminated unexpectedly
            if (
                not hasattr(self, "_update_completed") or not self._update_completed
            ) and self.update_worker.isFinished():
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
                    QMessageBox.StandardButton.Yes,
                )

                if reply == QMessageBox.StandardButton.Yes:
                    self._fallback_update()

    def _fallback_update(self) -> None:
        """Fallback update method using Terminal."""
        try:
            import subprocess  # nosec B404 # Required for Terminal automation

            # Find the script using dynamic project root detection
            from ...utils.file_io import find_project_root

            project_root = find_project_root()
            script_path = project_root / "scripts" / "build_macos_app.sh"
            if not script_path.exists():
                self.append_log("❌ Could not find build script for fallback update")
                return

            # Open Terminal and run the original script
            str(script_path.parent)
            script_path.name

            apple_script = """
tell application "Terminal"
  activate
  do script "cd {script_dir}; echo '🏗️ Running fallback updater…'; bash {script_name}; echo ''; echo '✅ Update finished. Please restart Skip the Podcast Desktop and close this window.'"
end tell
"""

            subprocess.run(  # nosec B603,B607 # Trusted AppleScript execution
                ["osascript", "-e", apple_script], check=True
            )
            self.append_log("🔄 Opened Terminal for fallback update")
            self.append_log(
                "Please follow the prompts in Terminal, then restart the app"
            )

        except Exception as e:
            self.append_log(f"❌ Fallback update failed: {e}")
            self.append_log(
                "Please run 'bash scripts/build_macos_app.sh' manually from Terminal"
            )

    def _admin_install(self) -> None:
        """Perform an admin install to /Applications via Terminal.

        Removes user-space copy first. This will prompt for the macOS password
        in Terminal (not inside the app).
        """
        try:
            import subprocess  # nosec B404 # Required for Terminal automation

            # Use dynamic project root detection instead of hardcoded path
            from ...utils.file_io import find_project_root

            workspace_path = find_project_root()
            script_path = workspace_path / "scripts" / "build_macos_app.sh"
            if not script_path.exists():
                self.append_log(
                    f"❌ Could not find build script for admin install at: {script_path}"
                )
                QMessageBox.critical(
                    self,
                    "Admin Install",
                    f"Build script not found at:\n{script_path}\n\nEnsure the script exists in the project's scripts directory.",
                )
                return

            str(script_path.parent)
            script_path.name

            self.append_log(
                "🔐 Admin install requested. A Terminal window will open and WILL prompt for your macOS password."
            )

            # Notify user about sudo requirement as per user preferences
            QMessageBox.information(
                self,
                "Admin Install",
                "📱 Ready to proceed with admin install.\n\n"
                "A Terminal window will open and prompt for your macOS password.\n"
                "Please be ready to enter your password when prompted.\n\n"
                "The install will:\n"
                "• Remove any user-space copy of the app\n"
                "• Install the app to /Applications (system-wide)\n"
                "• Require administrator privileges",
            )

            # Disable update actions during admin install to avoid conflicts
            self._set_admin_install_in_progress(True)

            apple_script = """
tell application "Terminal"
  activate
  do script "cd {script_dir}; echo '🧹 Removing user-space copy (if any)...'; rm -rf \"$HOME/Applications/Knowledge_Chipper.app\"; echo '🏗️ Running admin installer to /Applications...'; bash {script_name}; echo ''; echo '✅ Admin install complete. You can close this window.'"
end tell
"""

            subprocess.run(  # nosec B603,B607 # Trusted AppleScript execution
                ["osascript", "-e", apple_script], check=True
            )
            self.append_log("🔄 Opened Terminal for admin install")
        except Exception as e:
            self.append_log(f"❌ Admin install failed to launch: {e}")
            QMessageBox.critical(
                self, "Admin Install", f"Failed to start admin install: {e}"
            )
            # Re-enable on failure to launch
            self._set_admin_install_in_progress(False)

    def _set_admin_install_in_progress(self, in_progress: bool) -> None:
        """Enable/disable update controls while admin install runs externally."""
        try:
            if self.admin_install_btn:
                self.admin_install_btn.setEnabled(not in_progress)
                self.admin_install_btn.setToolTip(
                    "Admin install in progress…"
                    if in_progress
                    else "Install to /Applications (requires admin). Your macOS password will be requested in Terminal."
                )
            if self.update_btn:
                self.update_btn.setEnabled(not in_progress)
                self.update_btn.setToolTip(
                    "Disabled during Admin Install"
                    if in_progress
                    else "Check for and install the latest version.\n• Pulls latest code from GitHub\n• Updates the app bundle\n• Preserves your settings and configuration\n• Requires an active internet connection"
                )
        except Exception as e:
            logger.debug(f"Could not update button tooltip: {e}")

    def _handle_update_error(self, error: str) -> None:
        """Handle update errors."""
        # Mark update as completed (even though failed) to prevent false crash detection
        self._update_completed = True

        # Reset auto update tracking
        self._current_update_is_auto
        self._current_update_is_auto = False

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
            f"An error occurred while updating Skip the Podcast Desktop:\n\n{error}",
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
                            _os.environ["PATH"] = (
                                f"{bin_dir}:{current_path}" if current_path else bin_dir
                            )
                        # Try ffprobe next to it
                        probe = _Path(candidate).parent / "ffprobe"
                        if probe.exists():
                            _os.environ["FFPROBE_PATH"] = str(probe)
                        self.status_label.setText(
                            "✅ FFmpeg already installed and configured"
                        )
                        self.status_label.setStyleSheet(
                            "color: #4caf50; font-weight: bold;"
                        )
                        self.append_log(f"Using existing ffmpeg at: {candidate}")
                        return
                except (OSError, RuntimeError) as e:
                    logger.debug(f"FFmpeg check failed for {candidate}: {e}")

            # Use the same arch-aware default selection as the first-run installer
            from ..workers.ffmpeg_installer import get_default_ffmpeg_release

            release = get_default_ffmpeg_release()

            self.ffmpeg_worker = FFmpegInstaller(release)
            self.ffmpeg_worker.progress.connect(self._handle_ffmpeg_progress)
            self.ffmpeg_worker.finished.connect(self._handle_ffmpeg_finished)

            # Thread safety check for FFmpeg progress dialog
            from PyQt6.QtCore import QThread
            from PyQt6.QtWidgets import QApplication

            if QThread.currentThread() != QApplication.instance().thread():
                logger.error(
                    "🚨 CRITICAL: FFmpeg QProgressDialog creation attempted from background thread - BLOCKED!"
                )
                return

            self.update_progress_dialog = QProgressDialog(
                "Installing FFmpeg…", "Cancel", 0, 0, self
            )
            # Non-modal so the rest of the app remains responsive
            self.update_progress_dialog.setModal(False)
            self.update_progress_dialog.setMinimumDuration(0)
            self.update_progress_dialog.setMinimumWidth(520)
            self.update_progress_dialog.setStyleSheet(
                "QProgressDialog QLabel { font-family: 'Courier New', monospace; font-size: 12px; }"
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
            except RuntimeError:
                # Dialog was destroyed or not ready
                logger.debug("Could not update progress dialog text")

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

    # Hardware recommendations section removed - now handled automatically during installation

    # Hardware recommendations methods removed - now handled automatically during installation
    # TODO: Remove _apply_recommended_settings method starting at line 1982 - it's obsolete
    # Hardware optimization is now done during installation via scripts/generate_machine_config.py

    def _apply_recommended_settings(self):
        """Get hardware recommendations if needed, then apply them to the Local Transcription tab controls."""
        # First, check if we have recommendations - if not, get them
        if not hasattr(self, "_current_recommendations"):
            self.append_log("🔍 Getting hardware recommendations...")
            self._get_hardware_recommendations()

            # Check if we successfully got recommendations
            if not hasattr(self, "_current_recommendations"):
                self.append_log(
                    "❌ Failed to get recommendations. Please check hardware detection."
                )
                return

        # Get reference to the Local Transcription tab
        try:
            # Find the transcription tab through the main window
            main_window = self.parent()
            while main_window and not hasattr(main_window, "tabs"):
                main_window = main_window.parent()

            if not main_window:
                self.append_log(
                    "❌ Could not find main window to access transcription tab"
                )
                return

            # Find the Local Transcription tab
            transcription_tab = None
            for i in range(main_window.tabs.count()):
                tab = main_window.tabs.widget(i)
                if hasattr(tab, "tab_name") and tab.tab_name == "Local Transcription":
                    transcription_tab = tab
                    break

            if not transcription_tab:
                self.append_log("❌ Could not find Local Transcription tab")
                return

            specs = self._current_recommendations["specs"]

            # Debug logging
            self.append_log("🔧 Applying recommendations to Local Transcription tab:")
            self.append_log(f"   Model: {specs.recommended_whisper_model}")
            self.append_log(f"   Device: {specs.recommended_device}")
            self.append_log(f"   Batch Size: {specs.optimal_batch_size}")
            self.append_log(f"   Max Concurrent: {specs.max_concurrent_transcriptions}")
            self.append_log(f"   CPU Cores: {specs.cpu_cores}")

            # Apply recommended settings to transcription tab
            from ...config import get_valid_whisper_models

            # Model
            if specs.recommended_whisper_model in get_valid_whisper_models():
                old_model = transcription_tab.model_combo.currentText()
                index = transcription_tab.model_combo.findText(
                    specs.recommended_whisper_model
                )
                if index >= 0:
                    transcription_tab.model_combo.setCurrentIndex(index)
                    self.append_log(
                        f"   ✓ Model changed: {old_model} → {specs.recommended_whisper_model}"
                    )
                else:
                    self.append_log(
                        f"   ⚠️ Model '{specs.recommended_whisper_model}' not found in combo box"
                    )
            else:
                self.append_log(
                    f"   ⚠️ Model '{specs.recommended_whisper_model}' not supported"
                )

            # Device
            device_mapping = {"cpu": "cpu", "cuda": "cuda", "mps": "mps"}
            recommended_device = device_mapping.get(
                specs.recommended_device.lower(), "auto"
            )
            old_device = transcription_tab.device_combo.currentText()
            index = transcription_tab.device_combo.findText(recommended_device)
            if index >= 0:
                transcription_tab.device_combo.setCurrentIndex(index)
                self.append_log(
                    f"   ✓ Device changed: {old_device} → {recommended_device}"
                )
            else:
                self.append_log(
                    f"   ⚠️ Device '{recommended_device}' not found in combo box"
                )

            # Batch size
            if hasattr(specs, "optimal_batch_size") and specs.optimal_batch_size:
                old_batch = transcription_tab.batch_size.value()
                transcription_tab.batch_size.setValue(specs.optimal_batch_size)
                self.append_log(
                    f"   ✓ Batch size changed: {old_batch} → {specs.optimal_batch_size}"
                )
            else:
                self.append_log("   ⚠️ No optimal batch size available")

            # Max concurrent files
            if (
                hasattr(specs, "max_concurrent_transcriptions")
                and specs.max_concurrent_transcriptions
            ):
                old_concurrent = transcription_tab.max_concurrent.value()
                transcription_tab.max_concurrent.setValue(
                    specs.max_concurrent_transcriptions
                )
                self.append_log(
                    f"   ✓ Max concurrent changed: {old_concurrent} → {specs.max_concurrent_transcriptions}"
                )
            else:
                self.append_log("   ⚠️ No max concurrent recommendation available")

            # Calculate optimal thread count (usually leave some cores free)
            if hasattr(specs, "cpu_cores") and specs.cpu_cores:
                optimal_threads = max(1, min(8, specs.cpu_cores - 1))
                old_threads = transcription_tab.omp_threads.value()
                transcription_tab.omp_threads.setValue(optimal_threads)
                self.append_log(
                    f"   ✓ Thread count changed: {old_threads} → {optimal_threads}"
                )
            else:
                self.append_log("   ⚠️ No CPU cores information available")

            self.append_log(
                "✅ Recommended settings applied successfully to Local Transcription tab!"
            )

        except Exception as e:
            error_msg = f"Failed to apply recommended settings: {e}"
            self.append_log(f"❌ {error_msg}")
            import traceback

            self.append_log(f"   Stack trace: {traceback.format_exc()}")
