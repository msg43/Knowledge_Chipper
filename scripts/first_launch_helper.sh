#!/bin/bash
# First launch helper - runs with admin privileges to fix permissions

APP_PATH="/Applications/Skip the Podcast Desktop.app"

# Remove quarantine attribute
xattr -dr com.apple.quarantine "$APP_PATH" 2>/dev/null

# Set proper permissions
chmod -R 755 "$APP_PATH"
chown -R "$USER:admin" "$APP_PATH"

# Remove code signature to force re-evaluation
codesign --remove-signature "$APP_PATH" 2>/dev/null

# Create marker file to indicate setup is complete
touch "$HOME/.skip_podcast_desktop_configured"

exit 0
