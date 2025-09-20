#!/bin/bash
# Note: Not using set -e to allow graceful failure handling

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "📦 Bundling all models for distribution..."

# Get the app path (either from argument or default)
if [ -n "${1:-}" ]; then
    MACOS_PATH="$1"
else
    MACOS_PATH="$SCRIPT_DIR/.app_build/Skip the Podcast Desktop.app/Contents/MacOS"
fi

if [ ! -d "$MACOS_PATH" ]; then
    echo "❌ Error: App bundle not found at $MACOS_PATH"
    exit 1
fi

echo "🎯 App bundle: $MACOS_PATH"

# Create models directory
MODELS_DIR="$MACOS_PATH/models"
mkdir -p "$MODELS_DIR"

# Smart thin DMG strategy - NO models bundled
echo "📦 Creating thin DMG - models will download on first run..."
echo "   This keeps the DMG small and fast to download"
echo "   Models will be intelligently recommended based on user's system specs"
echo ""
echo "🧠 Smart model selection will offer:"
echo "   • Basic models for older/slower systems"
echo "   • Premium models for high-end systems with sufficient RAM/storage"
echo "   • All models downloaded from GitHub release for reliability"

echo "✅ Model bundling completed"
