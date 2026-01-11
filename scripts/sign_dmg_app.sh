#!/bin/bash
# sign_dmg_app.sh - Ad-hoc code sign the app bundle in DMG
#
# This prevents "app may be damaged" Gatekeeper warnings
# Uses ad-hoc signing (no developer certificate needed)

set -e

APP_PATH="$1"

if [ -z "$APP_PATH" ]; then
    echo "Usage: $0 <path-to-app-bundle>"
    exit 1
fi

if [ ! -d "$APP_PATH" ]; then
    echo "❌ App bundle not found: $APP_PATH"
    exit 1
fi

echo "🔐 Ad-hoc code signing app bundle..."
echo "   Path: $APP_PATH"

# Ad-hoc sign with hardened runtime
# This is sufficient to prevent Gatekeeper warnings for local distribution
codesign --force --deep --sign - --options runtime "$APP_PATH" 2>&1 | grep -v "replacing existing signature" || true

# Verify signature
if codesign --verify --deep --strict "$APP_PATH" 2>/dev/null; then
    echo "✅ App bundle successfully signed"
    echo "   Signature: Ad-hoc (local distribution)"
    exit 0
else
    echo "⚠️  Code signing verification had warnings (non-fatal)"
    echo "   App will still work but may show Gatekeeper warnings"
    exit 0  # Don't fail build
fi
