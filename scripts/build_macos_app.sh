#!/bin/bash

# Exit on any error
set -e

echo "🔄 Checking for updates..."
echo "##PERCENT## 0 Starting updater"

# Parse arguments
SKIP_INSTALL=0
MAKE_DMG=0
INCREMENTAL=0
for arg in "$@"; do
  case "$arg" in
    --no-install|--skip-install)
      SKIP_INSTALL=1
      ;;
    --make-dmg)
      MAKE_DMG=1
      ;;
    --incremental)
      INCREMENTAL=1
      ;;
  esac
done

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
# Go to the project root (parent of scripts directory)
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

# Determine current user early for ownership adjustments
CURRENT_USER=$(whoami)

# Store current branch name (fallback to main)
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo main)

# Pull latest code safely without corrupting local state (avoids stash/autostash)
echo "⬇️ Checking for updates (Git)..."
echo "##PERCENT## 5 Fetching updates"
git fetch origin || true

# If the working tree is clean, try a rebase pull without autostash
if git diff-index --quiet HEAD --; then
  if git pull --rebase origin "$CURRENT_BRANCH"; then
    echo "✅ Repository up to date."
    echo "##PERCENT## 10 Repository ready"
  else
    echo "ℹ️  Git pull failed; using local version for this build."
  fi
else
  echo "ℹ️  Local changes detected; skipping pull. Using local version for this build."
fi

# Strict version detection (fail-fast, no fallback)
if [ ! -f "pyproject.toml" ]; then
  echo "❌ pyproject.toml not found in $PROJECT_ROOT. Aborting."
  exit 1
fi
CURRENT_VERSION=$(python3 - <<'PY'
import sys, pathlib
pp = pathlib.Path('pyproject.toml')
try:
    import tomllib
except Exception as e:
    sys.stderr.write('❌ Python tomllib not available (requires Python 3.11+). Install python3.11+ and retry.\n')
    sys.exit(2)
with pp.open('rb') as f:
    data = tomllib.load(f)
ver = (data.get('project') or {}).get('version')
if not ver:
    sys.stderr.write('❌ Version missing in pyproject.toml [project.version]. Aborting.\n')
    sys.exit(3)
print(ver)
PY
)
if [ -z "$CURRENT_VERSION" ]; then
  echo "❌ Could not determine version from pyproject.toml. Aborting."
  exit 1
fi

echo "🏗️ Building Knowledge_Chipper.app... (version $CURRENT_VERSION)"
echo "##PERCENT## 15 Preparing build"

# Determine total steps for accurate high-level progress (no artificial heartbeats)
# When installing to /Applications, there are extra steps at the end
if [ "$SKIP_INSTALL" -eq 0 ]; then
  TOTAL_STEPS=16
else
  TOTAL_STEPS=12
fi
STEP=0
next_step() {
  STEP=$((STEP+1))
  echo "##PROGRESS## $STEP/$TOTAL_STEPS: $1"
}

# Define paths
APP_NAME="Knowledge_Chipper.app"
APP_PATH="/Applications/$APP_NAME"               # Final destination
CONTENTS_PATH="$APP_PATH/Contents"
MACOS_PATH="$CONTENTS_PATH/MacOS"
RESOURCES_PATH="$CONTENTS_PATH/Resources"
FRAMEWORKS_PATH="$CONTENTS_PATH/Frameworks"

# Output directories for artifacts (use .noindex so Spotlight ignores staging copies)
DIST_DIR="$PROJECT_ROOT/dist"
DMG_STAGING="$DIST_DIR/dmg_staging.noindex"

# Build in a user-writable staging directory, then move to /Applications at the end
BUILD_ROOT="$SCRIPT_DIR/.app_build"
BUILD_APP_PATH="$BUILD_ROOT/$APP_NAME"
BUILD_CONTENTS_PATH="$BUILD_APP_PATH/Contents"
BUILD_MACOS_PATH="$BUILD_CONTENTS_PATH/MacOS"
BUILD_RESOURCES_PATH="$BUILD_CONTENTS_PATH/Resources"
BUILD_FRAMEWORKS_PATH="$BUILD_CONTENTS_PATH/Frameworks"

# Create or reuse staging
echo "📁 Preparing app bundle structure (staging)..."
next_step "Prepare staging"
echo "##PERCENT## 18 Preparing staging"
if [ "$INCREMENTAL" -eq 1 ] && [ -d "$BUILD_APP_PATH" ]; then
  echo "🔄 Incremental mode: reusing existing staged app at $BUILD_APP_PATH"
else
  rm -rf "$BUILD_ROOT"
  mkdir -p "$BUILD_MACOS_PATH" "$BUILD_RESOURCES_PATH" "$BUILD_FRAMEWORKS_PATH"
