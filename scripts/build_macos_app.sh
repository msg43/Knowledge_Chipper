#!/bin/bash

# Exit on any error
set -e

echo "🔄 Checking for updates..."
echo "##PERCENT## 0 Starting updater"

# Parse arguments
SKIP_INSTALL=0
MAKE_DMG=0
INCREMENTAL=0
# Optional extras to include in the bundled app (defaults: diarization and hce ON)
WITH_DIARIZATION=1
WITH_HCE=1
WITH_CUDA=0
# Default to bundling all models for complete offline experience
BUNDLE_ALL_MODELS=${BUNDLE_ALL_MODELS:-1}
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
    --with-diarization)
      WITH_DIARIZATION=1
      ;;
    --with-hce)
      WITH_HCE=1
      ;;
    --with-cuda)
      WITH_CUDA=1
      ;;
    --full)
      WITH_DIARIZATION=1
      WITH_HCE=1
      WITH_CUDA=1
      ;;
    --bundle-all)
      BUNDLE_ALL_MODELS=1
      ;;
    --no-bundle)
      BUNDLE_ALL_MODELS=0
      ;;
    --clean)
      echo "🧹 Cleaning staging directory..."
      rm -rf "$SCRIPT_DIR/.app_build"
      echo "✅ Staging directory cleaned"
      exit 0
      ;;
    --help|-h)
      echo "Usage: $0 [OPTIONS]"
      echo ""
      echo "Options:"
      echo "  --skip-install    Build to staging only (don't install to /Applications)"
      echo "  --make-dmg        Create DMG after building"
      echo "  --incremental     Reuse existing staging directory if available"
      echo "  --clean           Clean staging directory and exit"
      echo "  --bundle-all      Bundle all models for offline use (default)"
      echo "  --no-bundle       Skip model bundling"
      echo "  --with-diarization Include speaker diarization (default)"
      echo "  --with-hce        Include HCE modules (default)"
      echo "  --with-cuda       Include CUDA support"
      echo "  --full            Include all optional features"
      echo "  --help, -h        Show this help message"
      echo ""
      echo "Examples:"
      echo "  $0 --skip-install --make-dmg    # Build DMG without installing"
      echo "  $0 --clean                      # Clean staging directory"
      echo "  $0 --incremental                # Fast incremental build"
      exit 0
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

echo "🏗️ Building Skip the Podcast Desktop.app... (version $CURRENT_VERSION)"
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
APP_NAME="Skip the Podcast Desktop.app"
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
  echo "🧹 Cleaning staging directory for fresh build..."
  rm -rf "$BUILD_ROOT"
  echo "📁 Creating fresh staging structure..."
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

# Copy config as fallback templates (app now uses macOS standard locations)
echo "📝 Including config templates for fallback..."
rsync -a --delete config/ "$BUILD_MACOS_PATH/config/"

# Create configuration guide for macOS paths
cat > "$BUILD_MACOS_PATH/MACOS_CONFIGURATION.md" << 'CONFIG_EOF'
# Skip the Podcast Desktop - macOS Configuration

## Configuration Locations

Skip the Podcast Desktop now follows Apple's macOS guidelines for file locations:

### Settings & Configuration
- **Primary**: `~/Library/Application Support/Skip the Podcast Desktop/Config/settings.yaml`
- **Credentials**: `~/Library/Application Support/Skip the Podcast Desktop/Config/credentials.yaml`
- **Fallback**: Files in this app bundle's `config/` directory (templates only)

### User Data
- **Database**: `~/Library/Application Support/Skip the Podcast Desktop/knowledge_system.db`
- **Output**: `~/Documents/Skip the Podcast Desktop/Output/`
- **Input**: `~/Documents/Skip the Podcast Desktop/Input/`

### Cache & Logs
- **Cache**: `~/Library/Caches/Skip the Podcast Desktop/`
- **Logs**: `~/Library/Logs/Skip the Podcast Desktop/`

## Benefits
- ✅ **Time Machine**: Automatically backs up your data
- ✅ **Updates**: Data survives app updates/reinstalls
- ✅ **Clean**: Separates app code from user data
- ✅ **Standard**: Follows Apple's guidelines

## Migration
The app automatically creates these directories and migrates settings as needed.
CONFIG_EOF

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

# Conditionally install optional extras into the staging venv
if [ "$WITH_HCE" -eq 1 ]; then
  next_step "Install HCE optional dependencies (staging)"
  # Install from project root (ensures pyproject.toml/extras resolution)
  "$VENV_DIR/bin/python" -m pip install -e "$PROJECT_ROOT"[hce] || {
    echo "⚠️ Failed to install HCE extras in staging; continuing"
  }
