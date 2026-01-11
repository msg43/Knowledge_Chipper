#!/bin/bash
# create_desktop_shortcut.sh - Create desktop shortcut for daemon control
#
# This script creates a clickable desktop shortcut that starts/restarts the daemon

set -e

# Get the actual user (not root if running via sudo)
if [ -n "$SUDO_USER" ]; then
    ACTUAL_USER="$SUDO_USER"
    USER_HOME=$(eval echo ~$SUDO_USER)
else
    ACTUAL_USER="$USER"
    USER_HOME="$HOME"
fi

DESKTOP_DIR="$USER_HOME/Desktop"
SHORTCUT_NAME="GetReceipts Daemon"

echo "Creating desktop shortcut for daemon control..."

# Create the app bundle structure for the shortcut
SHORTCUT_APP="$DESKTOP_DIR/$SHORTCUT_NAME.app"
mkdir -p "$SHORTCUT_APP/Contents/MacOS"
mkdir -p "$SHORTCUT_APP/Contents/Resources"

# Create Info.plist
cat > "$SHORTCUT_APP/Contents/Info.plist" << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key>
    <string>GetReceipts Daemon</string>
    <key>CFBundleDisplayName</key>
    <string>GetReceipts Daemon</string>
    <key>CFBundleIdentifier</key>
    <string>org.getreceipts.daemon.shortcut</string>
    <key>CFBundleVersion</key>
    <string>1.0</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0</string>
    <key>CFBundleExecutable</key>
    <string>daemon-control</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleIconFile</key>
    <string>AppIcon</string>
    <key>LSUIElement</key>
    <false/>
</dict>
</plist>
EOF

# Create the executable script
cat > "$SHORTCUT_APP/Contents/MacOS/daemon-control" << 'SCRIPT_EOF'
#!/bin/bash
# GetReceipts Daemon Control Script

# Function to check if daemon is running
is_daemon_running() {
    curl -s http://localhost:8765/health > /dev/null 2>&1
    return $?
}

# Function to show notification
notify() {
    osascript -e "display notification \"$1\" with title \"GetReceipts Daemon\"" 2>/dev/null || true
}

# Function to show dialog
show_dialog() {
    osascript -e "display dialog \"$1\" with title \"GetReceipts Daemon\" buttons {\"OK\"} default button 1" 2>/dev/null
}

# Check current status
if is_daemon_running; then
    # Daemon is running - offer to restart
    RESPONSE=$(osascript -e 'display dialog "GetReceipts Daemon is currently running.\n\nWhat would you like to do?" buttons {"Cancel", "Stop", "Restart"} default button "Restart" with title "GetReceipts Daemon"' 2>/dev/null | awk -F: '{print $2}')
    
    case "$RESPONSE" in
        *Restart*)
            notify "Restarting daemon..."
            launchctl stop org.skipthepodcast.daemon 2>/dev/null || true
            sleep 1
            launchctl start org.skipthepodcast.daemon 2>/dev/null || true
            sleep 2
            if is_daemon_running; then
                notify "✅ Daemon restarted successfully"
                show_dialog "Daemon restarted successfully!\n\nVisit GetReceipts.org/contribute to start processing."
            else
                show_dialog "⚠️ Daemon failed to restart.\n\nTry running from Terminal:\nlaunchctl start org.skipthepodcast.daemon"
            fi
            ;;
        *Stop*)
            notify "Stopping daemon..."
            launchctl stop org.skipthepodcast.daemon 2>/dev/null || true
            sleep 1
            notify "✅ Daemon stopped"
            show_dialog "Daemon stopped.\n\nDouble-click this icon again to start it."
            ;;
        *)
            # Cancelled
            exit 0
            ;;
    esac
else
    # Daemon is not running - start it
    notify "Starting daemon..."
    launchctl start org.skipthepodcast.daemon 2>/dev/null || true
    sleep 2
    
    if is_daemon_running; then
        notify "✅ Daemon started successfully"
        show_dialog "Daemon started successfully!\n\nVisit GetReceipts.org/contribute to start processing."
    else
        show_dialog "⚠️ Daemon failed to start.\n\nPlease check:\n1. Is the app installed in /Applications?\n2. Try running from Terminal:\n   launchctl start org.skipthepodcast.daemon"
    fi
fi
SCRIPT_EOF

chmod +x "$SHORTCUT_APP/Contents/MacOS/daemon-control"

# Copy icon if available (optional - will use default if not found)
if [ -f "/Applications/Skip the Podcast Desktop.app/Contents/Resources/app_icon.icns" ]; then
    cp "/Applications/Skip the Podcast Desktop.app/Contents/Resources/app_icon.icns" "$SHORTCUT_APP/Contents/Resources/AppIcon.icns"
fi

# Set proper ownership
chown -R "$ACTUAL_USER:staff" "$SHORTCUT_APP"

# Make it executable
chmod -R 755 "$SHORTCUT_APP"

echo "✅ Desktop shortcut created: $DESKTOP_DIR/$SHORTCUT_NAME.app"
echo ""
echo "Users can now:"
echo "  - Double-click to start/restart the daemon"
echo "  - See status and control options"
echo "  - Get notifications about daemon status"
