#!/usr/bin/env python3
"""
Privileged Installer for Skip the Podcast Desktop

This creates a Disk Drill-like experience where the app:
1. Detects it's being blocked by Gatekeeper
2. Shows a dialog asking for admin password
3. Automatically fixes the Gatekeeper block
4. Relaunches without warnings
"""

import os
import plistlib
import subprocess
import sys
import tempfile
from pathlib import Path


def create_auth_prompt_script():
    """Create an AppleScript that mimics Disk Drill's authorization prompt."""
    return """
on run argv
    set appPath to item 1 of argv

    -- Show professional authorization dialog
    display dialog "Skip the Podcast Desktop needs your administrator password to complete installation and remove security restrictions.\\n\\nThis is a one-time setup that allows the app to run without security warnings." buttons {"Cancel", "Authorize"} default button "Authorize" with title "Administrator Access Required" with icon caution

    if button returned of result is "Cancel" then
        error number -128
    end if

    -- Now run with admin privileges
    try
        do shell script "
            # Remove quarantine attribute
            xattr -cr '" & appPath & "' 2>/dev/null || true
            xattr -dr com.apple.quarantine '" & appPath & "' 2>/dev/null || true

            # Add to Gatekeeper whitelist
            spctl --add '" & appPath & "' 2>/dev/null || true
            spctl --enable --label 'Skip the Podcast Desktop' 2>/dev/null || true

            # Register with Launch Services
            /System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister -f '" & appPath & "' 2>/dev/null || true

            # Update modification time to appear fresh
            touch '" & appPath & "'

            # Mark as successfully authorized
            touch '$HOME/.skip_the_podcast_authorized'

            echo 'Authorization successful'
        " with administrator privileges

        display notification "Skip the Podcast Desktop has been authorized successfully" with title "Installation Complete"

        return "success"
    on error errMsg
        display dialog "Authorization failed: " & errMsg buttons {"OK"} default button "OK" with icon stop
        return "failed"
    end try
end run
"""


def create_embedded_helper():
    """Create a helper that can be embedded in the app."""
    helper_content = '''#!/usr/bin/env python3
"""
Skip the Podcast Desktop - Gatekeeper Bypass Helper
This runs when the app detects it's being blocked by Gatekeeper
"""

import os
import sys
import subprocess
from pathlib import Path

def is_app_blocked():
    """Check if the app is being blocked by Gatekeeper."""
    app_path = Path(sys.argv[0]).parent.parent.parent  # Get app bundle path

    # Check for quarantine attribute
    try:
        result = subprocess.run(
            ['xattr', '-p', 'com.apple.quarantine', str(app_path)],
            capture_output=True,
            text=True
        )
        return result.returncode == 0  # Has quarantine = blocked
    except:
        return False

def request_authorization():
    """Request admin authorization to bypass Gatekeeper."""
    app_path = Path(sys.argv[0]).parent.parent.parent

    # Create authorization script
    auth_script = """
    -- Skip the Podcast Desktop Authorization

    display dialog "Skip the Podcast Desktop requires authorization to run for the first time.\\n\\nClick Authorize and enter your password to continue." buttons {"Cancel", "Authorize"} default button "Authorize" with title "First Run Authorization" with icon note

    if button returned of result is "Cancel" then
        error number -128
    end if

    -- Run privileged operations
    do shell script "
        # Remove all extended attributes including quarantine
        xattr -cr '" & "%s" & "' || true

        # Whitelist in Gatekeeper
        spctl --add '" & "%s" & "' || true

        # Touch to update timestamps
        find '" & "%s" & "' -type f -exec touch {} \\\\; 2>/dev/null || true

        # Create success marker
        touch ~/.skip_the_podcast_desktop_authorized
    " with administrator privileges

    display notification "Authorization complete! The app will now restart." with title "Skip the Podcast Desktop"
    """ % (app_path, app_path, app_path)

    # Run the authorization
    try:
        result = subprocess.run(
            ['osascript', '-e', auth_script],
            capture_output=True,
            text=True
        )
        return result.returncode == 0
    except Exception as e:
        print(f"Authorization failed: {e}")
        return False

def main():
    """Main helper entry point."""
    # Check if we need authorization
    if is_app_blocked():
        print("App is blocked by Gatekeeper. Requesting authorization...")

        if request_authorization():
            print("Authorization successful! Relaunching app...")
            # Relaunch the main app
            app_path = Path(sys.argv[0]).parent.parent.parent
            subprocess.run(['open', str(app_path)])
            sys.exit(0)
        else:
            print("Authorization cancelled or failed.")
            sys.exit(1)
    else:
        # App is not blocked, continue normal launch
        print("App is not blocked. Proceeding with normal launch.")

if __name__ == "__main__":
    main()
'''
    return helper_content