fi

# Rsync project files into staging (delete removed files to avoid orphans)
echo "📦 Syncing project files..."
next_step "Sync project files"
echo "##PERCENT## 22 Sync project files"
mkdir -p "$BUILD_MACOS_PATH"
# Exclude packaging metadata to avoid stale version overrides inside the app bundle
rsync -a --delete \
  --exclude 'knowledge_system.egg-info/' \
  --exclude '*.egg-info' \
  --exclude '*.dist-info' \
  src/ "$BUILD_MACOS_PATH/src/"
rsync -a --delete config/ "$BUILD_MACOS_PATH/config/"
cp requirements.txt "$BUILD_MACOS_PATH/"
cp scripts/build_macos_app.sh "$BUILD_MACOS_PATH/"
# Safety: remove any stray packaging metadata if present
find "$BUILD_MACOS_PATH/src" -type d \( -name '*.egg-info' -o -name '*.dist-info' \) -prune -exec rm -rf {} + 2>/dev/null || true

# Explicitly exclude large model files from the app bundle
echo "🚫 Excluding large model files from app bundle..."
next_step "Exclude large files"
echo "##PERCENT## 28 Exclude large files"
if [ -d "models" ]; then
    echo "ℹ️  Found local models/ directory - excluding from app bundle ($(du -sh models | cut -f1) would be saved)"
fi
find "$BUILD_MACOS_PATH" -name "*.bin" -delete 2>/dev/null || true

# Set up virtual environment
echo "🐍 Setting up Python virtual environment..."
next_step "Create virtual environment"
echo "##PERCENT## 30 Start virtual environment setup"
PYTHON_BIN="$(command -v /opt/homebrew/bin/python3.13 || command -v python3.13 || true)"
if [ -z "$PYTHON_BIN" ]; then
    echo "❌ Python 3.13 not found. Please install with: brew install python@3.13"
    exit 1
fi

VENV_DIR="$BUILD_MACOS_PATH/venv"
REQS_HASH_FILE="$BUILD_MACOS_PATH/.requirements.sha256"
NEW_REQS_HASH=$(shasum -a 256 requirements.txt | awk '{print $1}')
RECREATE_VENV=0
if [ "$INCREMENTAL" -eq 1 ] && [ -d "$VENV_DIR" ] && [ -f "$REQS_HASH_FILE" ]; then
  OLD_HASH=$(cat "$REQS_HASH_FILE" 2>/dev/null || echo "")
  if [ "$OLD_HASH" != "$NEW_REQS_HASH" ]; then
    echo "📦 requirements.txt changed → recreating venv"
    RECREATE_VENV=1
  else
    echo "📦 requirements.txt unchanged → reusing venv"
  fi
else
  RECREATE_VENV=1
fi

if [ "$RECREATE_VENV" -eq 1 ]; then
  rm -rf "$VENV_DIR"
  "$PYTHON_BIN" -m venv "$VENV_DIR"
else
  : # reuse existing venv
fi

# Upgrade pip (separate step for clearer progress)
next_step "Upgrade pip"
"$VENV_DIR/bin/python" -m pip install --upgrade pip

# Install or update requirements (real work, no fake heartbeats)
next_step "Install requirements"
if [ "$RECREATE_VENV" -eq 1 ]; then
  "$VENV_DIR/bin/python" -m pip install -r "$BUILD_MACOS_PATH/requirements.txt"
  echo "$NEW_REQS_HASH" > "$REQS_HASH_FILE"
else
  "$VENV_DIR/bin/python" -m pip install -r "$BUILD_MACOS_PATH/requirements.txt" --upgrade --no-deps
  "$VENV_DIR/bin/python" -m pip check || true
fi

# Install HCE optional dependencies into the app bundle venv
next_step "Install HCE optional dependencies"
"$VENV_DIR/bin/python" -m pip install sentence-transformers scikit-learn || true

echo "🎯 Excluding heavy ML dependencies (torch, transformers, etc.) from app bundle"
echo "ℹ️  Heavy dependencies will be installed automatically when needed"

# Verify critical dependencies are installed
echo "🔍 Verifying critical dependencies..."
next_step "Verify dependencies"
echo "##PERCENT## 55 Verify critical dependencies"
"$VENV_DIR/bin/python" -c "import sqlalchemy; print('✅ SQLAlchemy:', sqlalchemy.__version__)" || { echo "❌ SQLAlchemy missing, installing..."; "$VENV_DIR/bin/python" -m pip install sqlalchemy alembic; }
"$VENV_DIR/bin/python" -c "import psutil; print('✅ psutil:', psutil.__version__)" || { echo "❌ psutil missing, installing..."; "$VENV_DIR/bin/python" -m pip install psutil; }
"$VENV_DIR/bin/python" -c "import openai; print('✅ OpenAI:', openai.__version__)" || { echo "❌ OpenAI missing, installing..."; "$VENV_DIR/bin/python" -m pip install openai; }

