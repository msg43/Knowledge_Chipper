"""Enhanced error dialog with actionable recovery suggestions."""

import webbrowser

from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


class EnhancedErrorDialog(QDialog):
    """Enhanced error dialog with contextual help and recovery suggestions."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Error Information")
        self.setMinimumSize(500, 400)
        self.setModal(True)

        # Error analysis patterns
        self.error_patterns = {
            "api_key": {
                "patterns": ["api key", "authentication", "unauthorized", "401", "403"],
                "title": "🔑 API Key Issue",
                "description": "There's a problem with your API key configuration.",
                "solutions": [
                    "1. Check that your API key is correctly entered in the Settings tab",
                    "2. Verify your API key is active and not expired",
                    "3. Ensure you have sufficient credits/quota remaining",
                    "4. For OpenAI: Check your account billing status",
                ],
                "help_url": "https://platform.openai.com/api-keys",
            },
            "model_access": {
                "patterns": [
                    "model",
                    "access denied",
                    "not available",
                    "invalid model",
                ],
                "title": "🤖 Model Access Issue",
                "description": "The selected AI model is not accessible with your current account.",
                "solutions": [
                    "1. Check if you have access to the selected model (e.g., GPT-4 requires special access)",
                    "2. Try using a different model (GPT-3.5-turbo is widely available)",
                    "3. Upgrade your API plan if needed",
                    "4. For Ollama: Run 'ollama pull <model-name>' to install the model",
                ],
                "help_url": "https://platform.openai.com/docs/models",
            },
            "network": {
                "patterns": ["network", "connection", "timeout", "unreachable", "dns"],
                "title": "🌐 Network Connection Issue",
                "description": "There's a problem connecting to the service.",
                "solutions": [
                    "1. Check your internet connection",
                    "2. Try again in a few minutes (temporary outage)",
                    "3. Check if your firewall is blocking the connection",
                    "4. For corporate networks: Check proxy settings",
                ],
                "help_url": "https://status.openai.com/",
            },
            "mvp_llm_setup": {
                "patterns": [
                    "mvp llm",
                    "ollama",
                    "setup failed",
                    "installation",
                    "model download",
                ],
                "title": "🤖 MVP AI System Setup Issue",
                "description": "There's a problem setting up the built-in AI system.",
                "solutions": [
                    "1. Check that you have sufficient disk space (~2GB needed)",
                    "2. Ensure you have internet connection for model download",
                    "3. Try running the app as administrator if installation fails",
                    "4. Check that no antivirus is blocking the installation",
                    "5. You can disable MVP AI in Settings and use cloud AI instead",
                ],
                "help_url": "https://ollama.ai/",
            },
            "mvp_llm_service": {
                "patterns": [
                    "ollama service",
                    "service not running",
                    "connection refused",
                    "11434",
                ],
                "title": "🤖 MVP AI Service Issue",
                "description": "The built-in AI service is not running properly.",
                "solutions": [
                    "1. Restart the application to auto-start the AI service",
                    "2. Check if another instance of Ollama is running",
                    "3. Try running: 'ollama serve' in terminal to start manually",
                    "4. Check if port 11434 is available and not blocked",
                    "5. You can use cloud AI instead while this is being fixed",
                ],
                "help_url": "https://ollama.ai/",
            },
            "mvp_llm_model": {
                "patterns": [
                    "model not found",
                    "model download failed",
                    "model corrupt",
                ],
                "title": "🤖 MVP AI Model Issue",
                "description": "There's a problem with the AI model for speaker identification.",
                "solutions": [
                    "1. The model will auto-download on first use - please wait",
                    "2. Check your internet connection for model downloads",
                    "3. Try clearing Ollama models: 'ollama rm <model-name>' and re-download",
                    "4. Ensure you have sufficient disk space for models",
                    "5. You can use cloud AI for speaker identification instead",
                ],
                "help_url": "https://ollama.ai/library",
            },
            "rate_limit": {
                "patterns": ["rate limit", "too many requests", "quota", "429"],
                "title": "⏱️ Rate Limit Exceeded",
                "description": "You've exceeded the allowed number of requests per minute/hour.",
                "solutions": [
                    "1. Wait a few minutes before trying again",
                    "2. Reduce the number of files being processed simultaneously",
                    "3. Upgrade your API plan for higher rate limits",
                    "4. Consider processing in smaller batches",
                ],
                "help_url": "https://platform.openai.com/docs/guides/rate-limits",
            },
            "file_access": {
                "patterns": [
                    "permission denied",
                    "file not found",
                    "access denied",
                    "path",
                ],
                "title": "📁 File Access Issue",
                "description": "There's a problem accessing files or directories.",
                "solutions": [
                    "1. Check that the file exists and hasn't been moved",
                    "2. Verify you have read/write permissions for the files",
                    "3. Make sure the output directory is writable",
                    "4. Try selecting a different output location",
                ],
            },
            "ffmpeg": {
                "patterns": ["ffmpeg", "codec", "audio format", "conversion"],
                "title": "🎵 Audio Processing Issue",
                "description": "There's a problem with audio/video file processing.",
                "solutions": [
                    "1. Install FFmpeg: 'brew install ffmpeg' (macOS) or equivalent",
                    "2. Check that the audio/video file isn't corrupted",
                    "3. Try converting the file to a standard format first",
                    "4. Ensure the file format is supported",
                ],
                "help_url": "https://ffmpeg.org/download.html",
            },
            "memory": {
                "patterns": ["memory", "out of memory", "ram", "allocation"],
                "title": "💾 Memory Issue",
                "description": "The system has run out of available memory.",
                "solutions": [
                    "1. Close other applications to free up memory",
                    "2. Process fewer files at once",
                    "3. Use a smaller transcription model",
                    "4. Restart the application",
                ],
            },
            "transcription_quality": {
                "patterns": [
                    "quality warning",
                    "word density",
                    "repetitive",
                    "low quality",
                ],
                "title": "⚠️ Transcription Quality Warning",
                "description": "The transcription completed but quality issues were detected.",
                "solutions": [
                    "1. Enable automatic quality retry in settings",
                    "2. Try using a larger/better model (e.g., 'base' instead of 'tiny')",
                    "3. Check if the audio quality is poor or has background noise",
                    "4. For very quiet audio, this might be normal",
                ],
                "is_warning": True,
            },
            "cloud_api": {
                "patterns": [
                    "402 payment required",
                    "cloud",
                    "skipthepodcast",
                    "payment",
                ],
                "title": "☁️ Cloud Service Issue",
                "description": "There's an issue with the cloud transcription service.",
                "solutions": [
                    "1. Check your Skipthepodcast.com account status",
                    "2. Verify you have remaining transcription credits",
                    "3. Check the service status page",
                    "4. Try again with local transcription if needed",
                ],
                "help_url": "https://skipthepodcast.com/account",
            },
            "import_error": {
                "patterns": [
                    "no module named",
                    "module not found",
                    "import error",
                    "cannot import",
                    "import failed",
                ],
                "title": "📦 Import/Module Error",
                "description": "There's a problem with a required module or dependency.",
                "solutions": [
                    "1. This is typically a development/build issue",
                    "2. Try restarting the application",
                    "3. If the problem persists, this may require a software update",
                    "4. Check if all required dependencies are properly installed",
                    "5. For advanced users: Check the application logs for more details",
                ],
                "help_url": None,
            },
        }

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Setup the enhanced error dialog UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        # Header section
        header_layout = QHBoxLayout()

        # Error icon and title
        self.error_icon = QLabel("❌")
        self.error_icon.setStyleSheet("font-size: 24px;")
        header_layout.addWidget(self.error_icon)

        self.error_title = QLabel("Error Occurred")
        self.error_title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        self.error_title.setStyleSheet("color: #d32f2f; margin-left: 10px;")
        header_layout.addWidget(self.error_title)

        header_layout.addStretch()
        layout.addLayout(header_layout)

        # Error description
        self.error_description = QLabel("")
        self.error_description.setWordWrap(True)
        self.error_description.setStyleSheet("font-size: 12px; margin-bottom: 10px;")
        layout.addWidget(self.error_description)

        # Solutions section
        self.solutions_label = QLabel("💡 Suggested Solutions:")
        self.solutions_label.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        self.solutions_label.setStyleSheet("color: #2e7d32; margin-top: 10px;")
        layout.addWidget(self.solutions_label)

        # Solutions list
        self.solutions_widget = QWidget()
        self.solutions_layout = QVBoxLayout(self.solutions_widget)
        self.solutions_layout.setContentsMargins(20, 10, 10, 10)

        # Scroll area for solutions
        scroll_area = QScrollArea()
        scroll_area.setWidget(self.solutions_widget)
        scroll_area.setWidgetResizable(True)
        scroll_area.setMaximumHeight(150)
        scroll_area.setStyleSheet(
            """
            QScrollArea {
                border: 1px solid #ddd;
                border-radius: 5px;
                background-color: #f9f9f9;
            }
        """
        )
        layout.addWidget(scroll_area)

        # Technical details (collapsible)
        self.technical_label = QLabel("🔧 Technical Details:")
        self.technical_label.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        self.technical_label.setStyleSheet("margin-top: 15px;")
        layout.addWidget(self.technical_label)

        self.technical_details = QTextEdit()
        self.technical_details.setMaximumHeight(100)
        self.technical_details.setReadOnly(True)
        self.technical_details.setStyleSheet(
            """
            QTextEdit {
                border: 1px solid #ddd;
                border-radius: 5px;
                background-color: #f5f5f5;
                font-family: 'Courier New', monospace;
                font-size: 10px;
            }
        """
        )
        layout.addWidget(self.technical_details)

        # Action buttons
        button_layout = QHBoxLayout()

        # Help button (if help URL available)
        self.help_btn = QPushButton("🌐 Get Help Online")
        self.help_btn.clicked.connect(self._open_help)
        self.help_btn.setStyleSheet(
            """
            QPushButton {
                background-color: #1976d2;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1565c0;
            }
        """
        )
        self.help_btn.hide()  # Initially hidden
        button_layout.addWidget(self.help_btn)

        button_layout.addStretch()

        # Copy error button
        copy_btn = QPushButton("📋 Copy Error")
        copy_btn.clicked.connect(self._copy_error)
        copy_btn.setStyleSheet(
            """
            QPushButton {
                background-color: #757575;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #616161;
            }
        """
        )
        button_layout.addWidget(copy_btn)

        # Close button
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        close_btn.setStyleSheet(
            """
            QPushButton {
                background-color: #4caf50;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """
        )
        close_btn.setDefault(True)
        button_layout.addWidget(close_btn)

        layout.addLayout(button_layout)

        # Store for later use
        self.current_help_url = None
        self.current_error_text = ""

    def show_error(
        self,
        error_title: str,
        error_message: str,
        context: str = "",
        technical_details: str = "",
    ) -> None:
        """Show enhanced error dialog with contextual help."""
        # Analyze error to provide contextual help
        error_info = self._analyze_error(error_message, context)

        # Update UI based on analysis
        if error_info["is_warning"]:
            self.error_icon.setText("⚠️")
            self.error_title.setText(error_info["title"])
            self.error_title.setStyleSheet(
                "color: #f57c00; margin-left: 10px; font-weight: bold;"
            )
        else:
            self.error_icon.setText("❌")
            self.error_title.setText(error_info["title"])
            self.error_title.setStyleSheet(
                "color: #d32f2f; margin-left: 10px; font-weight: bold;"
            )

        self.error_description.setText(error_info["description"])

        # Clear previous solutions
        for i in reversed(range(self.solutions_layout.count())):
            self.solutions_layout.itemAt(i).widget().setParent(None)

        # Add new solutions
        for solution in error_info["solutions"]:
            solution_label = QLabel(solution)
            solution_label.setWordWrap(True)
            solution_label.setStyleSheet("margin: 2px 0;")
            self.solutions_layout.addWidget(solution_label)

        # Set technical details
        full_technical = f"Error: {error_message}"
        if technical_details:
            full_technical += f"\n\nDetails: {technical_details}"
        if context:
            full_technical += f"\n\nContext: {context}"

        self.technical_details.setPlainText(full_technical)
        self.current_error_text = full_technical

        # Show/hide help button
        if error_info["help_url"]:
            self.current_help_url = error_info["help_url"]
            self.help_btn.show()
        else:
            self.help_btn.hide()

        # Show dialog
        self.show()

    def _analyze_error(self, error_message: str, context: str = "") -> dict:
        """Analyze error message to provide contextual help."""
        error_text = f"{error_message} {context}".lower()

        # Check for matching patterns
        for pattern_name, pattern_info in self.error_patterns.items():
            if any(pattern in error_text for pattern in pattern_info["patterns"]):
                return {
                    "title": pattern_info["title"],
                    "description": pattern_info["description"],
                    "solutions": pattern_info["solutions"],
                    "help_url": pattern_info.get("help_url"),
                    "is_warning": pattern_info.get("is_warning", False),
                }

        # Default fallback
        return {
            "title": "❌ Unexpected Error",
            "description": "An unexpected error occurred. Please review the technical details below.",
            "solutions": [
                "1. Try the operation again",
                "2. Restart the application if the problem persists",
                "3. Check the application logs for more information",
                "4. Report this issue if it continues to occur",
            ],
            "help_url": None,
            "is_warning": False,
        }

    def _open_help(self) -> None:
        """Open help URL in browser."""
        if self.current_help_url:
            webbrowser.open(self.current_help_url)

    def _copy_error(self) -> None:
        """Copy error details to clipboard."""
        from PyQt6.QtWidgets import QApplication

        clipboard = QApplication.clipboard()
        clipboard.setText(self.current_error_text)

        # Temporarily change button text to show copied
        original_text = "📋 Copy Error"
        self.sender().setText("✅ Copied!")

        # Reset button text after 1 second
        from PyQt6.QtCore import QTimer

        QTimer.singleShot(1000, lambda: self.sender().setText(original_text))