def integrate_into_app():
    """Generate code to integrate this into the main app startup."""
    integration_code = '''
# Add this to your main app startup (e.g., in __main__.py or launch script)

import os
import sys
import subprocess
from pathlib import Path

def check_and_handle_gatekeeper():
    """Check if app is blocked by Gatekeeper and handle it like Disk Drill."""

    if sys.platform != "darwin":
        return True

    # Check if we're running from /Applications (properly installed)
    app_path = Path(sys.argv[0])
    if "/Applications/" not in str(app_path):
        return True  # Not installed, skip check

    # Check for authorization marker
    auth_marker = Path.home() / ".skip_the_podcast_desktop_authorized"
    if auth_marker.exists():
        # Already authorized
        return True

    # Check for quarantine attribute
    try:
        result = subprocess.run(
            ['xattr', '-p', 'com.apple.quarantine', str(app_path.parent.parent.parent)],
            capture_output=True
        )

        if result.returncode == 0:
            # Has quarantine - we're being blocked!
            print("Detected Gatekeeper block. Initiating authorization...")

            # Show authorization dialog
            auth_script = """
            display dialog "Skip the Podcast Desktop needs to be authorized to run on your Mac.\\n\\nThis is a one-time setup similar to other professional apps like Disk Drill.\\n\\nClick Continue and enter your administrator password when prompted." buttons {"Quit", "Continue"} default button "Continue" with title "Authorization Required" with icon caution

            if button returned of result is "Quit" then
                error number -128
            end if

            -- Get app path
            set appPath to (path to current application as text)
            set posixPath to POSIX path of appPath

            -- Run with admin privileges
            do shell script "
                # Remove quarantine and all extended attributes
                xattr -cr '" & posixPath & "'
                xattr -dr com.apple.quarantine '" & posixPath & "'

                # Add to Gatekeeper exceptions
                spctl --add '" & posixPath & "'

                # Update Launch Services
                /System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister -f '" & posixPath & "'

                # Create marker
                touch ~/.skip_the_podcast_desktop_authorized

                # Brief pause
                sleep 1
            " with administrator privileges

            display notification "Authorization complete! Skip the Podcast Desktop is now ready to use." with title "Success" sound name "Glass"

            -- Relaunch the app
            delay 0.5
            tell application "Skip the Podcast Desktop" to activate
            """

            try:
                # Run authorization
                result = subprocess.run(
                    ['osascript', '-e', auth_script],
                    capture_output=True,
                    text=True
                )

                if result.returncode == 0:
                    print("Authorization successful!")
                    # Exit so the app can relaunch clean
                    sys.exit(0)
                else:
                    print("Authorization cancelled.")
                    sys.exit(1)

            except Exception as e:
                print(f"Authorization error: {e}")
                # Fall back to manual instructions
                subprocess.run([
                    'osascript', '-e',
                    'display dialog "Unable to authorize automatically.\\n\\nTo run the app:\\n1. Right-click Skip the Podcast Desktop\\n2. Select Open\\n3. Click Open in the dialog" buttons {"OK"} with title "Manual Authorization Required" with icon caution'
                ])
                sys.exit(1)

    except Exception:
        # Can't check, assume it's fine
        pass

    return True

# Call this at the very start of your app
if __name__ == "__main__":
    if not check_and_handle_gatekeeper():
        sys.exit(1)

    # Continue with normal app launch...
'''
    return integration_code


