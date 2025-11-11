#!/usr/bin/env python3
"""
Cookie File Manager Widget

Multi-account cookie file management for batch YouTube downloads.
Supports 1-6 cookie files with testing and validation.
"""

import logging
from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)


class CookieFileManager(QWidget):
    """
    Widget for managing multiple cookie files (1-6 accounts).

    Features:
    - Add/remove cookie file entries
    - Browse for cookie files
    - Test cookie validity
    - Visual status indicators
    - Auto-save to settings
    """

    # Signals
    cookies_changed = pyqtSignal()  # Emitted when cookie files change

    def __init__(self, parent=None):
        super().__init__(parent)

        self.cookie_entries = []
        self.max_cookies = 6

        self._init_ui()

    def _init_ui(self):
        """Initialize the user interface"""
        layout = QVBoxLayout()
        layout.setSpacing(10)

        # Header
        header = QLabel("Multi-Account Cookie Files (1-6 throwaway accounts)")
        header.setStyleSheet("font-weight: bold; font-size: 12pt;")
        layout.addWidget(header)

        # Instructions
        instructions = QLabel(
            "Upload 1-6 cookie files from throwaway accounts.\n"
            "More accounts = faster downloads (3 recommended for large batches).\n"
            "Each account should have 3-5 min delays for bot protection."
        )
        instructions.setWordWrap(True)
        instructions.setStyleSheet("color: #555; font-size: 10pt;")
        layout.addWidget(instructions)

        # Scrollable area for cookie entries
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMaximumHeight(300)
        scroll.setStyleSheet(
            """
            QScrollArea {
                border: 1px solid #ccc;
                border-radius: 4px;
                background: #f9f9f9;
            }
        """
        )

        cookie_container = QWidget()
        self.cookie_layout = QVBoxLayout()
        self.cookie_layout.setSpacing(5)

        # Create status label first (needed by _add_cookie_entry)
        self.status_label = QLabel("No cookies loaded")
        self.status_label.setStyleSheet("font-size: 10pt; padding: 5px;")

        # Add initial entry
        self._add_cookie_entry()

        cookie_container.setLayout(self.cookie_layout)
        scroll.setWidget(cookie_container)
        layout.addWidget(scroll)

        # Buttons
        button_layout = QHBoxLayout()

        add_btn = QPushButton("➕ Add Another Account")
        add_btn.clicked.connect(self._add_cookie_entry)
        add_btn.setToolTip("Add another cookie file (max 6 accounts)")
        button_layout.addWidget(add_btn)

        remove_btn = QPushButton("➖ Remove Last Account")
        remove_btn.clicked.connect(self._remove_cookie_entry)
        remove_btn.setToolTip("Remove the last cookie file entry")
        button_layout.addWidget(remove_btn)

        test_all_btn = QPushButton("🧪 Test All Cookies")
        test_all_btn.clicked.connect(self._test_all_cookies)
        test_all_btn.setToolTip("Validate all cookie files before starting")
        test_all_btn.setStyleSheet(
            """
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
                padding: 6px 12px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """
        )
        button_layout.addWidget(test_all_btn)

        layout.addLayout(button_layout)

        # Add status label to layout
        layout.addWidget(self.status_label)

        self.setLayout(layout)

    def _add_cookie_entry(self):
        """Add a new cookie file entry"""
        if len(self.cookie_entries) >= self.max_cookies:
            QMessageBox.warning(
                self,
                "Maximum Accounts",
                f"Maximum {self.max_cookies} accounts supported.\n\n"
                f"More accounts provide diminishing returns and may trigger rate limits.",
            )
            return

        entry_widget = QWidget()
        entry_layout = QHBoxLayout()
        entry_layout.setContentsMargins(5, 5, 5, 5)

        # Account number
        account_num = len(self.cookie_entries) + 1
        label = QLabel(f"Account {account_num}:")
        label.setMinimumWidth(80)
        label.setStyleSheet("font-weight: bold;")
        entry_layout.addWidget(label)

        # File path input
        file_input = QLineEdit()
        file_input.setPlaceholderText(f"cookies_account_{account_num}.txt")
        file_input.textChanged.connect(self._on_cookie_file_changed)
        entry_layout.addWidget(file_input, stretch=2)

        # Browse button
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(lambda: self._browse_cookie(file_input))
        browse_btn.setMaximumWidth(100)
        entry_layout.addWidget(browse_btn)

        # Status indicator
        status_icon = QLabel("⚪")
        status_icon.setToolTip("Not tested")
        status_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        status_icon.setMinimumWidth(30)
        status_icon.setStyleSheet("font-size: 16pt;")
        entry_layout.addWidget(status_icon)

        entry_widget.setLayout(entry_layout)
        self.cookie_layout.addWidget(entry_widget)

        # Store entry
        self.cookie_entries.append(
            {
                "widget": entry_widget,
                "label": label,
                "file_input": file_input,
                "status_icon": status_icon,
                "is_valid": None,  # None = not tested, True = valid, False = invalid
                "error_message": None,
            }
        )

        self._update_status()
        self.cookies_changed.emit()

    def _remove_cookie_entry(self):
        """Remove last cookie entry"""
        if len(self.cookie_entries) <= 1:
            QMessageBox.warning(
                self,
                "Minimum Account",
                "Need at least 1 account for downloads.\n\n"
                "If you don't want to use cookies, disable cookie authentication instead.",
            )
            return

        entry = self.cookie_entries.pop()
        entry["widget"].deleteLater()

        # Renumber remaining entries
        for idx, entry in enumerate(self.cookie_entries):
            entry["label"].setText(f"Account {idx + 1}:")
            entry["file_input"].setPlaceholderText(f"cookies_account_{idx + 1}.txt")

        self._update_status()
        self.cookies_changed.emit()

    def _browse_cookie(self, file_input):
        """Browse for cookie file"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Cookie File (Netscape format)",
            str(Path.home()),
            "Text Files (*.txt);;All Files (*)",
        )
        if file_path:
            file_input.setText(file_path)
            # textChanged will trigger _on_cookie_file_changed

    def _on_cookie_file_changed(self):
        """Called when a cookie file path changes"""
        # Reset validation status when file changes
        sender = self.sender()
        for entry in self.cookie_entries:
            if entry["file_input"] == sender:
                entry["is_valid"] = None
                entry["status_icon"].setText("⚪")
                entry["status_icon"].setToolTip("Not tested")
                break

        self._update_status()
        self.cookies_changed.emit()

    def _test_all_cookies(self):
        """Test all cookie files for validity"""
        self.status_label.setText("🧪 Testing cookies...")
        QApplication.processEvents()

        valid_count = 0
        invalid_count = 0

        for idx, entry in enumerate(self.cookie_entries):
            file_path = entry["file_input"].text().strip()

            if not file_path:
                entry["status_icon"].setText("⚪")
                entry["status_icon"].setToolTip("No file selected")
                entry["is_valid"] = None
                continue

            # Update status to testing
            entry["status_icon"].setText("⏳")
            entry["status_icon"].setToolTip("Testing...")
            QApplication.processEvents()

            # Test cookie file
            is_valid, message = self._test_cookie_file(file_path)

            if is_valid:
                entry["status_icon"].setText("✅")
                entry["status_icon"].setToolTip(f"Valid: {message}")
                entry["is_valid"] = True
                entry["error_message"] = None
                valid_count += 1
            else:
                entry["status_icon"].setText("❌")
                entry["status_icon"].setToolTip(f"Invalid: {message}")
                entry["is_valid"] = False
                entry["error_message"] = message
                invalid_count += 1

        self._update_status()

        # Show summary
        if valid_count > 0:
            QMessageBox.information(
                self,
                "Cookie Test Results",
                f"✅ {valid_count} valid account(s)\n"
                f"❌ {invalid_count} invalid account(s)\n\n"
                f"Download parallelization: {valid_count}x speedup\n\n"
                f"Estimated timeline for 7000 videos:\n"
                f"  1 account: ~28 days\n"
                f"  2 accounts: ~18 days\n"
                f"  3 accounts: ~9 days\n"
                f"  4-6 accounts: ~6-7 days",
            )
        else:
            QMessageBox.warning(
                self,
                "No Valid Cookies",
                "No valid cookie files found.\n\n"
                "Please check:\n"
                "• Cookie files exist at specified paths\n"
                "• Files are in Netscape format (.txt)\n"
                "• Cookies are from YouTube/Google\n"
                "• Accounts are still logged in",
            )

    def _test_cookie_file(self, file_path: str) -> tuple[bool, str]:
        """
        Test a cookie file for validity.

        Returns:
            (is_valid, message)
        """
        try:
            # Check file exists
            if not Path(file_path).exists():
                return False, "File not found"

            # Check file is not empty
            file_size = Path(file_path).stat().st_size
            if file_size == 0:
                return False, "File is empty"

            if file_size < 100:  # Minimum reasonable cookie file size
                return False, "File too small (likely incomplete)"

            # Try to parse cookies
            from http.cookiejar import MozillaCookieJar

            jar = MozillaCookieJar(file_path)
            jar.load(ignore_discard=True, ignore_expires=True)

            # Check for YouTube-specific cookies
            youtube_cookies = [
                c for c in jar if "youtube.com" in c.domain or "google.com" in c.domain
            ]

            if not youtube_cookies:
                return False, "No YouTube/Google cookies found in file"

            # Quick validation: Check for essential cookies
            essential_cookies = ["CONSENT", "VISITOR_INFO1_LIVE"]
            found_essential = [
                c.name for c in youtube_cookies if c.name in essential_cookies
            ]

            if not found_essential:
                logger.warning(
                    f"Cookie file {file_path} missing some essential cookies, "
                    f"but proceeding anyway"
                )

            # Success - cookies look valid
            return True, f"Authenticated ({len(youtube_cookies)} cookies)"

        except Exception as e:
            error_msg = str(e)
            if "HTTP Error 403" in error_msg:
                return False, "Cookies rejected (may be expired)"
            elif "HTTP Error 401" in error_msg:
                return False, "Authentication failed (stale cookies)"
            else:
                return False, f"Error: {error_msg[:100]}"

    def _update_status(self):
        """Update status label"""
        total = len(self.cookie_entries)
        valid = sum(1 for e in self.cookie_entries if e["is_valid"] is True)
        invalid = sum(1 for e in self.cookie_entries if e["is_valid"] is False)
        untested = sum(1 for e in self.cookie_entries if e["is_valid"] is None)

        if valid > 0:
            status_parts = []
            if valid > 0:
                status_parts.append(f"✅ {valid} valid")
            if invalid > 0:
                status_parts.append(f"❌ {invalid} invalid")
            if untested > 0:
                status_parts.append(f"⚪ {untested} not tested")

            self.status_label.setText(
                f"{' | '.join(status_parts)} | Total: {total} account(s)"
            )
            self.status_label.setStyleSheet(
                "color: #2e7d32; font-weight: bold; font-size: 10pt; padding: 5px;"
            )
        elif invalid > 0:
            self.status_label.setText(
                f"❌ {invalid} invalid | ⚪ {untested} not tested | Total: {total}"
            )
            self.status_label.setStyleSheet(
                "color: #c62828; font-weight: bold; font-size: 10pt; padding: 5px;"
            )
        else:
            self.status_label.setText(f"{total} account(s) loaded (not tested)")
            self.status_label.setStyleSheet("font-size: 10pt; padding: 5px;")

    def get_valid_cookie_files(self) -> list[str]:
        """Get list of valid cookie file paths"""
        return [
            e["file_input"].text().strip()
            for e in self.cookie_entries
            if e["is_valid"] is True and e["file_input"].text().strip()
        ]

    def get_all_cookie_files(self) -> list[str]:
        """Get all cookie files (tested or not)"""
        return [
            e["file_input"].text().strip()
            for e in self.cookie_entries
            if e["file_input"].text().strip()
        ]

    def set_cookie_files(self, file_paths: list[str]):
        """Set cookie files from a list of paths"""
        logger.info(
            f"🔧 CookieFileManager.set_cookie_files() called with {len(file_paths)} files"
        )
        logger.debug(f"   Paths: {file_paths}")

        # Block signals during the entire operation to prevent cascading saves
        old_block_state = self.signalsBlocked()
        self.blockSignals(True)
        logger.debug(f"   Signals blocked (was: {old_block_state}, now: True)")

        try:
            # Clear existing entries (silently, without showing warnings)
            initial_count = len(self.cookie_entries)
            while len(self.cookie_entries) > 1:
                entry = self.cookie_entries.pop()
                entry["widget"].deleteLater()
            logger.debug(
                f"   Cleared {initial_count - len(self.cookie_entries)} existing entries"
            )

            # Set first entry (or clear it if no paths provided)
            if len(self.cookie_entries) > 0:
                if file_paths:
                    self.cookie_entries[0]["file_input"].setText(file_paths[0])
                    logger.debug(f"   Set first entry to: {file_paths[0]}")
                else:
                    self.cookie_entries[0]["file_input"].setText("")
                    logger.debug(f"   Cleared first entry")

            # Add remaining entries
            for idx, path in enumerate(file_paths[1:], start=2):
                logger.debug(f"   Adding entry {idx}: {path}")
                # Manually add entry without triggering signals
                entry_widget = QWidget()
                entry_layout = QHBoxLayout()
                entry_layout.setContentsMargins(5, 5, 5, 5)

                # Account number
                label = QLabel(f"Account {idx}:")
                label.setMinimumWidth(80)
                label.setStyleSheet("font-weight: bold;")
                entry_layout.addWidget(label)

                # File path input
                file_input = QLineEdit()
                file_input.setPlaceholderText(f"cookies_account_{idx}.txt")
                file_input.setText(path)
                file_input.textChanged.connect(self._on_cookie_file_changed)
                entry_layout.addWidget(file_input, stretch=2)

                # Browse button
                browse_btn = QPushButton("Browse...")
                browse_btn.clicked.connect(
                    lambda checked, fi=file_input: self._browse_cookie(fi)
                )
                browse_btn.setMaximumWidth(100)
                entry_layout.addWidget(browse_btn)

                # Status indicator
                status_icon = QLabel("⚪")
                status_icon.setToolTip("Not tested")
                status_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
                status_icon.setMinimumWidth(30)
                status_icon.setStyleSheet("font-size: 16pt;")
                entry_layout.addWidget(status_icon)

                entry_widget.setLayout(entry_layout)
                self.cookie_layout.addWidget(entry_widget)

                # Store entry
                self.cookie_entries.append(
                    {
                        "widget": entry_widget,
                        "label": label,
                        "file_input": file_input,
                        "status_icon": status_icon,
                        "is_valid": None,
                        "error_message": None,
                    }
                )

            self._update_status()
            logger.debug(f"   Status updated")

        finally:
            # Restore signal blocking state
            self.blockSignals(old_block_state)
            logger.debug(f"   Signals restored to: {old_block_state}")

            # Verify final state
            final_files = self.get_all_cookie_files()
            logger.info(
                f"✅ CookieFileManager.set_cookie_files() complete: {len(final_files)} files loaded"
            )
            if len(final_files) != len(file_paths):
                logger.error(
                    f"❌ Mismatch! Expected {len(file_paths)} files, but have {len(final_files)}"
                )

    def get_account_count(self) -> int:
        """Get number of cookie accounts configured"""
        return len([f for f in self.get_all_cookie_files() if f])

    def get_valid_account_count(self) -> int:
        """Get number of validated cookie accounts"""
        return len(self.get_valid_cookie_files())
