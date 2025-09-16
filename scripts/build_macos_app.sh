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
      SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
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

# Track installation status for user feedback
EXTRAS_STATUS=""
FAILED_EXTRAS=""

# Conditionally install optional extras into the staging venv
if [ "$WITH_HCE" -eq 1 ]; then
  next_step "Install HCE optional dependencies (staging)"
  # Install from project root (ensures pyproject.toml/extras resolution)
  if "$VENV_DIR/bin/python" -m pip install -e "$PROJECT_ROOT"[hce]; then
    echo "✅ HCE extras installed successfully"
    EXTRAS_STATUS="${EXTRAS_STATUS}✅ HCE (Human-Centric Extraction): Advanced summarization, concept mining\n"
  else
    echo "❌ Failed to install HCE extras - advanced features will be unavailable"
    FAILED_EXTRAS="${FAILED_EXTRAS}❌ HCE (Human-Centric Extraction): Advanced summarization disabled\n"
    echo "$(date): HCE extras installation failed" >> "$BUILD_MACOS_PATH/installation_errors.log"
    "$VENV_DIR/bin/python" -m pip install -e "$PROJECT_ROOT"[hce] >> "$BUILD_MACOS_PATH/installation_errors.log" 2>&1 || true
  fi
else
  echo "🎯 Skipping HCE heavy dependencies in staging"
  EXTRAS_STATUS="${EXTRAS_STATUS}⏭️  HCE: Skipped (will download on first use)\n"
fi

if [ "$WITH_DIARIZATION" -eq 1 ]; then
  next_step "Install diarization dependencies (staging)"
  # Install from project root (ensures pyproject.toml/extras resolution)
  if "$VENV_DIR/bin/python" -m pip install -e "$PROJECT_ROOT"[diarization]; then
    echo "✅ Diarization extras installed successfully"
    EXTRAS_STATUS="${EXTRAS_STATUS}✅ Speaker Diarization: Multi-speaker audio processing\n"
  else
    echo "❌ Failed to install diarization extras - speaker separation will be unavailable"
    FAILED_EXTRAS="${FAILED_EXTRAS}❌ Speaker Diarization: Multi-speaker processing disabled\n"
    echo "$(date): Diarization extras installation failed" >> "$BUILD_MACOS_PATH/installation_errors.log"
    "$VENV_DIR/bin/python" -m pip install -e "$PROJECT_ROOT"[diarization] >> "$BUILD_MACOS_PATH/installation_errors.log" 2>&1 || true
  fi
else
  echo "🎯 Skipping diarization dependencies in staging"
  EXTRAS_STATUS="${EXTRAS_STATUS}⏭️  Diarization: Skipped (will download on first use)\n"
fi

if [ "$WITH_CUDA" -eq 1 ]; then
  next_step "Install CUDA-related dependencies (staging)"
  # Install from project root (ensures pyproject.toml/extras resolution)
  if "$VENV_DIR/bin/python" -m pip install -e "$PROJECT_ROOT"[cuda]; then
    echo "✅ CUDA extras installed successfully"
    EXTRAS_STATUS="${EXTRAS_STATUS}✅ CUDA Support: GPU-accelerated processing\n"
  else
    echo "❌ Failed to install CUDA extras - GPU acceleration will be unavailable"
    FAILED_EXTRAS="${FAILED_EXTRAS}❌ CUDA Support: GPU acceleration disabled\n"
    echo "$(date): CUDA extras installation failed" >> "$BUILD_MACOS_PATH/installation_errors.log"
    "$VENV_DIR/bin/python" -m pip install -e "$PROJECT_ROOT"[cuda] >> "$BUILD_MACOS_PATH/installation_errors.log" 2>&1 || true
  fi
else
  echo "🎯 Skipping CUDA extras in staging"
  EXTRAS_STATUS="${EXTRAS_STATUS}⏭️  CUDA: Skipped (CPU-only mode)\n"
