"""Diarization setup dialog to install optional dependencies.

Provides a simple guided flow to install the optional diarization
extras via pip, with non-interactive output and success detection.
"""

from __future__ import annotations

from typing import Any

from PyQt6.QtCore import QProcess, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)

from ...logger import get_logger

logger = get_logger(__name__)


class DiarizationSetupDialog(QDialog):
    """Dialog to install diarization dependencies using pip."""

    installation_completed = pyqtSignal(bool)

    def __init__(self, parent: Any = None) -> None:
        super().__init__(parent)
        self._process: QProcess | None = None
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setWindowTitle("Install Speaker Diarization Support")
        self.resize(640, 420)

        layout = QVBoxLayout(self)

        title = QLabel(
            "To enable speaker diarization, the optional dependencies must be installed.\n"
            "This will run: pip install -e '.[diarization]'"
        )
        title.setWordWrap(True)
        layout.addWidget(title)

        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        self.output.setPlaceholderText("Installation logs will appear here...")
        layout.addWidget(self.output)

        self.progress = QProgressBar()
        self.progress.setMinimum(0)
        self.progress.setMaximum(0)  # Indeterminate during install
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        btns = QHBoxLayout()
        self.cancel_btn = QPushButton("Close")
        self.cancel_btn.clicked.connect(self.reject)
        self.install_btn = QPushButton("Install Now")
        # On macOS, the default button remains blue even when disabled. Explicitly
        # clear the default/autoDefault state so it renders as a normal button
        # and can be visually greyed out after completion.
        try:
            # These methods exist on Qt push buttons; guard in case of API changes
            self.install_btn.setAutoDefault(False)
            self.install_btn.setDefault(False)
        except Exception:
            pass
        self.install_btn.clicked.connect(self._start_install)
        btns.addWidget(self.cancel_btn)
        btns.addStretch(1)
        btns.addWidget(self.install_btn)
        layout.addLayout(btns)

    def _append(self, text: str) -> None:
        self.output.appendPlainText(text.rstrip())

    def _start_install(self) -> None:
        if self._process is not None:
            return

        self.install_btn.setEnabled(False)
        self.progress.setVisible(True)
        self._append("Starting installation of diarization extras...\n")

        # Use the running Python to ensure environment correctness
        import sys

        cmd = [sys.executable, "-m", "pip", "install", "-e", ".[diarization]"]
        self._append("Command: " + " ".join(cmd))

        # Prefer QProcess for live streaming to UI
        self._process = QProcess(self)
        # Merge stderr into stdout for simpler logging
        self._process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self._process.readyReadStandardOutput.connect(self._on_output)
        self._process.finished.connect(self._on_finished)

        try:
            # Start in project root; QProcess inherits working dir from app
            self._process.start(cmd[0], cmd[1:])
        except Exception as e:
            logger.error(f"Failed to start pip install: {e}")
            self._append(f"Error starting installation: {e}")
            self.progress.setVisible(False)
            self.install_btn.setEnabled(True)

    def _on_output(self) -> None:
        if not self._process:
            return
        data = self._process.readAllStandardOutput()
        try:
            text = bytes(data).decode("utf-8", errors="replace")
        except Exception:
            text = str(data)
        self._append(text)

    def _on_finished(self, exit_code: int, _status: QProcess.ExitStatus) -> None:
        self.progress.setVisible(False)
        success = exit_code == 0
        if success:
            self._append("\n✅ Installation finished successfully.")
            self.installation_completed.emit(True)
            self.cancel_btn.setText("Close")
            self.cancel_btn.setEnabled(True)
            # Disable and visually de-emphasize the install button
            self.install_btn.setEnabled(False)
            try:
                self.install_btn.setAutoDefault(False)
                self.install_btn.setDefault(False)
            except Exception:
                pass
            self.install_btn.setText("Installed")
            return

        # Fallback: install packages directly in case extras resolution failed inside the app bundle
        self._append(
            "\n⚠️ Extras installation failed. Trying direct package install fallback...\n"
        )
        try:
            import sys

            fallback_cmd = [
                sys.executable,
                "-m",
                "pip",
                "install",
                "torch>=2.1.0",
                "transformers>=4.35.0",
                "pyannote.audio>=3.1.0",
            ]
            self._append("Fallback command: " + " ".join(fallback_cmd))
            self._process = QProcess(self)
            self._process.setProcessChannelMode(
                QProcess.ProcessChannelMode.MergedChannels
            )
            self._process.readyReadStandardOutput.connect(self._on_output)
            self._process.finished.connect(self._on_fallback_finished)
            self.progress.setVisible(True)
            self._process.start(fallback_cmd[0], fallback_cmd[1:])
        except Exception as e:
            logger.error(f"Failed to start fallback pip install: {e}")
            self._append(f"Error starting fallback installation: {e}")
            self.installation_completed.emit(False)
            self.progress.setVisible(False)
            self.cancel_btn.setText("Close")
            self.cancel_btn.setEnabled(True)
            self.install_btn.setEnabled(True)

    def _on_fallback_finished(
        self, exit_code: int, _status: QProcess.ExitStatus
    ) -> None:
        self.progress.setVisible(False)
        success = exit_code == 0
        if success:
            self._append("\n✅ Fallback installation finished successfully.")
        else:
            self._append(
                "\n❌ Fallback installation failed. Please run manually:\n  pip install torch>=2.1.0 transformers>=4.35.0 pyannote.audio>=3.1.0"
            )
        self.installation_completed.emit(success)
        self.cancel_btn.setText("Close")
        self.cancel_btn.setEnabled(True)
        self.install_btn.setEnabled(not success)
