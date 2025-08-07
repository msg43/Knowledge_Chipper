#!/bin/bash

# Exit on any error
set -e

echo "🔄 Updating Knowledge Chipper..."

# Get the script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

# Define paths
APP_NAME="Knowledge_Chipper.app"
APP_PATH="/Applications/$APP_NAME"
TEMP_APP_PATH="$SCRIPT_DIR/$APP_NAME"

# Function to close the app if it's running
close_app() {
    echo "👋 Closing Knowledge Chipper if it's running..."
    osascript -e 'tell application "Knowledge_Chipper" to quit' 2>/dev/null || true
    sleep 2
}

# Function to backup settings
backup_settings() {
    echo "💾 Backing up settings..."
    if [ -d "$APP_PATH/Contents/MacOS/state" ]; then
        cp -r "$APP_PATH/Contents/MacOS/state" "$SCRIPT_DIR/state_backup"
    fi
    if [ -d "$APP_PATH/Contents/MacOS/config" ]; then
        cp -r "$APP_PATH/Contents/MacOS/config" "$SCRIPT_DIR/config_backup"
    fi
}

# Function to restore settings
restore_settings() {
    echo "🔄 Restoring settings..."
    if [ -d "$SCRIPT_DIR/state_backup" ]; then
        cp -r "$SCRIPT_DIR/state_backup" "$APP_PATH/Contents/MacOS/state"
        rm -rf "$SCRIPT_DIR/state_backup"
    fi
    if [ -d "$SCRIPT_DIR/config_backup" ]; then
        cp -r "$SCRIPT_DIR/config_backup" "$APP_PATH/Contents/MacOS/config"
        rm -rf "$SCRIPT_DIR/config_backup"
    fi
}

# Pull latest code from GitHub
echo "⬇️ Pulling latest code from GitHub..."
git fetch origin
CURRENT_BRANCH=$(git branch --show-current)
git pull origin $CURRENT_BRANCH

# Check if pip requirements have changed
if git diff --name-only HEAD@{1} HEAD | grep -q "requirements.txt"; then
    echo "📦 Requirements changed, updating dependencies..."
    source venv/bin/activate
    pip install -r requirements.txt
    pip install -e .
fi

# Main update process
echo "🏗️ Creating new app bundle..."

# Create app structure
mkdir -p "$TEMP_APP_PATH/Contents/"{MacOS,Resources}

# Copy icon files
cp chipper.png "$TEMP_APP_PATH/Contents/Resources/AppIcon.png"

# Create iconset and convert to icns
mkdir icon.iconset
for size in 16 32 128 256 512; do
    sips -z $size $size chipper.png --out icon.iconset/icon_${size}x${size}.png
    sips -z $((size*2)) $((size*2)) chipper.png --out icon.iconset/icon_${size}x${size}@2x.png
done
iconutil -c icns icon.iconset -o "$TEMP_APP_PATH/Contents/Resources/AppIcon.icns"
rm -rf icon.iconset

# Copy required directories
echo "📦 Copying application files..."
cp -r src "$TEMP_APP_PATH/Contents/MacOS/"
cp -r venv "$TEMP_APP_PATH/Contents/MacOS/"
cp -r config "$TEMP_APP_PATH/Contents/MacOS/"

# Create Info.plist
cat > "$TEMP_APP_PATH/Contents/Info.plist" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>
    <string>KnowledgeChipper</string>
    <key>CFBundleIconFile</key>
    <string>AppIcon</string>
    <key>CFBundleIdentifier</key>
    <string>com.knowledgechipper.app</string>
    <key>CFBundleName</key>
    <string>Knowledge Chipper</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0.0</string>
    <key>LSMinimumSystemVersion</key>
    <string>10.12</string>
    <key>NSHighResolutionCapable</key>
    <true/>
</dict>
</plist>
EOF

# Create launch script
cat > "$TEMP_APP_PATH/Contents/MacOS/KnowledgeChipper" << EOF
#!/bin/bash

# Get the directory where this script is located
APP_DIR="\$( cd "\$( dirname "\${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

# Activate virtual environment
source "\$APP_DIR/venv/bin/activate"

# Set PYTHONPATH to include src directory
export PYTHONPATH="\$APP_DIR/src:\$PYTHONPATH"

# Launch the GUI
exec python3 -m knowledge_system.gui.__main__
EOF

# Make launch script executable
chmod +x "$TEMP_APP_PATH/Contents/MacOS/KnowledgeChipper"

# Close the app if it's running
close_app

# Backup current settings
backup_settings

# Replace the old app with the new one
echo "🔄 Installing updated app..."
rm -rf "$APP_PATH"
mv "$TEMP_APP_PATH" "$APP_PATH"

# Restore settings
restore_settings

# Show the version information
echo "📋 Current version information:"
git log -1 --pretty=format:"Commit: %h%nDate: %ad%nMessage: %s" --date=local

echo "✨ Update complete! You can now launch Knowledge Chipper from your Applications folder."
