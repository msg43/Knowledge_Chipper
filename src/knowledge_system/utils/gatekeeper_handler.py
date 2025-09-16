"""
Gatekeeper Handler for Skip the Podcast Desktop

Provides Disk Drill-like authorization when Gatekeeper blocks the app.
This runs at app startup to detect and fix Gatekeeper blocks.
"""

import os
import subprocess
import sys
from pathlib import Path

from knowledge_system.logger import get_logger

logger = get_logger(__name__)


def is_running_from_applications():
    """Check if we're running from /Applications."""
    try:
        exe_path = sys.executable if hasattr(sys, "executable") else sys.argv[0]
        return "/Applications/" in str(exe_path)
    except:
        return False


def has_quarantine_attribute():
    """Check if the app has quarantine attribute (Gatekeeper will block it)."""
    if sys.platform != "darwin":
        return False

    try:
        # Get the app bundle path
        exe_path = Path(sys.executable if hasattr(sys, "executable") else sys.argv[0])

        # Navigate up to find .app bundle
        app_path = exe_path
        while app_path.parent != app_path:
            if app_path.suffix == ".app":
                break
            app_path = app_path.parent

        if app_path.suffix != ".app":
            return False

        # Check for quarantine
        result = subprocess.run(
            ["xattr", "-p", "com.apple.quarantine", str(app_path)],
            capture_output=True,
            stderr=subprocess.DEVNULL,
        )

        return result.returncode == 0

    except Exception as e:
        logger.debug(f"Error checking quarantine: {e}")
        return False


def request_authorization_and_fix():
    """
    Show Disk Drill-style authorization dialog and fix Gatekeeper block.
    Returns True if successful, False otherwise.
    """
    try:
        # Get app bundle path
        exe_path = Path(sys.executable if hasattr(sys, "executable") else sys.argv[0])
        app_path = exe_path
        while app_path.parent != app_path:
            if app_path.suffix == ".app":
                break
            app_path = app_path.parent

        logger.info(f"Requesting authorization to bypass Gatekeeper for: {app_path}")

        # Create the authorization script
        auth_script = f"""
        -- Skip the Podcast Desktop - Gatekeeper Authorization

        set appPath to "{app_path}"
        set appName to "Skip the Podcast Desktop"

        -- Check if Terminal has automation permission first
        try
            tell application "System Events"
                set x to 1
            end tell
        on error
            display dialog "Skip the Podcast Desktop needs automation permission to complete setup.\\n\\n1. Click OK\\n2. Grant permission in System Settings\\n3. Run the app again" buttons {{"OK"}} default button "OK" with icon caution
            return "needs_automation"
        end try

        -- Show professional authorization dialog like Disk Drill
        set dialogResult to display dialog appName & " needs administrator access to complete installation.\\n\\nThis one-time setup removes macOS security restrictions and allows the app to run normally.\\n\\nYou'll be prompted for your password." buttons {{"Quit", "Authorize"}} default button "Authorize" with title appName & " - First Run Setup" with icon caution

        if button returned of dialogResult is "Quit" then
            return "cancelled"
        end if

        -- Run with administrator privileges
        try
            do shell script "
                # Log what we're doing
                echo 'Authorizing Skip the Podcast Desktop...' > /tmp/stp_auth.log

                # Remove ALL extended attributes including quarantine
                /usr/bin/xattr -cr '" & appPath & "' >> /tmp/stp_auth.log 2>&1
                /usr/bin/xattr -dr com.apple.quarantine '" & appPath & "' >> /tmp/stp_auth.log 2>&1

                # Add to Gatekeeper whitelist
                /usr/sbin/spctl --add '" & appPath & "' >> /tmp/stp_auth.log 2>&1
                /usr/sbin/spctl --enable --label '" & appName & "' >> /tmp/stp_auth.log 2>&1

                # Register with Launch Services
                /System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister -f '" & appPath & "' >> /tmp/stp_auth.log 2>&1

                # Touch to update timestamps
                /usr/bin/touch '" & appPath & "' >> /tmp/stp_auth.log 2>&1

                # Create success marker
                /usr/bin/touch ~/.skip_the_podcast_desktop_authorized

                echo 'Authorization complete!' >> /tmp/stp_auth.log
            " with administrator privileges

            -- Show success notification
            display notification "Skip the Podcast Desktop has been authorized successfully!" with title "Setup Complete" sound name "Glass"

            -- Brief success dialog
            display dialog "Authorization successful!\\n\\nSkip the Podcast Desktop is now ready to use." buttons {{"Launch App"}} default button "Launch App" with title "Setup Complete" with icon note

            return "success"

        on error errMsg number errNum
            if errNum is not -128 then
                display dialog "Authorization failed:\\n\\n" & errMsg buttons {{"OK"}} default button "OK" with icon stop with title "Authorization Error"
            end if
            return "failed"
        end try
        """

        # Run the authorization script
        result = subprocess.run(
            ["osascript", "-e", auth_script], capture_output=True, text=True
        )

        logger.info(f"Authorization result: {result.stdout.strip()}")

        if "success" in result.stdout:
            logger.info("Successfully authorized app!")
            return True
        elif "needs_automation" in result.stdout:
            logger.warning("Need automation permission first")
            return False
        else:
            logger.warning("Authorization cancelled or failed")
            return False

    except Exception as e:
        logger.error(f"Authorization error: {e}")
        return False


def handle_gatekeeper_at_startup():
    """
    Main function to call at app startup.
    Detects and handles Gatekeeper blocks with Disk Drill-style flow.

    Returns:
        True if app can proceed, False if it should exit
    """
    if sys.platform != "darwin":
        return True

    # Skip if not running from Applications
    if not is_running_from_applications():
        logger.debug("Not running from /Applications, skipping Gatekeeper check")
        return True

    # Check if already authorized
    auth_marker = Path.home() / ".skip_the_podcast_desktop_authorized"
    if auth_marker.exists():
        logger.debug("App already authorized")
        return True

    # Check for quarantine
    if has_quarantine_attribute():
        logger.info("Detected Gatekeeper quarantine - initiating authorization")

        # Request authorization
        if request_authorization_and_fix():
            # Successfully authorized - tell user to relaunch
            try:
                subprocess.run(
                    [
                        "osascript",
                        "-e",
                        'tell application "Skip the Podcast Desktop" to quit',
                    ]
                )
            except:
                pass

            # Relaunch the app
            subprocess.run(["open", "-a", "Skip the Podcast Desktop"])

            # Exit this instance
            return False
        else:
            # Authorization failed - show manual instructions
            subprocess.run(
                [
                    "osascript",
                    "-e",
                    """display dialog "To run Skip the Podcast Desktop:\\n\\n1. Close this dialog\\n2. Right-click the app\\n3. Select 'Open'\\n4. Click 'Open' in the security dialog\\n\\nThis only needs to be done once." buttons {"OK"} default button "OK" with title "Manual Authorization Required" with icon caution""",
                ]
            )
            return False

    # No quarantine or already authorized
    return True


def ensure_no_gatekeeper_block():
    """
    Simpler entry point that just ensures the app isn't blocked.
    Call this early in your app startup.
    """
    try:
        return handle_gatekeeper_at_startup()
    except Exception as e:
        logger.error(f"Gatekeeper handler error: {e}")
        # On error, let the app continue
        return True
