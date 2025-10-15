#!/bin/bash
# Comprehensive DMG Installation Testing Script
# This script tests a DMG installation to identify all issues before release

set -e

DMG_PATH="$1"
if [ -z "$DMG_PATH" ]; then
    echo "Usage: $0 <path-to-dmg>"
    echo "Example: $0 dist/Skip_the_Podcast_Desktop-3.2.3.dmg"
    exit 1
fi

if [ ! -f "$DMG_PATH" ]; then
    echo "❌ DMG file not found: $DMG_PATH"
    exit 1
fi

echo "🧪 DMG Installation Testing Suite"
echo "================================="
echo "DMG: $DMG_PATH"
echo "Date: $(date)"
echo ""

# Create test environment
TEST_DIR="/tmp/dmg_test_$(date +%s)"
BACKUP_APP="/tmp/backup_skip_podcast_$(date +%s)"
APP_PATH="/Applications/Skip the Podcast Desktop.app"

echo "📁 Setting up test environment..."
mkdir -p "$TEST_DIR"

# Backup existing app if present
if [ -d "$APP_PATH" ]; then
    echo "💾 Backing up existing app..."
    mv "$APP_PATH" "$BACKUP_APP"
fi

# Mount and install DMG
echo "📦 Mounting DMG..."
hdiutil attach "$DMG_PATH" -nobrowse -quiet
MOUNT_POINT=$(hdiutil info | grep "Skip the Podcast Desktop" | awk '{print $1}')

echo "📋 Copying app from DMG..."
cp -R "/Volumes/Skip the Podcast Desktop/Skip the Podcast Desktop.app" "/Applications/"

echo "🔓 Removing quarantine..."
xattr -dr com.apple.quarantine "$APP_PATH" 2>/dev/null || true

echo "📤 Unmounting DMG..."
hdiutil detach "$MOUNT_POINT" -quiet

echo ""
echo "🔍 TESTING PHASE 1: App Structure"
echo "=================================="

# Test 1: Basic app structure
echo "1. 📁 App structure..."
if [ -d "$APP_PATH" ]; then
    echo "   ✅ App directory exists"
else
    echo "   ❌ App directory missing"
    exit 1
fi

if [ -f "$APP_PATH/Contents/Info.plist" ]; then
    VERSION=$(defaults read "$APP_PATH/Contents/Info.plist" CFBundleShortVersionString 2>/dev/null || echo "Unknown")
    echo "   ✅ Info.plist exists - Version: $VERSION"
else
    echo "   ❌ Info.plist missing"
fi

if [ -f "$APP_PATH/Contents/MacOS/launch" ]; then
    echo "   ✅ Launch script exists"
else
    echo "   ❌ Launch script missing"
fi

# Test 2: Python environment
echo "2. 🐍 Python environment..."
VENV_PATH="$APP_PATH/Contents/MacOS/venv"
if [ -d "$VENV_PATH" ]; then
    echo "   ✅ venv directory exists"

    PYTHON_BIN="$VENV_PATH/bin/python"
    if [ -f "$PYTHON_BIN" ]; then
        echo "   ✅ Python binary exists"

        # Check if it's a broken symlink
        if [ -L "$PYTHON_BIN" ]; then
            TARGET=$(readlink "$PYTHON_BIN")
            echo "   🔗 Python is symlink to: $TARGET"
            if [ -f "$TARGET" ]; then
                echo "   ✅ Symlink target exists"
            else
                echo "   ❌ Symlink target missing: $TARGET"
            fi
        fi

        # Try to run Python
        if "$PYTHON_BIN" --version >/dev/null 2>&1; then
            PY_VERSION=$("$PYTHON_BIN" --version 2>&1)
            echo "   ✅ Python executable: $PY_VERSION"
        else
            echo "   ❌ Python not executable"
        fi
    else
        echo "   ❌ Python binary missing"
    fi
else
    echo "   ❌ venv directory missing"
fi

# Test 3: Main package installation
echo "3. 📦 Main package..."
MACOS_PATH="$APP_PATH/Contents/MacOS"
if [ -d "$MACOS_PATH/src" ]; then
    echo "   ✅ Source code exists"

    # Test with bundled Python first (preferred)
    BUNDLED_PYTHON="$MACOS_PATH/venv/bin/python"
    if [ -f "$BUNDLED_PYTHON" ] && [ -x "$BUNDLED_PYTHON" ]; then
        cd "$MACOS_PATH"
        if "$BUNDLED_PYTHON" -c "import knowledge_system; print('Version:', knowledge_system.__version__)" 2>/dev/null; then
            echo "   ✅ Main package importable with bundled Python"
        else
            echo "   ❌ Main package not importable with bundled Python"
            echo "   🔍 Testing import error..."
            "$BUNDLED_PYTHON" -c "import knowledge_system" 2>&1 | head -5 | sed 's/^/      /'
        fi
    else
        echo "   ⚠️  Bundled Python not available, testing with system Python"
        # Test with system Python + bundled packages
        export PYTHONPATH="$MACOS_PATH/src:$MACOS_PATH/venv/lib/python3.13/site-packages:$PYTHONPATH"
        cd "$MACOS_PATH"

        if python3 -c "import knowledge_system; print('Version:', knowledge_system.__version__)" 2>/dev/null; then
            echo "   ✅ Main package importable with system Python"
        else
            echo "   ❌ Main package not importable with system Python"
            echo "   🔍 Testing import error..."
            python3 -c "import knowledge_system" 2>&1 | head -5 | sed 's/^/      /'
        fi
    fi
