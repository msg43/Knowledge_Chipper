#!/bin/bash

# Exit on any error
set -e

echo "🔄 Checking for updates..."

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
cd "$SCRIPT_DIR"

# Store current branch name
CURRENT_BRANCH=$(git branch --show-current)

# Check if there are uncommitted changes
if [[ -n $(git status -s) ]]; then
    echo "⚠️  You have uncommitted changes. Please commit or stash them first."
    exit 1
fi

# Pull latest code
echo "⬇️ Pulling latest code from GitHub..."
git pull origin $CURRENT_BRANCH

echo "🏗️ Building Knowledge_Chipper.app..."

# Define paths
APP_NAME="Knowledge_Chipper.app"
APP_PATH="/Applications/$APP_NAME"
CONTENTS_PATH="$APP_PATH/Contents"
MACOS_PATH="$CONTENTS_PATH/MacOS"
RESOURCES_PATH="$CONTENTS_PATH/Resources"
FRAMEWORKS_PATH="$CONTENTS_PATH/Frameworks"

# Create directory structure
echo "📁 Creating app bundle structure..."
sudo rm -rf "$APP_PATH"
sudo mkdir -p "$MACOS_PATH" "$RESOURCES_PATH" "$FRAMEWORKS_PATH"

# Copy project files
echo "📦 Copying project files..."
sudo cp -r src "$MACOS_PATH/"
sudo cp -r venv "$MACOS_PATH/"
sudo cp -r config "$MACOS_PATH/"
sudo cp requirements.txt "$MACOS_PATH/"
sudo cp build_macos_app.sh "$MACOS_PATH/"

# Create logs directory
echo "📝 Creating logs directory..."
sudo mkdir -p "$MACOS_PATH/logs"
sudo chmod 777 "$MACOS_PATH/logs"

# Create Info.plist
echo "📝 Creating Info.plist..."
cat > "/tmp/Info.plist" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>
    <string>launch</string>
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
sudo mv "/tmp/Info.plist" "$CONTENTS_PATH/Info.plist"

# Create launch script
echo "📜 Creating launch script..."
cat > "/tmp/launch" << EOF
#!/bin/bash

# Get the directory where this script is located
APP_DIR="\$( cd "\$( dirname "\${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
LOG_FILE="\$APP_DIR/logs/knowledge_system.log"

# Ensure logs directory exists and is writable
mkdir -p "\$APP_DIR/logs"
touch "\$LOG_FILE"
chmod 666 "\$LOG_FILE"

# Log the git version being launched
echo "Launching Knowledge Chipper version:" >> "\$LOG_FILE"
git -C "\$APP_DIR" rev-parse HEAD >> "\$LOG_FILE"

# Activate virtual environment
source "\$APP_DIR/venv/bin/activate"

# Set PYTHONPATH to include src directory
export PYTHONPATH="\$APP_DIR/src:\$PYTHONPATH"

# Launch the GUI
cd "\$APP_DIR"
exec python3 -m knowledge_system.gui.__main__ 2>&1 | tee -a "\$LOG_FILE"
EOF
sudo mv "/tmp/launch" "$MACOS_PATH/launch"
sudo chmod +x "$MACOS_PATH/launch"

# Create icon set
echo "🎨 Creating app icon..."
mkdir -p icon.iconset
for size in 16 32 128 256 512; do
    sips -z $size $size chipper.png --out icon.iconset/icon_${size}x${size}.png
    sips -z $((size*2)) $((size*2)) chipper.png --out icon.iconset/icon_${size}x${size}@2x.png
done
iconutil -c icns icon.iconset -o "/tmp/AppIcon.icns"
sudo mv "/tmp/AppIcon.icns" "$RESOURCES_PATH/AppIcon.icns"
rm -rf icon.iconset

# Set permissions
echo "🔒 Setting permissions..."
# Set ownership to current user for the MacOS directory
CURRENT_USER=$(whoami)
sudo chown -R "$CURRENT_USER:staff" "$MACOS_PATH"
sudo chmod -R 755 "$MACOS_PATH"
sudo chmod 777 "$MACOS_PATH/logs"

# Keep root ownership for the rest of the app bundle
sudo chown -R root:wheel "$APP_PATH"
sudo chown -R root:wheel "$RESOURCES_PATH"
sudo chown -R root:wheel "$FRAMEWORKS_PATH"
sudo chown root:wheel "$CONTENTS_PATH"
sudo chown root:wheel "$APP_PATH"

# Ensure the build script is executable
sudo chmod +x "$MACOS_PATH/build_macos_app.sh"

# Copy git info for version tracking
echo "📝 Adding version information..."
sudo cp -r .git "$MACOS_PATH/"
sudo chmod -R 755 "$MACOS_PATH/.git"

# Get current version
CURRENT_VERSION=$(git describe --tags --always)
echo "✨ App bundle created successfully! Version: $CURRENT_VERSION"
echo "🚀 You can now launch Knowledge Chipper from your Applications folder"