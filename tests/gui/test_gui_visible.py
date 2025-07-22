#!/usr/bin/env python3
"""
Test script to force GUI visibility on macOS
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
        self.setWindowTitle("Knowledge System GUI Test")
        self.setGeometry(100, 100, 800, 600)

        # Force window to be visible
        self.setWindowState(Qt.WindowState.WindowActive)

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

        test_button = QPushButton("Test Button - Click Me!")
        test_button.setStyleSheet("padding: 10px; margin: 10px; font-size: 14px;")
        layout.addWidget(test_button)

        status_label = QLabel("GUI should be visible and properly rendered")
        status_label.setStyleSheet("color: green; margin: 10px;")
        layout.addWidget(status_label)

        # Add a quit button
        quit_button = QPushButton("Quit")
        quit_button.clicked.connect(self.close)
        layout.addWidget(quit_button)


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

    # Force window to be visible and active
    if platform.system() == "Darwin":
        # Set window flags to force visibility
        window.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowSystemMenuHint
            | Qt.WindowType.WindowTitleHint
            | Qt.WindowType.WindowMinMaxButtonsHint
        )

        # Remove the top hint after a moment
        QTimer.singleShot(
            200,
            lambda: window.setWindowFlags(
                Qt.WindowType.Window
                | Qt.WindowType.WindowSystemMenuHint
                | Qt.WindowType.WindowTitleHint
                | Qt.WindowType.WindowMinMaxButtonsHint
            ),
        )

    window.show()
    window.raise_()  # Bring window to front
    window.activateWindow()  # Activate the window

    print("GUI window should now be visible and active")
    print("If you still don't see it, check:")
    print("1. Other workspaces/spaces")
    print("2. Behind other windows")
    print("3. Mission Control")

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
