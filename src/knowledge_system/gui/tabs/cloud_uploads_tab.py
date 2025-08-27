"""
Cloud Uploads Tab

Allows users to browse local output files, select specific files, and upload
them to Supabase Storage on demand. No automatic uploads occur.
"""

from __future__ import annotations

from pathlib import Path
from typing import List

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGroupBox,
    QPushButton,
    QLabel,
    QFileDialog,
    QListWidget,
    QListWidgetItem,
    QCheckBox,
    QLineEdit,
    QSplitter,
    QMessageBox,
    QTableWidget,
    QTableWidgetItem,
)

from ...config import get_settings
from ...logger import get_logger
from ...services.supabase_storage import SupabaseStorageService
from ...services.supabase_auth import SupabaseAuthService
from ..components.base_tab import BaseTab


logger = get_logger(__name__)


class UploadWorker(QThread):
    progress = pyqtSignal(int, int, str)
    finished = pyqtSignal(int, int)
    error = pyqtSignal(str)

    def __init__(self, files: List[Path], client: object | None) -> None:
        super().__init__()
        self.files = files
        self.storage = SupabaseStorageService(client=client)
        self.bucket: str | None = None
        self.subfolder: str | None = None

    def run(self) -> None:
        # Require client to be initialized; bucket may be provided per-upload
        if self.storage.client is None:
            self.error.emit("Supabase storage is not configured")
            self.finished.emit(0, len(self.files))
            return

        success = 0
        total = len(self.files)
        for idx, fp in enumerate(self.files, start=1):
            ok, msg = self.storage.upload_file(fp, bucket=self.bucket, subfolder=self.subfolder)
            if ok:
                success += 1
            else:
                logger.error(f"Upload failed for {fp}: {msg}")
            self.progress.emit(idx, total, f"{fp.name}: {'OK' if ok else 'FAIL'}")

        self.finished.emit(success, total)