def create_standalone_authorizer():
    """Create a standalone app that just does the authorization."""
    return '''#!/usr/bin/env python3
"""
Skip the Podcast Desktop - Standalone Authorizer
Run this to authorize the app with a Disk Drill-like experience
"""

import os
import sys
import subprocess
from pathlib import Path

def main():
    app_path = "/Applications/Skip the Podcast Desktop.app"

    if not Path(app_path).exists():
        print("Error: App not found at", app_path)
        subprocess.run([
            'osascript', '-e',
            'display dialog "Skip the Podcast Desktop not found in Applications folder.\\n\\nPlease install the app first." buttons {"OK"} with icon stop'
        ])
        return 1

    # Show authorization dialog exactly like Disk Drill
    auth_script = f"""
    -- Professional authorization dialog
    display dialog "Skip the Podcast Desktop requires one-time authorization to run without security warnings.\\n\\nThis process is similar to other professional Mac apps and only needs to be done once.\\n\\nYou will be prompted for your administrator password." buttons {{"Cancel", "Authorize"}} default button "Authorize" with title "Skip the Podcast Desktop Setup" with icon caution

    if button returned of result is "Cancel" then
        error number -128
    end if

    -- Perform authorization
    try
        do shell script "
            # Remove ALL quarantine flags
            xattr -cr '{app_path}'
            xattr -dr com.apple.quarantine '{app_path}'

            # Whitelist in Gatekeeper
            spctl --add '{app_path}'
            spctl --enable --label 'Skip the Podcast Desktop'

            # Force Launch Services registration
            /System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister -f '{app_path}'

            # Touch all files to update timestamps
            find '{app_path}' -type f -exec touch {{}} + 2>/dev/null || true

            # Create authorization marker
            touch ~/.skip_the_podcast_desktop_authorized

            echo 'Success'
        " with administrator privileges

        -- Success message
        display dialog "Skip the Podcast Desktop has been successfully authorized!\\n\\nThe app will now open without any security warnings." buttons {{"Open App"}} default button "Open App" with title "Authorization Complete" with icon note

        -- Launch the app
        tell application "Skip the Podcast Desktop" to activate

    on error errMsg
        if errMsg does not contain "-128" then
            display dialog "Authorization failed:\\n\\n" & errMsg buttons {{"OK"}} default button "OK" with icon stop
        end if
    end try
    """

    try:
        subprocess.run(['osascript', '-e', auth_script], check=True)
        return 0
    except subprocess.CalledProcessError:
        return 1

if __name__ == "__main__":
    sys.exit(main())
'''


# Save all components
if __name__ == "__main__":
    # Save the auth prompt script
    auth_script_path = Path("macos_auth_prompt.applescript")
    auth_script_path.write_text(create_auth_prompt_script())

    # Save the embedded helper
    helper_path = Path("gatekeeper_bypass_helper.py")
    helper_path.write_text(create_embedded_helper())

    # Save the integration code
    integration_path = Path("app_integration_code.py")
    integration_path.write_text(integrate_into_app())

    # Save the standalone authorizer
    authorizer_path = Path("authorize_app.py")
    authorizer_path.write_text(create_standalone_authorizer())
    authorizer_path.chmod(0o755)

    print("Created Disk Drill-style authorization components:")
    print("  • macos_auth_prompt.applescript - Authorization dialog")
    print("  • gatekeeper_bypass_helper.py - Embedded helper")
    print("  • app_integration_code.py - Integration code")
    print("  • authorize_app.py - Standalone authorizer")
    print()
    print("This provides a Disk Drill-like experience where:")
    print("1. App detects it's blocked by Gatekeeper")
    print("2. Shows professional authorization dialog")
    print("3. Prompts for admin password")
    print("4. Automatically removes all restrictions")
    print("5. Relaunches without warnings")
