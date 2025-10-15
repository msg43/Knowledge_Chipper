#!/bin/bash
# release_minimal_dmg.sh - Build and release MINIMAL DMG without bundled models
# This creates a ~1GB DMG where models download on first use

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}🚀 Knowledge Chipper MINIMAL Release Builder${NC}"
echo "============================================"
echo -e "${YELLOW}📦 This creates a smaller DMG (~1GB) without bundled models${NC}"
echo

# Get current directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Ensure we're in the right place
cd "$PROJECT_ROOT"

# Get current version
CURRENT_VERSION=$(python3 -c "
import tomllib
with open('pyproject.toml', 'rb') as f:
    data = tomllib.load(f)
print(data['project']['version'])
")

echo -e "${BLUE}📋 Current version:${NC} $CURRENT_VERSION"
echo -e "${BLUE}📦 This will:${NC}"
echo "   1. Build a MINIMAL DMG (~1GB)"
echo "   2. Models will download on first use"
echo "   3. Create a tagged release on GitHub"
echo "   4. Upload the DMG to the public repository"
echo
echo -e "${YELLOW}⚡ Use this for:${NC}"
echo "   • Faster downloads"
echo "   • Users with good internet"
echo "   • Testing/development"
echo
echo -e "${YELLOW}🔗 Target repository:${NC} https://github.com/msg43/skipthepodcast.com"
echo

# Check if DMG already exists
DMG_FILE="$PROJECT_ROOT/dist/Skip_the_Podcast_Desktop-${CURRENT_VERSION}.dmg"
if [ -f "$DMG_FILE" ]; then
    DMG_SIZE=$(du -h "$DMG_FILE" | cut -f1)
    echo -e "${GREEN}✅ DMG already exists:${NC} Skip_the_Podcast_Desktop-${CURRENT_VERSION}.dmg ($DMG_SIZE)"
    echo
    read -p "Use existing DMG or rebuild? (u/rebuild): " -n 1 -r
    echo

    if [[ $REPLY =~ ^[Rr]$ ]]; then
        echo "🏗️ Will rebuild DMG..."
        rm -f "$DMG_FILE"
    else
        echo "📦 Will use existing DMG"
    fi
fi

# Ask for confirmation
echo
read -p "Continue with MINIMAL release? (y/N): " -n 1 -r
echo

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "❌ Release cancelled"
    exit 0
fi

echo
echo "🚀 Starting minimal release process..."

# Step 1: Build minimal DMG if needed
if [ ! -f "$DMG_FILE" ]; then
    echo "🏗️ Building minimal DMG..."

    # Explicitly disable full bundling
    export BUNDLE_ALL_MODELS=0

    # Check for HF token (still needed for pyannote)
    if [ -z "$HF_TOKEN" ] && [ -f "$PROJECT_ROOT/config/credentials.yaml" ]; then
        HF_TOKEN=$(grep "huggingface_token:" "$PROJECT_ROOT/config/credentials.yaml" | sed 's/.*: //' | tr -d '"' | tr -d "'")
    fi
    export HF_TOKEN

    # Build without --bundle-all flag
    bash "$SCRIPT_DIR/build_macos_app.sh" --make-dmg --skip-install

    if [ ! -f "$DMG_FILE" ]; then
        echo "❌ Failed to create DMG"
        exit 1
    fi
fi

# Step 2: Publish to public repository
echo "📤 Publishing to public repository..."
bash "$SCRIPT_DIR/publish_release.sh" --skip-build

echo
echo -e "${GREEN}🎉 Minimal release complete!${NC}"
echo -e "${BLUE}📍 Check your release at:${NC} https://github.com/msg43/skipthepodcast.com/releases"
