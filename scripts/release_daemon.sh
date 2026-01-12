#!/bin/bash
#
# Generic Daemon Release Script
#
# This script automatically detects the version from daemon/__init__.py
# and works for ANY version (1.1.4, 1.1.5, 2.0.0, etc.)
#
# Usage:
#   1. Update version in daemon/__init__.py (e.g., __version__ = "1.1.4")
#   2. Run: bash scripts/release_daemon.sh
#   3. Script handles everything automatically!
#

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

# Get script directory and project root
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

# Verify we're in the right directory
if [ ! -f "daemon/__init__.py" ]; then
    echo -e "${RED}ERROR: Not in Knowledge_Chipper root directory${NC}"
    exit 1
fi

# Auto-detect version from daemon/__init__.py
VERSION=$(python3 -c "import sys; sys.path.insert(0, '.'); from daemon import __version__; print(__version__)")

if [ -z "$VERSION" ]; then
    echo -e "${RED}ERROR: Could not detect version from daemon/__init__.py${NC}"
    exit 1
fi

echo ""
echo -e "${CYAN}╔════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║  Daemon v${VERSION} Release Script                 ║${NC}"
echo -e "${CYAN}╚════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${GREEN}✓ Auto-detected version: ${VERSION}${NC}"
echo ""

# [0/5] Pre-flight checks
echo ""
echo -e "${BLUE}[0/5] Pre-flight checks...${NC}"

# Check for running development daemon
if lsof -ti:8765 >/dev/null 2>&1; then
    PORT_PID=$(lsof -ti:8765)
    PROCESS=$(ps -p $PORT_PID -o command= 2>/dev/null)
    
    if [[ "$PROCESS" == *"python"*"daemon"* ]]; then
        echo -e "${YELLOW}⚠️  Development daemon detected on port 8765${NC}"
        echo "   Process: $PROCESS"
        echo "   This will cause version conflicts!"
        echo ""
        echo "Kill it and continue? (y/n)"
        read -r REPLY
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            kill -9 $PORT_PID
            sleep 2
            echo -e "${GREEN}✓ Killed development daemon${NC}"
        else
            echo -e "${RED}Aborting release${NC}"
            exit 1
        fi
    fi
fi

# Verify no stale build artifacts
if [ -d "build/" ] || [ -d "dist/" ]; then
    echo -e "${YELLOW}⚠️  Found existing build/ or dist/ directories${NC}"
    echo "   These may contain stale cached files"
    echo ""
    echo "Clean them before building? (recommended: y)"
    read -r REPLY
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm -rf build/ dist/
        echo -e "${GREEN}✓ Cleaned build artifacts${NC}"
    fi
fi

echo -e "${GREEN}✓ Pre-flight checks passed${NC}"
echo ""

# Check if PKG already exists
PKG_FILE="dist/GetReceipts-Daemon-${VERSION}.pkg"

if [ -f "$PKG_FILE" ]; then
    echo -e "${YELLOW}⚠️  PKG already exists: $PKG_FILE${NC}"
    read -p "Use existing PKG? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        SKIP_BUILD=true
    else
        echo "Deleting old PKG..."
        rm -f "$PKG_FILE"
        SKIP_BUILD=false
    fi
else
    SKIP_BUILD=false
fi

# Step 1: Build the PKG (if needed)
if [ "$SKIP_BUILD" = false ]; then
    echo ""
    echo -e "${BLUE}[1/5] Building signed & notarized PKG...${NC}"
    echo "⏱️  This will take 15-20 minutes (includes Apple notarization)"
    echo ""
    
    # Set app password (required for notarization)
    export APP_PASSWORD="mcdg-uecs-drmv-ygor"
    
    # Make scripts executable
    chmod +x installer/build_pkg.sh
    chmod +x installer/scripts/postinstall
    
    # Build
    bash installer/build_pkg.sh
    
    if [ ! -f "$PKG_FILE" ]; then
        echo -e "${RED}ERROR: PKG build failed - expected $PKG_FILE${NC}"
        exit 1
    fi
    
    PKG_SIZE=$(du -h "$PKG_FILE" | cut -f1)
    echo -e "${GREEN}✓ PKG built successfully: $PKG_SIZE${NC}"
else
    echo ""
    echo -e "${BLUE}[1/5] Using existing PKG${NC}"
    PKG_SIZE=$(du -h "$PKG_FILE" | cut -f1)
    echo "   Size: $PKG_SIZE"
fi

# Step 2: Commit changes to Knowledge_Chipper
echo ""
echo -e "${BLUE}[2/5] Committing changes to Knowledge_Chipper...${NC}"

# Stage common files that change with releases
git add daemon/__init__.py \
        CHANGELOG.md 2>/dev/null || true

# Stage installer files if they exist
git add installer/build_pkg.sh \
        installer/scripts/postinstall \
        .github/workflows/daemon-release.yml \
        docs/DAEMON_RELEASE_PROCESS.md 2>/dev/null || true

if git diff --staged --quiet; then
    echo -e "${YELLOW}⚠️  No changes to commit (already committed?)${NC}"
else
    git commit -m "Release daemon v${VERSION}

- Update daemon version to ${VERSION}
- Build signed & notarized PKG
- Update changelog and documentation

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

TAG_NAME="v${VERSION}"

