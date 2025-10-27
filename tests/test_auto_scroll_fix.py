#!/usr/bin/env python3
"""
Test script to verify the auto-scroll fix for console output.

This script tests that:
1. When user is at bottom, new messages auto-scroll
2. When user scrolls up, new messages don't force scroll to bottom
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import (
    QApplication,
    QLabel,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from knowledge_system.gui.components.base_tab import BaseTab


class TestTab(BaseTab):
    """Simple test tab to demonstrate the auto-scroll fix."""

    def __init__(self):
        self.message_count = 0
        super().__init__()

    def _setup_ui(self):
        """Setup simple test UI."""
        layout = QVBoxLayout(self)

        # Instructions
        instructions = QLabel(
            "Test Instructions:\n"
            "1. Click 'Start Messages' to begin adding log messages\n"
            "2. Try scrolling UP in the output area while messages are being added\n"
            "3. Notice that scrolling up is now preserved - you won't be yanked back down\n"
            "4. Scroll to the bottom manually - auto-scroll will resume"
        )
        instructions.setWordWrap(True)
        layout.addWidget(instructions)

        # Control buttons
        self.start_btn = QPushButton("Start Messages")
        self.start_btn.clicked.connect(self._start_messages)
        layout.addWidget(self.start_btn)

        self.stop_btn = QPushButton("Stop Messages")
        self.stop_btn.clicked.connect(self._stop_messages)
        self.stop_btn.setEnabled(False)
        layout.addWidget(self.stop_btn)

        # Output section
        output_layout = self._create_output_section()
        layout.addLayout(output_layout)

        self.timer = None

    def _start_messages(self):
        """Start adding messages periodically."""
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.message_count = 0

        self.append_log("=== Starting message stream ===")
        self.append_log("TIP: Try scrolling UP now!")

        # Create timer to add messages every 500ms
        self.timer = QTimer()
        self.timer.timeout.connect(self._add_test_message)
        self.timer.start(500)

    def _stop_messages(self):
        """Stop adding messages."""
        if self.timer:
            self.timer.stop()
            self.timer = None

        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.append_log("=== Stopped message stream ===")

    def _add_test_message(self):
        """Add a test message."""
        self.message_count += 1
        self.append_log(
            f"Message #{self.message_count} - Current time: {self.message_count * 0.5:.1f}s"
        )

        # Stop after 100 messages
        if self.message_count >= 100:
            self._stop_messages()
            self.append_log("=== Reached 100 messages, auto-stopped ===")

    def _get_start_button_text(self):
        return "Start"

    def _start_processing(self):
        pass

    def _connect_signals(self):
        pass


def main():
    """Run the test application."""
    app = QApplication(sys.argv)

    window = QMainWindow()
    window.setWindowTitle("Auto-Scroll Fix Test")
    window.setGeometry(100, 100, 800, 600)

    test_tab = TestTab()
    window.setCentralWidget(test_tab)

    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