def show_enhanced_error(
    parent, title: str, message: str, context: str = "", details: str = ""
) -> None:
    """Convenience function to show enhanced error dialog."""
    import logging
    import traceback as tb

    logger = logging.getLogger(__name__)

    # Handle empty/None messages
    if not message or message.strip() == "":
        logger.error("show_enhanced_error called with empty message!")
        logger.error(f"Title: {title}")
        logger.error(f"Context: {context}")
        logger.error(f"Details: {details}")
        logger.error(f"Caller traceback:\n{tb.format_stack()}")
        message = "An error occurred but no error message was provided. Check the logs for details."

    try:
        from PyQt6.QtCore import QThread, QTimer
        from PyQt6.QtWidgets import QApplication

        def _do_show():
            dlg_parent = parent
            # If parent is None, try to use active window
            if dlg_parent is None:
                app = QApplication.instance()
                if app:
                    dlg_parent = app.activeWindow()
            dialog = EnhancedErrorDialog(dlg_parent)
            dialog.show_error(title, message, context, details)
            dialog.exec()

        app = QApplication.instance()
        if app and QThread.currentThread() != app.thread():
            QTimer.singleShot(0, _do_show)
            return
        _do_show()
    except Exception as e:
        # Best-effort fallback
        logger.error(f"Error showing error dialog: {e}")
        logger.error(tb.format_exc())
        dialog = EnhancedErrorDialog(parent)
        dialog.show_error(title, message, context, details)
        dialog.exec()
