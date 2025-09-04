#!/bin/bash
# publish_release.sh - Create and push a tagged release to public GitHub repository
# This script creates a release on the public repository with the built DMG

set -e

# Configuration
PUBLIC_REPO_URL="https://github.com/msg43/skipthepodcast.com.git"
PUBLIC_REPO_NAME="skipthepodcast.com"
PRIVATE_REPO_PATH="/Users/matthewgreer/Projects/Knowledge_Chipper"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

error() {
    echo -e "${RED}❌ ERROR:${NC} $1" >&2
}

success() {
    echo -e "${GREEN}✅${NC} $1"
}

warning() {
    echo -e "${YELLOW}⚠️${NC} $1"
}

# Parse arguments
FORCE_REBUILD=0
SKIP_BUILD=0
DRY_RUN=0

while [[ $# -gt 0 ]]; do
    case $1 in
        --force-rebuild)
            FORCE_REBUILD=1
            shift
            ;;
        --skip-build)
            SKIP_BUILD=1
            shift
            ;;
        --dry-run)
            DRY_RUN=1
            shift
            ;;
        --help)
            echo "Usage: $0 [options]"
            echo "Options:"
            echo "  --force-rebuild  Force rebuild of DMG even if current version exists"
            echo "  --skip-build     Skip building DMG, just publish existing one"
            echo "  --dry-run        Show what would be done without actually doing it"
            echo "  --help           Show this help message"
            exit 0
            ;;
        *)
            error "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Ensure we're in the project root
cd "$PRIVATE_REPO_PATH"

# Check if this is the private repository
if [ ! -f "pyproject.toml" ] || [ ! -d "src/knowledge_system" ]; then
    error "This script must be run from the Knowledge_Chipper project root"
    exit 1
fi

log "🚀 Starting release publication process..."

# Get current version from pyproject.toml
CURRENT_VERSION=$(python3 - <<'PY'
import sys
try:
    import tomllib
except Exception:
    sys.stderr.write('❌ Python tomllib not available (requires Python 3.11+)\n')
    sys.exit(2)
with open('pyproject.toml', 'rb') as f:
    data = tomllib.load(f)
ver = (data.get('project') or {}).get('version')
if not ver:
    sys.stderr.write('❌ Version missing in pyproject.toml\n')
    sys.exit(3)
print(ver)
PY
)

if [ -z "$CURRENT_VERSION" ]; then
    error "Could not determine version from pyproject.toml"
    exit 1
fi

log "📋 Current version: $CURRENT_VERSION"

# Check if DMG exists for current version
DMG_FILE="$PRIVATE_REPO_PATH/dist/Knowledge_Chipper-${CURRENT_VERSION}.dmg"

if [ "$SKIP_BUILD" -eq 0 ]; then
    if [ -f "$DMG_FILE" ] && [ "$FORCE_REBUILD" -eq 0 ]; then
        log "📦 DMG already exists for version $CURRENT_VERSION"
        read -p "Use existing DMG? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            log "🏗️ Rebuilding DMG..."
            rm -f "$DMG_FILE"
        fi
    fi

    # Build DMG if it doesn't exist
    if [ ! -f "$DMG_FILE" ]; then
        log "🏗️ Building DMG with build_macos_app.sh..."
        if [ "$DRY_RUN" -eq 1 ]; then
            log "[DRY RUN] Would run: bash scripts/build_macos_app.sh --make-dmg --skip-install"
        else
            bash scripts/build_macos_app.sh --make-dmg --skip-install
        fi
    fi
fi

# Verify DMG exists (skip in dry-run mode)
if [ "$DRY_RUN" -eq 0 ] && [ ! -f "$DMG_FILE" ]; then
    error "DMG file not found: $DMG_FILE"
    exit 1
fi

if [ -f "$DMG_FILE" ]; then
    DMG_SIZE=$(du -h "$DMG_FILE" | cut -f1)
    log "📦 DMG ready: $DMG_FILE ($DMG_SIZE)"
else
    DMG_SIZE="(estimated ~200MB)"
    log "📦 DMG would be created: $DMG_FILE"
fi

# Setup temporary directory for public repo
TEMP_DIR=$(mktemp -d)
trap "rm -rf $TEMP_DIR" EXIT

log "📁 Setting up temporary directory: $TEMP_DIR"

if [ "$DRY_RUN" -eq 1 ]; then
    log "[DRY RUN] Would clone public repository to: $TEMP_DIR"
else
    # Clone the public repository
    cd "$TEMP_DIR"
    
    # Check if repository is empty (first release)
    if git ls-remote --heads "$PUBLIC_REPO_URL" | grep -q "refs/heads"; then
        log "📥 Cloning existing public repository..."
        git clone "$PUBLIC_REPO_URL" "$PUBLIC_REPO_NAME"
        cd "$PUBLIC_REPO_NAME"
    else
        log "📝 Initializing empty public repository..."
        mkdir "$PUBLIC_REPO_NAME"
        cd "$PUBLIC_REPO_NAME"
        git init
        git remote add origin "$PUBLIC_REPO_URL"
        
        # Create initial README for public repo
        cat > README.md << EOF
# Knowledge Chipper

A comprehensive knowledge management system for macOS that transforms videos, audio files, and documents into organized, searchable knowledge.

## Download

