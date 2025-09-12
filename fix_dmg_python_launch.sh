#!/bin/bash
# Emergency fix for Skip the Podcast Desktop - Missing Python venv in DMG

APP_PATH="/Applications/Skip the Podcast Desktop.app"
MACOS_PATH="$APP_PATH/Contents/MacOS"

echo "🚨 Skip the Podcast Desktop - Emergency Python Fix"
echo "=================================================="

if [ ! -d "$APP_PATH" ]; then
    echo "❌ App not found at: $APP_PATH"
    exit 1
fi

echo "✅ App found at: $APP_PATH"

# Check if the venv directory exists (it shouldn't based on the log)
if [ -d "$MACOS_PATH/venv" ]; then
    echo "✅ Virtual environment exists - this fix may not be needed"
else
    echo "❌ Virtual environment missing (confirmed issue)"
fi

# Create a fixed launch script that uses system Python
FIXED_LAUNCH_SCRIPT="$MACOS_PATH/launch_fixed"

echo ""
echo "🔧 Creating emergency launch script..."

cat > "$FIXED_LAUNCH_SCRIPT" << 'EOF'
#!/bin/bash
# Emergency launch script for Skip the Podcast Desktop
# This bypasses the missing venv and uses system Python with the bundled source

# Get the directory where this script is located
APP_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Set up environment
export PYTHONPATH="$APP_DIR/src:${PYTHONPATH}"
export MODELS_BUNDLED="true"
export WHISPER_CACHE_DIR="$APP_DIR/.cache/whisper"
export OLLAMA_HOME="$APP_DIR/.ollama"

# Try to find a working Python installation
PYTHON_CANDIDATES=(
    "/usr/bin/python3"
    "/opt/homebrew/bin/python3"
    "/usr/local/bin/python3"
    "python3"
)

PYTHON_CMD=""
for cmd in "${PYTHON_CANDIDATES[@]}"; do
    if command -v "$cmd" >/dev/null 2>&1; then
        PYTHON_CMD="$cmd"
        echo "✅ Using Python: $PYTHON_CMD"
        break
    fi
done

if [ -z "$PYTHON_CMD" ]; then
    echo "❌ No Python 3 installation found"
    echo "Please install Python 3 from python.org or using Homebrew"
    exit 1
fi

# Check if required modules are available
echo "🔍 Checking for required Python modules..."

# Try to install PyQt6 if missing
if ! "$PYTHON_CMD" -c "import PyQt6" 2>/dev/null; then
    echo "⚠️  PyQt6 not found - attempting to install..."
    "$PYTHON_CMD" -m pip install --user PyQt6 2>/dev/null || {
        echo "❌ Failed to install PyQt6"
        echo "Please run: pip3 install PyQt6"
        exit 1
    }
fi

echo "🚀 Launching Skip the Podcast Desktop..."

# Change to the app directory and launch
cd "$APP_DIR"
exec "$PYTHON_CMD" -m knowledge_system.gui 2>&1
EOF

# Make the script executable
chmod +x "$FIXED_LAUNCH_SCRIPT"

echo "✅ Emergency launch script created: $FIXED_LAUNCH_SCRIPT"

# Create a simple app launcher using AppleScript
APPLESCRIPT_LAUNCHER="/tmp/launch_skip_podcast.scpt"

cat > "$APPLESCRIPT_LAUNCHER" << EOF
tell application "Terminal"
    activate
    do script "bash '$FIXED_LAUNCH_SCRIPT'"
end tell
EOF

echo ""
echo "🚀 LAUNCH OPTIONS:"
echo ""
echo "Option 1 - Terminal Launch:"
echo "  bash '$FIXED_LAUNCH_SCRIPT'"
echo ""
echo "Option 2 - AppleScript Launch:"
echo "  osascript '$APPLESCRIPT_LAUNCHER'"
echo ""
echo "💡 If this works, we know the issue is just the missing venv in the DMG"
