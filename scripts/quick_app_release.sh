#!/bin/bash
# quick_app_release.sh - Fast release for app code changes only
# Skips rebuilding static components (Python framework, AI models, FFmpeg)

set -e
set -o pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Parse arguments
BUMP_VERSION=0
BUMP_PART="patch"
UPLOAD_RELEASE=0

for arg in "$@"; do
    case "$arg" in
        --bump-version)
            BUMP_VERSION=1
            ;;
        --bump-part)
            BUMP_PART="$2"
            shift
            ;;
        --upload-release)
            UPLOAD_RELEASE=1
            ;;
        --help|-h)
            echo "Usage: $0 [options]"
            echo ""
            echo "Fast release workflow for app code changes only."
            echo "Skips rebuilding static components (Python framework, AI models, FFmpeg)."
            echo ""
            echo "Options:"
            echo "  --bump-version        Bump version before release"
            echo "  --bump-part PART      Version part to bump (patch|minor|major, default: patch)"
            echo "  --upload-release      Upload to GitHub releases"
            echo "  --help, -h           Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0                                    # Quick PKG build only"
            echo "  $0 --bump-version --upload-release   # Bump version and release"
            echo "  $0 --bump-part minor --upload-release # Minor version bump and release"
            echo ""
            echo "What this does:"
            echo "• Skips Python framework (uses existing)"
            echo "• Skips AI models bundle (uses existing)"
            echo "• Skips FFmpeg bundle (uses existing)"
            echo "• Only rebuilds PKG with your app code changes"
            echo "• Optionally bumps version and releases"
            exit 0
            ;;
        *)
            echo "❌ Unknown option: $arg"
            exit 1
            ;;
    esac
done

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m'

echo -e "${BLUE}${BOLD}⚡ Quick App Release Workflow${NC}"
echo "============================="
echo "Fast release for app code changes only"
echo "Skipping static components rebuild"
echo ""

# Function to print status
print_status() {
    echo -e "${GREEN}✅${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠️${NC} $1"
}

print_error() {
    echo -e "${RED}❌${NC} $1"
}

# Check prerequisites for upload
if [ $UPLOAD_RELEASE -eq 1 ]; then
    echo -e "${BLUE}📋 Checking GitHub CLI prerequisites...${NC}"

    if ! command -v gh &> /dev/null; then
        print_error "GitHub CLI (gh) is required for release upload but not installed"
        echo "Install with: brew install gh"
        exit 1
    fi

    if ! gh auth status &> /dev/null; then
        print_error "GitHub CLI not authenticated"
        echo "Authenticate with: gh auth login"
        exit 1
    fi

    print_status "GitHub CLI ready for release upload"
    echo ""
fi

# Check if static components exist and if app code changed
echo -e "${BLUE}📋 Checking existing components and app code changes...${NC}"

MISSING_COMPONENTS=()

if [ ! -f "$PROJECT_ROOT/dist/python-framework-3.13-macos.tar.gz" ]; then
    MISSING_COMPONENTS+=("Python framework")
fi

if [ ! -f "$PROJECT_ROOT/dist/ai-models-bundle.tar.gz" ]; then
    MISSING_COMPONENTS+=("AI models bundle")
fi

if [ ! -f "$PROJECT_ROOT/dist/ffmpeg-macos-universal.tar.gz" ]; then
    MISSING_COMPONENTS+=("FFmpeg bundle")
fi

# Check if app code has changed using intelligent cache
APP_CODE_STATUS=$("$SCRIPT_DIR/intelligent_build_cache.sh" check app_code 2>/dev/null | head -1)
if [[ "$APP_CODE_STATUS" == "REBUILD_NEEDED:"* ]]; then
    print_status "App code changes detected - PKG will be rebuilt"
elif [[ "$APP_CODE_STATUS" == "UP_TO_DATE:"* ]]; then
    print_warning "No app code changes detected since last build"
    echo "Proceeding anyway (you may have other changes)..."
fi