fi

if [ "$WITH_HCE" -eq 0 ] && [ "$WITH_DIARIZATION" -eq 0 ] && [ "$WITH_CUDA" -eq 0 ]; then
  echo "🎯 Excluding heavy ML dependencies (torch, transformers, etc.) from app bundle"
  echo "ℹ️  Heavy dependencies will be installed automatically when needed"
fi

# Install the main package in staging venv (CRITICAL for --skip-install mode)
echo "📦 Installing main knowledge_system package in staging venv..."
next_step "Install main package (staging)"
"$VENV_DIR/bin/python" -m pip install -e "$PROJECT_ROOT" || {
  echo "❌ Failed to install main package in staging venv"
  exit 1
}

# Verify critical dependencies are installed
echo "🔍 Verifying critical dependencies..."
next_step "Verify dependencies"
echo "##PERCENT## 55 Verify critical dependencies"
"$VENV_DIR/bin/python" -c "import sqlalchemy; print('✅ SQLAlchemy:', sqlalchemy.__version__)" || { echo "❌ SQLAlchemy missing, installing..."; "$VENV_DIR/bin/python" -m pip install sqlalchemy alembic; }
"$VENV_DIR/bin/python" -c "import psutil; print('✅ psutil:', psutil.__version__)" || { echo "❌ psutil missing, installing..."; "$VENV_DIR/bin/python" -m pip install psutil; }
"$VENV_DIR/bin/python" -c "import openai; print('✅ OpenAI:', openai.__version__)" || { echo "❌ OpenAI missing, installing..."; "$VENV_DIR/bin/python" -m pip install openai; }

# Fix Python symlinks for cross-machine compatibility
echo "🔗 Making venv relocatable (fixing Python symlinks)..."
# Find the system Python that was used to create the venv
SYSTEM_PYTHON="$(command -v /opt/homebrew/bin/python3.13 || command -v python3.13 || true)"
if [ ! -f "$SYSTEM_PYTHON" ]; then
  # Last resort: look in common locations
  for path in "/opt/homebrew/bin/python3.13" "/usr/local/bin/python3.13" "/usr/bin/python3"; do
    if [ -f "$path" ]; then
      SYSTEM_PYTHON="$path"
      break
    fi
  done
fi

if [ -f "$SYSTEM_PYTHON" ]; then
  echo "   📍 Using system Python binary: $SYSTEM_PYTHON"
  # Verify the Python binary is the correct architecture
  PYTHON_ARCH=$(file "$SYSTEM_PYTHON" | grep -o 'arm64\|x86_64' | head -1)
  echo "   🏗️  Python architecture: $PYTHON_ARCH"
  if [[ "$PYTHON_ARCH" != "arm64" ]] && [[ "$(uname -m)" == "arm64" ]]; then
    echo "   ⚠️  WARNING: Python is $PYTHON_ARCH but system is arm64"
  fi
  # Create universal Python launchers instead of copying binaries
  echo "   🚀 Creating universal Python launchers..."
  for py_link in "$VENV_DIR/bin/python" "$VENV_DIR/bin/python3" "$VENV_DIR/bin/python3.13"; do
    echo "   🔧 Processing: $(basename "$py_link")"
    # Remove existing file/symlink if present
    if [ -e "$py_link" ] || [ -L "$py_link" ]; then
      echo "      ↳ Removing existing file/symlink"
      rm -f "$py_link"
    fi
    # Create launcher script
    echo "      ↳ Creating Python launcher"
    bash "$SCRIPT_DIR/create_python_launcher.sh" "$py_link"
    echo "      ✅ Created $(basename "$py_link") launcher"
  done

  # Verify the fix worked
  if [ -f "$VENV_DIR/bin/python" ]; then
    echo "   ✅ Python launchers successfully created"
    echo "   ℹ️  App will auto-detect Python 3.13+ on user's system"
  else
    echo "   ❌ FAILED: Python launchers still missing"
    exit 1
  fi

  # Add Python auto-installer and first launch helper
  echo "   📦 Adding helper scripts..."
  mkdir -p "$BUILD_MACOS_PATH/bin"
  cp "$SCRIPT_DIR/python_auto_installer.sh" "$BUILD_MACOS_PATH/bin/"
  cp "$SCRIPT_DIR/install_python.sh" "$BUILD_MACOS_PATH/bin/"
  cp "$SCRIPT_DIR/first_launch_helper.sh" "$BUILD_MACOS_PATH/bin/"
  chmod +x "$BUILD_MACOS_PATH/bin/python_auto_installer.sh"
  chmod +x "$BUILD_MACOS_PATH/bin/install_python.sh"
  chmod +x "$BUILD_MACOS_PATH/bin/first_launch_helper.sh"