class CloudUploadsTab(BaseTab):
    """Tab for selecting and uploading files to cloud storage manually."""

    def __init__(self, parent=None) -> None:
        self.upload_worker: UploadWorker | None = None
        self.tab_name = "Cloud Uploads"
        self.auth = SupabaseAuthService()
        super().__init__(parent)

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter)

        # Left panel: auth + file selection
        left = QWidget()
        left_layout = QVBoxLayout(left)

        # Auth box
        auth_group = QGroupBox("Authentication")
        auth_layout = QHBoxLayout(auth_group)
        self.email_edit = QLineEdit()
        self.email_edit.setPlaceholderText("Email")
        self.password_edit = QLineEdit()
        self.password_edit.setPlaceholderText("Password")
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.login_btn = QPushButton("Sign In")
        self.signup_btn = QPushButton("Sign Up")
        self.logout_btn = QPushButton("Sign Out")
        self.logout_btn.setEnabled(False)
        auth_layout.addWidget(self.email_edit)
        auth_layout.addWidget(self.password_edit)
        auth_layout.addWidget(self.login_btn)
        auth_layout.addWidget(self.signup_btn)
        auth_layout.addWidget(self.logout_btn)
        left_layout.addWidget(auth_group)

        input_group = QGroupBox("Select Files to Upload")
        input_layout = QVBoxLayout(input_group)

        paths_row = QHBoxLayout()
        self.root_edit = QLineEdit()
        self.root_edit.setPlaceholderText("Root folder (defaults to output_dir)")
        browse_btn = QPushButton("Browse…")
        browse_btn.clicked.connect(self._browse_root)
        paths_row.addWidget(QLabel("Root:"))
        paths_row.addWidget(self.root_edit, 1)
        paths_row.addWidget(browse_btn)
        input_layout.addLayout(paths_row)

        self.include_md = QCheckBox("Markdown (.md)")
        self.include_md.setChecked(True)
        self.include_txt = QCheckBox("Text (.txt)")
        self.include_txt.setChecked(True)
        self.include_srt = QCheckBox("SubRip (.srt)")
        self.include_vtt = QCheckBox("WebVTT (.vtt)")
        self.include_json = QCheckBox("JSON (.json)")
        for w in (self.include_md, self.include_txt, self.include_srt, self.include_vtt, self.include_json):
            input_layout.addWidget(w)

        refresh_btn = QPushButton("Scan Files")
        refresh_btn.clicked.connect(self._scan_files)
        input_layout.addWidget(refresh_btn)

        left_layout.addWidget(input_group)

        # Bucket + subfolder controls
        bucket_row = QHBoxLayout()
        self.bucket_edit = QLineEdit()
        self.bucket_edit.setPlaceholderText("Bucket (optional; defaults to settings)")
        self.subfolder_edit = QLineEdit()
        self.subfolder_edit.setPlaceholderText("Destination subfolder (optional)")
        self.use_user_subfolder = QCheckBox("Use user ID as subfolder")
        bucket_row.addWidget(QLabel("Bucket:"))
        bucket_row.addWidget(self.bucket_edit)
        bucket_row.addWidget(QLabel("Subfolder:"))
        bucket_row.addWidget(self.subfolder_edit)
        bucket_row.addWidget(self.use_user_subfolder)
        left_layout.addLayout(bucket_row)

        # Two-column table: file path and relative destination
        self.file_table = QTableWidget()
        self.file_table.setColumnCount(2)
        self.file_table.setHorizontalHeaderLabels(["File", "Destination (relative)"])
        self.file_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.file_table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        left_layout.addWidget(self.file_table, 1)

        splitter.addWidget(left)

        # Right panel: actions and status
        right = QWidget()
        right_layout = QVBoxLayout(right)

        status_group = QGroupBox("Upload Status")
        status_layout = QVBoxLayout(status_group)
        self.status_label = QLabel("Ready")
        status_layout.addWidget(self.status_label)
        right_layout.addWidget(status_group)

        actions = QHBoxLayout()
        self.upload_btn = QPushButton("Upload Selected")
        self.upload_btn.clicked.connect(self._start_upload)
        actions.addWidget(self.upload_btn)

        select_all_btn = QPushButton("Select All")
        select_all_btn.clicked.connect(self._select_all_rows)
        actions.addWidget(select_all_btn)

        clear_btn = QPushButton("Clear Selection")
        clear_btn.clicked.connect(self._clear_selection)
        actions.addWidget(clear_btn)

        actions.addStretch()
        right_layout.addLayout(actions)

        splitter.addWidget(right)
        splitter.setSizes([700, 300])

        self._load_defaults()

        # Wire auth buttons
        self.login_btn.clicked.connect(self._sign_in)
        self.signup_btn.clicked.connect(self._sign_up)
        self.logout_btn.clicked.connect(self._sign_out)
        self._refresh_auth_ui()

    def _load_defaults(self) -> None:
        try:
            out_dir = Path(get_settings().paths.output_dir or "").expanduser()
            if out_dir:
                self.root_edit.setText(str(out_dir))
        except Exception:
            pass

    def _browse_root(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "Select Root Folder")
        if directory:
            self.root_edit.setText(directory)

    def _scan_files(self) -> None:
        root = Path(self.root_edit.text().strip() or ".").expanduser()
        if not root.exists() or not root.is_dir():
            QMessageBox.warning(self, "Invalid Folder", f"Not a folder: {root}")
            return

        exts: List[str] = []
        if self.include_md.isChecked():
            exts.append(".md")
        if self.include_txt.isChecked():
            exts.append(".txt")
        if self.include_srt.isChecked():
            exts.append(".srt")
        if self.include_vtt.isChecked():
            exts.append(".vtt")
        if self.include_json.isChecked():
            exts.append(".json")

        files: List[Path] = []
        for p in root.rglob("*"):
            if p.is_file() and (not exts or p.suffix.lower() in exts):
                files.append(p)

        self.file_table.setRowCount(0)
        rows = []
        # Use output_dir as the basis for destination preview, to match upload logic
        try:
            out_dir = Path(get_settings().paths.output_dir or "").expanduser()
        except Exception:
            out_dir = None
        for p in sorted(files):
            # Compute relative destination for preview
            rel = p.name
            try:
                if out_dir and out_dir.exists():
                    rel = str(p.relative_to(out_dir))
                else:
                    rel = p.name
            except Exception:
                rel = p.name
            rows.append((str(p), rel))

        self.file_table.setRowCount(len(rows))
        for r, (fp, rel) in enumerate(rows):
            self.file_table.setItem(r, 0, QTableWidgetItem(fp))
            self.file_table.setItem(r, 1, QTableWidgetItem(rel))

        self.status_label.setText(f"Found {len(files)} files")

    def _start_upload(self) -> None:
        selected: List[Path] = []
        for idx in self._selected_row_indices():
            item = self.file_table.item(idx, 0)
            if item:
                selected.append(Path(item.text()))
        if not selected:
            QMessageBox.information(self, "No Files Selected", "Please select one or more files to upload.")
            return

        self.upload_btn.setEnabled(False)
        self.status_label.setText("Uploading…")

        # Stash bucket/subfolder for worker; we’ll use settings inside worker
        client = self.auth.get_client() if self.auth and self.auth.is_available() else None
        self.upload_worker = UploadWorker(selected, client)
        self.upload_worker.bucket = self.bucket_edit.text().strip() or None  # type: ignore[attr-defined]
        # If toggle is on and we have a user, default subfolder to user id
        subfolder = self.subfolder_edit.text().strip()
        if self.use_user_subfolder.isChecked() and self.auth and self.auth.is_authenticated():
            user_id = self.auth.get_user_id()
            if user_id:
                subfolder = user_id if not subfolder else f"{user_id}/{subfolder.strip('/')}"
        self.upload_worker.subfolder = subfolder or None  # type: ignore[attr-defined]
        self.upload_worker.progress.connect(self._on_progress)
        self.upload_worker.finished.connect(self._on_finished)
        self.upload_worker.error.connect(self._on_error)
        self.upload_worker.start()

    def _on_progress(self, current: int, total: int, message: str) -> None:
        self.status_label.setText(f"{current}/{total} • {message}")

    def _on_finished(self, success: int, total: int) -> None:
        self.status_label.setText(f"Completed: {success}/{total} uploaded")
        self.upload_btn.setEnabled(True)

    def _on_error(self, message: str) -> None:
        self.status_label.setText(message)
        self.upload_btn.setEnabled(True)

    def _selected_row_indices(self) -> List[int]:
        rows: List[int] = []
        for idx in self.file_table.selectedIndexes():
            if idx.column() == 0:
                if idx.row() not in rows:
                    rows.append(idx.row())
        return sorted(rows)

    def _select_all_rows(self) -> None:
        self.file_table.selectAll()

    def _clear_selection(self) -> None:
        self.file_table.clearSelection()

    # Auth helpers
    def _refresh_auth_ui(self) -> None:
        authed = self.auth.is_authenticated() if self.auth else False
        self.login_btn.setEnabled(not authed)
        self.logout_btn.setEnabled(authed)
        if authed:
            email = self.auth.get_user_email() or "Signed in"
            self.status_label.setText(f"{email} • Ready")

    def _sign_in(self) -> None:
        if not self.auth or not self.auth.is_available():
            QMessageBox.warning(self, "Auth Unavailable", "Supabase auth is not available")
            return
        email = self.email_edit.text().strip()
        password = self.password_edit.text()
        if not email or not password:
            QMessageBox.information(self, "Missing Credentials", "Enter email and password")
            return
        ok, msg = self.auth.sign_in(email, password)
        if not ok:
            QMessageBox.warning(self, "Sign In Failed", msg)
        self._refresh_auth_ui()

    def _sign_out(self) -> None:
        if not self.auth or not self.auth.is_available():
            return
        ok, msg = self.auth.sign_out()
        if not ok:
            QMessageBox.warning(self, "Sign Out Failed", msg)
        self._refresh_auth_ui()

    def _sign_up(self) -> None:
        if not self.auth or not self.auth.is_available():
            QMessageBox.warning(self, "Auth Unavailable", "Supabase auth is not available")
            return
        try:
            from ..dialogs.sign_up_dialog import SignUpDialog
        except Exception:
            QMessageBox.warning(self, "Unavailable", "Sign-up dialog not available")
            return

        dlg = SignUpDialog(self)
        if dlg.exec():
            email, password = dlg.get_values()
            if not email or not password:
                QMessageBox.information(self, "Missing", "Email and password are required")
                return
            ok, msg = self.auth.sign_up(email, password)
            if ok:
                QMessageBox.information(
                    self,
                    "Check Your Email",
                    "Account created. If email confirmations are enabled, check your inbox to verify before signing in.",
                )
            else:
                QMessageBox.warning(self, "Sign Up Failed", msg)


