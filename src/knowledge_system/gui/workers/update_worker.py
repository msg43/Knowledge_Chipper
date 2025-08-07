"""Worker for handling app updates."""

import os
import subprocess
import sys
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
        try:
            # Get the MacOS directory path
            if getattr(sys, 'frozen', False):
                # Running in a bundle
                macos_dir = Path(sys.executable).parent
            else:
                # Running from source
                macos_dir = Path(os.path.dirname(os.path.realpath(__file__))).parents[3]
            
            # Look for the script in the MacOS directory
            script_path = macos_dir / "build_macos_app.sh"
            if script_path.exists():
                logger.info(f"Found update script at: {script_path}")
                return script_path
            
            logger.warning(f"Update script not found at: {script_path}")
            return None
            
        except Exception as e:
            logger.error(f"Error finding update script: {e}")
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
