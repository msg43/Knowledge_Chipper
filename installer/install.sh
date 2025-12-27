#!/bin/bash
#
# GetReceipts Daemon Installer
#
# This script installs the GetReceipts local processing daemon:
# 1. Copies daemon executable to /Users/Shared/GetReceipts/
# 2. Installs LaunchAgent for auto-start
# 3. Creates website shortcut in Applications folder
# 4. Starts the daemon
#
# Usage:
#   ./install.sh              # Install to default locations
#   ./install.sh --uninstall  # Remove daemon and all files
#

set -e

# Configuration
INSTALL_DIR="/Users/Shared/GetReceipts"
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"
APPLICATIONS_DIR="$HOME/Applications"
PLIST_NAME="org.getreceipts.daemon.plist"
WEBLOC_NAME="GetReceipts.webloc"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${GREEN}✓${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}⚠${NC} $1"
}

log_error() {
    echo -e "${RED}✗${NC} $1"
}

# Get script directory (where the installer resources are)
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Uninstall function
uninstall() {
    echo "Uninstalling GetReceipts Daemon..."
    
    # Stop and unload LaunchAgent
    if [ -f "$LAUNCH_AGENTS_DIR/$PLIST_NAME" ]; then
        launchctl unload "$LAUNCH_AGENTS_DIR/$PLIST_NAME" 2>/dev/null || true
        rm "$LAUNCH_AGENTS_DIR/$PLIST_NAME"
        log_info "Removed LaunchAgent"
    fi
    
    # Remove shortcut
    if [ -f "$APPLICATIONS_DIR/$WEBLOC_NAME" ]; then
        rm "$APPLICATIONS_DIR/$WEBLOC_NAME"
        log_info "Removed shortcut"
    fi
    
    # Remove installation directory
    if [ -d "$INSTALL_DIR" ]; then
        rm -rf "$INSTALL_DIR"
        log_info "Removed $INSTALL_DIR"
    fi
    
    echo ""
    log_info "Uninstall complete!"
    exit 0
}

# Check for uninstall flag
if [ "$1" == "--uninstall" ]; then
    uninstall
fi

echo "=========================================="
echo "  GetReceipts Daemon Installer"
echo "=========================================="
echo ""

# Step 1: Create directories
echo "Creating directories..."
mkdir -p "$INSTALL_DIR"
mkdir -p "$INSTALL_DIR/logs"
mkdir -p "$LAUNCH_AGENTS_DIR"
mkdir -p "$APPLICATIONS_DIR"
log_info "Created directories"

# Step 2: Copy daemon executable
echo "Installing daemon..."
if [ -f "$SCRIPT_DIR/GetReceiptsDaemon" ]; then
    cp "$SCRIPT_DIR/GetReceiptsDaemon" "$INSTALL_DIR/"
    chmod +x "$INSTALL_DIR/GetReceiptsDaemon"
    log_info "Installed daemon to $INSTALL_DIR"
elif [ -d "$SCRIPT_DIR/GetReceiptsDaemon.app" ]; then
    cp -R "$SCRIPT_DIR/GetReceiptsDaemon.app" "$INSTALL_DIR/"
    log_info "Installed daemon app bundle to $INSTALL_DIR"
else
    log_error "Daemon executable not found!"
    log_warn "Looking for: $SCRIPT_DIR/GetReceiptsDaemon"
    exit 1
fi

# Step 3: Install LaunchAgent
echo "Installing LaunchAgent..."
if [ -f "$SCRIPT_DIR/$PLIST_NAME" ]; then
    # Update plist with correct paths
    sed "s|/Users/Shared/GetReceipts|$INSTALL_DIR|g" "$SCRIPT_DIR/$PLIST_NAME" > "$LAUNCH_AGENTS_DIR/$PLIST_NAME"
    log_info "Installed LaunchAgent"
else
    log_warn "LaunchAgent plist not found, skipping auto-start setup"
fi

# Step 4: Create website shortcut
echo "Creating website shortcut..."
cat > "$APPLICATIONS_DIR/$WEBLOC_NAME" << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>URL</key>
    <string>https://getreceipts.org/contribute</string>
</dict>
</plist>
EOF
log_info "Created shortcut at $APPLICATIONS_DIR/$WEBLOC_NAME"

# Step 5: Load and start daemon
echo "Starting daemon..."
if [ -f "$LAUNCH_AGENTS_DIR/$PLIST_NAME" ]; then
    launchctl unload "$LAUNCH_AGENTS_DIR/$PLIST_NAME" 2>/dev/null || true
    launchctl load "$LAUNCH_AGENTS_DIR/$PLIST_NAME"
    log_info "Daemon started"
else
    # Manual start if no LaunchAgent
    "$INSTALL_DIR/GetReceiptsDaemon" &
    log_info "Daemon started (manual)"
fi

# Step 6: Verify daemon is running
echo "Verifying installation..."
sleep 2
if curl -s "http://localhost:8765/api/health" > /dev/null 2>&1; then
    log_info "Daemon is running and healthy"
else
    log_warn "Daemon may still be starting up..."
fi

echo ""
echo "=========================================="
echo "  Installation Complete!"
echo "=========================================="
echo ""
echo "The GetReceipts daemon is now running on http://localhost:8765"
echo ""
echo "To open GetReceipts:"
echo "  - Double-click 'GetReceipts' in $APPLICATIONS_DIR"
echo "  - Or visit https://getreceipts.org/contribute"
echo ""
echo "To uninstall:"
echo "  $0 --uninstall"
echo ""

