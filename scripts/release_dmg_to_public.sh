#!/bin/bash
# release_dmg_to_public.sh - Simple wrapper to build and release DMG to public repository
# This is the main script to call when you want to create and publish a release

set -e

# Parse command line arguments
BUMP_VERSION=0
BUMP_PART="patch"

while [[ $# -gt 0 ]]; do
    case $1 in
        --bump-version)
            BUMP_VERSION=1
            shift
            ;;
        --bump-part)
            BUMP_PART="$2"
            if [[ ! "$BUMP_PART" =~ ^(patch|minor|major)$ ]]; then
                echo "❌ Invalid bump part: $BUMP_PART. Must be patch, minor, or major."
                exit 1
            fi
            shift 2
            ;;
        --help|-h)
            echo "Usage: $0 [options]"
            echo ""
            echo "Options:"
            echo "  --bump-version        Automatically increment version before release"
            echo "  --bump-part PART      Which version part to bump (patch|minor|major, default: patch)"
            echo "                        Only used with --bump-version"
            echo "  --help, -h           Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0                           # Release current version"
            echo "  $0 --bump-version            # Bump patch version and release"
            echo "  $0 --bump-version --bump-part minor  # Bump minor version and release"
            exit 0
            ;;
        *)
            echo "❌ Unknown option: $1"
            echo "Use --help for usage information."
            exit 1
            ;;
    esac
done

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

# Bump version if requested
if [ "$BUMP_VERSION" -eq 1 ]; then
    echo -e "${BLUE}📈 Bumping version (${BUMP_PART})...${NC}"
    python3 "$SCRIPT_DIR/bump_version.py" --part "$BUMP_PART"
    if [ $? -ne 0 ]; then
        echo "❌ Failed to bump version"
        exit 1
    fi
    echo
fi

# Get current version
CURRENT_VERSION=$(python3 -c "
import tomllib
with open('pyproject.toml', 'rb') as f:
    data = tomllib.load(f)
print(data['project']['version'])
")

echo -e "${BLUE}📋 Current version:${NC} $CURRENT_VERSION"
if [ "$BUMP_VERSION" -eq 1 ]; then
    echo -e "${BLUE}📈 Version was bumped using:${NC} --bump-part $BUMP_PART"
fi
echo -e "${BLUE}📦 This will:${NC}"
echo "   1. Build a FULL DMG with essential models (~2.0GB)"
echo "   2. Create a tagged release on GitHub"
echo "   3. Upload the DMG to the public repository"
echo
echo -e "${YELLOW}📌 Note:${NC} FULL build includes essential models + MVP LLM auto-download (GitHub 2GB compliant)"
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
    echo "🏗️ Building FULL DMG with all models..."

    # Clean staging directory to ensure fresh build
    echo "🧹 Cleaning staging directory for fresh build..."
    rm -rf "$SCRIPT_DIR/.app_build"

    # Default to full build with all models bundled
    export BUNDLE_ALL_MODELS=1

    # Check for HF token
    if [ -z "$HF_TOKEN" ] && [ -f "$PROJECT_ROOT/config/credentials.yaml" ]; then
        HF_TOKEN=$(grep "huggingface_token:" "$PROJECT_ROOT/config/credentials.yaml" | sed 's/.*: //' | tr -d '"' | tr -d "'")
    fi
    export HF_TOKEN

    bash "$SCRIPT_DIR/build_macos_app.sh" --make-dmg --skip-install --bundle-all

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
