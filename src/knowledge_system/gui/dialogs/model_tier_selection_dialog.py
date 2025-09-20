#!/usr/bin/env python3
"""
Smart Model Selection Dialog

Intelligently recommends AI models based on the user's system capabilities.
Analyzes RAM, storage, CPU, and provides personalized recommendations.
"""

import sys
from pathlib import Path

from PyQt6.QtCore import Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap
from PyQt6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QSpacerItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

# Import the GitHub model downloader and system detector
sys.path.append(str(Path(__file__).parent.parent.parent.parent.parent / "scripts"))
from download_models_from_github import GitHubModelDownloader

# Import system detection
sys.path.append(str(Path(__file__).parent.parent.parent))
from utils.system_detector import SystemCapabilityDetector, get_system_recommendations


class ModelDownloadWorker(QThread):
    """Background worker for downloading models."""

    progress_update = pyqtSignal(str)  # Status message
    download_complete = pyqtSignal(bool, str)  # Success, message

    def __init__(self, app_bundle_path: Path, tier: str):
        super().__init__()
        self.app_bundle_path = app_bundle_path
        self.tier = tier
        self.downloader = None

    def run(self):
        try:
            self.progress_update.emit(f"Starting {self.tier} tier download...")
            self.downloader = GitHubModelDownloader(self.app_bundle_path)

            success = self.downloader.download_tier(self.tier)

            if success:
                self.download_complete.emit(
                    True, f"✅ {self.tier.title()} models downloaded successfully!"
                )
            else:
                self.download_complete.emit(
                    False, f"❌ Some {self.tier} models failed to download"
                )

        except Exception as e:
            self.download_complete.emit(False, f"❌ Download failed: {str(e)}")


