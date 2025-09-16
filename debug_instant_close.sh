#!/bin/bash
# Debug script for app that opens and instantly closes
# Run this on the machine where the problem occurs

echo "🔍 Skip the Podcast Desktop Debug Script"
echo "========================================"
echo "Please run this script and share the output"
echo ""

APP_PATH="/Applications/Skip the Podcast Desktop.app"
MACOS_DIR="$APP_PATH/Contents/MacOS"
LOG_FILE="$HOME/Desktop/skip_podcast_debug_$(date +%Y%m%d_%H%M%S).log"

exec > >(tee -a "$LOG_FILE")
exec 2>&1

echo "📅 Date: $(date)"
echo "💻 System: $(uname -a)"
echo "🏗️ Architecture: $(uname -m)"
echo ""

# Check if app exists
echo "1. Checking app installation..."
if [ -d "$APP_PATH" ]; then
    echo "✅ App found at: $APP_PATH"
    echo "📋 Version: $(defaults read "$APP_PATH/Contents/Info.plist" CFBundleShortVersionString 2>/dev/null || echo "Unknown")"
else
    echo "❌ App not found at $APP_PATH"
    exit 1
fi
echo ""

# Check Python binaries
echo "2. Checking Python binaries..."
for py in python python3 python3.13; do
    py_path="$MACOS_DIR/venv/bin/$py"
    if [ -f "$py_path" ]; then
        echo "✅ Found: $py_path"
        echo "   Architecture: $(file "$py_path" | grep -o 'arm64\|x86_64' || echo "Unknown")"
        echo "   Size: $(ls -lh "$py_path" | awk '{print $5}')"
    else
        echo "❌ Missing: $py_path"
    fi
done
echo ""

# Check if venv can be activated
echo "3. Testing venv activation..."
if [ -f "$MACOS_DIR/venv/bin/activate" ]; then
    echo "✅ Found venv activate script"
    source "$MACOS_DIR/venv/bin/activate"
    echo "   VIRTUAL_ENV: $VIRTUAL_ENV"
    echo "   Python location: $(which python)"
else
    echo "❌ No venv activate script found"
fi
echo ""

# Test Python directly
echo "4. Testing Python binary directly..."
if [ -f "$MACOS_DIR/venv/bin/python" ]; then
    echo "Running: $MACOS_DIR/venv/bin/python --version"
    "$MACOS_DIR/venv/bin/python" --version 2>&1

    echo ""
    echo "Testing import of knowledge_system..."
    export PYTHONPATH="$MACOS_DIR/src:$PYTHONPATH"
    "$MACOS_DIR/venv/bin/python" -c "
try:
    import knowledge_system
    print('✅ knowledge_system imported successfully')
    print(f'   Version: {knowledge_system.__version__}')
except Exception as e:
    print(f'❌ Failed to import knowledge_system: {e}')
    import sys
    print(f'   Python path: {sys.path}')
" 2>&1
else
    echo "❌ Python binary not found"
fi
echo ""

# Check for crash logs
echo "5. Checking for crash logs..."
CRASH_DIR="$HOME/Library/Logs/DiagnosticReports"
if [ -d "$CRASH_DIR" ]; then
    recent_crashes=$(find "$CRASH_DIR" -name "*Skip*the*Podcast*" -mtime -1 2>/dev/null | head -5)
    if [ -n "$recent_crashes" ]; then
        echo "⚠️ Found recent crash logs:"
        echo "$recent_crashes"
        echo ""
        echo "Latest crash preview:"
        head -50 "$(echo "$recent_crashes" | head -1)" | grep -E "Process:|Exception:|Crashed:|Binary Images:"
    else
        echo "✅ No recent crash logs found"
    fi
else
    echo "❓ Crash log directory not found"
fi
echo ""

# Check Console.app logs
echo "6. Checking system logs..."
echo "Recent console messages for Skip the Podcast:"
log show --predicate 'process == "Skip the Podcast Desktop" OR processImagePath CONTAINS "Skip the Podcast"' --last 5m --style compact 2>/dev/null | tail -20
echo ""

# Test launch script directly
echo "7. Testing launch script with bash debug mode..."
echo "Running: bash -x $MACOS_DIR/launch"
echo "----------------------------------------"
cd "$MACOS_DIR"
timeout 10 bash -x ./launch 2>&1 || echo "⏱️ Launch timed out or failed"
echo "----------------------------------------"
echo ""

# Check if process is running
echo "8. Checking if process stayed running..."
sleep 2
if pgrep -f "Skip the Podcast" >/dev/null; then
    echo "✅ Process is running:"
    ps aux | grep -i "skip.*podcast" | grep -v grep
else
    echo "❌ Process is not running"
fi
echo ""

echo "📄 Debug log saved to: $LOG_FILE"
echo "Please share this file for troubleshooting."