else
  echo "❌ CRITICAL: Could not find any system Python binary to copy!"
  echo "   This will cause the app to fail on other machines."
  exit 1
fi

# CRITICAL: Verify the main package is importable in staging venv
echo "🧪 Testing main package import in staging venv..."
"$VENV_DIR/bin/python" -c "import knowledge_system; print('✅ knowledge_system package:', knowledge_system.__version__)" || {
  echo "❌ CRITICAL: knowledge_system package not importable in staging venv"
  echo "   This will cause DMG launch failures!"
  exit 1
}

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
    <key>NSDocumentsFolderUsageDescription</key>
    <string>Skip the Podcast Desktop needs access to your Documents folder to process and save transcribed files.</string>
    <key>NSDownloadsFolderUsageDescription</key>
    <string>Skip the Podcast Desktop needs access to your Downloads folder to process media files you've downloaded.</string>
    <key>NSDesktopFolderUsageDescription</key>
    <string>Skip the Podcast Desktop needs access to your Desktop to process and save transcribed files.</string>
    <key>NSRemovableVolumesUsageDescription</key>
    <string>Skip the Podcast Desktop needs access to external drives to process media files stored on them.</string>
    <key>LSApplicationCategoryType</key>
    <string>public.app-category.productivity</string>
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

# Skip Gatekeeper check if installed via our installer
if [ -f "\$HOME/.skip_podcast_clean_install" ]; then
    echo "Clean install detected - skipping Gatekeeper checks" >> "\$LOG_FILE"
fi

# Check for bundled FFMPEG and set up environment
if [ -f "\$APP_DIR/setup_bundled_ffmpeg.sh" ]; then
    echo "Setting up bundled FFMPEG..." >> "\$LOG_FILE"
    source "\$APP_DIR/setup_bundled_ffmpeg.sh"
    echo "FFMPEG_PATH: \$FFMPEG_PATH" >> "\$LOG_FILE"
    echo "FFPROBE_PATH: \$FFPROBE_PATH" >> "\$LOG_FILE"
fi

# Check for bundled whisper.cpp and set up environment
if [ -f "\$APP_DIR/setup_bundled_whisper.sh" ]; then
    echo "Setting up bundled whisper.cpp..." >> "\$LOG_FILE"
    source "\$APP_DIR/setup_bundled_whisper.sh"
    echo "WHISPER_CPP_PATH: \$WHISPER_CPP_PATH" >> "\$LOG_FILE"
    echo "WHISPER_CPP_BUNDLED: \$WHISPER_CPP_BUNDLED" >> "\$LOG_FILE"
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

# Set up Python environment - use manual setup to avoid hardcoded paths
export VIRTUAL_ENV="\$APP_DIR/venv"
export PATH="\$VIRTUAL_ENV/bin:\$PATH"
export PYTHONPATH="\$APP_DIR/src:\$PYTHONPATH"
unset PYTHONHOME
hash -r 2>/dev/null
cd "\$APP_DIR"