class ModelTierSelectionDialog(QDialog):
    """Smart dialog for selecting model tier based on system capabilities."""

    def __init__(self, app_bundle_path: Path, parent=None):
        super().__init__(parent)
        self.app_bundle_path = app_bundle_path
        self.download_worker = None

        # Analyze system capabilities
        self.system_analysis = get_system_recommendations()
        self.system_info = self.system_analysis["system_info"]
        self.recommendations = self.system_analysis["recommendations"]

        # Set intelligent default based on system
        self.selected_tier = self.recommendations["recommended_tier"]

        self.setWindowTitle("🧠 Smart AI Model Setup")
        self.setModal(True)
        self.setMinimumSize(750, 700)
        self.setMaximumSize(1000, 900)

        # Load tier information
        downloader = GitHubModelDownloader(app_bundle_path)
        self.tier_info = downloader.get_tier_info()

        self.setup_ui()

    def setup_ui(self):
        """Set up the user interface."""
        layout = QVBoxLayout(self)
        layout.setSpacing(20)

        # Header
        self.setup_header(layout)

        # System analysis section
        self.setup_system_analysis(layout)

        # Tier selection cards
        self.setup_tier_cards(layout)

        # Download section (hidden initially)
        self.setup_download_section(layout)

        # Action buttons
        self.setup_action_buttons(layout)

    def setup_header(self, layout: QVBoxLayout):
        """Set up the header section."""
        header_frame = QFrame()
        header_frame.setStyleSheet(
            """
            QFrame {
                background-color: #f8f9fa;
                border: 1px solid #e9ecef;
                border-radius: 8px;
                padding: 20px;
            }
        """
        )

        header_layout = QVBoxLayout(header_frame)

        # Title
        title = QLabel("🧠 Smart AI Model Setup")
        title_font = QFont()
        title_font.setPointSize(18)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(title)

        # Subtitle
        subtitle = QLabel(
            "We've analyzed your system and will recommend the best AI models for your hardware. "
            "All models download from our fast GitHub servers."
        )
        subtitle.setStyleSheet("color: #6c757d; font-size: 14px;")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setWordWrap(True)
        header_layout.addWidget(subtitle)

        layout.addWidget(header_frame)

    def setup_system_analysis(self, layout: QVBoxLayout):
        """Set up the system analysis section."""
        analysis_frame = QFrame()
        analysis_frame.setStyleSheet(
            """
            QFrame {
                background-color: #f1f3f4;
                border: 1px solid #dadce0;
                border-radius: 8px;
                padding: 15px;
            }
        """
        )

        analysis_layout = QVBoxLayout(analysis_frame)

        # System info header
        system_header = QLabel("🖥️ Your System Analysis")
        system_header.setStyleSheet(
            "font-weight: bold; font-size: 16px; color: #1a73e8;"
        )
        analysis_layout.addWidget(system_header)

        # System summary
        system_summary = QLabel(self.system_analysis["system_summary"])
        system_summary.setStyleSheet("font-size: 14px; color: #5f6368; margin: 5px 0;")
        analysis_layout.addWidget(system_summary)

        # Recommendations
        rec_text = f"💡 Recommendation: {self.recommendations['recommended_tier'].title()} tier models"
        if self.recommendations["performance_explanation"]:
            rec_text += f" - {self.recommendations['performance_explanation']}"

        recommendation_label = QLabel(rec_text)
        recommendation_label.setStyleSheet(
            "font-size: 14px; color: #137333; font-weight: bold; margin: 5px 0;"
        )
        recommendation_label.setWordWrap(True)
        analysis_layout.addWidget(recommendation_label)

        # Benefits section
        if self.recommendations["benefits"]:
            benefits_text = "✅ " + " • ".join(
                self.recommendations["benefits"][:2]
            )  # Show top 2 benefits
            benefits_label = QLabel(benefits_text)
            benefits_label.setStyleSheet(
                "font-size: 13px; color: #137333; margin: 5px 0;"
            )
            benefits_label.setWordWrap(True)
            analysis_layout.addWidget(benefits_label)

        # Warnings section
        if self.recommendations["warnings"]:
            warnings_text = "⚠️ " + " • ".join(
                self.recommendations["warnings"][:2]
            )  # Show top 2 warnings
            warnings_label = QLabel(warnings_text)
            warnings_label.setStyleSheet(
                "font-size: 13px; color: #ea4335; margin: 5px 0;"
            )
            warnings_label.setWordWrap(True)
            analysis_layout.addWidget(warnings_label)

        # Storage note
        if self.recommendations["storage_note"]:
            storage_label = QLabel(self.recommendations["storage_note"])
            storage_label.setStyleSheet(
                "font-size: 13px; color: #5f6368; margin: 5px 0;"
            )
            analysis_layout.addWidget(storage_label)

        layout.addWidget(analysis_frame)

    def setup_tier_cards(self, layout: QVBoxLayout):
        """Set up the tier selection cards."""
        cards_frame = QFrame()
        cards_layout = QHBoxLayout(cards_frame)
        cards_layout.setSpacing(20)

        # Button group for radio buttons
        self.tier_group = QButtonGroup(self)

        # Base tier card
        base_card = self.create_tier_card("base", self.tier_info.get("base", {}))
        cards_layout.addWidget(base_card)

        # Premium tier card
        premium_card = self.create_tier_card(
            "premium", self.tier_info.get("premium", {})
        )
        cards_layout.addWidget(premium_card)

        layout.addWidget(cards_frame)

    def create_tier_card(self, tier_name: str, tier_data: dict) -> QFrame:
        """Create a card for a specific tier."""
        card = QFrame()
        card.setStyleSheet(
            f"""
            QFrame {{
                border: 2px solid #dee2e6;
                border-radius: 12px;
                padding: 20px;
                background-color: white;
            }}
            QFrame:hover {{
                border-color: #007bff;
            }}
        """
        )

        layout = QVBoxLayout(card)
        layout.setSpacing(15)

        # Radio button and title
        radio_layout = QHBoxLayout()

        radio = QRadioButton()
        radio.setObjectName(f"{tier_name}_radio")
        # Set checked based on system recommendation
        if tier_name == self.recommendations["recommended_tier"]:
            radio.setChecked(True)

        self.tier_group.addButton(radio)
        radio.toggled.connect(
            lambda checked, t=tier_name: self.on_tier_selected(t) if checked else None
        )

        tier_title = QLabel(f"📦 {tier_name.title()} Package")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        tier_title.setFont(title_font)

        if tier_name == "base":
            tier_title.setStyleSheet("color: #28a745;")  # Green
        else:
            tier_title.setStyleSheet("color: #6f42c1;")  # Purple

        radio_layout.addWidget(radio)
        radio_layout.addWidget(tier_title)
        radio_layout.addStretch()
        layout.addLayout(radio_layout)

        # Description
        description = QLabel(tier_data.get("description", ""))
        description.setStyleSheet("color: #6c757d; font-size: 14px;")
        description.setWordWrap(True)
        layout.addWidget(description)

        # Size info
        total_size_mb = tier_data.get("total_size_mb", 0)
        size_label = QLabel(
            f"📏 Download Size: {total_size_mb:,} MB ({total_size_mb/1024:.1f} GB)"
        )
        size_label.setStyleSheet("font-weight: bold; color: #495057;")
        layout.addWidget(size_label)

        # Models list
        models_label = QLabel("🎯 Included Models:")
        models_label.setStyleSheet("font-weight: bold; margin-top: 10px;")
        layout.addWidget(models_label)

        for model in tier_data.get("models", []):
            model_item = QLabel(f"   • {model['description']}")
            model_item.setStyleSheet("color: #495057; margin-left: 10px;")
            layout.addWidget(model_item)

        # Smart recommendation badge based on system analysis
        if tier_name == self.recommendations["recommended_tier"]:
            badge_text = f"🧠 Recommended for your system"
            badge = QLabel(badge_text)
            badge.setStyleSheet(
                """
                background-color: #d4edda;
                color: #155724;
                border: 1px solid #c3e6cb;
                border-radius: 4px;
                padding: 8px;
                font-weight: bold;
                text-align: center;
            """
            )
            badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(badge)
        elif tier_name == "premium" and not self.recommendations["can_run_premium"]:
            badge = QLabel("⚠️ May be slow on your system")
            badge.setStyleSheet(
                """
                background-color: #fff3cd;
                color: #856404;
                border: 1px solid #ffeaa7;
                border-radius: 4px;
                padding: 8px;
                font-weight: bold;
                text-align: center;
            """
            )
            badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(badge)
        elif tier_name == "premium" and self.recommendations["can_run_premium"]:
            badge = QLabel("🚀 Your system can handle this")
            badge.setStyleSheet(
                """
                background-color: #e2e3f0;
                color: #5a5c8a;
                border: 1px solid #c8c9e0;
                border-radius: 4px;
                padding: 8px;
                font-weight: bold;
                text-align: center;
            """
            )
            badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(badge)

        layout.addStretch()
        return card

    def setup_download_section(self, layout: QVBoxLayout):
        """Set up the download progress section."""
        self.download_frame = QFrame()
        self.download_frame.setVisible(False)  # Hidden initially
        self.download_frame.setStyleSheet(
            """
            QFrame {
                background-color: #f8f9fa;
                border: 1px solid #e9ecef;
                border-radius: 8px;
                padding: 20px;
            }
        """
        )

        download_layout = QVBoxLayout(self.download_frame)

        self.download_status = QLabel("Preparing to download...")
        self.download_status.setStyleSheet("font-weight: bold; font-size: 14px;")
        download_layout.addWidget(self.download_status)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # Indeterminate progress
        download_layout.addWidget(self.progress_bar)

        self.download_log = QTextEdit()
        self.download_log.setMaximumHeight(150)
        self.download_log.setStyleSheet(
            """
            QTextEdit {
                background-color: #ffffff;
                border: 1px solid #ced4da;
                border-radius: 4px;
                font-family: monospace;
                font-size: 12px;
            }
        """
        )
        download_layout.addWidget(self.download_log)

        layout.addWidget(self.download_frame)

    def setup_action_buttons(self, layout: QVBoxLayout):
        """Set up the action buttons."""
        button_layout = QHBoxLayout()

        # Skip button
        self.skip_button = QPushButton("⏭️ Skip Download (Download Later)")
        self.skip_button.setStyleSheet(
            """
            QPushButton {
                background-color: #6c757d;
                color: white;
                border: none;
                padding: 12px 20px;
                border-radius: 6px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #5a6268;
            }
        """
        )
        self.skip_button.clicked.connect(self.skip_download)

        button_layout.addWidget(self.skip_button)
        button_layout.addStretch()

        # Download button
        self.download_button = QPushButton("📥 Download Selected Package")
        self.download_button.setStyleSheet(
            """
            QPushButton {
                background-color: #007bff;
                color: white;
                border: none;
                padding: 12px 20px;
                border-radius: 6px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0056b3;
            }
            QPushButton:disabled {
                background-color: #6c757d;
            }
        """
        )
        self.download_button.clicked.connect(self.start_download)

        button_layout.addWidget(self.download_button)

        layout.addLayout(button_layout)

    def on_tier_selected(self, tier: str):
        """Handle tier selection change."""
        self.selected_tier = tier

        # Update download button text
        tier_data = self.tier_info.get(tier, {})
        size_gb = tier_data.get("total_size_mb", 0) / 1024
        self.download_button.setText(
            f"📥 Download {tier.title()} Package ({size_gb:.1f} GB)"
        )

    def start_download(self):
        """Start downloading the selected tier."""
        self.download_frame.setVisible(True)
        self.download_button.setEnabled(False)
        self.skip_button.setText("Cancel Download")

        # Start download worker
        self.download_worker = ModelDownloadWorker(
            self.app_bundle_path, self.selected_tier
        )
        self.download_worker.progress_update.connect(self.update_download_progress)
        self.download_worker.download_complete.connect(self.download_finished)
        self.download_worker.start()

    def update_download_progress(self, message: str):
        """Update download progress display."""
        self.download_status.setText(message)
        self.download_log.append(message)

        # Auto-scroll to bottom
        cursor = self.download_log.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self.download_log.setTextCursor(cursor)

    def download_finished(self, success: bool, message: str):
        """Handle download completion."""
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(100 if success else 0)

        self.download_status.setText(message)
        self.download_log.append(message)

        if success:
            # Auto-close after 3 seconds
            QTimer.singleShot(3000, self.accept)

            # Update button
            self.download_button.setText("✅ Download Complete")
            self.download_button.setStyleSheet(
                """
                QPushButton {
                    background-color: #28a745;
                    color: white;
                    border: none;
                    padding: 12px 20px;
                    border-radius: 6px;
                    font-size: 14px;
                    font-weight: bold;
                }
            """
            )
        else:
            self.download_button.setEnabled(True)
            self.download_button.setText("🔄 Retry Download")

        self.skip_button.setText("Close")

    def skip_download(self):
        """Skip the download process."""
        if self.download_worker and self.download_worker.isRunning():
            # Cancel ongoing download
            self.download_worker.terminate()
            self.download_worker.wait()

        self.reject()


def show_model_tier_dialog(app_bundle_path: Path, parent=None) -> str:
    """
    Show the model tier selection dialog.

    Returns:
        str: Selected tier ("base", "premium", or "skip")
    """
    dialog = ModelTierSelectionDialog(app_bundle_path, parent)
    result = dialog.exec()

    if result == QDialog.DialogCode.Accepted:
        return dialog.selected_tier
    else:
        return "skip"


if __name__ == "__main__":
    # Test the dialog
    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv)

    # Mock app bundle path for testing
    test_path = Path("/tmp/test_app.app")
    test_path.mkdir(exist_ok=True)

    selected_tier = show_model_tier_dialog(test_path)
    print(f"Selected tier: {selected_tier}")

    sys.exit(0)
