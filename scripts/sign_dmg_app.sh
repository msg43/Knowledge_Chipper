#!/bin/bash
# Sign the app bundle to avoid Gatekeeper issues
# This uses ad-hoc signing (no certificate required)

set -e

echo "🔐 Ad-hoc Code Signing for Skip the Podcast Desktop"
echo "=================================================="
echo ""

# Check if we're building or have a staged app
if [ "$1" == "--dmg" ]; then
    # Sign the app inside the DMG (requires mounting)
    DMG_PATH="${2:-dist/Skip_the_Podcast_Desktop-3.2.8.dmg}"

    if [ ! -f "$DMG_PATH" ]; then
        echo "❌ DMG not found: $DMG_PATH"
        echo "Usage: $0 --dmg [path/to/dmg]"
        exit 1
    fi

    echo "📦 Mounting DMG..."
    MOUNT_POINT=$(hdiutil attach "$DMG_PATH" | grep "/Volumes" | awk '{print $3}')
    APP_PATH="$MOUNT_POINT/Skip the Podcast Desktop.app"
else
    # Sign the staged app before DMG creation
    APP_PATH="${1:-scripts/.app_build/Skip the Podcast Desktop.app}"
fi

if [ ! -d "$APP_PATH" ]; then
    echo "❌ App not found at: $APP_PATH"
    exit 1
fi

echo "📍 Signing app at: $APP_PATH"
echo ""

# Remove existing signatures and extended attributes
echo "🧹 Cleaning existing signatures and attributes..."
xattr -cr "$APP_PATH" 2>/dev/null || true
codesign --remove-signature "$APP_PATH" 2>/dev/null || true

# Sign all embedded frameworks and libraries first
echo "📚 Signing embedded components..."
find "$APP_PATH" -type f -name "*.dylib" -o -name "*.so" | while read -r lib; do
    echo "   Signing: $(basename "$lib")"
    codesign --force --sign - "$lib" 2>/dev/null || true
done

# Sign Python binaries
echo "🐍 Signing Python binaries..."
if [ -d "$APP_PATH/Contents/MacOS/venv/bin" ]; then
    for py in "$APP_PATH/Contents/MacOS/venv/bin/python"*; do
        if [ -f "$py" ]; then
            echo "   Signing: $(basename "$py")"
            codesign --force --sign - "$py"
        fi
    done
fi

# Sign FFMPEG binaries if present
if [ -d "$APP_PATH/Contents/MacOS/Library/Application Support/Knowledge_Chipper/bin" ]; then
    echo "🎬 Signing FFMPEG binaries..."
    for bin in "$APP_PATH/Contents/MacOS/Library/Application Support/Knowledge_Chipper/bin/"*; do
        if [ -f "$bin" ]; then
            echo "   Signing: $(basename "$bin")"
            codesign --force --sign - "$bin"
        fi
    done
fi

# Sign the main app bundle (deep signing)
echo "📱 Signing main app bundle (deep)..."
codesign --force --deep --sign - "$APP_PATH"

# Verify the signature
echo ""
echo "🔍 Verifying signature..."
if codesign --verify --verbose "$APP_PATH"; then
    echo "✅ App successfully signed!"
else
    echo "⚠️  Signature verification failed, but app may still work"
fi

# Check Gatekeeper assessment
echo ""
echo "🛡️  Checking Gatekeeper assessment..."
spctl -a -t exec -vv "$APP_PATH" 2>&1 || echo "⚠️  Gatekeeper check failed (normal for ad-hoc signing)"

if [ "$1" == "--dmg" ]; then
    echo ""
    echo "💿 Unmounting DMG..."
    hdiutil detach "$MOUNT_POINT" -quiet
    echo ""
    echo "⚠️  Note: DMG was signed in read-only mode"
    echo "📍 To create a signed DMG, sign the app BEFORE creating the DMG"
fi

echo ""
echo "✨ Signing complete!"
echo ""
echo "📌 Next steps:"
echo "1. If signed before DMG: Create DMG with signed app"
echo "2. If signed after install: Remove quarantine with:"
echo "   sudo xattr -dr com.apple.quarantine '/Applications/Skip the Podcast Desktop.app'"
echo "3. For permanent solution: Get an Apple Developer certificate"
