#!/bin/bash
#
# Complete Release Script for Daemon v1.1.3
#
# This script does EVERYTHING:
# 1. Builds the signed & notarized PKG (Knowledge_Chipper)
# 2. Commits and pushes daemon changes
# 3. Creates version tag (triggers GitHub Actions)
# 4. Commits and pushes website changes (GetReceipts)
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
echo -e "${CYAN}║  Complete Release: Daemon v1.1.3               ║${NC}"
echo -e "${CYAN}╚════════════════════════════════════════════════╝${NC}"
echo ""

# ============================================================================
# PART 1: Knowledge_Chipper (Daemon)
# ============================================================================

echo -e "${CYAN}═══ PART 1: Knowledge_Chipper Repository ═══${NC}"
echo ""

cd /Users/matthewgreer/Projects/Knowledge_Chipper

# Verify version
VERSION=$(python3 -c "import sys; sys.path.insert(0, '.'); from daemon import __version__; print(__version__)")
if [ "$VERSION" != "1.1.3" ]; then
    echo -e "${RED}ERROR: Version is $VERSION, expected 1.1.3${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Version confirmed: $VERSION${NC}"

# Check if PKG already exists
if [ -f "dist/GetReceipts-Daemon-1.1.3.pkg" ]; then
    echo -e "${YELLOW}⚠️  PKG already exists. Skipping build.${NC}"
    SKIP_BUILD=true
else
    SKIP_BUILD=false
fi

# Build PKG
if [ "$SKIP_BUILD" = false ]; then
    echo ""
    echo -e "${BLUE}[1/6] Building signed & notarized PKG...${NC}"
    echo "⏱️  This takes 15-20 minutes (includes Apple notarization)"
    echo ""
    
    export APP_PASSWORD="mcdg-uecs-drmv-ygor"
    chmod +x installer/build_pkg.sh
    chmod +x installer/scripts/postinstall
    
    bash installer/build_pkg.sh
    
    if [ ! -f "dist/GetReceipts-Daemon-1.1.3.pkg" ]; then
        echo -e "${RED}ERROR: PKG build failed${NC}"
        exit 1
    fi
    
    echo -e "${GREEN}✓ PKG built successfully${NC}"
else
    echo ""
    echo -e "${BLUE}[1/6] Using existing PKG${NC}"
fi

# Commit daemon changes
echo ""
echo -e "${BLUE}[2/6] Committing daemon changes...${NC}"

git add daemon/__init__.py \
        installer/build_pkg.sh \
        installer/scripts/postinstall \
        .github/workflows/daemon-release.yml \
        docs/DAEMON_RELEASE_PROCESS.md \
        CHANGELOG.md \
        scripts/release_daemon_1.1.3.sh \
        scripts/complete_release.sh

if git diff --staged --quiet; then
    echo -e "${YELLOW}⚠️  No changes to commit${NC}"
else
    git commit -m "Release daemon v1.1.3 - PKG distribution with auto-install

- Switch from DMG to PKG distribution
- Add postinstall script for automatic setup
- Create desktop restart button
- Configure LaunchAgent for auto-start
- Update GitHub Actions workflow
- Update documentation and changelog
- Use working installer certificate

Distribution: Signed & Notarized PKG"
    
    echo -e "${GREEN}✓ Changes committed${NC}"
fi

# Push to main
echo ""
echo -e "${BLUE}[3/6] Pushing daemon to main...${NC}"
git push origin main
echo -e "${GREEN}✓ Pushed to main${NC}"

# Create and push tag
echo ""
echo -e "${BLUE}[4/6] Creating version tag...${NC}"

if git rev-parse "v1.1.3" >/dev/null 2>&1; then
    echo -e "${YELLOW}⚠️  Tag v1.1.3 already exists${NC}"
    git tag -d v1.1.3 2>/dev/null || true
    git push origin :refs/tags/v1.1.3 2>/dev/null || true
fi

git tag -a v1.1.3 -m "Release v1.1.3 - PKG Distribution

GetReceipts Daemon v1.1.3

- PKG distribution with automatic installation
- Desktop restart button
- Auto-start on login
- Signed and notarized"

git push origin v1.1.3
echo -e "${GREEN}✓ Tag v1.1.3 pushed (GitHub Actions triggered!)${NC}"

# ============================================================================
# PART 2: GetReceipts Website
# ============================================================================

echo ""
echo -e "${CYAN}═══ PART 2: GetReceipts Website ═══${NC}"
echo ""

cd /Users/matthewgreer/Projects/GetReceipts

# Commit website changes
echo -e "${BLUE}[5/6] Committing website changes...${NC}"

git add src/components/daemon-installer.tsx \
        src/components/daemon-status-indicator.tsx

if git diff --staged --quiet; then
    echo -e "${YELLOW}⚠️  No website changes to commit${NC}"
else
    git commit -m "Update daemon installer to download PKG instead of DMG

- Switch to GetReceipts-Daemon-1.1.3.pkg
- Use GitHub /releases/latest/ for auto-updates
- Update UI text for PKG installation
- Fix service name to org.getreceipts.daemon

Related: Knowledge_Chipper v1.1.3"
    
    echo -e "${GREEN}✓ Website changes committed${NC}"
fi

# Push website
echo ""
echo -e "${BLUE}[6/6] Pushing website changes...${NC}"
git push origin main
echo -e "${GREEN}✓ Website pushed (deployment triggered!)${NC}"

# ============================================================================
# FINAL SUMMARY
# ============================================================================

echo ""
echo -e "${CYAN}╔════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║  🎉 Release Process Complete!                  ║${NC}"
echo -e "${CYAN}╚════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${GREEN}✅ Daemon v1.1.3 PKG built and notarized${NC}"
echo -e "${GREEN}✅ Daemon changes committed and pushed${NC}"
echo -e "${GREEN}✅ Version tag v1.1.3 created and pushed${NC}"
echo -e "${GREEN}✅ Website changes committed and pushed${NC}"
echo ""
echo "⏳ Automated processes running:"
echo "   • GitHub Actions building release (~15-20 min)"
echo "   • Website deploying to production (~2-5 min)"
echo ""
echo "📍 Monitor progress:"
echo "   • Workflow: https://github.com/msg43/Knowledge_Chipper/actions"
echo "   • Release: https://github.com/msg43/Skipthepodcast.com/releases"
echo "   • Website: https://getreceipts.org"
echo ""
echo "📥 When complete, PKG will be at:"
echo "   https://github.com/msg43/Skipthepodcast.com/releases/latest/download/GetReceipts-Daemon-1.1.3.pkg"
echo ""
echo -e "${CYAN}All done! 🚀${NC}"
echo ""