else
  echo "🎯 Skipping HCE heavy dependencies in staging (default)"
fi

if [ "$WITH_DIARIZATION" -eq 1 ]; then
  next_step "Install diarization dependencies (staging)"
  # Install from project root (ensures pyproject.toml/extras resolution)
  "$VENV_DIR/bin/python" -m pip install -e "$PROJECT_ROOT"[diarization] || {
    echo "⚠️ Failed to install diarization extras in staging; continuing"
  }
else
  echo "🎯 Skipping diarization dependencies in staging (default)"
fi

if [ "$WITH_CUDA" -eq 1 ]; then
  next_step "Install CUDA-related dependencies (staging)"
  # Install from project root (ensures pyproject.toml/extras resolution)
  "$VENV_DIR/bin/python" -m pip install -e "$PROJECT_ROOT"[cuda] || {
    echo "⚠️ Failed to install CUDA extras in staging; continuing"
  }
else
  echo "🎯 Skipping CUDA extras in staging (default)"
fi

if [ "$WITH_HCE" -eq 0 ] && [ "$WITH_DIARIZATION" -eq 0 ] && [ "$WITH_CUDA" -eq 0 ]; then
  echo "🎯 Excluding heavy ML dependencies (torch, transformers, etc.) from app bundle"
  echo "ℹ️  Heavy dependencies will be installed automatically when needed"
fi

# Verify critical dependencies are installed
echo "🔍 Verifying critical dependencies..."
next_step "Verify dependencies"
echo "##PERCENT## 55 Verify critical dependencies"
"$VENV_DIR/bin/python" -c "import sqlalchemy; print('✅ SQLAlchemy:', sqlalchemy.__version__)" || { echo "❌ SQLAlchemy missing, installing..."; "$VENV_DIR/bin/python" -m pip install sqlalchemy alembic; }
"$VENV_DIR/bin/python" -c "import psutil; print('✅ psutil:', psutil.__version__)" || { echo "❌ psutil missing, installing..."; "$VENV_DIR/bin/python" -m pip install psutil; }
"$VENV_DIR/bin/python" -c "import openai; print('✅ OpenAI:', openai.__version__)" || { echo "❌ OpenAI missing, installing..."; "$VENV_DIR/bin/python" -m pip install openai; }

# Copy full project pyproject.toml (includes optional dependency extras like [diarization])
if [ -f "$PROJECT_ROOT/pyproject.toml" ]; then
  cp "$PROJECT_ROOT/pyproject.toml" "$BUILD_MACOS_PATH/pyproject.toml"
  # Ensure version inside the copied pyproject matches CURRENT_VERSION (best-effort in-place replace)
  if command -v gsed >/dev/null 2>&1; then
    gsed -i "s/^version = \".*\"/version = \"$CURRENT_VERSION\"/" "$BUILD_MACOS_PATH/pyproject.toml" || true
  else
    sed -i '' "s/^version = \".*\"/version = \"$CURRENT_VERSION\"/" "$BUILD_MACOS_PATH/pyproject.toml" || true
  fi
  chown "$CURRENT_USER:staff" "$BUILD_MACOS_PATH/pyproject.toml" 2>/dev/null || true
else
  echo "⚠️  pyproject.toml not found at project root; extras installation inside app may fail."
fi

# Ensure venv ownership (should already be current user in staging)
chown -R "$CURRENT_USER:staff" "$VENV_DIR" 2>/dev/null || true

# Note: Logs now go to ~/Library/Logs/Skip the Podcast Desktop (macOS standard)
# Create a logs directory in app bundle for backward compatibility, but it won't be used
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
    <string>com.skipthepodcast.desktop</string>
    <key>CFBundleName</key>
    <string>Skip the Podcast Desktop</string>
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

# Use macOS standard locations for logs (not app bundle)
LOG_DIR="\$HOME/Library/Logs/Skip the Podcast Desktop"
mkdir -p "\$LOG_DIR"
LOG_FILE="\$LOG_DIR/knowledge_system.log"
touch "\$LOG_FILE"; chmod 644 "\$LOG_FILE"

echo "=== Skip the Podcast Desktop Launch \$(date) ===" >> "\$LOG_FILE"
if [ -f "\$APP_DIR/version.txt" ]; then
    echo "Version Info:" >> "\$LOG_FILE"
    cat "\$APP_DIR/version.txt" >> "\$LOG_FILE"
