"""Model download notification widget for persistent user feedback."""

from PyQt6.QtCore import QTimer, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
)

from ...logger import get_logger

logger = get_logger(__name__)


class ModelNotificationWidget(QFrame):
    """Persistent notification widget for model downloads."""

    # Signals
    retry_requested = pyqtSignal(str)  # model_type
    dismissed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameStyle(QFrame.Shape.Box)
        self.setStyleSheet(
            """
            ModelNotificationWidget {
                background-color: #f0f8ff;
                border: 2px solid #4a90e2;
                border-radius: 8px;
                padding: 10px;
            }
        """
        )

        # Setup UI
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)

        # Icon label
        self.icon_label = QLabel("📥")
        self.icon_label.setFont(QFont("", 16))
        layout.addWidget(self.icon_label)

        # Message label
        self.message_label = QLabel("Downloading models...")
        self.message_label.setWordWrap(True)
        layout.addWidget(self.message_label, 1)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximumWidth(200)
        self.progress_bar.setTextVisible(True)
        layout.addWidget(self.progress_bar)

        # Action button
        self.action_button = QPushButton("Dismiss")
        self.action_button.clicked.connect(self._on_dismiss)
        layout.addWidget(self.action_button)

        # Auto-hide timer
        self.auto_hide_timer = QTimer()
        self.auto_hide_timer.timeout.connect(self.hide)

        # Track state
        self.model_states = {}  # model_type -> {'status', 'progress', 'message'}

    def show_model_download(self, model_type: str, message: str):
        """Show notification for model download starting."""
        self.model_states[model_type] = {
            "status": "downloading",
            "progress": 0,
            "message": message,
        }
        self._update_display()
        self.show()

    def update_progress(self, model_type: str, progress: int, message: str):
        """Update download progress."""
        if model_type in self.model_states:
            self.model_states[model_type]["progress"] = progress
            self.model_states[model_type]["message"] = message
            self._update_display()

    def show_completion(self, model_type: str, success: bool, message: str):
        """Show download completion."""
        if model_type in self.model_states:
            self.model_states[model_type]["status"] = (
                "completed" if success else "failed"
            )
            self.model_states[model_type]["message"] = message
            self._update_display()

            # Auto-hide after 5 seconds if successful
            if success:
                self.auto_hide_timer.start(5000)

    def show_feature_blocked(self, feature: str, required_model: str):
        """Show notification that a feature is blocked pending model download."""
        self.icon_label.setText("⚠️")
        self.message_label.setText(
            f"{feature} requires {required_model} model. "
            "The model is downloading in the background..."
        )
        self.progress_bar.setVisible(True)
        self.action_button.setText("Check Progress")
        self.action_button.clicked.disconnect()
        self.action_button.clicked.connect(
            lambda: self.retry_requested.emit(required_model)
        )

        self.setStyleSheet(
            """
            ModelNotificationWidget {
                background-color: #fff9e6;
                border: 2px solid #ffa500;
                border-radius: 8px;
                padding: 10px;
            }
        """
        )
        self.show()

    def _update_display(self):
        """Update the display based on current model states."""
        if not self.model_states:
            self.hide()
            return

        # Calculate overall progress
        total_progress = 0
        active_downloads = []
        completed = []
        failed = []

        for model_type, state in self.model_states.items():
            if state["status"] == "downloading":
                active_downloads.append(model_type)
                total_progress += state["progress"]
            elif state["status"] == "completed":
                completed.append(model_type)
            elif state["status"] == "failed":
                failed.append(model_type)

        # Update display based on state
        if active_downloads:
            avg_progress = (
                total_progress / len(active_downloads) if active_downloads else 0
            )
            self.icon_label.setText("📥")
            self.message_label.setText(
                f"Downloading {len(active_downloads)} model(s): "
                f"{', '.join(active_downloads)}"
            )
            self.progress_bar.setValue(int(avg_progress))
            self.progress_bar.setVisible(True)
            self.action_button.setText("Hide")

        elif failed:
            self.icon_label.setText("❌")
            self.message_label.setText(
                f"Failed to download {len(failed)} model(s): " f"{', '.join(failed)}"
            )
            self.progress_bar.setVisible(False)
            self.action_button.setText("Retry")
            self.action_button.clicked.disconnect()
            self.action_button.clicked.connect(
                lambda: self.retry_requested.emit(failed[0])
            )

        elif completed:
            self.icon_label.setText("✅")
            self.message_label.setText(
                f"Successfully downloaded {len(completed)} model(s)"
            )
            self.progress_bar.setVisible(False)
            self.action_button.setText("Dismiss")

    def _on_dismiss(self):
        """Handle dismiss action."""
        self.hide()
        self.model_states.clear()
        self.dismissed.emit()
