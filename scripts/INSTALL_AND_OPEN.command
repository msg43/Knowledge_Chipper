#!/bin/bash
# INSTALL_AND_OPEN.command - Smart installer for Skip the Podcast Desktop
#
# This script:
# 1. Copies app to Applications
# 2. Removes quarantine attributes (bypasses Gatekeeper warnings)
# 3. Creates desktop shortcut for daemon control
# 4. Launches the daemon

set -e

# Get the directory where this script is located (inside the DMG)
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
APP_NAME="Skip the Podcast Desktop.app"
SOURCE_APP="$SCRIPT_DIR/$APP_NAME"
DEST_APP="/Applications/$APP_NAME"

echo "🚀 GetReceipts Daemon Installer"
echo "================================"
echo ""

# Check if app exists in DMG
if [ ! -d "$SOURCE_APP" ]; then
    echo "❌ Error: $APP_NAME not found in DMG"
    echo "   Expected at: $SOURCE_APP"
    read -p "Press Enter to exit..."
    exit 1
fi

# Check if already installed
if [ -d "$DEST_APP" ]; then
    echo "⚠️  Skip the Podcast Desktop is already installed"
    echo ""
    read -p "Replace existing installation? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Installation cancelled"
        read -p "Press Enter to exit..."
        exit 0
    fi
    echo "🗑️  Removing old installation..."
    sudo rm -rf "$DEST_APP"
fi

# Copy app to Applications
echo "📦 Installing to /Applications..."
echo "   (You may be asked for your password)"
sudo cp -R "$SOURCE_APP" "$DEST_APP"

# Remove quarantine attribute (prevents Gatekeeper warnings)
echo "🔓 Removing quarantine attributes..."
sudo xattr -dr com.apple.quarantine "$DEST_APP" 2>/dev/null || true

# Set proper permissions
echo "🔐 Setting permissions..."
sudo chmod -R 755 "$DEST_APP"
sudo chown -R $(whoami):staff "$DEST_APP"

# Create desktop shortcut for daemon control
echo "🖥️  Creating desktop shortcut..."
DESKTOP_SHORTCUT="$HOME/Desktop/GetReceipts Daemon.app"

# Remove old shortcut if exists
if [ -d "$DESKTOP_SHORTCUT" ]; then
    rm -rf "$DESKTOP_SHORTCUT"
fi

# Create shortcut app bundle
mkdir -p "$DESKTOP_SHORTCUT/Contents/MacOS"
mkdir -p "$DESKTOP_SHORTCUT/Contents/Resources"

# Create Info.plist
cat > "$DESKTOP_SHORTCUT/Contents/Info.plist" << 'PLIST_EOF'
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
    <key>CFBundleExecutable</key>
    <string>daemon-control</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>LSUIElement</key>
    <false/>
</dict>
</plist>
PLIST_EOF

# Create executable
cat > "$DESKTOP_SHORTCUT/Contents/MacOS/daemon-control" << 'SCRIPT_EOF'
#!/bin/bash
# GetReceipts Daemon Control

is_running() {
    curl -s http://localhost:8765/health > /dev/null 2>&1
}

notify() {
    osascript -e "display notification \"$1\" with title \"GetReceipts Daemon\"" 2>/dev/null || true
}

show_dialog() {
    osascript -e "display dialog \"$1\" with title \"GetReceipts Daemon\" buttons {\"OK\"} default button 1" 2>/dev/null
}

if is_running; then
    RESPONSE=$(osascript -e 'display dialog "GetReceipts Daemon is running.\n\nWhat would you like to do?" buttons {"Cancel", "Stop", "Restart"} default button "Restart"' 2>/dev/null | awk -F: '{print $2}')
    
    case "$RESPONSE" in
        *Restart*)
            notify "Restarting daemon..."
            launchctl stop org.skipthepodcast.daemon 2>/dev/null || true
            sleep 1
            launchctl start org.skipthepodcast.daemon 2>/dev/null || true
            sleep 2
            if is_running; then
                notify "✅ Daemon restarted"
                show_dialog "Daemon restarted successfully!\n\nVisit GetReceipts.org/contribute to start processing."
            else
                show_dialog "⚠️ Daemon failed to restart.\n\nTry: launchctl start org.skipthepodcast.daemon"
            fi
            ;;
        *Stop*)
            launchctl stop org.skipthepodcast.daemon 2>/dev/null || true
            notify "✅ Daemon stopped"
            show_dialog "Daemon stopped.\n\nDouble-click this icon to start it again."
            ;;
    esac
else
    notify "Starting daemon..."
    launchctl start org.skipthepodcast.daemon 2>/dev/null || true
    sleep 2
    if is_running; then
        notify "✅ Daemon started"
        show_dialog "Daemon started!\n\nVisit GetReceipts.org/contribute to start processing."
    else
        show_dialog "⚠️ Daemon failed to start.\n\nCheck if app is installed in /Applications."
    fi
fi
SCRIPT_EOF

chmod +x "$DESKTOP_SHORTCUT/Contents/MacOS/daemon-control"

# Copy icon if available
if [ -f "$DEST_APP/Contents/Resources/AppIcon.icns" ]; then
    cp "$DEST_APP/Contents/Resources/AppIcon.icns" "$DESKTOP_SHORTCUT/Contents/Resources/" 2>/dev/null || true
fi

echo "✅ Desktop shortcut created"

# Launch the app
echo "🚀 Launching GetReceipts Daemon..."
open "$DEST_APP"

echo ""
echo "✅ Installation Complete!"
echo ""
echo "🌐 Next Steps:"
echo "   1. Visit https://getreceipts.org/contribute"
echo "   2. The daemon will auto-connect"
echo "   3. Start processing videos!"
echo ""
echo "🖥️  Desktop Shortcut:"
echo "   Double-click 'GetReceipts Daemon' on your desktop"
echo "   to start/restart/stop the daemon anytime."
echo ""
read -p "Press Enter to close..."
