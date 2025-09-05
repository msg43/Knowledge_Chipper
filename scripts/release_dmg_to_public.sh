#!/bin/bash
# release_dmg_to_public.sh - Simple wrapper to build and release DMG to public repository
# This is the main script to call when you want to create and publish a release

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}🚀 Knowledge Chipper Release Builder${NC}"
echo "====================================="
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
echo "   1. Build a DMG (or use existing)"
echo "   2. Create a tagged release on GitHub"
echo "   3. Upload the DMG to the public repository"
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
read -p "Continue with release? (y/N): " -n 1 -r
echo

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "❌ Release cancelled"
    exit 0
fi

echo
echo "🚀 Starting release process..."

# Step 1: Build DMG if needed
if [ ! -f "$DMG_FILE" ]; then
    echo "🏗️ Building DMG..."
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
echo -e "${GREEN}🎉 Release complete!${NC}"
echo -e "${BLUE}📍 Check your release at:${NC} https://github.com/msg43/skipthepodcast.com/releases"
