"""Worker for handling app updates."""

import os
import subprocess
import sys
import tempfile
from pathlib import Path

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

    def _find_update_script(self) -> Path | None:
        """Find the build_macos_app.sh script."""
        try:
            # Always use the main repository path for updates
            # This avoids permission issues with the app bundle
            main_repo_path = Path.home() / "Projects" / "Knowledge_Chipper"

            # Look for the script in the main repository
            script_path = main_repo_path / "scripts" / "build_macos_app.sh"
            if script_path.exists():
                logger.info(f"Found update script at: {script_path}")
                return script_path

            # Fallback to checking relative to current file location
            if not getattr(sys, "frozen", False):
                # Running from source
                fallback_dir = Path(
                    os.path.dirname(os.path.realpath(__file__))
                ).parents[3]
                script_path = fallback_dir / "scripts" / "build_macos_app.sh"
                if script_path.exists():
                    logger.info(f"Found update script at: {script_path}")
                    return script_path

            logger.warning("Update script not found")
            return None

        except Exception as e:
            logger.error(f"Error finding update script: {e}")
            return None

    def run(self) -> None:
        """Run the update process."""
        try:
            if not self.script_path:
                raise FileNotFoundError("Could not find scripts/build_macos_app.sh")

            # Make script executable
            os.chmod(self.script_path, 0o755)

            # Run the update script in-process with real-time monitoring
            self.update_progress.emit("🔄 Checking for updates…")
            logger.info(f"Starting update using script: {self.script_path}")

            # Create a temporary file for combined output
            with tempfile.NamedTemporaryFile(mode="w+", delete=False) as temp_file:
                # Change to the script directory before running
                script_dir = self.script_path.parent
                logger.info(f"Working directory: {script_dir}")
                
                # Create a modified script that avoids sudo requirements
                try:
                    sudo_free_script = self._create_sudo_free_script()
                    logger.info(f"Created sudo-free script: {sudo_free_script}")
                    self.update_progress.emit("📝 Preparing update script...")
                except Exception as e:
                    logger.error(f"Failed to create sudo-free script: {e}")
                    self.update_error.emit(f"Failed to prepare update script: {e}")
                    return
                
                # Use bash explicitly for consistent behavior
                self.update_progress.emit("🚀 Starting update process...")
                try:
                    process = subprocess.Popen(
                        ["/bin/bash", str(sudo_free_script)],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,  # Combine stdout and stderr
                        text=True,
                        bufsize=1,
                        universal_newlines=True,
                        cwd=str(script_dir),  # Run from the repository directory
                    )
                    logger.info(f"Started subprocess with PID: {process.pid}")
                except Exception as e:
                    logger.error(f"Failed to start update subprocess: {e}")
                    self.update_error.emit(f"Failed to start update: {e}")
                    return

                # Read output in real-time with timeout
                line_count = 0
                import time
                start_time = time.time()
                max_update_time = 600  # 10 minutes timeout
                
                try:
                    while True:
                        # Check for timeout
                        if time.time() - start_time > max_update_time:
                            logger.error("Update timeout reached")
                            process.terminate()
                            self.update_error.emit("Update timed out after 10 minutes")
                            return
                        
                        output = process.stdout.readline() if process.stdout else ""
                        if output == "" and process.poll() is not None:
                            break
                        if output:
                            line_count += 1
                            temp_file.write(output)
                            stripped_output = output.strip()
                            if stripped_output:  # Only emit non-empty lines
                                self.update_progress.emit(stripped_output)
                                logger.debug(f"Update output [{line_count}]: {stripped_output}")
                        
                        # Small delay to prevent excessive CPU usage
                        time.sleep(0.01)
                    
                    logger.info(f"Update process finished with return code: {process.returncode}")
                except Exception as e:
                    logger.error(f"Error reading update output: {e}")
                    process.terminate()
                    self.update_error.emit(f"Error during update: {e}")
                    return

                # Get the final status
                if process.returncode == 0:
                    logger.info("Update completed successfully")
                    self.update_finished.emit(True, "✅ Update completed successfully!")
                else:
                    # Read the entire output for error analysis
                    temp_file.seek(0)
                    full_output = temp_file.read()
                    logger.error(f"Update failed with return code {process.returncode}")
                    logger.error(f"Full update output:\n{full_output}")

                    # Look for specific error patterns
                    if "fatal: detected dubious ownership" in full_output:
                        error = "Git ownership error. Please run the app from the terminal for more details."
                    elif (
                        "fatal: bad object" in full_output
                        or "fatal: bad object refs/stash" in full_output
                    ):
                        error = "Git stash error. Try running the update from Terminal: bash scripts/build_macos_app.sh"
                    elif "Permission denied" in full_output:
                        error = "Permission error. Please check file permissions."
                    elif "No such file or directory" in full_output:
                        error = "Missing dependency. Please check your development environment."
                    else:
                        error = f"Update failed with exit code {process.returncode}. Check logs for details."

                    self.update_finished.emit(False, f"❌ {error}")

                # Clean up
                temp_file_path = temp_file.name
                # Clean up the temporary sudo-free script
                try:
                    os.unlink(sudo_free_script)
                    logger.debug("Cleaned up temporary script")
                except Exception:
                    pass

            # Delete the temporary file
            try:
                os.unlink(temp_file_path)
                logger.debug("Cleaned up temporary output file")
            except Exception as e:
                logger.warning(f"Failed to delete temporary file: {e}")

        except Exception as e:
            logger.error(f"Update error: {e}", exc_info=True)
            self.update_error.emit(str(e))

    def _create_sudo_free_script(self) -> Path:
        """Create a modified version of the build script that doesn't require sudo."""
        temp_script = Path(tempfile.mktemp(suffix=".sh"))
        
        try:
            # Read the original script
            with open(self.script_path, 'r') as f:
                original_content = f.read()
            
            logger.debug(f"Original script size: {len(original_content)} bytes")
            
            # Create a modified version that builds in user space and uses cp instead of sudo mv
            modified_content = original_content.replace(
                'sudo rm -rf "$APP_PATH"',
                'rm -rf "$APP_PATH" || true'  # Don't fail if app doesn't exist
            ).replace(
                'sudo mv "$BUILD_APP_PATH" "$APP_PATH"',
                '''# Copy to Applications directory without sudo
if [ -w "/Applications" ]; then
    cp -r "$BUILD_APP_PATH" "$APP_PATH"
else
    echo "⚠️  Cannot write to /Applications. Installing to ~/Applications instead..."
    mkdir -p "$HOME/Applications"
    APP_PATH="$HOME/Applications/$APP_NAME"
    cp -r "$BUILD_APP_PATH" "$APP_PATH"
fi'''
            ).replace(
                'sudo chown -R root:wheel "$APP_PATH"',
                '# Skip chown - not needed for user installation'
            ).replace(
                'sudo chmod -R 755 "$APP_PATH"',
                'chmod -R 755 "$APP_PATH" || true'
            ).replace(
                'sudo mkdir -p "$MACOS_PATH/logs"',
                'mkdir -p "$MACOS_PATH/logs"'
            ).replace(
                'sudo chmod 777 "$MACOS_PATH/logs"',
                'chmod 777 "$MACOS_PATH/logs" || true'
            ).replace(
                'sudo chown "$CURRENT_USER:staff" "$MACOS_PATH/scripts/build_macos_app.sh"',
                'chown "$CURRENT_USER:staff" "$MACOS_PATH/scripts/build_macos_app.sh" || true'
            ).replace(
                'sudo chmod 755 "$MACOS_PATH/scripts/build_macos_app.sh"',
                'chmod 755 "$MACOS_PATH/scripts/build_macos_app.sh" || true'
            ).replace(
                'sudo mv "/tmp/version.txt" "$MACOS_PATH/version.txt"',
                'mv "/tmp/version.txt" "$MACOS_PATH/version.txt"'
            )
            
            logger.debug(f"Modified script size: {len(modified_content)} bytes")
            
            # Write the modified script
            with open(temp_script, 'w') as f:
                f.write(modified_content)
            
            # Make it executable
            os.chmod(temp_script, 0o755)
            
            # Verify the script was written correctly
            if not temp_script.exists():
                raise FileNotFoundError(f"Failed to create temporary script at {temp_script}")
            
            script_size = temp_script.stat().st_size
            if script_size == 0:
                raise ValueError("Created script is empty")
            
            logger.debug(f"Created sudo-free script: {temp_script} ({script_size} bytes)")
            return temp_script
            
        except Exception as e:
            logger.error(f"Error creating sudo-free script: {e}")
            # Fallback: just copy the original script
            logger.info("Falling back to original script")
            with open(self.script_path, 'r') as f:
                original_content = f.read()
            
            with open(temp_script, 'w') as f:
                f.write(original_content)
            
            os.chmod(temp_script, 0o755)
            return temp_script