# Log environment info
echo "Current directory: \$(pwd)" >> "\$LOG_FILE"
echo "PYTHONPATH: \$PYTHONPATH" >> "\$LOG_FILE"
echo "Python version: \$("\$APP_DIR/venv/bin/python" --version)" >> "\$LOG_FILE"
echo "Virtual env: \$VIRTUAL_ENV" >> "\$LOG_FILE"
echo "Architecture: \$(arch)" >> "\$LOG_FILE"

# Check if Python launcher exists and is executable
if [ ! -x "\$APP_DIR/venv/bin/python" ]; then
    echo "Python launcher not found or not executable" >> "\$LOG_FILE"
    osascript -e 'display dialog "Application files are missing or corrupted. Please reinstall Skip the Podcast Desktop." buttons {"OK"} default button 1 with title "Installation Error" with icon stop'
    exit 1
fi

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

# Check if initialization worked (Python is available)
if [ \$? -ne 0 ]; then
    echo "Python initialization failed" >> "\$LOG_FILE"
    # The Python launcher will show the installation dialog
    exit 1
fi

# Check for Gatekeeper block (Disk Drill-style)
if [ -f "\$APP_DIR/../../Info.plist" ]; then
    # We're in an app bundle - check for quarantine
    if xattr -p com.apple.quarantine "\$APP_DIR/../.." &>/dev/null; then
        echo "Detected Gatekeeper quarantine" >> "\$LOG_FILE"

        # Check if already authorized
        if [ ! -f "\$HOME/.skip_the_podcast_desktop_authorized" ]; then
            echo "Showing authorization dialog..." >> "\$LOG_FILE"

            # Disk Drill-style authorization dialog
            osascript << 'EOAUTH' 2>&1 | tee -a "\$LOG_FILE"
-- Skip the Podcast Desktop - Gatekeeper Authorization

set appBundle to (path to current application) as text
set appPath to POSIX path of appBundle

-- Professional authorization dialog
display dialog "Skip the Podcast Desktop needs administrator permission to complete installation.

This one-time authorization removes macOS security warnings, just like professional apps such as Disk Drill.

You'll be prompted for your password." buttons {"Cancel", "Authorize"} default button "Authorize" with title "Administrator Permission Required" with icon caution

if button returned of result is "Cancel" then
    return "cancelled"
end if

-- Request admin privileges
try
    do shell script "
        # Remove quarantine attribute
        /usr/bin/xattr -cr '" & appPath & "' 2>&1
        /usr/bin/xattr -dr com.apple.quarantine '" & appPath & "' 2>&1

        # Add to Gatekeeper whitelist
        /usr/sbin/spctl --add '" & appPath & "' 2>&1 || true

        # Force Launch Services update
        /System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister -f '" & appPath & "' 2>&1

        # Mark as authorized
        /usr/bin/touch ~/.skip_the_podcast_desktop_authorized

        echo 'Authorization successful'
    " with administrator privileges

    display notification "Skip the Podcast Desktop has been authorized!" with title "Success" sound name "Glass"

    return "success"
on error errMsg
    if errMsg does not contain "-128" then
        display alert "Authorization Failed" message errMsg as critical
    end if
    return "failed"
end try
EOAUTH

            AUTH_RESULT=\$?
            if [ \$AUTH_RESULT -ne 0 ] || grep -q "cancelled\\|failed" "\$LOG_FILE"; then
                echo "Authorization cancelled or failed" >> "\$LOG_FILE"
                osascript -e 'display dialog "To run Skip the Podcast Desktop manually:\n\n1. Right-click the app\n2. Select Open\n3. Click Open in the security dialog" buttons {"OK"} with icon caution'
                exit 1
            fi

            echo "Authorization successful!" >> "\$LOG_FILE"
            # The app needs to restart for changes to take effect
            osascript -e 'display dialog "Authorization complete!\n\nPlease reopen Skip the Podcast Desktop." buttons {"OK"} default button "OK" with icon note'
            exit 0
        fi
    fi
fi

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