fi

# Check for bundled FFMPEG and set up environment
if [ -f "\$APP_DIR/setup_bundled_ffmpeg.sh" ]; then
    echo "Setting up bundled FFMPEG..." >> "\$LOG_FILE"
    source "\$APP_DIR/setup_bundled_ffmpeg.sh"
    echo "FFMPEG_PATH: \$FFMPEG_PATH" >> "\$LOG_FILE"
    echo "FFPROBE_PATH: \$FFPROBE_PATH" >> "\$LOG_FILE"
fi

# Check for bundled Pyannote model and set up environment
if [ -f "\$APP_DIR/setup_bundled_pyannote.sh" ]; then
    echo "Setting up bundled Pyannote model..." >> "\$LOG_FILE"
    source "\$APP_DIR/setup_bundled_pyannote.sh"
    echo "PYANNOTE_MODEL_PATH: \$PYANNOTE_MODEL_PATH" >> "\$LOG_FILE"
    echo "PYANNOTE_BUNDLED: \$PYANNOTE_BUNDLED" >> "\$LOG_FILE"
fi

# Check for bundled models (Whisper, Ollama, etc)
if [ -f "\$APP_DIR/setup_bundled_models.sh" ]; then
    echo "Setting up bundled models..." >> "\$LOG_FILE"
    source "\$APP_DIR/setup_bundled_models.sh"
    echo "MODELS_BUNDLED: \$MODELS_BUNDLED" >> "\$LOG_FILE"
    echo "WHISPER_CACHE_DIR: \$WHISPER_CACHE_DIR" >> "\$LOG_FILE"
    echo "OLLAMA_HOME: \$OLLAMA_HOME" >> "\$LOG_FILE"
fi

# Set up Python environment
source "\$APP_DIR/venv/bin/activate"
export PYTHONPATH="\$APP_DIR/src:\$PYTHONPATH"
cd "\$APP_DIR"

# Log environment info
echo "Current directory: \$(pwd)" >> "\$LOG_FILE"
echo "PYTHONPATH: \$PYTHONPATH" >> "\$LOG_FILE"
echo "Python version: \$("\$APP_DIR/venv/bin/python" --version)" >> "\$LOG_FILE"
echo "Virtual env: \$VIRTUAL_ENV" >> "\$LOG_FILE"
echo "Architecture: \$(arch)" >> "\$LOG_FILE"

# Initialize macOS paths on first run
echo "Initializing macOS standard paths..." >> "\$LOG_FILE"
"\$APP_DIR/venv/bin/python" -c "
try:
    from knowledge_system.utils.macos_paths import get_default_paths, log_paths_info
    log_paths_info()
    print('macOS paths initialized successfully')
except Exception as e:
    print(f'Path initialization warning: {e}')
" >> "\$LOG_FILE" 2>&1

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
    sips -z $size $size Assets/STP_Icon_1.png --out icon.iconset/icon_${size}x${size}.png
    sips -z $((size*2)) $((size*2)) Assets/STP_Icon_1.png --out icon.iconset/icon_${size}x${size}@2x.png
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
  # Logs now use macOS standard location, but keep legacy directory for compatibility
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

  # Ensure pyproject.toml exists at final app path for extras resolution
  if [ ! -f "$MACOS_PATH/pyproject.toml" ] && [ -f "$PROJECT_ROOT/pyproject.toml" ]; then
    sudo cp "$PROJECT_ROOT/pyproject.toml" "$MACOS_PATH/pyproject.toml"
  fi

  # Conditionally install extras in the final venv as well
  if [ "$WITH_HCE" -eq 1 ]; then
    next_step "Install HCE extras (final)"
    sudo -H "$MACOS_PATH/venv/bin/python" -m pip install -e "$MACOS_PATH"[hce] || {
      echo "⚠️ Failed to install HCE extras in final venv; continuing"
    }
  fi

  if [ "$WITH_DIARIZATION" -eq 1 ]; then
    next_step "Install diarization extras (final)"
    sudo -H "$MACOS_PATH/venv/bin/python" -m pip install -e "$MACOS_PATH"[diarization] || {
      echo "⚠️ Failed to install diarization extras in final venv; continuing"
    }
  fi

  if [ "$WITH_CUDA" -eq 1 ]; then
    next_step "Install CUDA extras (final)"
    sudo -H "$MACOS_PATH/venv/bin/python" -m pip install -e "$MACOS_PATH"[cuda] || {
      echo "⚠️ Failed to install CUDA extras in final venv; continuing"
    }
  fi
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

