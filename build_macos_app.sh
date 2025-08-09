#!/bin/bash

# Exit on any error
set -e

echo "🔄 Checking for updates..."

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
cd "$SCRIPT_DIR"

# Determine current user early for ownership adjustments
CURRENT_USER=$(whoami)

# Store current branch name (fallback to main)
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo main)

# Pull latest code safely without corrupting local state (avoids stash/autostash)
echo "⬇️ Checking for updates (Git)..."
git fetch origin || true

# If the working tree is clean, try a rebase pull without autostash
if git diff-index --quiet HEAD --; then
  if git pull --rebase origin "$CURRENT_BRANCH"; then
    echo "✅ Repository up to date."
  else
    echo "ℹ️  Git pull failed; using local version for this build."
  fi
else
  echo "ℹ️  Local changes detected; skipping pull. Using local version for this build."
fi

echo "🏗️ Building Knowledge_Chipper.app..."

# Define paths
APP_NAME="Knowledge_Chipper.app"
APP_PATH="/Applications/$APP_NAME"               # Final destination
CONTENTS_PATH="$APP_PATH/Contents"
MACOS_PATH="$CONTENTS_PATH/MacOS"
RESOURCES_PATH="$CONTENTS_PATH/Resources"
FRAMEWORKS_PATH="$CONTENTS_PATH/Frameworks"

# Build in a user-writable staging directory, then move to /Applications at the end
BUILD_ROOT="$SCRIPT_DIR/.app_build"
BUILD_APP_PATH="$BUILD_ROOT/$APP_NAME"
BUILD_CONTENTS_PATH="$BUILD_APP_PATH/Contents"
BUILD_MACOS_PATH="$BUILD_CONTENTS_PATH/MacOS"
BUILD_RESOURCES_PATH="$BUILD_CONTENTS_PATH/Resources"
BUILD_FRAMEWORKS_PATH="$BUILD_CONTENTS_PATH/Frameworks"

# Create directory structure
echo "📁 Creating app bundle structure (staging)..."
rm -rf "$BUILD_ROOT"
mkdir -p "$BUILD_MACOS_PATH" "$BUILD_RESOURCES_PATH" "$BUILD_FRAMEWORKS_PATH"

# Copy project files
echo "📦 Copying project files..."
cp -r src "$BUILD_MACOS_PATH/"
cp -r config "$BUILD_MACOS_PATH/"
cp requirements.txt "$BUILD_MACOS_PATH/"
cp build_macos_app.sh "$BUILD_MACOS_PATH/"

# Set up virtual environment
echo "🐍 Setting up Python virtual environment..."
# Prefer Python 3.13 from Homebrew
PYTHON_BIN="$(command -v python3.13 || command -v /opt/homebrew/bin/python3.13 || true)"
if [ -z "$PYTHON_BIN" ]; then
    echo "❌ Python 3.13 not found. Please install with: brew install python@3.13"
    exit 1
fi

# Create venv directly inside the staging app bundle
rm -rf "$BUILD_MACOS_PATH/venv"
"$PYTHON_BIN" -m venv "$BUILD_MACOS_PATH/venv"

# Install packages in the venv
"$BUILD_MACOS_PATH/venv/bin/python" -m pip install --upgrade pip
"$BUILD_MACOS_PATH/venv/bin/python" -m pip install -r "$BUILD_MACOS_PATH/requirements.txt"
"$BUILD_MACOS_PATH/venv/bin/python" -m pip install beautifulsoup4 youtube-transcript-api pydantic-settings

# Create pyproject.toml for editable install
cat > "/tmp/pyproject.toml" << EOF
[build-system]
requires = ["setuptools>=61.0"]
build-backend = "setuptools.build_meta"

[project]
name = "knowledge_system"
version = "1.0.0"
authors = [
  { name="Matthew Greer" },
]
description = "Knowledge Chipper - Your Personal Knowledge Assistant"
requires-python = ">=3.13"

[tool.setuptools]
packages = ["knowledge_system"]
package-dir = {"" = "src"}
EOF

# Move pyproject.toml to MacOS directory
mv "/tmp/pyproject.toml" "$BUILD_MACOS_PATH/pyproject.toml"
chown "$CURRENT_USER:staff" "$BUILD_MACOS_PATH/pyproject.toml" 2>/dev/null || true

# Skip editable install - just ensure PYTHONPATH is set in launch script