# Show user what features are included/missing
echo ""
echo "📋 Feature Installation Summary:"
echo "================================="
if [ -n "$EXTRAS_STATUS" ]; then
  echo -e "$EXTRAS_STATUS"
fi
# Always create troubleshooting files for users (even if no failures)
INSTALL_SCRIPT="$BUILD_MACOS_PATH/install_missing_features.sh"

if [ -n "$FAILED_EXTRAS" ]; then
  echo ""
  echo "⚠️  Failed Installations:"
  echo -e "$FAILED_EXTRAS"
  echo ""

  # Create installation script for failed features
  cat > "$INSTALL_SCRIPT" << 'EOF'
#!/bin/bash
# Install Missing Skip the Podcast Desktop Features
# Run this script to install features that failed during the initial build

APP_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PYTHON_BIN="$APP_DIR/venv/bin/python"

echo "🔧 Installing Missing Skip the Podcast Desktop Features"
echo "======================================================"

if [ ! -f "$PYTHON_BIN" ]; then
    echo "❌ Python environment not found at: $PYTHON_BIN"
    echo "Please reinstall Skip the Podcast Desktop"
    exit 1
fi

echo "🐍 Using Python: $PYTHON_BIN"
echo ""

# Check which features need installation
NEED_HCE=0
NEED_DIARIZATION=0
NEED_CUDA=0

# Test imports to see what's missing
echo "🔍 Checking which features need installation..."

if ! "$PYTHON_BIN" -c "import torch; import transformers" 2>/dev/null; then
    echo "   📦 HCE (Advanced Summarization) needs installation"
    NEED_HCE=1
fi

if ! "$PYTHON_BIN" -c "import pyannote.audio" 2>/dev/null; then
    echo "   📦 Speaker Diarization needs installation"
    NEED_DIARIZATION=1
fi

if ! "$PYTHON_BIN" -c "import torch; print('CUDA Available:', torch.cuda.is_available())" 2>/dev/null | grep -q "True"; then
    echo "   📦 CUDA Support needs installation"
    NEED_CUDA=1
fi

if [ $NEED_HCE -eq 0 ] && [ $NEED_DIARIZATION -eq 0 ] && [ $NEED_CUDA -eq 0 ]; then
    echo "✅ All features are already installed!"
    exit 0
fi

echo ""
read -p "Install missing features? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "❌ Installation cancelled"
    exit 0
fi

# Install missing features
if [ $NEED_HCE -eq 1 ]; then
    echo "📦 Installing HCE (Advanced Summarization)..."
    "$PYTHON_BIN" -m pip install -e "$APP_DIR"[hce] || echo "❌ HCE installation failed"
fi

if [ $NEED_DIARIZATION -eq 1 ]; then
    echo "📦 Installing Speaker Diarization..."
    "$PYTHON_BIN" -m pip install -e "$APP_DIR"[diarization] || echo "❌ Diarization installation failed"
fi

if [ $NEED_CUDA -eq 1 ]; then
    echo "📦 Installing CUDA Support..."
    "$PYTHON_BIN" -m pip install -e "$APP_DIR"[cuda] || echo "❌ CUDA installation failed"
fi

echo ""
echo "✅ Feature installation complete!"
echo "🔄 Please restart Skip the Podcast Desktop to use new features"
EOF

  chmod +x "$INSTALL_SCRIPT"

  # Create comprehensive troubleshooting log for developer
  TROUBLESHOOT_LOG="$BUILD_MACOS_PATH/build_troubleshooting.log"
  cat > "$TROUBLESHOOT_LOG" << EOF
Skip the Podcast Desktop - Build Troubleshooting Log
===================================================
Build Date: $(date)
Version: $CURRENT_VERSION
Build Flags: $@
Python Version: $("$VENV_DIR/bin/python" --version 2>/dev/null || echo "Unknown")
Platform: $(uname -a)