# Create minimal pyproject.toml for runtime metadata (not used for build)
cat > "/tmp/pyproject.toml" << EOF
[build-system]
requires = ["setuptools>=61.0"]
build-backend = "setuptools.build_meta"

[project]
name = "knowledge_system"
version = "$CURRENT_VERSION"
authors = [ { name="Matthew Greer" } ]
description = "Knowledge Chipper - Your Personal Knowledge Assistant"
requires-python = ">=3.13"

[tool.setuptools]
packages = ["knowledge_system"]
package-dir = {"" = "src"}
EOF
mv "/tmp/pyproject.toml" "$BUILD_MACOS_PATH/pyproject.toml"
chown "$CURRENT_USER:staff" "$BUILD_MACOS_PATH/pyproject.toml" 2>/dev/null || true

# Ensure venv ownership (should already be current user in staging)
chown -R "$CURRENT_USER:staff" "$VENV_DIR" 2>/dev/null || true

# Create logs directory in staging so permissions can be applied post-install
mkdir -p "$BUILD_MACOS_PATH/logs"

# Create Info.plist (with proper version)
echo "📝 Creating Info.plist..."
next_step "Create metadata"
echo "##PERCENT## 60 Create metadata"
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
    <string>$CURRENT_VERSION</string>
    <key>LSMinimumSystemVersion</key>
    <string>10.12</string>
    <key>NSHighResolutionCapable</key>
    <true/>
    <key>LSRequiresNativeExecution</key>
    <true/>
</dict>
</plist>
EOF
mkdir -p "$BUILD_CONTENTS_PATH"
mv "/tmp/Info.plist" "$BUILD_CONTENTS_PATH/Info.plist"

