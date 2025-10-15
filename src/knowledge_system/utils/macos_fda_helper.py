"""
macOS Full Disk Access Helper

This module provides a Disk Drill-like experience for requesting
Full Disk Access on macOS, with clear user guidance.
"""

import subprocess
import sys
import time
from pathlib import Path

from knowledge_system.logger import get_logger

logger = get_logger(__name__)


class FullDiskAccessHelper:
    """
    Helper class to guide users through granting Full Disk Access.
    Similar to how Disk Drill and CleanMyMac handle FDA requests.
    """

    def __init__(self):
        self.is_macos = sys.platform == "darwin"
        self.app_name = "Skip the Podcast Desktop"
        self.app_identifier = "com.skipthepodcast.desktop"

    def check_fda_status(self) -> bool:
        """Check if app has Full Disk Access."""
        if not self.is_macos:
            return True

        # Test by trying to access a protected location
        test_paths = [
            Path.home() / "Library/Application Support/com.apple.TCC/TCC.db",
            Path.home() / "Library/Safari/Bookmarks.plist",
            Path.home() / "Library/Messages/chat.db",
        ]

        for test_path in test_paths:
            try:
                if test_path.exists():
                    with open(test_path, "rb") as f:
                        f.read(1)
                    return True
            except (PermissionError, OSError):
                continue

        return False

    def show_fda_dialog(self) -> str:
        """
        Show a professional dialog explaining FDA needs.
        Returns 'grant', 'later', or 'cancel'.
        """
        try:
            dialog_script = """
            set iconPath to (path to application "Skip the Podcast Desktop") & "Contents:Resources:AppIcon.icns" as string

            try
                set dialogIcon to alias iconPath
            on error
                set dialogIcon to caution
            end try

            set dialogResult to display dialog "Skip the Podcast Desktop works best with Full Disk Access enabled.\\n\\nWith Full Disk Access, you can:\\n✓ Process media files from any location\\n✓ Save transcriptions anywhere on your Mac\\n✓ Access files on external drives\\n✓ Work with cloud storage folders\\n\\nWithout it, you'll need to manually select each file through dialogs.\\n\\nWould you like to enable Full Disk Access now?" buttons {"Not Now", "Learn More", "Enable Access"} default button "Enable Access" with icon dialogIcon with title "Enhance Your Experience"

            return button returned of dialogResult
            """

            result = subprocess.run(
                ["osascript", "-e", dialog_script],
                capture_output=True,
                text=True,
                check=False,
            )

            if result.returncode == 0:
                button = result.stdout.strip()
                if button == "Enable Access":
                    return "grant"
                elif button == "Learn More":
                    self._show_learn_more()
                    return "later"
                else:
                    return "later"

            return "cancel"

        except Exception as e:
            logger.error(f"Failed to show FDA dialog: {e}")
            return "cancel"

    def _show_learn_more(self):
        """Show detailed information about FDA."""
        try:
            info_script = """
            display dialog "About Full Disk Access\\n\\nFull Disk Access is a macOS security feature that controls which apps can access all files on your computer.\\n\\nWhy does Skip the Podcast Desktop need it?\\n• To read media files from any folder without repeated permission dialogs\\n• To save output files wherever you choose\\n• To access external drives and cloud storage\\n\\nYour Privacy:\\n• We only access files you explicitly choose to process\\n• No data is sent to any servers\\n• You can revoke access anytime in System Settings\\n\\nThe app works without FDA, but you'll need to grant permission for each folder individually." buttons {"OK"} default button "OK" with title "Full Disk Access Information" with icon note
            """
            subprocess.run(["osascript", "-e", info_script], check=False)
        except Exception:
            pass

    def guide_to_fda_settings(self) -> bool:
        """
        Guide the user to FDA settings with visual assistance.
        This is the Disk Drill approach - clear visual guidance.
        """
        try:
            # First, show instructions
            instruction_script = """
            display dialog "I'll guide you through enabling Full Disk Access:\\n\\n1. System Settings will open to Privacy & Security\\n2. Click the lock 🔒 and enter your password\\n3. Find 'Skip the Podcast Desktop' in the list\\n4. Check the box ☑️ next to it\\n5. The app may need to restart\\n\\nReady? Click Continue to open System Settings." buttons {"Cancel", "Continue"} default button "Continue" with title "Enable Full Disk Access - Step by Step" with icon note

            if button returned of result is "Cancel" then
                return "cancel"
            end if
            """

            result = subprocess.run(
                ["osascript", "-e", instruction_script],
                capture_output=True,
                text=True,
                check=False,
            )

            if result.returncode != 0 or "cancel" in result.stdout.lower():
                return False

            # Open System Settings to the exact location
            subprocess.run(
                [
                    "open",
                    "x-apple.systempreferences:com.apple.preference.security?Privacy_AllFiles",
                ],
                check=False,
            )

            # Wait a moment for System Settings to open
            time.sleep(2)

            # Show a reminder overlay
            reminder_script = """
            display notification "Look for Skip the Podcast Desktop in the list and check the box" with title "Full Disk Access" subtitle "Don't forget to unlock first 🔒"
            """
            subprocess.run(["osascript", "-e", reminder_script], check=False)

            # Mark that we've shown the FDA guide
            marker = Path.home() / ".skip_the_podcast_fda_guided"
            marker.touch()

            return True

        except Exception as e:
            logger.error(f"Failed to guide to FDA settings: {e}")
            return False

    def check_and_request_fda(self) -> tuple[bool, str]:
        """
        Check FDA status and request if needed.
        Returns (has_fda, action_taken).
        """
        if not self.is_macos:
            return True, "not_needed"

        # Check current status
        if self.check_fda_status():
            logger.info("Full Disk Access already granted")
            return True, "already_granted"

        # Check if we've already asked
        asked_marker = Path.home() / ".skip_the_podcast_fda_asked"
        guided_marker = Path.home() / ".skip_the_podcast_fda_guided"

        # If we've never asked, or it's been more than 30 days
        should_ask = False
        if not asked_marker.exists():
            should_ask = True
        else:
            days_since_asked = (time.time() - asked_marker.stat().st_mtime) / 86400
            if days_since_asked > 30 and not guided_marker.exists():
                should_ask = True

        if should_ask:
            # Show the dialog
            choice = self.show_fda_dialog()

            # Mark that we asked
            asked_marker.touch()

            if choice == "grant":
                # Guide to settings
                if self.guide_to_fda_settings():
                    return False, "guided_to_settings"
                else:
                    return False, "guide_failed"
            else:
                return False, "user_declined"

        # We've asked before and user hasn't enabled it
        logger.info("FDA not enabled - app will use standard file dialogs")
        return False, "previously_declined"


def setup_full_disk_access() -> bool:
    """
    Main entry point to set up Full Disk Access.
    Returns True if FDA is granted or user was guided to settings.
    """
    if sys.platform != "darwin":
        return True

    helper = FullDiskAccessHelper()
    has_fda, action = helper.check_and_request_fda()

    if has_fda:
        return True

    # Return True if we guided them (don't block app launch)
    return action in ["guided_to_settings", "previously_declined", "user_declined"]


def ensure_fda_on_startup():
    """
    Check FDA on startup and show setup if appropriate.
    This provides the Disk Drill-like experience without being annoying.
    """
    if sys.platform != "darwin":
        return True

    try:
        helper = FullDiskAccessHelper()
        has_fda, action = helper.check_and_request_fda()

        # Log the result for debugging
        logger.info(f"FDA check result: has_fda={has_fda}, action={action}")

        # Always return True so app continues to launch
        return True

    except Exception as e:
        logger.error(f"FDA check failed: {e}")
        # Don't block app launch on errors
        return True
