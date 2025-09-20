#!/bin/bash
# Diagnose DMG build issue - check if venv was created during staging

echo "🔍 DMG Build Diagnosis"
echo "====================="

# Check if staging build exists
STAGING_APP="/Users/matthewgreer/Projects/Knowledge_Chipper/scripts/.app_build/Skip the Podcast Desktop.app"

if [ -d "$STAGING_APP" ]; then
    echo "✅ Staging app found: $STAGING_APP"

    # Check if venv exists in staging
    STAGING_VENV="$STAGING_APP/Contents/MacOS/venv"
    if [ -d "$STAGING_VENV" ]; then
        echo "✅ Virtual environment found in staging"
        echo "   Path: $STAGING_VENV"

        # Check if Python binary exists
        STAGING_PYTHON="$STAGING_VENV/bin/python"
        if [ -f "$STAGING_PYTHON" ]; then
            echo "✅ Python binary found: $STAGING_PYTHON"
            echo "   Version: $($STAGING_PYTHON --version 2>&1)"
        else
            echo "❌ Python binary missing: $STAGING_PYTHON"
        fi

        # List venv contents
        echo ""
        echo "📂 Virtual environment contents:"
        ls -la "$STAGING_VENV/"
        echo ""
        echo "📂 bin/ directory contents:"
        ls -la "$STAGING_VENV/bin/" | head -10

    else
        echo "❌ Virtual environment missing from staging: $STAGING_VENV"
    fi

    echo ""
    echo "📂 MacOS directory contents:"
    ls -la "$STAGING_APP/Contents/MacOS/" | head -15

else
    echo "❌ Staging app not found: $STAGING_APP"
    echo "   You may need to run the build script first"
fi

# Check installed app
INSTALLED_APP="/Applications/Skip the Podcast Desktop.app"
if [ -d "$INSTALLED_APP" ]; then
    echo ""
    echo "✅ Installed app found: $INSTALLED_APP"

    INSTALLED_VENV="$INSTALLED_APP/Contents/MacOS/venv"
    if [ -d "$INSTALLED_VENV" ]; then
        echo "✅ Virtual environment found in installed app"
    else
        echo "❌ Virtual environment missing from installed app: $INSTALLED_VENV"
        echo ""
        echo "📂 Installed MacOS directory contents:"
        ls -la "$INSTALLED_APP/Contents/MacOS/" | head -15
    fi
else
    echo ""
    echo "❌ Installed app not found: $INSTALLED_APP"
fi

echo ""
echo "🔍 Recent DMG files:"
find /Users/matthewgreer/Projects/Knowledge_Chipper/dist -name "*.dmg" -mtime -7 2>/dev/null | head -5
