"""Worker for handling app updates."""

import os
import subprocess
import sys
import tempfile
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
            # Always use the main repository path for updates
            # This avoids permission issues with the app bundle
            main_repo_path = Path.home() / "Projects" / "Knowledge_Chipper"
            
            # Look for the script in the main repository
            script_path = main_repo_path / "build_macos_app.sh"
            if script_path.exists():
                logger.info(f"Found update script at: {script_path}")
                return script_path
            
            # Fallback to checking relative to current file location
            if not getattr(sys, 'frozen', False):
                # Running from source
                fallback_dir = Path(os.path.dirname(os.path.realpath(__file__))).parents[3]
                script_path = fallback_dir / "build_macos_app.sh"
                if script_path.exists():
                    logger.info(f"Found update script at: {script_path}")
                    return script_path
            
            logger.warning(f"Update script not found")
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

            # Create a temporary file for combined output
            with tempfile.NamedTemporaryFile(mode='w+', delete=False) as temp_file:
                # Change to the script directory before running
                script_dir = self.script_path.parent
                process = subprocess.Popen(
                    [str(self.script_path)],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,  # Combine stdout and stderr
                    text=True,
                    bufsize=1,
                    universal_newlines=True,
                    cwd=str(script_dir)  # Run from the repository directory
                )

                # Read output in real-time
                while True:
                    output = process.stdout.readline() if process.stdout else ""
                    if output == "" and process.poll() is not None:
                        break
                    if output:
                        temp_file.write(output)
                        self.update_progress.emit(output.strip())

                # Get the final status
                if process.returncode == 0:
                    self.update_finished.emit(True, "✅ Update completed successfully!")
                else:
                    # Read the entire output
                    temp_file.seek(0)
                    full_output = temp_file.read()
                    
                    # Look for specific error patterns
                    if "fatal: detected dubious ownership" in full_output:
                        error = "Git ownership error. Please run the app from the terminal for more details."
                    elif "Permission denied" in full_output:
                        error = "Permission error. Please check file permissions."
                    else:
                        error = "Update failed. Please check the logs for details."
                    
                    logger.error(f"Update failed with output:\n{full_output}")
                    self.update_finished.emit(False, f"❌ {error}")

                # Clean up
                temp_file_path = temp_file.name

            # Delete the temporary file
            try:
                os.unlink(temp_file_path)
            except Exception as e:
                logger.warning(f"Failed to delete temporary file: {e}")

        except Exception as e:
            logger.error(f"Update error: {e}")
            self.update_error.emit(str(e))