FAILED INSTALLATIONS:
$(echo -e "$FAILED_EXTRAS")

DETAILED ERROR LOGS:
===================
$(cat "$BUILD_MACOS_PATH/installation_errors.log" 2>/dev/null || echo "No detailed error logs available")

ENVIRONMENT INFO:
================
HOMEBREW_PREFIX: ${HOMEBREW_PREFIX:-"Not set"}
PATH: $PATH
PYTHONPATH: ${PYTHONPATH:-"Not set"}

PIP LIST (staging venv):
=======================
$("$VENV_DIR/bin/python" -m pip list 2>/dev/null || echo "Failed to get pip list")

SYSTEM DEPENDENCIES:
===================
Git version: $(git --version 2>/dev/null || echo "Git not found")
Homebrew version: $(brew --version 2>/dev/null || echo "Homebrew not found")

TROUBLESHOOTING STEPS:
=====================
1. Check if Homebrew is properly installed and updated
2. Verify Python 3.13 is available: brew install python@3.13
3. Check internet connectivity for package downloads
4. Review detailed error logs above for specific package conflicts
5. Try clean rebuild: bash scripts/build_macos_app.sh --clean && bash scripts/build_macos_app.sh --make-dmg --skip-install

QUICK FIXES:
===========
- HCE issues: Usually torch/transformers conflicts or insufficient disk space
- Diarization issues: Often pyannote.audio dependency conflicts
- CUDA issues: Requires compatible GPU and CUDA toolkit installation

For support, share this log file: $TROUBLESHOOT_LOG
EOF

  echo "🔗 Easy Fix Available:"
  echo "   Double-click: install_missing_features.sh (in the app folder)"
  echo "   Or run: bash '$INSTALL_SCRIPT'"
  echo ""
  echo "📋 Developer Troubleshooting:"
  echo "   Full build log: $TROUBLESHOOT_LOG"
  echo "   Installation errors: $BUILD_MACOS_PATH/installation_errors.log"
  echo ""
  echo "💡 Note: Failed features can also be installed automatically when first used."
  echo "   The app will download missing dependencies as needed."
else
  # Create installation script even when no failures (for future use)
  cat > "$INSTALL_SCRIPT" << 'EOF'
#!/bin/bash
# Skip the Podcast Desktop - Feature Management
# Run this script to check and install additional features

APP_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PYTHON_BIN="$APP_DIR/venv/bin/python"

echo "🔧 Skip the Podcast Desktop - Feature Management"
echo "==============================================="

if [ ! -f "$PYTHON_BIN" ]; then
    echo "❌ Python environment not found at: $PYTHON_BIN"
    echo "Please reinstall Skip the Podcast Desktop"
    exit 1
fi

echo "🐍 Using Python: $PYTHON_BIN"
echo ""

# Check current feature status
echo "🔍 Checking installed features..."

HCE_STATUS="❓"
DIARIZATION_STATUS="❓"
CUDA_STATUS="❓"

if "$PYTHON_BIN" -c "import torch; import transformers" 2>/dev/null; then
    HCE_STATUS="✅"
else
    HCE_STATUS="❌"
fi

if "$PYTHON_BIN" -c "import pyannote.audio" 2>/dev/null; then
    DIARIZATION_STATUS="✅"
else
    DIARIZATION_STATUS="❌"
fi

if "$PYTHON_BIN" -c "import torch; print('CUDA Available:', torch.cuda.is_available())" 2>/dev/null | grep -q "True"; then
    CUDA_STATUS="✅"
else
    CUDA_STATUS="❌"
fi

echo ""
echo "📋 Feature Status:"
echo "=================="
echo "$HCE_STATUS HCE (Advanced Summarization)"
echo "$DIARIZATION_STATUS Speaker Diarization"
echo "$CUDA_STATUS CUDA Support"
echo ""

