#!/bin/bash

# Exit on any error
set -e

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
sudo chown -R root:wheel "$APP_PATH"
sudo chmod -R 755 "$APP_PATH"
sudo chmod 777 "$MACOS_PATH/logs"

echo "✨ App bundle created successfully!"
echo "🚀 You can now launch Knowledge Chipper from your Applications folder"
