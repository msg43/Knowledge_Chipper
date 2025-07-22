#!/usr/bin/env python3
"""
Simple test script to check GUI rendering on macOS
"""

import sys
import platform
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QVBoxLayout,
    QWidget,
    QLabel,
    QPushButton,
)
from PyQt6.QtCore import Qt, QTimer


class TestWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("GUI Test - Knowledge System")
        self.setGeometry(100, 100, 600, 400)

        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Create layout
        layout = QVBoxLayout(central_widget)

        # Add test content
        title_label = QLabel("Knowledge System GUI Test")
        title_label.setStyleSheet("font-size: 18px; font-weight: bold; margin: 10px;")
        layout.addWidget(title_label)

        info_label = QLabel(f"Platform: {platform.system()}\nPython: {sys.version}")
        info_label.setStyleSheet(
            "margin: 10px; padding: 10px; background-color: #f0f0f0; border: 1px solid #ccc;"
        )
        layout.addWidget(info_label)

        test_button = QPushButton("Test Button")
        test_button.setStyleSheet("padding: 10px; margin: 10px; font-size: 14px;")
        layout.addWidget(test_button)

        status_label = QLabel("GUI should be visible and properly rendered")
        status_label.setStyleSheet("color: green; margin: 10px;")
        layout.addWidget(status_label)


def main():
    # Bus error prevention - set environment variables early
    import os
    os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = "1"
    os.environ["OMP_NUM_THREADS"] = "1"
    os.environ["TOKENIZERS_PARALLELISM"] = "false"
    
    app = QApplication(sys.argv)

    # macOS-specific fixes
    if platform.system() == "Darwin":
        # Set macOS-specific attributes
        app.setAttribute(Qt.ApplicationAttribute.AA_DontShowIconsInMenus, False)

        # Force native macOS style for better rendering
        app.setStyle("macos")
        print("Applied macOS-specific GUI fixes")
    else:
        app.setStyle("Fusion")
        print("Using Fusion style for non-macOS platform")

    window = TestWindow()

    # Set proper window flags for macOS
    if platform.system() == "Darwin":
        window.setWindowFlags(window.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        # Remove the flag after a moment to allow normal window behavior
        QTimer.singleShot(
            100,
            lambda: window.setWindowFlags(
                window.windowFlags() & ~Qt.WindowType.WindowStaysOnTopHint
            ),
        )

    window.show()
    print("GUI window should now be visible")

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