Download the latest release from the [Releases](https://github.com/msg43/skipthepodcast.com/releases) page.

## Installation

1. Download the latest \`.dmg\` file from releases
2. Open the \`.dmg\` file
3. Drag Knowledge Chipper.app to your Applications folder
4. Launch from Applications

## Version

**Version:** $CURRENT_VERSION | **Build Date:** $(date +"%Y-%m-%d")

## License

MIT License - see the private repository for full details.
EOF
        
        git add README.md
        git commit -m "Initial commit with README"
        
        if [ "$DRY_RUN" -eq 0 ]; then
            git branch -M main
            git push -u origin main
        fi
    fi
fi

# Create and push tag
TAG_NAME="v${CURRENT_VERSION}"
log "🏷️ Creating tag: $TAG_NAME"

if [ "$DRY_RUN" -eq 1 ]; then
    log "[DRY RUN] Would create tag: $TAG_NAME"
    log "[DRY RUN] Would copy DMG to: releases/"
    log "[DRY RUN] Would push tag and trigger release"
else
    cd "$TEMP_DIR/$PUBLIC_REPO_NAME"
    
    # Create releases directory if it doesn't exist
    mkdir -p releases
    
    # Copy the DMG to releases directory
    cp "$DMG_FILE" "releases/Knowledge_Chipper-${CURRENT_VERSION}.dmg"
    
    # Update README with current version if it exists
    if [ -f "README.md" ]; then
        if grep -q "**Version:**" README.md; then
            # Update existing version line
            if command -v gsed >/dev/null 2>&1; then
                gsed -i "s/\*\*Version:\*\* [0-9][^|]*/\*\*Version:\*\* $CURRENT_VERSION/" README.md
                gsed -i "s/\*\*Build Date:\*\* [0-9][^*]*/\*\*Build Date:\*\* $(date +"%Y-%m-%d")/" README.md
            else
                sed -i '' "s/\*\*Version:\*\* [0-9][^|]*/\*\*Version:\*\* $CURRENT_VERSION/" README.md
                sed -i '' "s/\*\*Build Date:\*\* [0-9][^*]*/\*\*Build Date:\*\* $(date +"%Y-%m-%d")/" README.md
            fi
        fi
    fi
    
    # Commit the new release
    git add .
    if ! git diff --staged --quiet; then
        git commit -m "Release v${CURRENT_VERSION}

- Updated Knowledge Chipper to version ${CURRENT_VERSION}
- DMG size: $DMG_SIZE
- Build date: $(date +"%Y-%m-%d")"
    fi
    
    # Create and push tag
    if git tag -l | grep -q "^${TAG_NAME}$"; then
        warning "Tag $TAG_NAME already exists, deleting and recreating..."
        git tag -d "$TAG_NAME" || true
        git push origin --delete "$TAG_NAME" || true
    fi
    
    git tag -a "$TAG_NAME" -m "Knowledge Chipper v${CURRENT_VERSION}

Release notes:
- Version: ${CURRENT_VERSION}
- Build date: $(date +"%Y-%m-%d")
- DMG size: $DMG_SIZE

This is an automated release from the build system."
    
    log "📤 Pushing to public repository..."
    git push origin main
    git push origin "$TAG_NAME"
fi

# Check if gh CLI is available for creating the release
if command -v gh >/dev/null 2>&1; then
    log "🚀 Creating GitHub release with gh CLI..."
    
    if [ "$DRY_RUN" -eq 1 ]; then
        log "[DRY RUN] Would create GitHub release with:"
        log "  Title: Knowledge Chipper v${CURRENT_VERSION}"
        log "  Tag: $TAG_NAME"
        log "  Asset: releases/Knowledge_Chipper-${CURRENT_VERSION}.dmg"
    else
        cd "$TEMP_DIR/$PUBLIC_REPO_NAME"
        
        # Create the release
        gh release create "$TAG_NAME" \
            --repo "msg43/skipthepodcast.com" \
            --title "Knowledge Chipper v${CURRENT_VERSION}" \
            --notes "**Knowledge Chipper v${CURRENT_VERSION}**

🍎 **macOS Application Release**

## Installation
1. Download the \`.dmg\` file below
2. Open the downloaded file
3. Drag Knowledge Chipper.app to your Applications folder
4. Launch from Applications

## Release Info
- **Version:** ${CURRENT_VERSION}
- **Build Date:** $(date +"%Y-%m-%d")
- **File Size:** $DMG_SIZE
- **Platform:** macOS (Universal Binary)

## What's New
This release includes the latest features and improvements from the Knowledge Chipper development cycle.

---
*This release was automatically generated from the build system.*" \
            "releases/Knowledge_Chipper-${CURRENT_VERSION}.dmg"
    fi
else
    warning "GitHub CLI (gh) not found. Release created but you'll need to manually:"
    warning "1. Go to https://github.com/msg43/skipthepodcast.com/releases"
    warning "2. Create a new release for tag $TAG_NAME"
    warning "3. Upload the DMG file: releases/Knowledge_Chipper-${CURRENT_VERSION}.dmg"
fi

success "🎉 Release publication complete!"
log "📍 Public repository: https://github.com/msg43/skipthepodcast.com"
log "📍 Releases page: https://github.com/msg43/skipthepodcast.com/releases"
log "📦 Release tag: $TAG_NAME"
log "💾 DMG size: $DMG_SIZE"

if [ "$DRY_RUN" -eq 1 ]; then
    warning "This was a dry run. No actual changes were made."
    log "Run without --dry-run to perform the actual release."
fi

# Cleanup
log "🧹 Cleaning up temporary directory..."
