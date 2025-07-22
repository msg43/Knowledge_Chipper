"""API Keys configuration tab for managing all API credentials."""

from typing import Optional
from pathlib import Path

from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QGroupBox, QGridLayout,
    QLabel, QPushButton, QLineEdit, QFrame
)
from PyQt6.QtCore import QTimer, pyqtSignal

from ..components.base_tab import BaseTab
from ...logger import get_logger

logger = get_logger(__name__)


class APIKeysTab(BaseTab):
    """Tab for API keys configuration."""
    
    # Signals for settings changes
    settings_saved = pyqtSignal()
    
    def __init__(self, parent=None):
        # Initialize _actual_api_keys before calling super().__init__
        self._actual_api_keys = {}
        super().__init__(parent)
        
    def _setup_ui(self):
        """Setup the API keys UI."""
        main_layout = QVBoxLayout(self)
        
        # Instructions section with dark background - moved to top
        instructions_group = QGroupBox("Instructions")
        instructions_layout = QVBoxLayout()
        
        instructions_text = QLabel("""
🔑 API Key Configuration Guide:

• WebShare Proxy: Required for YouTube access. The system uses only WebShare rotating residential proxies.
  Sign up at: https://www.webshare.io/

• OpenAI API Key: Required for GPT-based summarization.
  Get your key at: https://platform.openai.com/api-keys

• Anthropic API Key: Required for Claude-based summarization.
  Get your key at: https://console.anthropic.com/

• HuggingFace Token: Required for speaker diarization (separating different speakers in audio).
  Get your free token at: https://huggingface.co/settings/tokens


        """)
        instructions_text.setWordWrap(True)
        # Dark background with light text for better readability
        instructions_text.setStyleSheet("""
            background-color: #2b2b2b; 
            color: #ffffff; 
            padding: 15px; 
            border: 1px solid #555; 
            border-radius: 5px;
        """)
        instructions_layout.addWidget(instructions_text)
        
        instructions_group.setLayout(instructions_layout)
        main_layout.addWidget(instructions_group)
        
        # API Key Input Fields - moved below instructions
        layout = QGridLayout()
        layout.addWidget(QLabel("🗝️ API Keys"), 0, 0, 1, 2)
        layout.addWidget(QFrame(), 1, 0, 1, 2)  # Separator

        # OpenAI API Key
        layout.addWidget(QLabel("OpenAI API Key:"), 2, 0)
        self.openai_key_edit = QLineEdit()
        self.openai_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.openai_key_edit.setPlaceholderText("sk-...")
        layout.addWidget(self.openai_key_edit, 2, 1)

        # Anthropic API Key
        layout.addWidget(QLabel("Anthropic API Key:"), 3, 0)
        self.anthropic_key_edit = QLineEdit()
        self.anthropic_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.anthropic_key_edit.setPlaceholderText("sk-ant-api03-...")
        layout.addWidget(self.anthropic_key_edit, 3, 1)

        # HuggingFace Token
        layout.addWidget(QLabel("HuggingFace Token:"), 4, 0)
        self.huggingface_token_edit = QLineEdit()
        self.huggingface_token_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.huggingface_token_edit.setPlaceholderText("hf_...")
        layout.addWidget(self.huggingface_token_edit, 4, 1)

        # WebShare Proxy Credentials
        layout.addWidget(QLabel("🌐 WebShare Proxy Credentials"), 5, 0, 1, 2)
        
        # WebShare Username
        layout.addWidget(QLabel("WebShare Username:"), 6, 0)
        self.webshare_username_edit = QLineEdit()
        self.webshare_username_edit.setPlaceholderText("username")
        layout.addWidget(self.webshare_username_edit, 6, 1)

        # WebShare Password
        layout.addWidget(QLabel("WebShare Password:"), 7, 0)
        self.webshare_password_edit = QLineEdit()
        self.webshare_password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.webshare_password_edit.setPlaceholderText("password")
        layout.addWidget(self.webshare_password_edit, 7, 1)

        # Load existing values and set up change handlers
        self._load_existing_values()
        self._setup_change_handlers()

        # Add the layout to a group and then to main layout
        api_group = QGroupBox("API Keys Configuration") 
        api_group.setLayout(layout)
        main_layout.addWidget(api_group)

        # Save button
        save_btn = QPushButton("💾 Save API Keys")
        save_btn.clicked.connect(self._save_settings)
        save_btn.setStyleSheet("background-color: #4caf50; font-weight: bold; padding: 10px; font-size: 14px;")
        main_layout.addWidget(save_btn)

        # Status label
        self.status_label = QLabel("")
        main_layout.addWidget(self.status_label)
        
        main_layout.addStretch()

    def _load_existing_values(self):
        """Load existing API key values from settings."""
        # Load OpenAI key
        if self.settings.api_keys.openai_api_key:
            self._actual_api_keys['openai_api_key'] = self.settings.api_keys.openai_api_key
            self.openai_key_edit.setText("••••••••••••••••••••••••••••••••••••••••••••••••••••")

        # Load Anthropic key  
        if self.settings.api_keys.anthropic_api_key:
            self._actual_api_keys['anthropic_api_key'] = self.settings.api_keys.anthropic_api_key
            self.anthropic_key_edit.setText("••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••")

        # Load HuggingFace token
        if self.settings.api_keys.huggingface_token:
            self._actual_api_keys['huggingface_token'] = self.settings.api_keys.huggingface_token
            self.huggingface_token_edit.setText("••••••••••••••••••••••••••••••••••••••••••••••••••••")

        # Load WebShare credentials
        if self.settings.api_keys.webshare_username:
            self.webshare_username_edit.setText(self.settings.api_keys.webshare_username)
            
        if self.settings.api_keys.webshare_password:
            self._actual_api_keys['webshare_password'] = self.settings.api_keys.webshare_password
            self.webshare_password_edit.setText("••••••••••••••••")

    def _setup_change_handlers(self):
        """Set up change handlers for password/key fields."""
        self.openai_key_edit.textChanged.connect(lambda text: self._handle_key_change('openai_api_key', text))
        self.anthropic_key_edit.textChanged.connect(lambda text: self._handle_key_change('anthropic_api_key', text))
        self.huggingface_token_edit.textChanged.connect(lambda text: self._handle_key_change('huggingface_token', text))
        self.webshare_password_edit.textChanged.connect(lambda text: self._handle_password_change('webshare_password', text))

    def _handle_key_change(self, key_name: str, new_text: str):
        """Handle changes to API key fields."""
        # If user types new content (not just the obscured dots), update the actual key
        if new_text and not new_text.startswith('••'):
            self._actual_api_keys[key_name] = new_text

    def _handle_password_change(self, key_name: str, new_text: str):
        """Handle changes to password fields."""
        # If user types new content (not just the obscured dots), update the actual password
        if new_text and not new_text.startswith('••'):
            self._actual_api_keys[key_name] = new_text
        
    def _get_start_button_text(self) -> str:
        """Get the text for the start button."""
        return "Save API Keys"
        
    def _start_processing(self):
        """Save settings when start button is pressed."""
        self._save_settings()

    def _save_settings(self):
        """Save API key settings and update environment variables."""
        try:
            # Update settings object with actual values or form values
            self.settings.api_keys.webshare_username = self.webshare_username_edit.text().strip()
            
            # For password/key fields, use actual stored values if available, otherwise use form input
            webshare_password = self._actual_api_keys.get('webshare_password', self.webshare_password_edit.text().strip())
            if not webshare_password.startswith('••'):
                self.settings.api_keys.webshare_password = webshare_password
            
            openai_key = self._actual_api_keys.get('openai_api_key', self.openai_key_edit.text().strip())
            if not openai_key.startswith('••'):
                self.settings.api_keys.openai_api_key = openai_key
            
            anthropic_key = self._actual_api_keys.get('anthropic_api_key', self.anthropic_key_edit.text().strip())
            if not anthropic_key.startswith('••'):
                self.settings.api_keys.anthropic_api_key = anthropic_key
            
            huggingface_token = self._actual_api_keys.get('huggingface_token', self.huggingface_token_edit.text().strip())
            if not huggingface_token.startswith('••'):
                self.settings.api_keys.huggingface_token = huggingface_token


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
            
    def _load_api_keys_to_environment(self):
        """Load API keys to environment variables - stub method."""
        # This method should be connected to the main window's implementation
        parent = self.parent()
        if parent and hasattr(parent, '_load_api_keys_to_environment'):
            parent._load_api_keys_to_environment()  # type: ignore
            
    def _save_session(self):
        """Save session data - stub method."""
        # This method should be connected to the main window's implementation
        parent = self.parent()
        if parent and hasattr(parent, '_save_session'):
            parent._save_session()  # type: ignore
            
    def validate_inputs(self) -> bool:
        """Validate API key inputs."""
        # All API keys are optional, so always valid
        return True 