# Create launch script
echo "📜 Creating launch script..."
next_step "Create launch script"
echo "##PERCENT## 65 Create launch script"
cat > "/tmp/launch" << EOF
#!/bin/bash
APP_DIR="\$( cd "\$( dirname "\${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
LOG_FILE="\$APP_DIR/logs/knowledge_system.log"
mkdir -p "\$APP_DIR/logs"; touch "\$LOG_FILE"; chmod 666 "\$LOG_FILE"
if [ -f "\$APP_DIR/version.txt" ]; then echo "Launching Knowledge Chipper:" >> "\$LOG_FILE"; cat "\$APP_DIR/version.txt" >> "\$LOG_FILE"; fi
source "\$APP_DIR/venv/bin/activate"
export PYTHONPATH="\$APP_DIR/src:\$PYTHONPATH"
cd "\$APP_DIR"
echo "Current directory: \$(pwd)" >> "\$LOG_FILE"
echo "PYTHONPATH: \$PYTHONPATH" >> "\$LOG_FILE"
echo "Python version: \$("\$APP_DIR/venv/bin/python" --version)" >> "\$LOG_FILE"
echo "Virtual env: \$VIRTUAL_ENV" >> "\$LOG_FILE"
echo "Architecture: \$(arch)" >> "\$LOG_FILE"
echo "Launching GUI..." >> "\$LOG_FILE"
if [[ "\$(uname -m)" == "arm64" ]]; then
    exec arch -arm64 "\$APP_DIR/venv/bin/python" -m knowledge_system.gui.__main__ 2>&1 | tee -a "\$LOG_FILE"
else
    exec "\$APP_DIR/venv/bin/python" -m knowledge_system.gui.__main__ 2>&1 | tee -a "\$LOG_FILE"
fi
EOF
mv "/tmp/launch" "$BUILD_MACOS_PATH/launch"
chmod +x "$BUILD_MACOS_PATH/launch"

# Create app icon
echo "🎨 Creating app icon..."
next_step "Create assets"
echo "##PERCENT## 70 Create assets"
mkdir -p icon.iconset
for size in 16 32 128 256 512; do
    sips -z $size $size Assets/chipper.png --out icon.iconset/icon_${size}x${size}.png
    sips -z $((size*2)) $((size*2)) Assets/chipper.png --out icon.iconset/icon_${size}x${size}@2x.png
done
iconutil -c icns icon.iconset -o "/tmp/AppIcon.icns"
mv "/tmp/AppIcon.icns" "$BUILD_RESOURCES_PATH/AppIcon.icns"
rm -rf icon.iconset

# Preflight import check (fail-fast)
echo "🧪 Preflight import check..."
next_step "Preflight import check"
echo "##PERCENT## 75 Preflight import check"
if ! PYTHONPATH="$BUILD_MACOS_PATH/src:${PYTHONPATH}" "$VENV_DIR/bin/python" -c "import knowledge_system.gui.__main__"; then
  echo "❌ Preflight import failed. Aborting build."
  exit 1
fi

# Version file for logging (write into staged app before install/move)
echo "📝 Adding version information..."
next_step "Add version information"
echo "##PERCENT## 78 Add version information"
CURRENT_DATE=$(date +"%Y-%m-%d")
cat > "$BUILD_MACOS_PATH/version.txt" << EOF
VERSION=$CURRENT_VERSION
BRANCH=$CURRENT_BRANCH
BUILD_DATE=$CURRENT_DATE
EOF

# Install or stage only
if [ "$SKIP_INSTALL" -eq 0 ]; then
  echo "📦 Installing app to /Applications..."
  next_step "Install app"
  sudo rm -rf "$APP_PATH"
  sudo mv "$BUILD_APP_PATH" "$APP_PATH"
  echo "🔒 Setting permissions..."
  sudo chown -R root:wheel "$APP_PATH"
  sudo chmod -R 755 "$APP_PATH"
  sudo mkdir -p "$MACOS_PATH/logs" && sudo chmod 777 "$MACOS_PATH/logs"
  sudo chown "$CURRENT_USER:staff" "$MACOS_PATH/build_macos_app.sh" || true
  sudo chmod 755 "$MACOS_PATH/build_macos_app.sh" || true

  echo "🐍 Recreating virtual environment at final location..."
  next_step "Recreate venv (final location)"
  # Recreate venv to avoid hardcoded paths from staging
  sudo rm -rf "$MACOS_PATH/venv"
  PYTHON_BIN_INSTALL="$(command -v /opt/homebrew/bin/python3.13 || command -v python3.13 || true)"
  if [ -z "$PYTHON_BIN_INSTALL" ]; then
    echo "❌ Python 3.13 not found for install step. Please: brew install python@3.13"
    exit 1
  fi
  sudo "$PYTHON_BIN_INSTALL" -m venv "$MACOS_PATH/venv"
  next_step "Upgrade pip (final)"
  sudo -H "$MACOS_PATH/venv/bin/python" -m pip install --upgrade pip
  next_step "Install requirements (final)"
  sudo -H "$MACOS_PATH/venv/bin/python" -m pip install -r "$MACOS_PATH/requirements.txt"
  # Post-install preflight
  next_step "Final verification"
  if ! PYTHONPATH="$MACOS_PATH/src:${PYTHONPATH}" "$MACOS_PATH/venv/bin/python" -c "import knowledge_system.gui.__main__"; then
    echo "❌ Post-install preflight import failed. Aborting."
    exit 1
  fi
else
  echo "ℹ️  Skipping install to /Applications (no-install mode)"
fi

echo "✨ App bundle created successfully! Version: $CURRENT_VERSION"
echo "##PERCENT## 100 Complete"
echo "🎯 Large model files excluded - they'll download automatically when needed"
if [ "$SKIP_INSTALL" -eq 0 ]; then
  echo "🚀 You can now launch Knowledge Chipper from your Applications folder"
else
  echo "🚀 Staged app is at: $BUILD_APP_PATH"
fi

# Optionally create a DMG from the staged app
# Skip DMG creation during in-app updates (IN_APP_UPDATER=1) to significantly reduce update time
# Still allow DMG when explicitly requested with --make-dmg, or when running manually with --skip-install outside the app
if [ "$MAKE_DMG" -eq 1 ] || { [ "$SKIP_INSTALL" -eq 1 ] && [ "${IN_APP_UPDATER:-0}" != "1" ]; }; then
  echo "📦 Creating DMG..."
  mkdir -p "$DMG_STAGING/root" "$DIST_DIR"
  rm -rf "$DMG_STAGING/root"/*
  # Strip extended attributes to avoid Finder copy errors
  /usr/bin/xattr -rc "$BUILD_APP_PATH" || true
  cp -R "$BUILD_APP_PATH" "$DMG_STAGING/root/"
  ln -sf /Applications "$DMG_STAGING/root/Applications"
  hdiutil create -volname "Knowledge Chipper" -srcfolder "$DMG_STAGING/root" -ov -format UDZO "$DIST_DIR/Knowledge_Chipper-${CURRENT_VERSION}.dmg"
  echo "✅ DMG created at: $DIST_DIR/Knowledge_Chipper-${CURRENT_VERSION}.dmg"
  # Clean up staging to avoid Spotlight finding duplicate app bundles
  rm -rf "$DMG_STAGING"
fi
