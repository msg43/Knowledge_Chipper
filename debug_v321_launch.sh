#!/bin/bash
# Debug script for v3.2.1 launch issues

echo "🔍 Skip the Podcast Desktop v3.2.1 Debug"
echo "========================================"

APP_PATH="/Applications/Skip the Podcast Desktop.app"

# 1. Check if app exists and basic structure
echo "1. 📁 Checking app structure..."
if [ -d "$APP_PATH" ]; then
    echo "   ✅ App found: $APP_PATH"

    # Check version from Info.plist
    VERSION=$(defaults read "$APP_PATH/Contents/Info.plist" CFBundleShortVersionString 2>/dev/null || echo "Unknown")
    echo "   📋 Version: $VERSION"

    # Check executable
    EXECUTABLE="$APP_PATH/Contents/MacOS/launch"
    if [ -f "$EXECUTABLE" ]; then
        echo "   ✅ Launch script found: $EXECUTABLE"
        echo "   📏 Launch script size: $(wc -l < "$EXECUTABLE") lines"

        # Check if executable
        if [ -x "$EXECUTABLE" ]; then
            echo "   ✅ Launch script is executable"
        else
            echo "   ❌ Launch script lacks execute permissions"
            echo "   🔧 Fixing permissions..."
            chmod +x "$EXECUTABLE"
        fi
    else
        echo "   ❌ Launch script missing: $EXECUTABLE"
        echo "   📂 Contents of MacOS directory:"
        ls -la "$APP_PATH/Contents/MacOS/" 2>/dev/null || echo "   ❌ MacOS directory missing"
    fi
else
    echo "   ❌ App not found: $APP_PATH"
    exit 1
fi

echo ""

# 2. Check quarantine status
echo "2. 🔒 Checking quarantine status..."
QUARANTINE=$(xattr -l "$APP_PATH" 2>/dev/null | grep com.apple.quarantine || echo "")
if [ -n "$QUARANTINE" ]; then
    echo "   ⚠️  App is quarantined: $QUARANTINE"
    echo "   🔧 Removing quarantine..."
    sudo xattr -dr com.apple.quarantine "$APP_PATH"
    echo "   ✅ Quarantine removed"
else
    echo "   ✅ App is not quarantined"
fi

echo ""

# 3. Check where logs should be
echo "3. 📝 Checking log locations..."
LOG_DIR="$HOME/Library/Logs/Skip the Podcast Desktop"
LOG_FILE="$LOG_DIR/knowledge_system.log"

echo "   📂 Expected log directory: $LOG_DIR"
if [ -d "$LOG_DIR" ]; then
    echo "   ✅ Log directory exists"
    if [ -f "$LOG_FILE" ]; then
        echo "   📄 Log file exists: $LOG_FILE"
        echo "   📊 Log file size: $(wc -l < "$LOG_FILE" 2>/dev/null || echo "0") lines"
        echo "   🕒 Last modified: $(stat -f "%Sm" "$LOG_FILE" 2>/dev/null || echo "Unknown")"
    else
        echo "   ❌ Log file missing: $LOG_FILE"
    fi
else
    echo "   ❌ Log directory missing: $LOG_DIR"
    echo "   🔧 Creating log directory..."
    mkdir -p "$LOG_DIR"
    echo "   ✅ Log directory created"
fi

echo ""

# 4. Check Console.app for system-level errors
echo "4. 🖥️  Checking system logs for recent app launch attempts..."
echo "   📋 Looking for errors in last 5 minutes..."
LOG_ENTRIES=$(log show --predicate 'process CONTAINS "Skip the Podcast"' --info --last 5m 2>/dev/null | head -20)
if [ -n "$LOG_ENTRIES" ]; then
    echo "   📝 Recent system log entries:"
    echo "$LOG_ENTRIES"
else
    echo "   ℹ️  No recent system log entries found"
fi

echo ""

# 5. Try direct launch with debugging
echo "5. 🚀 Attempting direct launch with debugging..."
echo "   📍 This will show exactly what happens when the app tries to start..."
echo "   ⏳ Press Ctrl+C if it hangs for more than 30 seconds"
echo ""

cd "$APP_PATH/Contents/MacOS"
export DYLD_PRINT_LIBRARIES=1
timeout 30s ./launch 2>&1 | tee /tmp/skip_podcast_direct_launch.log || {
    EXIT_CODE=$?
    echo ""
    if [ $EXIT_CODE -eq 124 ]; then
        echo "   ⏰ Launch timed out after 30 seconds"
    else
        echo "   ❌ Launch failed with exit code: $EXIT_CODE"
    fi
}

echo ""
echo "📋 Debug Summary:"
echo "=================="
echo "App Path: $APP_PATH"
echo "Version: $VERSION"
echo "Expected Log: $LOG_FILE"
echo "Direct Launch Log: /tmp/skip_podcast_direct_launch.log"
echo ""
echo "💡 Next steps:"
echo "   1. Check the direct launch log: cat /tmp/skip_podcast_direct_launch.log"
echo "   2. Look for missing dependencies or permission issues"
echo "   3. Try launching from Applications folder again"