# Count missing features
MISSING_COUNT=0
if [ "$HCE_STATUS" = "❌" ]; then ((MISSING_COUNT++)); fi
if [ "$DIARIZATION_STATUS" = "❌" ]; then ((MISSING_COUNT++)); fi
if [ "$CUDA_STATUS" = "❌" ]; then ((MISSING_COUNT++)); fi

if [ $MISSING_COUNT -eq 0 ]; then
    echo "🎉 All features are installed and working!"
    echo "💡 If you're having issues, try restarting the app"
    exit 0
fi

echo "⚠️  $MISSING_COUNT feature(s) need installation"
echo ""
read -p "Install missing features? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "❌ Installation cancelled"
    exit 0
fi

# Install missing features
if [ "$HCE_STATUS" = "❌" ]; then
    echo "📦 Installing HCE (Advanced Summarization)..."
    "$PYTHON_BIN" -m pip install -e "$APP_DIR"[hce] || echo "❌ HCE installation failed"
fi

if [ "$DIARIZATION_STATUS" = "❌" ]; then
    echo "📦 Installing Speaker Diarization..."
    "$PYTHON_BIN" -m pip install -e "$APP_DIR"[diarization] || echo "❌ Diarization installation failed"
fi

if [ "$CUDA_STATUS" = "❌" ]; then
    echo "📦 Installing CUDA Support..."
    "$PYTHON_BIN" -m pip install -e "$APP_DIR"[cuda] || echo "❌ CUDA installation failed"
fi

echo ""
echo "✅ Feature installation complete!"
echo "🔄 Please restart Skip the Podcast Desktop to use new features"
EOF

  chmod +x "$INSTALL_SCRIPT"

  # Create basic troubleshooting log
  TROUBLESHOOT_LOG="$BUILD_MACOS_PATH/build_troubleshooting.log"
  cat > "$TROUBLESHOOT_LOG" << EOF
Skip the Podcast Desktop - Build Information
===========================================
Build Date: $(date)
Version: $CURRENT_VERSION
Build Flags: $@
Python Version: $("$VENV_DIR/bin/python" --version 2>/dev/null || echo "Unknown")
Platform: $(uname -a)

BUILD STATUS: ✅ SUCCESS
All features installed successfully during build.

INSTALLED FEATURES:
$(echo -e "$EXTRAS_STATUS")

TROUBLESHOOTING TOOLS:
=====================
- Feature manager: install_missing_features.sh
- App logs: ~/Library/Logs/Skip the Podcast Desktop/
- Console.app: Search for "Skip the Podcast"

For support: https://github.com/skipthepodcast/desktop/issues
EOF

fi
echo "================================="

# Install core dependencies into the app bundle for DMG distribution [[memory:7770522]]
if [ "$MAKE_DMG" -eq 1 ] || { [ "$SKIP_INSTALL" -eq 1 ] && [ "${IN_APP_UPDATER:-0}" != "1" ]; }; then
  echo "🎬 Installing FFMPEG into app bundle for DMG distribution..."
  echo "##PERCENT## 92 Installing FFMPEG"

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

  # Install whisper.cpp binary for local transcription
  echo "🎤 Installing whisper.cpp binary for local transcription..."
  echo "##PERCENT## 94 Installing whisper.cpp"

  if [ -f "$SCRIPT_DIR/install_whisper_cpp_binary.py" ]; then
    # Install whisper.cpp binary in the app bundle
    if "$PYTHON_BIN" "$SCRIPT_DIR/install_whisper_cpp_binary.py" --app-bundle "$BUILD_APP_PATH" --quiet; then
      echo "✅ whisper.cpp successfully installed in app bundle"
    else
      echo "⚠️ whisper.cpp installation failed - local transcription will require manual installation"
    fi
  else
    echo "⚠️ whisper.cpp installer not found - local transcription will require manual installation"
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

  # Add the click-to-install script that bypasses Gatekeeper
  if [ -f "$SCRIPT_DIR/INSTALL_AND_OPEN.command" ]; then
    cp "$SCRIPT_DIR/INSTALL_AND_OPEN.command" "$DMG_STAGING/root/⚠️ CLICK ME TO INSTALL.command"
    chmod +x "$DMG_STAGING/root/⚠️ CLICK ME TO INSTALL.command"
  fi

  # Also add the alternative installer
  if [ -f "$SCRIPT_DIR/first_run_setup.sh" ]; then
    cp "$SCRIPT_DIR/first_run_setup.sh" "$DMG_STAGING/root/Alternative Installer.command"
    chmod +x "$DMG_STAGING/root/Alternative Installer.command"
  fi

  # Create helpful README for DMG users
  cat > "$DMG_STAGING/root/README - Installation.txt" << EOF
