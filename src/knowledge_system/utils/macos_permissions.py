"""
macOS Permission Handler for Skip the Podcast Desktop

This module handles file access permissions on macOS.
The app uses standard file dialogs which automatically grant
permissions to selected files and folders.
"""

import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, Optional, Tuple

from knowledge_system.logger import get_logger

logger = get_logger(__name__)


class MacOSPermissionHandler:
    """Handle macOS file access permissions."""

    def __init__(self):
        self.is_macos = sys.platform == "darwin"

    def check_app_sandbox_status(self) -> bool:
        """
        Check if the app is properly sandboxed (recommended for macOS apps).
        Non-sandboxed apps have more implicit permissions but less security.
        """
        if not self.is_macos:
            return False

        # Check if we're running from /Applications
        try:
            app_path = os.path.abspath(sys.executable)
            return "/Applications/" in app_path
        except:
            return False

    def check_file_access(self, path: str) -> tuple[bool, str]:
        """
        Check if we can access a specific file or directory.

        Returns:
            Tuple of (can_access, error_message)
        """
        path_obj = Path(path)

        try:
            if path_obj.is_dir():
                # Try to list directory contents
                list(path_obj.iterdir())
                return True, ""
            elif path_obj.exists():
                # Try to read file
                with open(path_obj, "rb") as f:
                    f.read(1)
                return True, ""
            else:
                return False, f"Path does not exist: {path}"
        except PermissionError:
            return False, f"Permission denied: {path}"
        except Exception as e:
            return False, f"Cannot access {path}: {str(e)}"

    def request_folder_access_via_dialog(
        self, title: str = "Select Folder"
    ) -> str | None:
        """
        Show a folder selection dialog which automatically grants permission
        to the selected folder. This is the recommended way to get folder access.

        Returns:
            Selected folder path or None if cancelled
        """
        if not self.is_macos:
            return None

        try:
            # Use AppleScript to show folder selection dialog
            script = f"""
            set chosenFolder to choose folder with prompt "{title}"
            return POSIX path of chosenFolder
            """

            result = subprocess.run(
                ["osascript", "-e", script], capture_output=True, text=True, check=False
            )

            if result.returncode == 0:
                folder_path = result.stdout.strip()
                logger.info(f"User selected folder: {folder_path}")
                return folder_path
            else:
                logger.info("User cancelled folder selection")
                return None

        except Exception as e:
            logger.error(f"Failed to show folder dialog: {e}")
            return None

    def request_file_access_via_dialog(
        self, title: str = "Select File", file_types: list = None
    ) -> str | None:
        """
        Show a file selection dialog which automatically grants permission
        to the selected file. This is the recommended way to get file access.

        Args:
            title: Dialog title
            file_types: List of allowed file extensions (e.g., ["mp4", "mp3", "wav"])

        Returns:
            Selected file path or None if cancelled
        """
        if not self.is_macos:
            return None

        try:
            # Build file type filter for AppleScript
            if file_types:
                type_list = ", ".join([f'"{ext}"' for ext in file_types])
                type_filter = f" of type {{{type_list}}}"
            else:
                type_filter = ""

            script = f"""
            set chosenFile to choose file with prompt "{title}"{type_filter}
            return POSIX path of chosenFile
            """

            result = subprocess.run(
                ["osascript", "-e", script], capture_output=True, text=True, check=False
            )

            if result.returncode == 0:
                file_path = result.stdout.strip()
                logger.info(f"User selected file: {file_path}")
                return file_path
            else:
                logger.info("User cancelled file selection")
                return None

        except Exception as e:
            logger.error(f"Failed to show file dialog: {e}")
            return None

    def check_all_permissions(self) -> dict[str, bool]:
        """
        Check basic app permissions.

        Note: Skip the Podcast Desktop doesn't need special permissions.
        File access is granted through standard file dialogs.
        """
        permissions = {}

        if self.is_macos:
            # Check if we're properly installed
            permissions["properly_installed"] = self.check_app_sandbox_status()

            # Check if we can write to common directories
            home_dir = Path.home()
            desktop = home_dir / "Desktop"
            downloads = home_dir / "Downloads"
            documents = home_dir / "Documents"

            for name, path in [
                ("desktop", desktop),
                ("downloads", downloads),
                ("documents", documents),
            ]:
                can_access, _ = self.check_file_access(str(path))
                permissions[f"{name}_access"] = can_access
        else:
            # Non-macOS systems don't have these restrictions
            permissions["properly_installed"] = True
            permissions["desktop_access"] = True
            permissions["downloads_access"] = True
            permissions["documents_access"] = True

        return permissions

    def show_file_access_help(self):
        """Show help dialog about file access."""
        try:
            message = (
                "Skip the Podcast Desktop uses standard macOS file dialogs for secure file access.\\n\\n"
                "When you:\\n"
                "• Select input files → The app gets permission to read those files\\n"
                "• Choose output folders → The app gets permission to write there\\n\\n"
                "This is the secure, Apple-recommended approach that protects your privacy."
            )

            script = f"""
            display dialog "{message}" with title "File Access Information" buttons {{"OK"}} default button "OK" with icon note
            """
            subprocess.run(["osascript", "-e", script], check=False)
        except Exception as e:
            logger.debug(f"Failed to show help dialog: {e}")
            print("\n" + "=" * 60)
            print("File Access Information")
            print("=" * 60)
            print(
                "Skip the Podcast Desktop uses standard macOS file dialogs for secure file access."
            )
            print("\nWhen you:")
            print("• Select input files → The app gets permission to read those files")
            print("• Choose output folders → The app gets permission to write there")
            print(
                "\nThis is the secure, Apple-recommended approach that protects your privacy."
            )
            print("=" * 60 + "\n")


def check_and_request_permissions() -> bool:
    """
    Convenience function to check basic app status.

    Returns:
        True (app doesn't require special permissions)
    """
    handler = MacOSPermissionHandler()
    permissions = handler.check_all_permissions()

    if not permissions.get("properly_installed", False):
        logger.info(
            "App is not installed in /Applications - some features may be limited"
        )

    # Always return True - the app uses standard dialogs for file access
    return True


def ensure_permissions_on_startup():
    """
    Check app installation status on startup.
    Skip the Podcast Desktop doesn't need special permissions -
    it uses standard file dialogs for secure file access.
    """
    if sys.platform != "darwin":
        return True

    handler = MacOSPermissionHandler()

    # Just log the installation status
    if handler.check_app_sandbox_status():
        logger.info("App properly installed in /Applications")
    else:
        logger.debug("App not in /Applications - running from alternate location")

    return True