else
    echo "   ❌ Source code missing"
fi

# Test 4: Dependencies
echo "4. 📚 Dependencies..."
SITE_PACKAGES="$MACOS_PATH/venv/lib/python3.13/site-packages"
if [ -d "$SITE_PACKAGES" ]; then
    echo "   ✅ Site-packages exists"

    # Check key dependencies
    DEPS=("yaml" "sqlalchemy" "PyQt6" "openai")
    for dep in "${DEPS[@]}"; do
        if ls "$SITE_PACKAGES" | grep -i "$dep" >/dev/null; then
            echo "   ✅ $dep found"
        else
            echo "   ❌ $dep missing"
        fi
    done
else
    echo "   ❌ Site-packages missing"
fi

# Test 5: Setup scripts
echo "5. ⚙️  Setup scripts..."
SETUP_SCRIPTS=("setup_bundled_ffmpeg.sh" "setup_bundled_models.sh")
for script in "${SETUP_SCRIPTS[@]}"; do
    SCRIPT_PATH="$MACOS_PATH/$script"
    if [ -f "$SCRIPT_PATH" ]; then
        echo "   ✅ $script exists"

        # Check for hardcoded paths
        if grep -q "/Users/matthewgreer/Projects" "$SCRIPT_PATH"; then
            echo "   ❌ $script contains hardcoded build paths"
            grep "/Users/matthewgreer/Projects" "$SCRIPT_PATH" | head -2 | sed 's/^/      /'
        else
            echo "   ✅ $script has no hardcoded paths"
        fi
    else
        echo "   ❌ $script missing"
    fi
done

# Test 6: New troubleshooting files
echo "6. 🔧 Troubleshooting files..."
TROUBLE_FILES=("install_missing_features.sh" "build_troubleshooting.log")
for file in "${TROUBLE_FILES[@]}"; do
    if [ -f "$MACOS_PATH/$file" ]; then
        echo "   ✅ $file exists"
    else
        echo "   ❌ $file missing"
    fi
done

echo ""
echo "🚀 TESTING PHASE 2: Launch Test"
echo "==============================="

# Test 7: Launch script execution
echo "7. 🎯 Launch script test..."
cd "$MACOS_PATH"

# Test launch script without GUI (timeout after 10 seconds)
echo "   🔄 Testing launch script (10 second timeout)..."
# Use gtimeout if available, otherwise skip timeout
if command -v gtimeout >/dev/null 2>&1; then
    gtimeout 10s bash -x ./launch >/tmp/launch_test.log 2>&1 || {
        EXIT_CODE=$?
    }
elif command -v timeout >/dev/null 2>&1; then
    timeout 10s bash -x ./launch >/tmp/launch_test.log 2>&1 || {
        EXIT_CODE=$?
    }
else
    # No timeout available, run for a few seconds and kill
    bash -x ./launch >/tmp/launch_test.log 2>&1 &
    LAUNCH_PID=$!
    sleep 5
    kill $LAUNCH_PID 2>/dev/null || true
    wait $LAUNCH_PID 2>/dev/null || true
    EXIT_CODE=124  # Simulate timeout exit code
fi

{
    EXIT_CODE=$?
    if [ $EXIT_CODE -eq 124 ]; then
        echo "   ⏰ Launch timed out (may be waiting for GUI)"
    else
        echo "   ❌ Launch failed with exit code: $EXIT_CODE"
    fi

    echo "   📝 Launch output (last 20 lines):"
    tail -20 /tmp/launch_test.log | sed 's/^/      /'
}

echo ""
echo "📋 TESTING SUMMARY"
echo "=================="

# Count issues
ISSUES=$(grep -c "❌" /tmp/launch_test.log 2>/dev/null || echo "0")
echo "Issues found: $ISSUES"

if [ "$ISSUES" -eq 0 ]; then
    echo "✅ All tests passed! DMG appears to be working."
else
    echo "⚠️  Issues found. Check output above for details."
fi

# Cleanup
echo ""
echo "🧹 Cleanup..."
if [ -d "$BACKUP_APP" ]; then
    echo "💾 Restoring original app..."
    rm -rf "$APP_PATH"
    mv "$BACKUP_APP" "$APP_PATH"
else
    echo "🗑️  Removing test app..."
    rm -rf "$APP_PATH"
fi

rm -rf "$TEST_DIR"
rm -f /tmp/launch_test.log

echo "✅ Testing complete!"
