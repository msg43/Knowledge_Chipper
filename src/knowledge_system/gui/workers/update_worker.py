"""Worker for handling app updates."""

import os
import subprocess
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import QThread, pyqtSignal

from ...logger import get_logger

logger = get_logger(__name__)


class UpdateWorker(QThread):
    """Worker thread for handling app updates."""

    # Signals
    update_progress = pyqtSignal(str)  # Status message
    update_finished = pyqtSignal(bool, str)  # Success, Message
    update_error = pyqtSignal(str)  # Error message

    def __init__(self) -> None:
        """Initialize the update worker."""
        super().__init__()
        self.script_path = self._find_update_script()

    def _find_update_script(self) -> Optional[Path]:
        """Find the build_macos_app.sh script."""
        # Check in the app bundle first
        app_dir = Path(os.path.dirname(os.path.realpath(__file__))).parents[4]
        script_path = app_dir / "build_macos_app.sh"
        
        if script_path.exists():
            return script_path
        
        # Check in the project directory
        project_dir = Path(os.path.dirname(os.path.realpath(__file__))).parents[3]
        script_path = project_dir / "build_macos_app.sh"
        
        if script_path.exists():
            return script_path
            
        return None

    def run(self) -> None:
        """Run the update process."""
        try:
            if not self.script_path:
                raise FileNotFoundError("Could not find build_macos_app.sh")

            # Make script executable
            os.chmod(self.script_path, 0o755)

            # Run the update script
            self.update_progress.emit("🔄 Checking for updates...")
            
            process = subprocess.Popen(
                [str(self.script_path)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                universal_newlines=True
            )

            # Read output in real-time
            while True:
                output = process.stdout.readline() if process.stdout else ""
                if output == "" and process.poll() is not None:
                    break
                if output:
                    self.update_progress.emit(output.strip())

            # Get the final status
            if process.returncode == 0:
                self.update_finished.emit(True, "✅ Update completed successfully!")
            else:
                error = process.stderr.read() if process.stderr else "Unknown error"
                self.update_finished.emit(False, f"❌ Update failed: {error}")

        except Exception as e:
            logger.error(f"Update error: {e}")
            self.update_error.emit(str(e))
