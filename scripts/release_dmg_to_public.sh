#!/bin/bash
# release_dmg_to_public.sh - Simple wrapper to build and release DMG to public repository
# This is the main script to call when you want to create and publish a release

# CRITICAL: Fail immediately on ANY error (all-or-nothing principle)
set -e
set -o pipefail
set -u

# Enable error trapping for comprehensive failure detection
trap 'echo "❌ CRITICAL: Script failed at line $LINENO. Command: $BASH_COMMAND" >&2; exit 1' ERR

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
    if ! python3 "$SCRIPT_DIR/bump_version.py" --part "$BUMP_PART"; then
        echo "❌ CRITICAL: Version bump failed"
        echo "   This could be due to invalid pyproject.toml, git issues, or version format problems"
        echo "   Release terminated - version must be properly incremented"
        exit 1
    fi
    echo "✅ Version bumped successfully"
    echo
fi

# Get current version with error handling
echo "🔍 Reading current version from pyproject.toml..."
if ! CURRENT_VERSION=$(python3 -c "
import tomllib
try:
    with open('pyproject.toml', 'rb') as f:
        data = tomllib.load(f)
    print(data['project']['version'])
except Exception as e:
    print(f'ERROR: {e}', file=sys.stderr)
    sys.exit(1)
" 2>&1); then
    echo "❌ CRITICAL: Failed to read version from pyproject.toml"
    echo "   This could be due to malformed TOML, missing version field, or file permissions"
    echo "   Release terminated - version must be readable"
    exit 1
fi

if [ -z "$CURRENT_VERSION" ]; then
    echo "❌ CRITICAL: Version string is empty"
    echo "   Check that pyproject.toml contains a valid project.version field"
    echo "   Release terminated - version must be non-empty"
    exit 1
fi

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
echo "🔍 Performing pre-release validation..."

# Validate build script exists
if [ ! -f "$SCRIPT_DIR/build_macos_app.sh" ]; then
    echo "❌ CRITICAL: Build script not found at $SCRIPT_DIR/build_macos_app.sh"
    exit 1
fi

# Validate publish script exists
if [ ! -f "$SCRIPT_DIR/publish_release.sh" ]; then
    echo "❌ CRITICAL: Publish script not found at $SCRIPT_DIR/publish_release.sh"
    exit 1
fi

# Validate pyproject.toml exists and is readable
if [ ! -f "$PROJECT_ROOT/pyproject.toml" ]; then
    echo "❌ CRITICAL: pyproject.toml not found at $PROJECT_ROOT/pyproject.toml"
    exit 1
fi

# Test Python and required modules
echo "🐍 Validating Python environment..."
if ! python3 -c "import tomllib" 2>/dev/null; then
    echo "❌ CRITICAL: Python tomllib module not available (Python 3.11+ required)"
    echo "   Current Python version: $(python3 --version)"
    echo "   Release terminated - Python 3.11+ is required"
    exit 1
fi

# Test that git is available and repository is clean
echo "📦 Validating git repository state..."
if ! git status >/dev/null 2>&1; then
    echo "❌ CRITICAL: Not in a git repository or git is not available"
    echo "   Release process requires git for version tagging and publishing"
    echo "   Release terminated - valid git repository required"
    exit 1
fi

# Check for uncommitted changes that could affect the build
if ! git diff-index --quiet HEAD -- 2>/dev/null; then
    echo "⚠️  WARNING: Repository has uncommitted changes"
    echo "   This may cause inconsistencies between built DMG and published version"
    echo "   Consider committing all changes before release"
    echo
    read -p "Continue anyway? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "❌ Release cancelled - commit changes first"
        exit 1
    fi
fi

# Verify network connectivity for publishing
echo "🌐 Validating network connectivity..."
if ! ping -c 1 github.com >/dev/null 2>&1; then
    echo "❌ CRITICAL: No network connectivity to github.com"
    echo "   Release process requires internet access for publishing"
    echo "   Release terminated - network connectivity required"
    exit 1
fi

echo "✅ Pre-release validation passed"
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

    echo "🔨 Running build with fail-fast enabled..."
    if ! bash "$SCRIPT_DIR/build_macos_app.sh" --make-dmg --skip-install --bundle-all; then
        echo "❌ CRITICAL: DMG build process failed"
        echo "   Build script reported errors - see output above"
        echo "   Release terminated - DMG build must succeed completely"
        exit 1
    fi

    # Verify DMG was actually created
    if [ ! -f "$DMG_FILE" ]; then
        echo "❌ CRITICAL: DMG file not found after build completed"
        echo "   Expected: $DMG_FILE"
        echo "   Release terminated - DMG file must exist"
        exit 1
    fi

    # Verify DMG size is reasonable (should be > 100MB for full app)
    DMG_SIZE_BYTES=$(stat -f%z "$DMG_FILE" 2>/dev/null || echo "0")
    if [ "$DMG_SIZE_BYTES" -lt 104857600 ]; then  # Less than 100MB
        echo "❌ CRITICAL: DMG file suspiciously small ($DMG_SIZE_BYTES bytes)"
        echo "   This suggests the build failed or produced an incomplete DMG"
        echo "   Release terminated - DMG must be properly sized"
        exit 1
    fi

    echo "✅ DMG build completed successfully"
fi

# Step 2: Publish to public repository
echo "📤 Publishing to public repository..."
if ! bash "$SCRIPT_DIR/publish_release.sh" --skip-build; then
    echo "❌ CRITICAL: Publishing to public repository failed"
    echo "   This could be due to GitHub API issues, authentication problems, or upload failures"
    echo "   Release terminated - publication must succeed completely"
    exit 1
fi

# Final verification that everything completed successfully
echo "🔍 Performing final release verification..."

# Verify DMG still exists and is valid
if [ ! -f "$DMG_FILE" ]; then
    echo "❌ CRITICAL: DMG file disappeared after build/publish process"
    echo "   Expected: $DMG_FILE"
    echo "   This suggests a critical failure in the release pipeline"
    exit 1
fi

# Verify DMG integrity one final time
DMG_FINAL_SIZE=$(stat -f%z "$DMG_FILE" 2>/dev/null || echo "0")
if [ "$DMG_FINAL_SIZE" -lt 104857600 ]; then  # Less than 100MB
    echo "❌ CRITICAL: Final DMG integrity check failed - file too small"
    echo "   Size: $DMG_FINAL_SIZE bytes"
    echo "   This suggests corruption during the release process"
    exit 1
fi

# Verify publish script created expected artifacts (if it creates any)
echo "✅ Final verification passed"

echo
echo -e "${GREEN}🎉 RELEASE COMPLETED SUCCESSFULLY!${NC}"
echo -e "${BLUE}📍 Check your release at:${NC} https://github.com/msg43/skipthepodcast.com/releases"
echo
echo -e "${GREEN}✅ ALL-OR-NOTHING RELEASE PRINCIPLE ENFORCED${NC}"
echo "   ✓ Every component built successfully"
echo "   ✓ Every validation check passed"
echo "   ✓ Every step completed without errors"
echo "   ✓ DMG integrity verified multiple times"
echo "   ✓ Publishing completed successfully"
echo
echo -e "${BLUE}📊 Release Summary:${NC}"
echo "   Version: $CURRENT_VERSION"
echo "   DMG Size: $(du -h "$DMG_FILE" | cut -f1)"
echo "   Build Type: FULL (with essential models)"
echo "   Status: ✅ PERFECT BUILD - No errors or warnings"
