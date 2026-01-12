#!/bin/bash
#
# Complete Release Script for Daemon v1.1.3
#
# This script:
# 1. Builds the signed & notarized PKG
# 2. Commits all changes to git
# 3. Pushes to main branch
# 4. Creates and pushes version tag
# 5. GitHub Actions automatically publishes the release
#

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo ""
echo -e "${CYAN}╔════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║  Daemon v1.1.3 Release Script                  ║${NC}"
echo -e "${CYAN}╚════════════════════════════════════════════════╝${NC}"
echo ""

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

# Verify we're in the right directory
if [ ! -f "daemon/__init__.py" ]; then
    echo -e "${RED}ERROR: Not in Knowledge_Chipper root directory${NC}"
    exit 1
fi

# Check version
VERSION=$(python3 -c "import sys; sys.path.insert(0, '.'); from daemon import __version__; print(__version__)")
if [ "$VERSION" != "1.1.3" ]; then
    echo -e "${RED}ERROR: Version in daemon/__init__.py is $VERSION, expected 1.1.3${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Version confirmed: $VERSION${NC}"

# Check if PKG already exists
if [ -f "dist/GetReceipts-Daemon-1.1.3.pkg" ]; then
    echo -e "${YELLOW}⚠️  PKG already exists. Skipping build.${NC}"
    echo "   If you want to rebuild, delete dist/GetReceipts-Daemon-1.1.3.pkg first"
    SKIP_BUILD=true
else
    SKIP_BUILD=false
fi

# Step 1: Build the PKG (if needed)
if [ "$SKIP_BUILD" = false ]; then
    echo ""
    echo -e "${BLUE}[1/5] Building signed & notarized PKG...${NC}"
    echo "This will take 15-20 minutes (includes notarization)"
    echo ""
    
    # Set app password
    export APP_PASSWORD="mcdg-uecs-drmv-ygor"
    
    # Make scripts executable
    chmod +x installer/build_pkg.sh
    chmod +x installer/scripts/postinstall
    
    # Build
    bash installer/build_pkg.sh
    
    if [ ! -f "dist/GetReceipts-Daemon-1.1.3.pkg" ]; then
        echo -e "${RED}ERROR: PKG build failed${NC}"
        exit 1
    fi
    
    echo -e "${GREEN}✓ PKG built successfully${NC}"
else
    echo ""
    echo -e "${BLUE}[1/5] Using existing PKG${NC}"
fi

# Step 2: Commit changes to Knowledge_Chipper
echo ""
echo -e "${BLUE}[2/5] Committing changes to Knowledge_Chipper...${NC}"

git add daemon/__init__.py \
        installer/build_pkg.sh \
        installer/scripts/postinstall \
        .github/workflows/daemon-release.yml \
        docs/DAEMON_RELEASE_PROCESS.md \
        CHANGELOG.md

if git diff --staged --quiet; then
    echo -e "${YELLOW}⚠️  No changes to commit (already committed?)${NC}"
else
    git commit -m "Release daemon v1.1.3 - PKG distribution with auto-install

- Switch from DMG to PKG distribution
- Add postinstall script for automatic setup
- Create desktop restart button at ~/Desktop/Restart GetReceipts.command
- Configure LaunchAgent for auto-start on login
- Update GitHub Actions workflow to build PKG
- Update documentation and changelog
- Use working installer certificate (773033...)

Closes: PKG notarization issue
Distribution: Signed & Notarized PKG"
    
    echo -e "${GREEN}✓ Changes committed${NC}"
fi

# Step 3: Push to main
echo ""
echo -e "${BLUE}[3/5] Pushing to main branch...${NC}"

git push origin main

echo -e "${GREEN}✓ Pushed to main${NC}"

# Step 4: Create and push tag
echo ""
echo -e "${BLUE}[4/5] Creating and pushing version tag...${NC}"

# Check if tag already exists
if git rev-parse "v1.1.3" >/dev/null 2>&1; then
    echo -e "${YELLOW}⚠️  Tag v1.1.3 already exists locally${NC}"
    read -p "Delete and recreate tag? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        git tag -d v1.1.3
        git push origin :refs/tags/v1.1.3 2>/dev/null || true
        echo "Deleted old tag"
    else
        echo "Keeping existing tag"
    fi
fi

# Create tag if it doesn't exist
if ! git rev-parse "v1.1.3" >/dev/null 2>&1; then
    git tag -a v1.1.3 -m "Release v1.1.3 - PKG Distribution

GetReceipts Daemon v1.1.3

Major Changes:
- PKG distribution with automatic installation
- Desktop restart button
- Auto-start on login via LaunchAgent
- Signed and notarized by Apple

Download: https://github.com/msg43/Skipthepodcast.com/releases/latest/download/GetReceipts-Daemon-1.1.3.pkg"
    
    echo -e "${GREEN}✓ Tag created${NC}"
fi

# Push tag
git push origin v1.1.3

echo -e "${GREEN}✓ Tag pushed to GitHub${NC}"

# Step 5: Trigger GitHub Actions
echo ""
echo -e "${BLUE}[5/5] GitHub Actions triggered!${NC}"
echo ""
echo "The automated workflow will now:"
echo "  1. Run daemon tests"
echo "  2. Build signed & notarized PKG"
echo "  3. Publish to Skipthepodcast.com repository"
echo "  4. Create GitHub release with PKG attached"
echo ""
echo "This will take approximately 15-20 minutes."
echo ""

# Final summary
echo -e "${CYAN}╔════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║  Release Process Started!                      ║${NC}"
echo -e "${CYAN}╚════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${GREEN}✓ Local PKG built and notarized${NC}"
echo -e "${GREEN}✓ Changes committed and pushed${NC}"
echo -e "${GREEN}✓ Version tag v1.1.3 created and pushed${NC}"
echo -e "${GREEN}✓ GitHub Actions workflow triggered${NC}"
echo ""
echo "Monitor progress:"
echo "  • Workflow: https://github.com/msg43/Knowledge_Chipper/actions"
echo "  • Release: https://github.com/msg43/Skipthepodcast.com/releases"
echo ""
echo "When complete, the PKG will be available at:"
echo "  https://github.com/msg43/Skipthepodcast.com/releases/latest/download/GetReceipts-Daemon-1.1.3.pkg"
echo ""
echo -e "${YELLOW}Next: Update GetReceipts website${NC}"
echo "Run: cd /Users/matthewgreer/Projects/GetReceipts && bash scripts/deploy_website_changes.sh"
echo ""