if [ ${#MISSING_COMPONENTS[@]} -gt 0 ]; then
    print_error "Missing static components: ${MISSING_COMPONENTS[*]}"
    echo ""
    echo "First-time setup required. Run:"
    echo "  ./scripts/build_complete_pkg.sh"
    echo ""
    echo "After that, you can use this quick release script for app updates."
    exit 1
fi

print_status "All static components available"

# Show component ages
echo ""
echo -e "${BLUE}📊 Component status:${NC}"

for component in "python-framework-3.13-macos.tar.gz" "ai-models-bundle.tar.gz" "ffmpeg-macos-universal.tar.gz"; do
    if [ -f "$PROJECT_ROOT/dist/$component" ]; then
        AGE_DAYS=$(( ($(date +%s) - $(stat -f %m "$PROJECT_ROOT/dist/$component")) / 86400 ))
        SIZE=$(du -h "$PROJECT_ROOT/dist/$component" | cut -f1)
        echo "  • $component: $SIZE (${AGE_DAYS} days old)"
    fi
done

echo ""

# Optional version bump
if [ $BUMP_VERSION -eq 1 ]; then
    echo -e "${BLUE}🔢 Bumping version ($BUMP_PART)...${NC}"

    CURRENT_VERSION=$(python3 -c "import tomllib; print(tomllib.load(open('$PROJECT_ROOT/pyproject.toml', 'rb'))['project']['version'])")
    echo "Current version: $CURRENT_VERSION"

    if ! python3 "$SCRIPT_DIR/bump_version.py" --part "$BUMP_PART"; then
        print_error "Version bump failed"
        exit 1
    fi

    NEW_VERSION=$(python3 -c "import tomllib; print(tomllib.load(open('$PROJECT_ROOT/pyproject.toml', 'rb'))['project']['version'])")
    print_status "Version bumped: $CURRENT_VERSION → $NEW_VERSION"
    echo ""
fi

# Quick PKG build (skipping static components)
echo -e "${BLUE}📦 Building PKG with app code changes...${NC}"

BUILD_CMD="$SCRIPT_DIR/build_complete_pkg.sh --skip-framework --skip-models --skip-ffmpeg --build-only --force"
# Set environment variable to avoid sudo prompts during build
export NO_SUDO_BUILD=1

echo "Running: $BUILD_CMD"
echo ""

if $BUILD_CMD; then
    print_status "PKG built successfully"
else
    print_error "PKG build failed"
    exit 1
fi

# Handle quick release upload separately (PKG only)
if [ $UPLOAD_RELEASE -eq 1 ]; then
    echo ""
    echo -e "${BLUE}🚀 Creating quick GitHub release (DMG installer)...${NC}"

    VERSION=$(python3 -c "import tomllib; print(tomllib.load(open('$PROJECT_ROOT/pyproject.toml', 'rb'))['project']['version'])")
    PKG_FILE="$PROJECT_ROOT/dist/Skip_the_Podcast_Desktop-$VERSION.pkg"
    README_FILE="$PROJECT_ROOT/README.md"

    # Also create the installer app if PKG exists
    if [ -f "$PKG_FILE" ]; then
        echo -e "${BLUE}🔐 Creating installer app...${NC}"
        if "$SCRIPT_DIR/create_installer_app.sh" >/dev/null 2>&1; then
            AUTH_DMG="$PROJECT_ROOT/dist/Skip_the_Podcast_Desktop-$VERSION-Installer.dmg"
            if [ -f "$AUTH_DMG" ]; then
                echo -e "${GREEN}✅ Installer app created${NC}"
            fi
        else
            echo -e "${YELLOW}Note: Could not create installer app${NC}"
        fi
    fi

    if [ ! -f "$PKG_FILE" ]; then
        print_error "PKG file not found: $PKG_FILE"
        exit 1
    fi

    # Check if release already exists
    if gh release view "v$VERSION" --repo msg43/skipthepodcast.com &>/dev/null; then
        echo -e "${YELLOW}Release v$VERSION already exists. Updating with new installer...${NC}"

        # Delete existing assets if they exist
        gh release delete-asset "v$VERSION" "Skip_the_Podcast_Desktop-$VERSION.pkg" --repo msg43/skipthepodcast.com --yes 2>/dev/null || true
        gh release delete-asset "v$VERSION" "README.md" --repo msg43/skipthepodcast.com --yes 2>/dev/null || true
        gh release delete-asset "v$VERSION" "Skip_the_Podcast_Desktop-$VERSION-Installer.dmg" --repo msg43/skipthepodcast.com --yes 2>/dev/null || true
        gh release delete-asset "v$VERSION" "Skip_the_Podcast_Desktop-$VERSION-Installer.dmg.sha256" --repo msg43/skipthepodcast.com --yes 2>/dev/null || true

        # Only upload DMG installer (not raw PKG)
        AUTH_DMG="$PROJECT_ROOT/dist/Skip_the_Podcast_Desktop-$VERSION-Installer.dmg"
        if [ -f "$AUTH_DMG" ] && [ -f "$AUTH_DMG.sha256" ]; then
            gh release upload "v$VERSION" "$AUTH_DMG" "$AUTH_DMG.sha256" "$README_FILE" --repo msg43/skipthepodcast.com
        else
            print_error "Authentication installer DMG not found"
            exit 1
        fi
        print_status "Installer updated in existing release v$VERSION"
    else
        # Create new release with PKG only
        RELEASE_NOTES="# Skip the Podcast Desktop v$VERSION

## Quick App Update
This is a quick release containing app code changes only. Static components (Python framework, AI models, FFmpeg) are downloaded automatically during installation.

### Installation
Download and run the PKG installer. All required components will be downloaded automatically:
- Python Framework (~40MB)
- AI Models (~1.2GB)
- FFmpeg (~48MB)
- Ollama (~50MB)
- Hardware-optimized Ollama model (1.3-4.7GB)

### Changes
App code improvements and bug fixes. See [CHANGELOG.md](https://github.com/msg43/Knowledge_Chipper/blob/main/CHANGELOG.md) for details."

        # Only upload DMG installer (not raw PKG)
        AUTH_DMG="$PROJECT_ROOT/dist/Skip_the_Podcast_Desktop-$VERSION-Installer.dmg"
        if [ -f "$AUTH_DMG" ] && [ -f "$AUTH_DMG.sha256" ]; then
            gh release create "v$VERSION" "$AUTH_DMG" "$AUTH_DMG.sha256" "$README_FILE" \
                --repo msg43/skipthepodcast.com \
                --title "Skip the Podcast Desktop v$VERSION" \
                --notes "$RELEASE_NOTES" \
                --generate-notes=false \
                --latest
        else
            print_error "Authentication installer DMG not found"
            exit 1
        fi

        print_status "New release v$VERSION created"
    fi
fi

# Summary
echo ""
echo -e "${GREEN}${BOLD}⚡ Quick Release Complete!${NC}"
echo "==============================="

VERSION=$(python3 -c "import tomllib; print(tomllib.load(open('$PROJECT_ROOT/pyproject.toml', 'rb'))['project']['version'])")
PKG_SIZE=$(du -h "$PROJECT_ROOT/dist/Skip_the_Podcast_Desktop-$VERSION.pkg" 2>/dev/null | cut -f1 || echo "N/A")

echo "Version: $VERSION"
echo "PKG Size: $PKG_SIZE"
echo ""
echo "What was rebuilt:"
echo "• ✅ PKG installer (with your app code changes)"
echo "• ⏭️ Python framework (reused existing)"
echo "• ⏭️ AI models (reused existing)"
echo "• ⏭️ FFmpeg (reused existing)"

if [ $UPLOAD_RELEASE -eq 1 ]; then
    echo ""
    echo "🚀 Release uploaded to GitHub!"
    echo "Download URL: https://github.com/msg43/skipthepodcast.com/releases/tag/v$VERSION"
else
    echo ""
    echo "📦 PKG ready for testing: dist/Skip_the_Podcast_Desktop-$VERSION.pkg"
    echo ""
    echo "To upload to GitHub:"
    echo "  ./scripts/create_github_release.sh"
fi

echo ""
echo "💡 Tip: This workflow is perfect for frequent app updates!"
echo "   Only rebuild static components when dependencies change."
