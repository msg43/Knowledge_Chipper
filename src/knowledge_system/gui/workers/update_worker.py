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
    update_progress_percent = pyqtSignal(int, str)  # Percent [0-100], message
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
            # This avoids permission issues and path confusion with the app bundle
            main_repo_path = Path.home() / "Projects" / "Knowledge_Chipper"

            # Look for the script in the main repository (preferred)
            script_path = main_repo_path / "scripts" / "build_macos_app.sh"
            if script_path.exists():
                logger.info(f"Found update script at: {script_path}")
                return script_path

            # Fallback to checking relative to current file location (running from source)
            if not getattr(sys, "frozen", False):
                # Running from source
                fallback_dir = Path(
                    os.path.dirname(os.path.realpath(__file__))
                ).parents[3]
                script_path = fallback_dir / "scripts" / "build_macos_app.sh"
                if script_path.exists():
                    logger.info(f"Found update script at: {script_path}")
                    return script_path

            # Last resort: try to find the repository by looking for typical Git project structure
            # This helps when running from an app bundle
            current_path = Path.cwd()
            for potential_repo in [current_path, current_path.parent, current_path.parent.parent]:
                script_path = potential_repo / "scripts" / "build_macos_app.sh"
                if script_path.exists() and (potential_repo / ".git").exists():
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
                
                # Determine correct working directory - use the repository root, not script directory
                repo_root = self.script_path.parent.parent if self.script_path.name == "build_macos_app.sh" and self.script_path.parent.name == "scripts" else self.script_path.parent
                logger.info(f"Using repository root: {repo_root}")
                
                try:
                    env = os.environ.copy()
                    env["IN_APP_UPDATER"] = "1"
                    process = subprocess.Popen(
                        ["/bin/bash", str(sudo_free_script), "--skip-install", "--incremental"],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,  # Combine stdout and stderr
                        text=True,
                        bufsize=1,
                        universal_newlines=True,
                        cwd=str(repo_root),  # Run from the repository root directory
                        env=env,
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
                    # Suppress noisy repeated permission messages and persist full log
                    permission_denied_repeats = 0
                    
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
                                # Collapse extremely noisy permission denied spam
                                if "Permission denied" in stripped_output:
                                    permission_denied_repeats += 1
                                    # Emit a summary every 200 occurrences
                                    if permission_denied_repeats % 200 == 1:
                                        self.update_progress.emit(
                                            f"Permission denied (x{permission_denied_repeats})"
                                        )
                                else:
                                    # Before emitting a normal line, flush any pending summary
                                    if permission_denied_repeats:
                                        self.update_progress.emit(
                                            f"Permission denied (x{permission_denied_repeats})"
                                        )
                                        permission_denied_repeats = 0

                                    # Parse structured progress markers first
                                    percent = self._parse_percent_marker(stripped_output)
                                    if percent is not None:
                                        # Extract message after marker for nicer UX
                                        message = self._strip_marker_message(stripped_output)
                                        self.update_progress_percent.emit(percent, message)
                                    else:
                                        # Fallback: emit plain text for log
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

                # Flush any remaining permission summary
                if 'permission_denied_repeats' in locals() and permission_denied_repeats:
                    self.update_progress.emit(
                        f"Permission denied (x{permission_denied_repeats})"
                    )

                # Get the final status
                if process.returncode == 0:
                    logger.info("Update build completed successfully; installing to ~/Applications")
                    # After skip-install, copy staged app to ~/Applications
                    try:
                        from shutil import rmtree, copytree
                        user_apps = Path.home() / "Applications"
                        user_apps.mkdir(parents=True, exist_ok=True)
                        staged_app = self.script_path.parent / ".app_build" / "Knowledge_Chipper.app"
                        dest_app = user_apps / "Knowledge_Chipper.app"
                        if dest_app.exists():
                            try:
                                rmtree(dest_app)
                            except Exception as e:
                                logger.warning(f"Failed to remove existing app at {dest_app}: {e}")
                        copytree(staged_app, dest_app)
                        self.update_finished.emit(True, "✅ Update installed to ~/Applications")
                    except Exception as e:
                        logger.error(f"Failed to copy app to ~/Applications: {e}")
                        self.update_finished.emit(True, "✅ Update built; copy from scripts/.app_build to ~/Applications manually")
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
                    elif "sudo" in full_output.lower() and "password" in full_output.lower():
                        error = "Update requires admin privileges. Please run from Terminal: bash scripts/build_macos_app.sh"
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

            # Persist update output to logs directory for debugging
            try:
                from datetime import datetime
                logs_dir = Path(repo_root) / "logs"
                logs_dir.mkdir(parents=True, exist_ok=True)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                dest = logs_dir / f"update_{timestamp}.log"
                Path(temp_file_path).replace(dest)
                logger.info(f"Update log saved to: {dest}")
            except Exception as e:
                logger.warning(f"Failed to persist update log: {e}")

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
            
            # Fix the script directory and project root paths to use the original script location
            # instead of the temporary script location
            original_script_dir = str(self.script_path.parent)
            original_project_root = str(self.script_path.parent.parent)
            
            # Replace the dynamic path detection with fixed paths
            path_fixed_content = original_content.replace(
                'SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"',
                f'SCRIPT_DIR="{original_script_dir}"'
            ).replace(
                'PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"',
                f'PROJECT_ROOT="{original_project_root}"'
            )
            
            # Create a modified version that builds in user space and uses cp instead of sudo mv
            modified_content = path_fixed_content.replace(
                'APP_PATH="/Applications/$APP_NAME"',
                'APP_PATH="$HOME/Applications/$APP_NAME"\nmkdir -p "$HOME/Applications"'
            ).replace(
                'sudo rm -rf "$APP_PATH"',
                '# Skip removing /Applications without privileges; fallback will install in user space\nif [ -w "/Applications" ]; then\n    rm -rf "$APP_PATH" || true\nfi'
            ).replace(
                'sudo mv "$BUILD_APP_PATH" "$APP_PATH"',
                '''# Non-sudo install with robust fallback to ~/Applications
# First try to install into /Applications; if it fails, fall back to user Applications
if cp -R "$BUILD_APP_PATH" "$APP_PATH" 2>/dev/null; then
    : # success
else
    echo "⚠️  Cannot copy to /Applications. Installing to ~/Applications instead..."
    mkdir -p "$HOME/Applications"
    APP_PATH="$HOME/Applications/$APP_NAME"
    # Recompute dependent paths for user install location
    CONTENTS_PATH="$APP_PATH/Contents"
    MACOS_PATH="$CONTENTS_PATH/MacOS"
    RESOURCES_PATH="$CONTENTS_PATH/Resources"
    FRAMEWORKS_PATH="$CONTENTS_PATH/Frameworks"
    cp -R "$BUILD_APP_PATH" "$APP_PATH"
fi'''
            ).replace(
                'sudo chown -R root:wheel "$APP_PATH"',
                '# Skip chown - not needed for user installation'
            ).replace(
                'sudo chmod -R 755 "$APP_PATH"',
                'chmod -R 755 "$APP_PATH" || true'
            ).replace(
                'sudo mkdir -p "$MACOS_PATH/logs"',
                'if [ -w "$MACOS_PATH" ]; then mkdir -p "$MACOS_PATH/logs"; fi'
            ).replace(
                'sudo chmod 777 "$MACOS_PATH/logs"',
                'if [ -w "$MACOS_PATH/logs" ]; then chmod 777 "$MACOS_PATH/logs"; fi'
            ).replace(
                'sudo chown "$CURRENT_USER:staff" "$MACOS_PATH/build_macos_app.sh"',
                ': # skip chown of build_macos_app.sh in user install'
            ).replace(
                'sudo chmod 755 "$MACOS_PATH/build_macos_app.sh"',
                'if [ -w "$MACOS_PATH/build_macos_app.sh" ]; then chmod 755 "$MACOS_PATH/build_macos_app.sh"; fi'
            ).replace(
                'sudo mv "/tmp/version.txt" "$MACOS_PATH/version.txt"',
                'mv "/tmp/version.txt" "$MACOS_PATH/version.txt" || true'
            ).replace(
                'sudo rm -rf "$MACOS_PATH/venv"',
                'rm -rf "$MACOS_PATH/venv" || true'
            ).replace(
                'sudo "$PYTHON_BIN_INSTALL" -m venv "$MACOS_PATH/venv"',
                '"$PYTHON_BIN_INSTALL" -m venv "$MACOS_PATH/venv"'
            ).replace(
                'sudo "$MACOS_PATH/venv/bin/python" -m pip install --upgrade pip',
                '"$MACOS_PATH/venv/bin/python" -m pip install --upgrade pip'
            ).replace(
                'sudo "$MACOS_PATH/venv/bin/python" -m pip install -r "$MACOS_PATH/requirements.txt"',
                '"$MACOS_PATH/venv/bin/python" -m pip install -r "$MACOS_PATH/requirements.txt"'
            ).replace(
                'sudo "$MACOS_PATH/venv/bin/python" -m pip install -r "$MACOS_PATH/requirements.txt" &',
                '"$MACOS_PATH/venv/bin/python" -m pip install -r "$MACOS_PATH/requirements.txt" &'
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

    @staticmethod
    def _parse_percent_marker(line: str) -> int | None:
        """Parse percent markers of the form:
        - '##PERCENT## 45 message...'
        - '##PROGRESS## 3/12: message...'
        Returns integer percent [0,100] or None if no marker found.
        """
        try:
            if line.startswith("##PERCENT##"):
                parts = line.split()
                if len(parts) >= 2:
                    value = int(parts[1])
                    return max(0, min(100, value))
            if line.startswith("##PROGRESS##"):
                # Format: ##PROGRESS## X/Y: message
                import re as _re
                m = _re.search(r"##PROGRESS##\s+(\d+)\s*/\s*(\d+)", line)
                if m:
                    current = int(m.group(1))
                    total = int(m.group(2))
                    if total > 0:
                        return max(0, min(100, round(100 * current / total)))
        except Exception:
            return None
        return None

    @staticmethod
    def _strip_marker_message(line: str) -> str:
        """Strip marker prefix and return just the human-friendly message."""
        try:
            if line.startswith("##PERCENT##"):
                # Drop the leading '##PERCENT## NN' and optional colon
                parts = line.split(maxsplit=2)
                if len(parts) >= 3:
                    return parts[2].lstrip(": ")
                return ""
            if line.startswith("##PROGRESS##"):
                # Drop up to the colon
                colon_idx = line.find(":")
                if colon_idx != -1:
                    return line[colon_idx + 1 :].strip()
                return ""
        except Exception:
            return line
        return line
