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
cp scripts/build_macos_app.sh "$BUILD_MACOS_PATH/"

# Explicitly exclude large model files from the app bundle
echo "🚫 Excluding large model files from app bundle..."
# Models will be downloaded at runtime to ~/.cache/whisper-cpp/
# This significantly reduces DMG size (models can be 75MB-3GB each)
if [ -d "models" ]; then
    echo "ℹ️  Found local models/ directory - excluding from app bundle ($(du -sh models | cut -f1) would be saved)"
fi
# Ensure no .bin files are accidentally copied
find "$BUILD_MACOS_PATH" -name "*.bin" -delete 2>/dev/null || true

# Set up virtual environment
echo "🐍 Setting up Python virtual environment..."
# Prefer Python 3.13 from Homebrew (ARM64 native)
PYTHON_BIN="$(command -v /opt/homebrew/bin/python3.13 || command -v python3.13 || true)"
if [ -z "$PYTHON_BIN" ]; then
    echo "❌ Python 3.13 not found. Please install with: brew install python@3.13"
    exit 1
fi

# Create venv directly inside the staging app bundle
rm -rf "$BUILD_MACOS_PATH/venv"
"$PYTHON_BIN" -m venv "$BUILD_MACOS_PATH/venv"

# Install packages in the venv with proper path handling
echo "📦 Installing Python dependencies (lightweight core)..."
"$BUILD_MACOS_PATH/venv/bin/python" -m pip install --upgrade pip
"$BUILD_MACOS_PATH/venv/bin/python" -m pip install -r "$BUILD_MACOS_PATH/requirements.txt"

echo "🎯 Excluding heavy ML dependencies (torch, transformers, etc.) from app bundle"
echo "ℹ️  Heavy dependencies will be installed automatically when needed"

# Verify critical dependencies are installed
echo "🔍 Verifying critical dependencies..."
"$BUILD_MACOS_PATH/venv/bin/python" -c "import sqlalchemy; print('✅ SQLAlchemy:', sqlalchemy.__version__)" || {
    echo "❌ SQLAlchemy missing, installing..."
    "$BUILD_MACOS_PATH/venv/bin/python" -m pip install sqlalchemy alembic
}

"$BUILD_MACOS_PATH/venv/bin/python" -c "import psutil; print('✅ psutil:', psutil.__version__)" || {
    echo "❌ psutil missing, installing..."
    "$BUILD_MACOS_PATH/venv/bin/python" -m pip install psutil
}

"$BUILD_MACOS_PATH/venv/bin/python" -c "import openai; print('✅ OpenAI:', openai.__version__)" || {
    echo "❌ OpenAI missing, installing..."
    "$BUILD_MACOS_PATH/venv/bin/python" -m pip install openai
}

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
# First check if we're on Apple Silicon
if [[ "\$(uname -m)" == "arm64" ]]; then
    exec arch -arm64 "\$APP_DIR/venv/bin/python" -m knowledge_system.gui.__main__ 2>&1 | tee -a "\$LOG_FILE"
else
    exec "\$APP_DIR/venv/bin/python" -m knowledge_system.gui.__main__ 2>&1 | tee -a "\$LOG_FILE"
fi
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
sudo chown "$CURRENT_USER:staff" "$MACOS_PATH/scripts/build_macos_app.sh"
sudo chmod 755 "$MACOS_PATH/scripts/build_macos_app.sh"

# Update version file and Python version.py with current build date
echo "📝 Adding version information..."
PY_VER_FILE="$SCRIPT_DIR/src/knowledge_system/version.py"
CURRENT_DATE=$(date +"%Y-%m-%d")

# Generate clean version for display (user wants just base version)
CURRENT_BRANCH=$(git branch --show-current 2>/dev/null || echo "main")

# Get the base version from pyproject.toml if available
if [ -f "pyproject.toml" ]; then
  CURRENT_VERSION=$(grep '^version\s*=\s*"' pyproject.toml | sed -E 's/.*"([^"]+)".*/\1/')
  echo "📋 Using version from pyproject.toml: $CURRENT_VERSION"
else
  # Fallback to git tags but clean it up for display
  if git describe --tags --match "v*" >/dev/null 2>&1; then
    GIT_VERSION=$(git describe --tags --match "v*" 2>/dev/null)
    # Extract just the base version (3.0.0 from v3.0.0-4-g707477f)
    CURRENT_VERSION=$(echo "$GIT_VERSION" | sed 's/^v//' | sed 's/-[0-9]*-g[a-f0-9]*$//')
    echo "📋 Using cleaned version from git: $CURRENT_VERSION"
  else
    # Fallback to version.py file
    if [ -f "$PY_VER_FILE" ]; then
      CURRENT_VERSION=$(grep '^VERSION\s*=\s*"' "$PY_VER_FILE" | sed -E 's/.*"([^"]+)".*/\1/')
    else
      CURRENT_VERSION="3.0.1"
    fi
  fi
fi

# Update the Python version.py file in the app bundle with current date
cat > "/tmp/version.py" << EOF
# Auto-generated version info
VERSION = "$CURRENT_VERSION"
BRANCH = "$CURRENT_BRANCH"
BUILD_DATE = "$CURRENT_DATE"
EOF
sudo mv "/tmp/version.py" "$MACOS_PATH/src/knowledge_system/version.py"

# Also create version.txt for logging
cat > "/tmp/version.txt" << EOF
VERSION=$CURRENT_VERSION
BRANCH=$CURRENT_BRANCH
BUILD_DATE=$CURRENT_DATE
EOF
sudo mv "/tmp/version.txt" "$MACOS_PATH/version.txt"

# Get current version for final echo
echo "✨ App bundle created successfully! Version: $CURRENT_VERSION"
echo "🎯 Large model files excluded - they'll download automatically when needed"
echo "🚀 You can now launch Knowledge Chipper from your Applications folder"