# Ensure venv ownership (should already be current user in staging)
chown -R "$CURRENT_USER:staff" "$BUILD_MACOS_PATH/venv" 2>/dev/null || true

# Create logs directory in staging so permissions can be applied post-install
mkdir -p "$BUILD_MACOS_PATH/logs"

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
    <key>LSRequiresNativeExecution</key>
    <true/>
</dict>
</plist>
EOF
mv "/tmp/Info.plist" "$BUILD_CONTENTS_PATH/Info.plist"

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

# Log the version being launched
if [ -f "\$APP_DIR/version.txt" ]; then
    echo "Launching Knowledge Chipper:" >> "\$LOG_FILE"
    cat "\$APP_DIR/version.txt" >> "\$LOG_FILE"
fi

# Activate virtual environment
source "\$APP_DIR/venv/bin/activate"

# Set PYTHONPATH to include src directory
export PYTHONPATH="\$APP_DIR/src:\$PYTHONPATH"

# Launch the GUI with debug output
cd "\$APP_DIR"
echo "Current directory: \$(pwd)" >> "\$LOG_FILE"
echo "PYTHONPATH: \$PYTHONPATH" >> "\$LOG_FILE"
echo "Python version: \$("\$APP_DIR/venv/bin/python" --version)" >> "\$LOG_FILE"
echo "Virtual env: \$VIRTUAL_ENV" >> "\$LOG_FILE"
echo "Architecture: \$(arch)" >> "\$LOG_FILE"
echo "Launching GUI..." >> "\$LOG_FILE"

# Force native ARM64 execution using the venv python explicitly
exec arch -arm64 "\$APP_DIR/venv/bin/python" -m knowledge_system.gui.__main__ 2>&1 | tee -a "\$LOG_FILE"
EOF
mv "/tmp/launch" "$BUILD_MACOS_PATH/launch"
chmod +x "$BUILD_MACOS_PATH/launch"

# Create icon set
echo "🎨 Creating app icon..."
mkdir -p icon.iconset
for size in 16 32 128 256 512; do
    sips -z $size $size chipper.png --out icon.iconset/icon_${size}x${size}.png
    sips -z $((size*2)) $((size*2)) chipper.png --out icon.iconset/icon_${size}x${size}@2x.png
done
iconutil -c icns icon.iconset -o "/tmp/AppIcon.icns"
mv "/tmp/AppIcon.icns" "$BUILD_RESOURCES_PATH/AppIcon.icns"
rm -rf icon.iconset

# Move staged app into /Applications and set permissions
echo "📦 Installing app to /Applications..."
sudo rm -rf "$APP_PATH"
sudo mv "$BUILD_APP_PATH" "$APP_PATH"

echo "🔒 Setting permissions..."
sudo chown -R root:wheel "$APP_PATH"
sudo chmod -R 755 "$APP_PATH"
# Ensure logs directory exists and is writable
sudo mkdir -p "$MACOS_PATH/logs"
sudo chmod 777 "$MACOS_PATH/logs"
sudo chown "$CURRENT_USER:staff" "$MACOS_PATH/build_macos_app.sh"
sudo chmod 755 "$MACOS_PATH/build_macos_app.sh"

# Create version file from src/knowledge_system/version.py for user-facing display
echo "📝 Adding version information..."
PY_VER_FILE="$SCRIPT_DIR/src/knowledge_system/version.py"
if [ -f "$PY_VER_FILE" ]; then
  CURRENT_VERSION=$(grep '^VERSION\s*=\s*"' "$PY_VER_FILE" | sed -E 's/.*"([^"]+)".*/\1/')
  CURRENT_BRANCH=$(git branch --show-current)
  CURRENT_DATE=$(grep '^BUILD_DATE\s*=\s*"' "$PY_VER_FILE" | sed -E 's/.*"([^"]+)".*/\1/')
else
  # Fallback to git if the file is missing
  CURRENT_VERSION=$(git describe --tags --always)
  CURRENT_BRANCH=$(git branch --show-current)
  CURRENT_DATE=$(date +"%Y-%m-%d")
fi
cat > "/tmp/version.txt" << EOF
VERSION=$CURRENT_VERSION
BRANCH=$CURRENT_BRANCH
BUILD_DATE=$CURRENT_DATE
EOF
sudo mv "/tmp/version.txt" "$MACOS_PATH/version.txt"

# Get current version for final echo
echo "✨ App bundle created successfully! Version: $CURRENT_VERSION"
echo "🚀 You can now launch Knowledge Chipper from your Applications folder"
