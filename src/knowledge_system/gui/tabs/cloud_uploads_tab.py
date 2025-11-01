"""
Cloud Uploads Tab

OAuth-based upload system for uploading claims and associated data
directly to Skipthepodcast.com via authenticated user uploads.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from getreceipts_uploader import GetReceiptsUploader

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ...logger import get_logger
from ...services.claims_upload_service import ClaimsUploadService, ClaimUploadData
from ..components.base_tab import BaseTab

# Note: OAuth implementation now uses dynamic import from knowledge_chipper_oauth/


logger = get_logger(__name__)


class DatabaseUploadWorker(QThread):
    """Worker thread for uploading claims data via GetReceipts OAuth."""

    progress = pyqtSignal(int, int, str)  # current, total, message
    finished = pyqtSignal(int, int)  # success_count, total_count
    error = pyqtSignal(str)  # error_message

    def __init__(
        self, claims_data: list[ClaimUploadData], uploader: GetReceiptsUploader
    ):
        super().__init__()
        self.claims_data = claims_data
        self.uploader = uploader
        self.should_stop = False

    def run(self) -> None:
        """Upload claims data via GetReceipts OAuth."""
        if not self.uploader:
            self.error.emit("GetReceipts uploader not available")
            self.finished.emit(0, len(self.claims_data))
            return

        success_count = 0
        total_count = len(self.claims_data)

        try:
            # Convert claims data to GetReceipts format and upload
            session_data = self._convert_to_getreceipts_format()

            self.progress.emit(
                0, total_count, "🔄 Starting upload to Skipthepodcast.com..."
            )

            # Upload all data at once using the GetReceipts uploader
            upload_results = self.uploader.upload_session_data(session_data)

            # Count successes based on upload results
            success_count = sum(
                len(data) if data else 0 for data in upload_results.values()
            )

            self.progress.emit(
                total_count,
                total_count,
                f"✅ Upload completed! {success_count} records uploaded",
            )

        except Exception as e:
            logger.error(f"Error uploading to GetReceipts: {e}")
            self.error.emit(f"Upload failed: {str(e)}")

        self.finished.emit(success_count, total_count)

    def _convert_to_getreceipts_format(self) -> dict[str, Any]:
        """Convert Knowledge_Chipper claims data to GetReceipts format."""
        session_data = {
            "episodes": [],
            "claims": [],
            "evidence_spans": [],
            "people": [],
            "jargon": [],
            "concepts": [],
            "relations": [],
        }

        # Track unique episodes
        seen_episodes = set()

        for claim in self.claims_data:
            # Add episode data (if not already added)
            if claim.episode_data and claim.source_id not in seen_episodes:
                session_data["episodes"].append(claim.episode_data)
                seen_episodes.add(claim.source_id)

            # Add claim data
            claim_dict = {
                "claim_id": claim.claim_id,
                "canonical": claim.canonical,
                "source_id": claim.source_id,
                "claim_type": claim.claim_type,
                "tier": claim.tier,
                "scores_json": claim.scores_json,
                "first_mention_ts": claim.first_mention_ts,
                "inserted_at": claim.inserted_at,
            }
            session_data["claims"].append(claim_dict)

            # Add associated data
            session_data["evidence_spans"].extend(claim.evidence_spans)
            session_data["people"].extend(claim.people)
            session_data["jargon"].extend(claim.jargon)
            session_data["concepts"].extend(claim.concepts)
            session_data["relations"].extend(claim.relations)

        return session_data

    def stop(self) -> None:
        """Stop the upload process."""
        self.should_stop = True


class CloudUploadsTab(BaseTab):
    """Tab for uploading claims data to Skipthepodcast.com via OAuth."""

    def __init__(self, parent=None) -> None:
        self.upload_worker: DatabaseUploadWorker | None = None
        self.tab_name = "Cloud Uploads"
        self.uploader: GetReceiptsUploader | None = None
        self.authenticated_user: dict[str, Any] | None = None
        self.claims_service: ClaimsUploadService | None = None
        self.claims_data: list[ClaimUploadData] = []

        # Initialize OAuth-related attributes
        self._oauth_auth = None
        self._auth_thread = None
        self._check_timer = None
        self._progress_dialog = None

        # Initialize UI attributes to None before calling super().__init__
        self.claims_table = None
        self.upload_btn = None
        self.status_label = None
        self.progress_bar = None
        self.upload_log = None

        super().__init__(parent)

    def _setup_ui(self) -> None:
        """Setup the UI for database uploads."""
        layout = QVBoxLayout(self)

        # Main splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter)

        # Left panel: Authentication + Database selection
        left_widget = self._create_left_panel()
        splitter.addWidget(left_widget)

        # Right panel: Claims list + Upload controls
        right_widget = self._create_right_panel()
        splitter.addWidget(right_widget)

        splitter.setSizes([400, 800])

        # Load default database
        self._load_default_database()

    def _connect_signals(self) -> None:
        """Connect internal signals. Override to prevent base class errors."""
        # No additional signal connections needed beyond what's in the UI setup

    def _create_left_panel(self) -> QWidget:
        """Create left panel with auth and database controls."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Authentication section
        auth_group = self._create_auth_section()
        layout.addWidget(auth_group)

        # Database selection section
        db_group = self._create_database_section()
        layout.addWidget(db_group)

        # Database stats section
        stats_group = self._create_stats_section()
        layout.addWidget(stats_group)

        layout.addStretch()
        return widget

    def _create_auth_section(self) -> QGroupBox:
        """Create authentication section."""
        group = QGroupBox("Skipthepodcast Authentication")
        layout = QVBoxLayout(group)

        # Auth status
        self.auth_status_label = QLabel("Not authenticated")
        self.auth_status_label.setStyleSheet("color: #666; font-style: italic;")
        layout.addWidget(self.auth_status_label)

        # Info text about OAuth flow
        info_text = QLabel(
            "🔐 Sign in via Skipthepodcast.com to upload your claims data.\n"
            "This will open your browser for secure authentication."
        )
        info_text.setWordWrap(True)
        info_text.setStyleSheet(
            "color: #666; font-style: italic; margin: 8px; padding: 8px; "
            "background-color: #f5f5f5; border-radius: 4px;"
        )
        layout.addWidget(info_text)

        # OAuth authentication button
        self.oauth_btn = QPushButton("🌐 Sign In via Skipthepodcast.com")
        self.oauth_btn.setStyleSheet(
            "QPushButton { padding: 10px; font-size: 14px; background-color: #2196F3; color: white; border: none; border-radius: 6px; }"
            "QPushButton:hover { background-color: #1976D2; }"
            "QPushButton:disabled { background-color: #cccccc; }"
        )
        self.oauth_btn.clicked.connect(self._sign_in_with_oauth)
        layout.addWidget(self.oauth_btn)

        # Sign out button
        self.logout_btn = QPushButton("Sign Out")
        self.logout_btn.setEnabled(False)
        self.logout_btn.clicked.connect(self._sign_out)
        layout.addWidget(self.logout_btn)

        # Legacy email/password section removed - OAuth is the primary auth method

        self._refresh_auth_ui()
        return group

    def _create_legacy_auth_section(self, parent_layout: QVBoxLayout) -> None:
        """Create collapsible legacy email/password auth section."""
        # Expandable section for legacy auth
        self.legacy_auth_toggle = QPushButton(
            "▶ Advanced: Direct Email/Password Sign-In"
        )
        self.legacy_auth_toggle.setStyleSheet(
            "text-align: left; border: none; padding: 5px;"
        )
        self.legacy_auth_toggle.clicked.connect(self._toggle_legacy_auth)
        parent_layout.addWidget(self.legacy_auth_toggle)

        # Legacy auth widget (initially hidden)
        self.legacy_auth_widget = QWidget()
        self.legacy_auth_widget.setVisible(False)
        legacy_layout = QVBoxLayout(self.legacy_auth_widget)

        # Email and password
        auth_layout = QHBoxLayout()
        self.email_edit = QLineEdit()
        self.email_edit.setPlaceholderText("Email")
        self.password_edit = QLineEdit()
        self.password_edit.setPlaceholderText("Password")
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)

        auth_layout.addWidget(self.email_edit)
        auth_layout.addWidget(self.password_edit)
        legacy_layout.addLayout(auth_layout)

        # Legacy auth buttons
        button_layout = QHBoxLayout()
        self.login_btn = QPushButton("Sign In")
        self.signup_btn = QPushButton("Sign Up")

        button_layout.addWidget(self.login_btn)
        button_layout.addWidget(self.signup_btn)
        legacy_layout.addLayout(button_layout)

        # Connect legacy auth buttons
        self.login_btn.clicked.connect(self._sign_in)
        self.signup_btn.clicked.connect(self._sign_up)

        parent_layout.addWidget(self.legacy_auth_widget)

    def _toggle_legacy_auth(self) -> None:
        """Toggle visibility of legacy auth section."""
        is_visible = self.legacy_auth_widget.isVisible()
        self.legacy_auth_widget.setVisible(not is_visible)

        if is_visible:
            self.legacy_auth_toggle.setText("▶ Advanced: Direct Email/Password Sign-In")
        else:
            self.legacy_auth_toggle.setText("▼ Advanced: Direct Email/Password Sign-In")

    def _create_database_section(self) -> QGroupBox:
        """Create database selection section."""
        group = QGroupBox("Database Selection")
        layout = QVBoxLayout(group)

        # Database file selection
        file_layout = QHBoxLayout()
        self.db_path_edit = QLineEdit()
        self.db_path_edit.setPlaceholderText("Select SQLite database file...")
        self.db_path_edit.setReadOnly(True)

        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse_database)

        file_layout.addWidget(self.db_path_edit)
        file_layout.addWidget(browse_btn)
        layout.addLayout(file_layout)

        # Scan button
        self.scan_btn = QPushButton("Load Claims from Database")
        self.scan_btn.clicked.connect(self._load_claims)
        self.scan_btn.setEnabled(False)
        layout.addWidget(self.scan_btn)

        return group

    def _create_stats_section(self) -> QGroupBox:
        """Create database statistics section."""
        group = QGroupBox("Database Statistics")
        layout = QVBoxLayout(group)

        self.stats_label = QLabel("No database loaded")
        self.stats_label.setWordWrap(True)
        layout.addWidget(self.stats_label)

        return group

    def _create_right_panel(self) -> QWidget:
        """Create right panel with claims list and upload controls."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Claims list section
        claims_group = self._create_claims_section()
        layout.addWidget(claims_group)

        # Upload controls section
        upload_group = self._create_upload_section()
        layout.addWidget(upload_group)

        return widget

    def _create_claims_section(self) -> QGroupBox:
        """Create claims list section."""
        group = QGroupBox("Claims Ready for Upload")
        layout = QVBoxLayout(group)

        # Info label removed as requested

        # Claims table
        self.claims_table = QTableWidget()
        self.claims_table.setColumnCount(6)
        self.claims_table.setHorizontalHeaderLabels(
            ["Select", "Claim Text", "Type", "Tier", "Episode", "Inserted"]
        )

        # Configure table
        header = self.claims_table.horizontalHeader()
        header.setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )  # Select column
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)  # Claim text
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)  # Type
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)  # Tier
        header.setSectionResizeMode(
            4, QHeaderView.ResizeMode.ResizeToContents
        )  # Episode
        header.setSectionResizeMode(
            5, QHeaderView.ResizeMode.ResizeToContents
        )  # Inserted

        self.claims_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.claims_table.setAlternatingRowColors(True)
        layout.addWidget(self.claims_table)

        # Selection controls
        selection_layout = QHBoxLayout()
        select_all_btn = QPushButton("Select All")
        select_none_btn = QPushButton("Select None")
        select_all_btn.clicked.connect(self._select_all_claims)
        select_none_btn.clicked.connect(self._select_no_claims)

        selection_layout.addWidget(select_all_btn)
        selection_layout.addWidget(select_none_btn)
        selection_layout.addStretch()
        layout.addLayout(selection_layout)

        return group

    def _create_upload_section(self) -> QGroupBox:
        """Create upload controls section."""
        group = QGroupBox("Upload to Supabase")
        layout = QVBoxLayout(group)

        # Upload button and status
        upload_layout = QHBoxLayout()
        self.upload_btn = QPushButton("Upload Selected Claims")
        self.upload_btn.clicked.connect(self._start_upload)
        self.upload_btn.setEnabled(False)

        self.stop_btn = QPushButton("Stop Upload")
        self.stop_btn.clicked.connect(self._stop_upload)
        self.stop_btn.setEnabled(False)

        upload_layout.addWidget(self.upload_btn)
        upload_layout.addWidget(self.stop_btn)
        upload_layout.addStretch()
        layout.addLayout(upload_layout)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # Status label
        self.status_label = QLabel("Ready")
        layout.addWidget(self.status_label)

        # Upload log
        log_label = QLabel("Upload Log:")
        layout.addWidget(log_label)

        self.upload_log = QTextEdit()
        self.upload_log.setMaximumHeight(150)
        self.upload_log.setReadOnly(True)
        layout.addWidget(self.upload_log)

        return group

    def _load_default_database(self) -> None:
        """Load the default knowledge_system.db file."""
        try:
            # Try to find the default database
            default_path = Path.cwd() / "knowledge_system.db"
            if default_path.exists():
                if hasattr(self, "db_path_edit") and self.db_path_edit:
                    self.db_path_edit.setText(str(default_path))
                self._setup_claims_service(default_path)
                if hasattr(self, "scan_btn") and self.scan_btn:
                    self.scan_btn.setEnabled(True)
                self._update_database_stats()
            else:
                if hasattr(self, "status_label") and self.status_label:
                    self.status_label.setText(
                        "Default database not found. Please select a database file."
                    )
        except Exception as e:
            logger.error(f"Error loading default database: {e}")
            if hasattr(self, "status_label") and self.status_label:
                self.status_label.setText("Error loading default database")

    def _browse_database(self) -> None:
        """Browse for SQLite database file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select SQLite Database",
            str(Path.cwd()),
            "SQLite Database (*.db *.sqlite *.sqlite3);;All Files (*)",
        )

        if file_path:
            db_path = Path(file_path)

            # Show warning if not the default database
            if db_path.name != "knowledge_system.db":
                reply = QMessageBox.question(
                    self,
                    "Non-Standard Database",
                    f"You selected '{db_path.name}' instead of the standard 'knowledge_system.db'.\n\n"
                    "This may cause issues if the database doesn't have the expected schema or data.\n\n"
                    "Are you sure you want to continue?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )

                if reply == QMessageBox.StandardButton.No:
                    return

            self.db_path_edit.setText(str(db_path))
            self._setup_claims_service(db_path)
            self.scan_btn.setEnabled(True)
            self._update_database_stats()

    def _setup_claims_service(self, db_path: Path) -> None:
        """Setup the claims service with the selected database."""
        try:
            self.claims_service = ClaimsUploadService(db_path)

            # Validate database
            is_valid, message = self.claims_service.is_database_valid()
            if not is_valid:
                logger.warning(f"Invalid database: {message}")
                if hasattr(self, "scan_btn") and self.scan_btn:
                    self.scan_btn.setEnabled(False)
                return

            if hasattr(self, "status_label") and self.status_label:
                self.status_label.setText(f"Database loaded: {db_path.name}")

        except Exception as e:
            logger.error(f"Error setting up claims service: {e}")
            if hasattr(self, "scan_btn") and self.scan_btn:
                self.scan_btn.setEnabled(False)

    def _update_database_stats(self) -> None:
        """Update database statistics display."""
        if not self.claims_service:
            return

        try:
            _stats = self.claims_service.get_database_stats()
            stats_text = """Total Claims: {stats.get('total_claims', 0)}
Unuploaded: {stats.get('unuploaded_claims', 0)}
Uploaded: {stats.get('uploaded_claims', 0)}
Episodes: {stats.get('total_episodes', 0)}"""

            self.stats_label.setText(stats_text)

        except Exception as e:
            logger.error(f"Error updating database stats: {e}")

    def _load_claims(self) -> None:
        """Load claims from the database."""
        if not self.claims_service:
            return

        try:
            self.claims_data = self.claims_service.get_unuploaded_claims()
            self._populate_claims_table()
            self._update_upload_button_state()

            if self.claims_data:
                self.status_label.setText(
                    f"Loaded {len(self.claims_data)} unuploaded claims"
                )
            else:
                self.status_label.setText("No unuploaded claims found")

        except Exception as e:
            logger.error(f"Error loading claims: {e}")
            QMessageBox.critical(self, "Error", f"Error loading claims: {str(e)}")

    def _populate_claims_table(self) -> None:
        """Populate the claims table with data."""
        self.claims_table.setRowCount(len(self.claims_data))

        for row, claim in enumerate(self.claims_data):
            # Checkbox for selection (all selected by default)
            checkbox = QCheckBox()
            checkbox.setChecked(True)
            checkbox.stateChanged.connect(self._update_upload_button_state)
            self.claims_table.setCellWidget(row, 0, checkbox)

            # Claim text (truncated)
            claim_text = (
                claim.canonical[:100] + "..."
                if len(claim.canonical) > 100
                else claim.canonical
            )
            self.claims_table.setItem(row, 1, QTableWidgetItem(claim_text))

            # Type
            self.claims_table.setItem(row, 2, QTableWidgetItem(claim.claim_type or ""))

            # Tier
            tier_item = QTableWidgetItem(claim.tier or "")
            if claim.tier == "A":
                tier_item.setBackground(Qt.GlobalColor.green)
            elif claim.tier == "B":
                tier_item.setBackground(Qt.GlobalColor.yellow)
            elif claim.tier == "C":
                tier_item.setBackground(Qt.GlobalColor.red)
            self.claims_table.setItem(row, 3, tier_item)

            # Episode
            episode_title = ""
            if claim.episode_data:
                episode_title = claim.episode_data.get("title", "")[:30]
                if len(episode_title) > 30:
                    episode_title += "..."
            self.claims_table.setItem(row, 4, QTableWidgetItem(episode_title))

            # Inserted date
            inserted_date = claim.inserted_at[:10] if claim.inserted_at else ""
            self.claims_table.setItem(row, 5, QTableWidgetItem(inserted_date))

    def _select_all_claims(self) -> None:
        """Select all claims."""
        for row in range(self.claims_table.rowCount()):
            checkbox = self.claims_table.cellWidget(row, 0)
            if checkbox:
                checkbox.setChecked(True)

    def _select_no_claims(self) -> None:
        """Deselect all claims."""
        for row in range(self.claims_table.rowCount()):
            checkbox = self.claims_table.cellWidget(row, 0)
            if checkbox:
                checkbox.setChecked(False)

    def _get_selected_claims(self) -> list[ClaimUploadData]:
        """Get list of selected claims."""
        if not self.claims_table:
            return []

        selected = []
        for row in range(self.claims_table.rowCount()):
            checkbox = self.claims_table.cellWidget(row, 0)
            if checkbox and checkbox.isChecked():
                selected.append(self.claims_data[row])
        return selected

    def _update_upload_button_state(self) -> None:
        """Update upload button enabled state based on selection and auth."""
        # Check if UI elements exist before accessing them
        if not self.claims_table or not self.upload_btn:
            return

        selected_claims = self._get_selected_claims()
        is_authenticated = (
            self.uploader is not None and self.authenticated_user is not None
        )

        self.upload_btn.setEnabled(
            len(selected_claims) > 0
            and is_authenticated
            and not (self.upload_worker and self.upload_worker.isRunning())
        )

    def _start_upload(self) -> None:
        """Start uploading selected claims via GetReceipts."""
        selected_claims = self._get_selected_claims()
        if not selected_claims:
            QMessageBox.information(
                self, "No Selection", "Please select claims to upload."
            )
            return

        if not self.uploader or not self.authenticated_user:
            QMessageBox.warning(
                self, "Not Authenticated", "Please sign in to Skipthepodcast first."
            )
            return

        # Start upload worker
        self.upload_worker = DatabaseUploadWorker(selected_claims, self.uploader)
        self.upload_worker.progress.connect(self._on_upload_progress)
        self.upload_worker.finished.connect(self._on_upload_finished)
        self.upload_worker.error.connect(self._on_upload_error)

        self.upload_worker.start()

        # Update UI
        self.upload_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.progress_bar.setVisible(True)
        self.progress_bar.setMaximum(len(selected_claims))
        self.progress_bar.setValue(0)

        self.upload_log.clear()
        self.upload_log.append(f"Starting upload of {len(selected_claims)} claims...")
        self.status_label.setText("Uploading...")

    def _stop_upload(self) -> None:
        """Stop the current upload."""
        if self.upload_worker:
            self.upload_worker.stop()
            self.stop_btn.setEnabled(False)

    def _on_upload_progress(self, current: int, total: int, message: str) -> None:
        """Handle upload progress updates."""
        self.progress_bar.setValue(current)

        # Check if we should auto-scroll BEFORE appending
        scrollbar = self.upload_log.verticalScrollBar()
        should_scroll = scrollbar and scrollbar.value() >= scrollbar.maximum() - 10

        self.upload_log.append(f"[{current}/{total}] {message}")

        # Only auto-scroll if user was already at the bottom
        if should_scroll and scrollbar:
            scrollbar.setValue(scrollbar.maximum())

    def _on_upload_finished(self, success_count: int, total_count: int) -> None:
        """Handle upload completion."""
        self.progress_bar.setVisible(False)
        self.upload_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)

        self.upload_log.append(
            f"\n✅ Upload completed: {success_count}/{total_count} claims uploaded successfully"
        )

        if success_count > 0:
            # Mark successful claims as uploaded
            if self.claims_service:
                selected_claims = self._get_selected_claims()
                successful_ids = [
                    (claim.source_id, claim.claim_id)
                    for claim in selected_claims[:success_count]
                ]
                self.claims_service.mark_claims_uploaded(successful_ids)

            # Reload claims to update the list
            self._load_claims()
            self._update_database_stats()

        self.status_label.setText(
            f"Upload completed: {success_count}/{total_count} successful"
        )

        if success_count == total_count:
            QMessageBox.information(
                self,
                "Upload Complete",
                f"Successfully uploaded {success_count} claims!",
            )
        else:
            QMessageBox.warning(
                self,
                "Upload Partially Complete",
                f"Uploaded {success_count} out of {total_count} claims. Check the log for details.",
            )

    def _on_upload_error(self, error_message: str) -> None:
        """Handle upload errors."""
        self.progress_bar.setVisible(False)
        self.upload_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)

        self.upload_log.append(f"❌ Upload error: {error_message}")
        self.status_label.setText(f"Upload error: {error_message}")

        QMessageBox.critical(self, "Upload Error", f"Upload failed: {error_message}")

    # Authentication methods
    def _refresh_auth_ui(self) -> None:
        """Refresh authentication UI state."""
        is_authenticated = (
            self.uploader is not None and self.authenticated_user is not None
        )

        # Update OAuth button
        self.oauth_btn.setEnabled(not is_authenticated)

        # Update legacy auth buttons (if they exist)
        if hasattr(self, "login_btn"):
            self.login_btn.setEnabled(not is_authenticated)

        # Update logout button
        self.logout_btn.setEnabled(is_authenticated)

        if is_authenticated and self.authenticated_user:
            email = self.authenticated_user.get("email", "Unknown")
            name = self.authenticated_user.get("name", email)
            self.auth_status_label.setText(f"✅ Signed in as: {name}")
            self.auth_status_label.setStyleSheet("color: #4CAF50;")
            self.oauth_btn.setText("✅ Signed In")
        else:
            self.auth_status_label.setText("❌ Not authenticated")
            self.auth_status_label.setStyleSheet("color: #F44336;")
            self.oauth_btn.setText("🌐 Sign In via Skipthepodcast.com")

        self._update_upload_button_state()

    def _sign_in_with_oauth(self) -> None:
        """Sign in using GetReceipts OAuth flow."""
        # Store reference for cancellation
        self._oauth_auth = None

        try:
            # Initialize GetReceipts configuration using the new OAuth package
            import os
            import sys

            oauth_package_path = os.path.join(
                os.path.dirname(
                    os.path.dirname(
                        os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
                    )
                ),
                "knowledge_chipper_oauth",
            )
            if oauth_package_path not in sys.path:
                sys.path.append(oauth_package_path)

            # Check if the OAuth module files exist before importing
            config_path = os.path.join(oauth_package_path, "getreceipts_config.py")
            uploader_path = os.path.join(oauth_package_path, "getreceipts_uploader.py")

            if not os.path.exists(config_path):
                raise ImportError(
                    f"OAuth authentication is not yet available. Missing config module at {config_path}"
                )
            if not os.path.exists(uploader_path):
                raise ImportError(
                    f"OAuth authentication is not yet available. Missing uploader module at {uploader_path}"
                )

            from getreceipts_config import get_config, set_production  # type: ignore
            from getreceipts_uploader import GetReceiptsUploader  # type: ignore

            set_production()  # Ensure we're using production URLs for OAuth
            config = get_config()
            self.uploader = GetReceiptsUploader(
                supabase_url=config["supabase_url"],
                supabase_anon_key=config["supabase_anon_key"],
                base_url=config["base_url"],
            )

            # Store auth reference for potential cancellation
            self._oauth_auth = self.uploader.auth

            # Show progress dialog with proper cancellation handling
            from PyQt6.QtCore import Qt, QTimer
            from PyQt6.QtWidgets import QProgressDialog

            progress = QProgressDialog(
                "Waiting for authentication...", "Cancel", 0, 0, self
            )
            progress.setWindowTitle("Skipthepodcast Authentication")
            progress.setWindowModality(Qt.WindowModality.WindowModal)
            progress.setAutoClose(False)  # Manual control
            progress.setAutoReset(False)  # Manual control

            # Handle cancellation
            def on_cancelled():
                try:
                    logger.info("OAuth authentication cancelled by user")

                    # Stop the timer first
                    if hasattr(self, "_check_timer") and self._check_timer:
                        self._check_timer.stop()

                    # Cancel OAuth authentication
                    if self._oauth_auth and hasattr(
                        self._oauth_auth, "cancel_authentication"
                    ):
                        self._oauth_auth.cancel_authentication()

                    # Terminate authentication thread if running
                    if (
                        hasattr(self, "_auth_thread")
                        and self._auth_thread
                        and self._auth_thread.isRunning()
                    ):
                        self._auth_thread.terminate()
                        self._auth_thread.wait(
                            1000
                        )  # Wait up to 1 second for termination

                    # Clear authentication state
                    self.uploader = None
                    self.authenticated_user = None
                    self._oauth_auth = None

                    # Refresh UI
                    self._refresh_auth_ui()

                except Exception as e:
                    logger.warning(f"Error during OAuth cancellation: {e}")
                finally:
                    try:
                        if "progress" in locals() and progress:
                            progress.close()
                    except Exception as e:
                        logger.warning(f"Error closing progress dialog: {e}")

            progress.canceled.connect(on_cancelled)
            progress.show()

            # Update progress text to show steps
            progress.setLabelText(
                "🌐 Opening Skipthepodcast.com in your browser...\n\n"
                "1. Sign in or create account on Skipthepodcast.com\n"
                "2. Authorize Knowledge_Chipper access\n"
                "3. Browser should redirect back automatically\n\n"
                "⚠️ If browser stays on dashboard after login:\n"
                "   • Look for 'Return to Knowledge Chipper' link\n"
                "   • Or check the console for manual instructions\n\n"
                "Waiting for authentication...\n\n"
                "Click Cancel to abort the authentication process."
            )

            # Create a timer to periodically check if dialog was cancelled
            check_timer = QTimer()
            auth_completed = False
            auth_result = None
            auth_error = None

            def check_progress():
                try:
                    if progress.wasCanceled():
                        check_timer.stop()
                        logger.info("OAuth progress dialog was cancelled")

                        # Cleanup and terminate authentication
                        if self._oauth_auth and hasattr(
                            self._oauth_auth, "cancel_authentication"
                        ):
                            try:
                                self._oauth_auth.cancel_authentication()
                            except Exception as e:
                                logger.warning(f"Error canceling OAuth: {e}")

                        # Terminate thread if still running
                        if (
                            hasattr(self, "_auth_thread")
                            and self._auth_thread
                            and self._auth_thread.isRunning()
                        ):
                            self._auth_thread.terminate()
                            self._auth_thread.wait(1000)

                        # Clear references
                        self._auth_thread = None
                        self._check_timer = None
                        self._progress_dialog = None

                        return

                    # Check if authentication completed (this will be set by the thread)
                    if auth_completed:
                        check_timer.stop()

                        # Close progress dialog
                        try:
                            progress.close()
                        except Exception as e:
                            logger.warning(f"Error closing progress dialog: {e}")

                        # Clean up thread
                        if hasattr(self, "_auth_thread") and self._auth_thread:
                            if self._auth_thread.isRunning():
                                self._auth_thread.wait(1000)
                            self._auth_thread = None

                        # Clear references
                        self._check_timer = None
                        self._progress_dialog = None

                        if auth_error:
                            # Handle error in main thread
                            try:
                                self._handle_oauth_error(auth_error)
                            except Exception as e:
                                logger.error(f"Error handling OAuth error: {e}")
                        elif auth_result:
                            # Handle success in main thread
                            try:
                                self._handle_oauth_success(auth_result)
                            except Exception as e:
                                logger.error(f"Error handling OAuth success: {e}")
                except Exception as e:
                    logger.error(f"Error in OAuth progress check: {e}")
                    try:
                        check_timer.stop()
                        progress.close()
                    except Exception:
                        pass

            check_timer.timeout.connect(check_progress)
            check_timer.start(500)  # Check every 500ms

            # Start authentication in a separate thread to avoid blocking
            from PyQt6.QtCore import QThread

            class AuthThread(QThread):
                def __init__(self, parent, uploader):
                    super().__init__(parent)
                    self.uploader = uploader

                def run(self):
                    nonlocal auth_completed, auth_result, auth_error
                    try:
                        auth_result = self.uploader.authenticate()
                    except Exception as e:
                        auth_error = e
                    finally:
                        auth_completed = True

            auth_thread = AuthThread(self, self.uploader)

            # Store references to prevent garbage collection
            self._auth_thread = auth_thread
            self._check_timer = check_timer
            self._progress_dialog = progress

            auth_thread.start()

            # Return immediately - results will be handled by the timer
            return

        except ImportError as e:
            # Handle missing OAuth dependencies with specific messaging
            error_msg = str(e)
            if "OAuth authentication is not yet available" in error_msg:
                self._handle_oauth_error(e)
            else:
                # Handle other import errors
                self._handle_oauth_error(
                    ImportError(
                        f"OAuth authentication is not yet available: {error_msg}"
                    )
                )
        except Exception as e:
            if "progress" in locals():
                progress.close()
            self._handle_oauth_error(e)

    def _handle_oauth_success(self, auth_result):
        """Handle successful OAuth authentication."""
        try:
            # Store authentication result
            self.authenticated_user = auth_result["user_info"]

            self._refresh_auth_ui()
            QMessageBox.information(
                self,
                "Authentication Successful",
                f"Successfully signed in as {self.authenticated_user['name']}!\n\n"
                "You can now upload your claims data to Skipthepodcast.com.",
            )
        except Exception as e:
            logger.error(f"Error handling OAuth success: {e}")
            self._handle_oauth_error(e)

    def _handle_oauth_error(self, error):
        """Handle OAuth authentication error."""
        logger.error(f"OAuth authentication error: {error}")

        # Handle specific OAuth endpoint unavailable error differently
        error_message = str(error)
        if "OAuth authentication is not yet available" in error_message:
            # Show a more detailed dialog for OAuth unavailability
            from PyQt6.QtWidgets import QTextEdit

            msg_box = QMessageBox(self)
            msg_box.setWindowTitle("OAuth Not Available")
            msg_box.setIcon(QMessageBox.Icon.Warning)
            msg_box.setText("Sign-in via Skipthepodcast.com is not yet available")

            # Create detailed text widget
            details = QTextEdit()
            details.setPlainText(error_message)
            details.setReadOnly(True)
            details.setMaximumHeight(300)
            msg_box.setDetailedText(error_message)

            msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
            msg_box.exec()
        elif "cancelled by user" in error_message.lower():
            # Don't show error dialog for user cancellation
            logger.info("OAuth authentication cancelled by user")
        else:
            # Show regular error dialog for other authentication errors
            QMessageBox.critical(
                self, "Authentication Error", f"OAuth error: {str(error)}"
            )

        # Clear authentication state on error
        self.uploader = None
        self.authenticated_user = None
        self._oauth_auth = None
        self._refresh_auth_ui()

    def _sign_in(self) -> None:
        """Sign in to Supabase."""
        if not self.auth or not self.auth.is_available():
            QMessageBox.warning(
                self, "Auth Unavailable", "Supabase authentication is not available"
            )
            return

        email = self.email_edit.text().strip()
        password = self.password_edit.text()

        if not email or not password:
            QMessageBox.information(
                self, "Missing Credentials", "Please enter email and password"
            )
            return

        success, message = self.auth.sign_in(email, password)
        if success:
            self._refresh_auth_ui()
            self.password_edit.clear()  # Clear password for security
        else:
            QMessageBox.warning(self, "Sign In Failed", message)

    def _sign_up(self) -> None:
        """Sign up for Supabase account."""
        if not self.auth or not self.auth.is_available():
            QMessageBox.warning(
                self, "Auth Unavailable", "Supabase authentication is not available"
            )
            return

        try:
            from ..dialogs.sign_up_dialog import SignUpDialog

            dialog = SignUpDialog(self)
            if dialog.exec():
                email, password = dialog.get_values()
                if email and password:
                    success, message = self.auth.sign_up(email, password)
                    if success:
                        QMessageBox.information(
                            self,
                            "Check Your Email",
                            "Account created. Check your email to verify before signing in.",
                        )
                    else:
                        QMessageBox.warning(self, "Sign Up Failed", message)
        except ImportError:
            QMessageBox.warning(self, "Unavailable", "Sign-up dialog not available")

    def _sign_out(self) -> None:
        """Sign out of GetReceipts."""
        self.uploader = None
        self.authenticated_user = None
        self._refresh_auth_ui()

        QMessageBox.information(
            self, "Signed Out", "Successfully signed out of Skipthepodcast.com"
        )