# Install FFMPEG into the app bundle for DMG distribution [[memory:7770522]]
if [ "$MAKE_DMG" -eq 1 ] || { [ "$SKIP_INSTALL" -eq 1 ] && [ "${IN_APP_UPDATER:-0}" != "1" ]; }; then
  echo "🎬 Installing FFMPEG into app bundle for DMG distribution..."
  echo "##PERCENT## 94 Installing FFMPEG"

  if [ -f "$SCRIPT_DIR/silent_ffmpeg_installer.py" ]; then
    # Use our silent installer to embed FFMPEG in the app bundle
    if "$PYTHON_BIN" "$SCRIPT_DIR/silent_ffmpeg_installer.py" --app-bundle "$BUILD_APP_PATH" --quiet; then
      echo "✅ FFMPEG successfully installed in app bundle"
    else
      echo "⚠️ FFMPEG installation failed - DMG will not include FFMPEG"
    fi
  else
    echo "⚠️ Silent FFMPEG installer not found - DMG will not include FFMPEG"
  fi

  # Download and install Pyannote diarization model for internal company use
  echo "🎙️ Downloading Pyannote diarization model (internal use)..."
  echo "##PERCENT## 97 Downloading Pyannote model"

  # Check for HF token
  if [ -z "$HF_TOKEN" ] && [ -f "$SCRIPT_DIR/../config/credentials.yaml" ]; then
    HF_TOKEN=$(grep "huggingface_token:" "$SCRIPT_DIR/../config/credentials.yaml" | sed 's/.*: //' | tr -d '"' | tr -d "'")
  fi

  if [ ! -z "$HF_TOKEN" ] && [ "$HF_TOKEN" != "your_huggingface_token_here" ]; then
    if [ -f "$SCRIPT_DIR/download_pyannote_direct.py" ]; then
      # Download model directly during build
      if HF_TOKEN="$HF_TOKEN" "$PYTHON_BIN" "$SCRIPT_DIR/download_pyannote_direct.py" --app-bundle "$BUILD_APP_PATH"; then
        echo "✅ Pyannote model downloaded and bundled (internal use only)"
      else
        echo "⚠️ Pyannote model download failed - DMG will require HF token at runtime"
      fi
    else
      echo "⚠️ Pyannote downloader not found"
    fi
  else
    echo "⚠️ No HuggingFace token found - skipping pyannote bundling"
    echo "   Users will need to provide token on first use"
  fi

  # Optionally bundle ALL models for complete offline experience
  if [ "${BUNDLE_ALL_MODELS:-0}" = "1" ]; then
    echo "📦 Bundling ALL models for complete offline use..."
    echo "##PERCENT## 98 Bundling remaining models"

    if [ -f "$SCRIPT_DIR/bundle_all_models.sh" ]; then
      if bash "$SCRIPT_DIR/bundle_all_models.sh" "$BUILD_APP_PATH"; then
        echo "✅ All models bundled - DMG will work completely offline (~4GB)"
      else
        echo "⚠️ Some models not bundled - they'll download on first use"
      fi
    fi
  fi
fi

echo "##PERCENT## 100 Complete"
if [ "${BUNDLE_ALL_MODELS:-0}" = "1" ]; then
  echo "🎯 All models bundled for complete offline experience"
else
  echo "🎯 Core models bundled - additional models download on first use"
fi
if [ "$SKIP_INSTALL" -eq 0 ]; then
  echo "🚀 You can now launch Skip the Podcast Desktop from your Applications folder"
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
  hdiutil create -volname "Skip the Podcast Desktop" -srcfolder "$DMG_STAGING/root" -ov -format UDZO "$DIST_DIR/Skip_the_Podcast_Desktop-${CURRENT_VERSION}.dmg"
  echo "✅ DMG created at: $DIST_DIR/Skip_the_Podcast_Desktop-${CURRENT_VERSION}.dmg"

  # Optional: Offer to publish release to public repository
  if [ "$SKIP_INSTALL" -eq 1 ] && [ "${IN_APP_UPDATER:-0}" != "1" ]; then
    echo ""
    echo "🌐 DMG ready for release!"
    echo "📍 To publish to public repository: bash scripts/publish_release.sh"
    echo "📍 To publish with existing DMG: bash scripts/publish_release.sh --skip-build"
  fi

  # Clean up staging to avoid Spotlight finding duplicate app bundles
  rm -rf "$DMG_STAGING"
fi
