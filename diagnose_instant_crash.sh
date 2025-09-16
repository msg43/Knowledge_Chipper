#!/bin/bash
# Diagnose why Skip the Podcast Desktop crashes immediately after launch
# Run this AFTER approving in Privacy Settings

echo "🔬 Skip the Podcast Desktop - Crash Diagnosis"
echo "=============================================="
echo "Running comprehensive diagnostics..."
echo ""

APP_PATH="/Applications/Skip the Podcast Desktop.app"
MACOS_DIR="$APP_PATH/Contents/MacOS"
LOG_DIR="$HOME/Library/Logs/Skip the Podcast Desktop"
CRASH_DIR="$HOME/Library/Logs/DiagnosticReports"
DIAG_LOG="$HOME/Desktop/skip_podcast_crash_diagnosis.log"

# Redirect all output to both console and log file
exec > >(tee -a "$DIAG_LOG")
exec 2>&1

echo "📅 Diagnosis Time: $(date)"
echo "💻 System: $(sw_vers -productVersion) on $(uname -m)"
echo ""

# 1. Check basic app structure
echo "1️⃣ Checking app structure..."
echo "----------------------------------------"
if [ -d "$APP_PATH" ]; then
    echo "✅ App exists at: $APP_PATH"
    echo "📋 Version: $(defaults read "$APP_PATH/Contents/Info.plist" CFBundleShortVersionString 2>/dev/null || echo "Unknown")"
else
    echo "❌ App not found!"
    exit 1
fi

# 2. Check Python environment
echo ""
echo "2️⃣ Checking Python environment..."
echo "----------------------------------------"
if [ -f "$MACOS_DIR/venv/bin/python" ]; then
    echo "✅ Python binary exists"
    echo "📊 File info: $(file "$MACOS_DIR/venv/bin/python")"
    echo "📏 Size: $(ls -lh "$MACOS_DIR/venv/bin/python" | awk '{print $5}')"

    # Test Python directly
    echo ""
    echo "Testing Python execution:"
    "$MACOS_DIR/venv/bin/python" --version 2>&1 || echo "❌ Python execution failed: $?"
else
    echo "❌ Python binary missing!"
fi

# 3. Check for missing dependencies
echo ""
echo "3️⃣ Checking dependencies..."
echo "----------------------------------------"
export PYTHONPATH="$MACOS_DIR/src:$PYTHONPATH"
"$MACOS_DIR/venv/bin/python" -c "
import sys
print(f'Python: {sys.version}')
print(f'Executable: {sys.executable}')
print(f'Path: {sys.path[:3]}...')

try:
    import knowledge_system
    print('✅ knowledge_system imported')
except Exception as e:
    print(f'❌ Import failed: {e}')

try:
    from PyQt6 import QtCore
    print('✅ PyQt6 imported')
except Exception as e:
    print(f'❌ PyQt6 failed: {e}')
" 2>&1

# 4. Check application logs
echo ""
echo "4️⃣ Checking application logs..."
echo "----------------------------------------"
if [ -f "$LOG_DIR/knowledge_system.log" ]; then
    echo "📄 Last 20 lines of app log:"
    tail -20 "$LOG_DIR/knowledge_system.log"
else
    echo "❓ No app logs found"
fi

# 5. Check for crash reports
echo ""
echo "5️⃣ Checking for crash reports..."
echo "----------------------------------------"
RECENT_CRASHES=$(find "$CRASH_DIR" -name "*Skip*" -o -name "*Python*" -mtime -1 2>/dev/null | head -5)
if [ -n "$RECENT_CRASHES" ]; then
    echo "⚠️ Found recent crash reports:"
    for crash in $RECENT_CRASHES; do
        echo ""
        echo "📋 $(basename "$crash"):"
        grep -A5 "Exception Type\|Termination Reason\|Crashed Thread" "$crash" 2>/dev/null | head -20
    done
else
    echo "✅ No recent crash reports"
fi

# 6. Check system console for errors
echo ""
echo "6️⃣ Checking system console (last 2 minutes)..."
echo "----------------------------------------"
log show --predicate 'eventMessage CONTAINS "Skip the Podcast" OR processImagePath CONTAINS "Skip the Podcast"' --last 2m --style compact 2>/dev/null | tail -30

# 7. Test launch with error capture
echo ""
echo "7️⃣ Testing direct launch..."
echo "----------------------------------------"
cd "$MACOS_DIR"
echo "Working directory: $(pwd)"
echo "Running launch script..."
timeout 10 bash -x ./launch 2>&1 | tail -50

# 8. Check for architecture issues
echo ""
echo "8️⃣ Checking architecture compatibility..."
echo "----------------------------------------"
echo "System arch: $(uname -m)"
echo "Python arch: $(file "$MACOS_DIR/venv/bin/python" | grep -o 'arm64\|x86_64')"

# Check a few key libraries
for lib in "$MACOS_DIR/venv/lib/python3.13/site-packages/PyQt6/Qt6/lib/QtCore.framework/QtCore" \
           "$MACOS_DIR/venv/lib/python3.13/site-packages/numpy/_core/_multiarray_umath.cpython-313-darwin.so"; do
    if [ -f "$lib" ]; then
        echo "$(basename "$lib"): $(file "$lib" | grep -o 'arm64\|x86_64' | head -1)"
    fi
done

echo ""
echo "🏁 Diagnosis Complete!"
echo "----------------------------------------"
echo "📄 Full diagnosis saved to: $DIAG_LOG"
echo ""
echo "🔎 Look for:"
echo "   - ❌ Import failures (missing dependencies)"
echo "   - Architecture mismatches (arm64 vs x86_64)"
echo "   - Python execution errors"
echo "   - Crash reports with specific error messages"
echo ""
echo "📤 Please share the diagnosis log for troubleshooting."
