#!/bin/bash
# Simple GitHub Release Creator - PKG only

set -e

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
DIST_DIR="$PROJECT_ROOT/dist"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color
BOLD='\033[1m'

print_status() {
    echo -e "${GREEN}✅${NC} $1"
}

print_error() {
    echo -e "${RED}❌${NC} $1"
}

echo -e "${BLUE}${BOLD}📦 Simple GitHub Release Creator${NC}"
echo "=================================="

# Get version
VERSION=$(grep "^version = " "$PROJECT_ROOT/pyproject.toml" | cut -d'"' -f2)
RELEASE_TAG="v${VERSION}"
echo "Version: $VERSION"
echo "Release Tag: $RELEASE_TAG"

# Configuration
GITHUB_REPO="msg43/Skipthepodcast.com"
PKG_FILE="$DIST_DIR/Skip_the_Podcast_Desktop-${VERSION}.pkg"

# Check prerequisites
echo -e "\n${BLUE}📋 Checking prerequisites...${NC}"

# Check if GitHub CLI is installed
if ! command -v gh &> /dev/null; then
    print_error "GitHub CLI (gh) is not installed"
    echo "Install with: brew install gh"
    exit 1
fi

# Check if authenticated
if ! gh auth status &> /dev/null; then
    print_error "Not authenticated with GitHub"
    echo "Run: gh auth login"
    exit 1
fi

print_status "GitHub CLI authenticated"

# Verify PKG exists
echo -e "\n${BLUE}🔍 Verifying PKG installer...${NC}"
if [ ! -f "$PKG_FILE" ]; then
    print_error "PKG not found: $PKG_FILE"
    echo "Run: ./scripts/build_pkg_installer.sh"
    exit 1
fi

PKG_SIZE=$(du -h "$PKG_FILE" | cut -f1)
print_status "Skip_the_Podcast_Desktop-${VERSION}.pkg ($PKG_SIZE)"

# Create simple release notes
echo -e "\n${BLUE}📝 Creating release notes...${NC}"
RELEASE_NOTES_FILE="$(mktemp).md"

cat > "$RELEASE_NOTES_FILE" << EOF
# Skip the Podcast Desktop v${VERSION}

Download and install the PKG file below.
EOF

print_status "Release notes created"

# Check for existing release
echo -e "\n${BLUE}🔍 Checking for existing release...${NC}"
if gh release view "$RELEASE_TAG" --repo "$GITHUB_REPO" &> /dev/null; then
    print_error "Release $RELEASE_TAG already exists"
    echo -n "Delete existing release? (y/N): "
    read -r response
    if [[ "$response" =~ ^[Yy]$ ]]; then
        gh release delete "$RELEASE_TAG" --repo "$GITHUB_REPO" --yes
        print_status "Existing release deleted"
    else
        echo "Aborted"
        exit 1
    fi
fi

# Create release
echo -e "\n${BLUE}🚀 Creating GitHub release...${NC}"
gh release create "$RELEASE_TAG" \
    --repo "$GITHUB_REPO" \
    --title "Skip the Podcast Desktop v${VERSION}" \
    --notes-file "$RELEASE_NOTES_FILE" \
    --draft

print_status "Draft release created"

# Upload files
echo -e "\n${BLUE}📤 Uploading files...${NC}"

cd "$DIST_DIR"

# Upload PKG
echo "Uploading PKG installer..."
gh release upload "$RELEASE_TAG" \
    "Skip_the_Podcast_Desktop-${VERSION}.pkg" \
    --repo "$GITHUB_REPO"

# Upload README
echo "Uploading README..."
gh release upload "$RELEASE_TAG" \
    "$PROJECT_ROOT/README.md" \
    --repo "$GITHUB_REPO"

print_status "Files uploaded"

# Publish release
echo -e "\n${BLUE}🎉 Publishing release...${NC}"
gh release edit "$RELEASE_TAG" \
    --repo "$GITHUB_REPO" \
    --draft=false

print_status "Release published"

# Clean up
rm -f "$RELEASE_NOTES_FILE"

# Final summary
echo -e "\n${GREEN}${BOLD}🎉 GitHub Release Complete!${NC}"
echo "=============================================="
echo "Release: Skip the Podcast Desktop v${VERSION}"
echo "Tag: $RELEASE_TAG"
echo "URL: https://github.com/$GITHUB_REPO/releases/tag/$RELEASE_TAG"
echo ""
echo "📦 Files:"
echo "• Skip_the_Podcast_Desktop-${VERSION}.pkg ($PKG_SIZE)"
echo "• README.md"