# Check if tag already exists
if git rev-parse "$TAG_NAME" >/dev/null 2>&1; then
    echo -e "${YELLOW}⚠️  Tag $TAG_NAME already exists locally${NC}"
    read -p "Delete and recreate tag? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        git tag -d "$TAG_NAME"
        git push origin ":refs/tags/$TAG_NAME" 2>/dev/null || true
        echo "Deleted old tag"
    else
        echo "Keeping existing tag"
    fi
fi

# Create tag if it doesn't exist
if ! git rev-parse "$TAG_NAME" >/dev/null 2>&1; then
    git tag -a "$TAG_NAME" -m "Release v${VERSION} - PKG Distribution

GetReceipts Daemon v${VERSION}

Features:
- PKG distribution with automatic installation
- Desktop restart button
- Auto-start on login via LaunchAgent
- Signed and notarized by Apple

Download: https://github.com/msg43/Skipthepodcast.com/releases/latest/download/GetReceipts-Daemon-${VERSION}.pkg"
    
    echo -e "${GREEN}✓ Tag created${NC}"
fi

# Push tag
git push origin "$TAG_NAME"

echo -e "${GREEN}✓ Tag pushed to GitHub${NC}"

# Step 5: Create GitHub release manually (since GitHub Actions may fail)
echo ""
echo -e "${BLUE}[5/5] Creating GitHub release...${NC}"

# Check if gh CLI is available
if command -v gh >/dev/null 2>&1; then
    echo "Using GitHub CLI to create release..."
    
    # Check if release already exists
    if gh release view "$TAG_NAME" --repo "msg43/skipthepodcast.com" >/dev/null 2>&1; then
        echo -e "${YELLOW}⚠️  Release $TAG_NAME already exists${NC}"
        read -p "Delete and recreate release? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            gh release delete "$TAG_NAME" --repo "msg43/skipthepodcast.com" --yes || true
            echo "Deleted old release"
        else
            echo "Keeping existing release"
            echo -e "${GREEN}✓ Release already published${NC}"
            RELEASE_EXISTS=true
        fi
    fi
    
    if [ -z "$RELEASE_EXISTS" ]; then
        # Create new release
        gh release create "$TAG_NAME" \
            --repo "msg43/skipthepodcast.com" \
            --title "GetReceipts Daemon v${VERSION}" \
            --notes "**GetReceipts Daemon v${VERSION}**

🍎 **macOS Background Service**

## What Is This?

The GetReceipts daemon runs in the background on your Mac and processes videos/audio locally. All control happens through your web browser at [GetReceipts.org/contribute](https://getreceipts.org/contribute).

## Installation

1. Download the \`.pkg\` file below
2. Double-click the downloaded PKG file
3. Follow the installer - it will:
   - Install the daemon to /Applications
   - Set up automatic startup on login
   - Create a desktop restart button
   - Start the daemon immediately
4. Visit [GetReceipts.org/contribute](https://getreceipts.org/contribute) to start processing

**No drag-and-drop needed!** The PKG installer handles everything automatically.

## Release Info

- **Version:** ${VERSION}
- **Build Date:** $(date +"%Y-%m-%d")
- **File Size:** ${PKG_SIZE}
- **Platform:** macOS (Universal Binary)
- **Control Interface:** Web browser (GetReceipts.org)
- **Distribution:** Signed & Notarized PKG

## System Requirements

- macOS 11.0+ (Big Sur or later)
- 4GB RAM minimum
- 500MB free disk space
- Internet connection for model downloads

## After Installation

- Daemon runs at: \`http://localhost:8765\`
- Desktop shortcut: \`~/Desktop/Restart GetReceipts.command\`
- Auto-starts on login via LaunchAgent

📖 **See [CHANGELOG.md](https://github.com/msg43/Knowledge_Chipper/blob/main/CHANGELOG.md) for detailed changes.**

---
*Automated release via release_daemon.sh script*" \
            "$PKG_FILE"
        
        echo -e "${GREEN}✓ GitHub release created${NC}"
    fi
else
    echo -e "${YELLOW}⚠️  GitHub CLI (gh) not found${NC}"
    echo "Install with: brew install gh"
    echo "Then authenticate with: gh auth login"
    echo ""
    echo "Manual steps:"
    echo "1. Go to https://github.com/msg43/Skipthepodcast.com/releases"
    echo "2. Create a new release for tag $TAG_NAME"
    echo "3. Upload: $PKG_FILE"
fi

# Final summary
echo ""
echo -e "${CYAN}╔════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║  🎉 Release Process Complete!                  ║${NC}"
echo -e "${CYAN}╚════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${GREEN}✅ Daemon v${VERSION} PKG built and notarized${NC}"
echo -e "${GREEN}✅ Changes committed and pushed to main${NC}"
echo -e "${GREEN}✅ Version tag v${VERSION} created and pushed${NC}"
echo -e "${GREEN}✅ GitHub release created${NC}"
echo ""
echo "📍 Release URLs:"
echo "   • Release page: https://github.com/msg43/Skipthepodcast.com/releases/tag/v${VERSION}"
echo "   • Direct download: https://github.com/msg43/Skipthepodcast.com/releases/download/v${VERSION}/GetReceipts-Daemon-${VERSION}.pkg"
echo "   • Latest (auto-redirect): https://github.com/msg43/Skipthepodcast.com/releases/latest"
echo ""
echo -e "${CYAN}Next steps:${NC}"
echo "   • Test the download URL"
echo "   • Update GetReceipts website if needed"
echo "   • Announce the release"
echo ""