Skip the Podcast Desktop - Quick Start Guide
===============================================

⚠️  IMPORTANT - USE THE INSTALLER TO AVOID SECURITY WARNINGS:

📦 RECOMMENDED INSTALLATION:
   Double-click "⚠️ CLICK ME TO INSTALL.command"

   This smart installer will:
   ✓ Copy the app to Applications
   ✓ Bypass ALL macOS security warnings
   ✓ Configure permissions automatically
   ✓ Launch the app when done

   You'll be asked for your password once during installation.

🚫 IF YOU DRAG THE APP MANUALLY:
   macOS will show security warnings ("app is damaged" etc.)
   You'll need to right-click → Open → Open to bypass them

💡 WHY USE THE INSTALLER?
   • No security warnings or "damaged app" messages
   • Automatic configuration (like professional apps)
   • One-time password prompt during install
   • App launches normally every time after

⚙️ SYSTEM REQUIREMENTS:
   • macOS 11.0 or later
   • 4GB RAM recommended
   • 2GB free disk space

🔧 ADVANCED FEATURES:
   Some features auto-install on first use:
   • Advanced Summarization (HCE)
   • Speaker Diarization (Multi-speaker audio)
   • GPU Acceleration (CUDA - if compatible)

📋 TROUBLESHOOTING:
   If the app doesn't launch:
   • Ensure you have macOS 11.0 or later
   • Try the right-click → Open method
   • Check ~/Library/Logs/Skip the Podcast Desktop/

💡 The app includes an embedded Python runtime for maximum compatibility.

💬 NEED HELP?
   Visit: https://github.com/skipthepodcast/desktop/issues

Built: $(date)
Version: $CURRENT_VERSION
EOF
  hdiutil create -volname "Skip the Podcast Desktop" -srcfolder "$DMG_STAGING/root" -ov -format UDZO "$DIST_DIR/Skip_the_Podcast_Desktop-${CURRENT_VERSION}.dmg"
  echo "✅ DMG created at: $DIST_DIR/Skip_the_Podcast_Desktop-${CURRENT_VERSION}.dmg"

  # Show DMG contents summary
  DMG_SIZE=$(du -h "$DIST_DIR/Skip_the_Podcast_Desktop-${CURRENT_VERSION}.dmg" | cut -f1)
  echo ""
  echo "📦 DMG Summary:"
  echo "==============="
  echo "📁 File: Skip_the_Podcast_Desktop-${CURRENT_VERSION}.dmg"
  echo "📏 Size: $DMG_SIZE"
  echo ""
  echo "🎯 Included Features:"
  if [ -n "$EXTRAS_STATUS" ]; then
    echo -e "$EXTRAS_STATUS"
  fi
  if [ -n "$FAILED_EXTRAS" ]; then
    echo ""
    echo "⚠️  Missing Features (will auto-install on first use):"
    echo -e "$FAILED_EXTRAS"
    echo ""
    echo "🔗 User Fix Options:"
    echo "   1. Double-click: install_missing_features.sh (in app Contents/MacOS/)"
    echo "   2. Features auto-install when first used"
    echo "   3. Manual install: pip install knowledge-system[hce,diarization]"
  fi
  echo "==============="

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
