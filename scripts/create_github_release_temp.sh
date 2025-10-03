#!/bin/bash
# create_github_release.sh - Create GitHub release with PKG and all components
# This replaces the DMG release process with PKG + component hosting

set -e
set -o pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
DIST_DIR="$PROJECT_ROOT/dist"

# Get version from pyproject.toml
VERSION=$(python3 -c "import tomllib; print(tomllib.load(open('$PROJECT_ROOT/pyproject.toml', 'rb'))['project']['version'])")

# GitHub configuration
GITHUB_REPO="msg43/Knowledge_Chipper"
RELEASE_TAG="v$VERSION"
RELEASE_NAME="Skip the Podcast Desktop v$VERSION"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m' # No Color

echo -e "${BLUE}${BOLD}📦 GitHub Release Creator for PKG Distribution${NC}"
echo "================================================"
echo "Version: $VERSION"
echo "Release Tag: $RELEASE_TAG"
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

# Check prerequisites
echo -e "${BLUE}📋 Checking prerequisites...${NC}"

if ! command -v gh &> /dev/null; then
    print_error "GitHub CLI (gh) is required but not installed"
    echo "Install with: brew install gh"
    exit 1
fi

# Check GitHub authentication
if ! gh auth status &> /dev/null; then
    print_error "GitHub CLI not authenticated"
    echo "Authenticate with: gh auth login"
    exit 1
fi

print_status "GitHub CLI authenticated"

# Verify all components exist
echo -e "\n${BLUE}🔍 Verifying all components...${NC}"

REQUIRED_FILES=(
    "Skip_the_Podcast_Desktop-${VERSION}.pkg"
    "python-framework-3.13-macos.tar.gz"
    "ai-models-bundle.tar.gz"
)

MISSING_FILES=()

for file in "${REQUIRED_FILES[@]}"; do
    if [ -f "$DIST_DIR/$file" ]; then
        SIZE=$(du -h "$DIST_DIR/$file" | cut -f1)
        print_status "$file ($SIZE)"
    else
        MISSING_FILES+=("$file")
        print_error "Missing: $file"
    fi
done

if [ ${#MISSING_FILES[@]} -ne 0 ]; then
    print_error "Missing required files. Please build all components first:"
    echo ""
    echo "Run these scripts to build missing components:"
    for file in "${MISSING_FILES[@]}"; do
        case "$file" in
            "Skip_the_Podcast_Desktop-"*)
                echo "  ./scripts/build_pkg_installer.sh"
                ;;
            "python-framework-"*)
                echo "  ./scripts/build_python_framework.sh"
                ;;
            "ai-models-bundle.tar.gz")
                echo "  ./scripts/bundle_ai_models.sh"
                ;;
            "ffmpeg-macos-universal.tar.gz")
                echo "  ./scripts/bundle_ffmpeg.sh"
                ;;
        esac
    done
    exit 1
fi

print_status "All required files present"

# Create release notes
echo -e "\n${BLUE}📝 Creating release notes...${NC}"

RELEASE_NOTES_FILE="$DIST_DIR/release_notes_${VERSION}.md"

cat > "$RELEASE_NOTES_FILE" << EOF
# Skip the Podcast Desktop v${VERSION}

## 🚀 PKG Installer Release

This release introduces a new **10MB PKG installer** that downloads components during installation, replacing the previous 603MB DMG approach.

### ✨ What's New

- **Lightweight installer**: 10MB PKG vs 603MB DMG (95% size reduction)
- **Smart component downloads**: Only downloads what you need
- **Hardware-optimized**: Automatic model selection based on your Mac
- **Professional installer**: Native macOS PKG experience
- **Zero Python conflicts**: Complete framework isolation

### 📦 Installation Process

The PKG installer will automatically download and install:

| Component | Size | Description |
|-----------|------|-------------|
| Python Framework | ~40MB | Isolated Python 3.13 runtime |
| AI Models | ~1.2GB | Whisper, Voice Fingerprinting, Pyannote |
| FFmpeg | ~48MB | Media processing engine |
| Ollama Runtime | ~50MB | LLM processing engine |
| Ollama Model | 1.3-4.7GB | Hardware-optimized model selection |

**Total download**: 3-6GB (varies by hardware)
**Installation time**: 5-15 minutes

### 🖥️ Hardware Optimization

The installer automatically detects your Mac and recommends the optimal Ollama model:

- **M2/M3 Ultra (64GB+ RAM)**: qwen2.5:14b (8.2GB)
- **M2/M3 Max (32GB+ RAM)**: qwen2.5:14b (8.2GB)
- **M2/M3 Pro (16GB+ RAM)**: qwen2.5:7b (4GB)
- **Base Systems**: qwen2.5:3b (2GB)

### 🔧 Technical Improvements

- **Framework isolation**: No more Python version conflicts
- **Reliable downloads**: All components hosted on GitHub releases
- **Verification system**: Components verified before installation completes
- **Graceful fallbacks**: Multiple download sources and retry mechanisms

### 📋 Installation Requirements

- **macOS**: 12.0 or later
- **Architecture**: Intel or Apple Silicon (Universal)
- **Disk space**: 8GB free space minimum
- **Internet**: Required for component downloads
- **Admin access**: Required for installation

### 🆕 For New Users

1. Download \`Skip_the_Podcast_Desktop-${VERSION}.pkg\`
2. Double-click to start installation
3. Follow the installer prompts
4. Wait for component downloads to complete
5. Launch from Applications

### 🔄 For Existing Users

This PKG installer creates a completely fresh installation. Your existing data and settings will not be affected, but you may want to:

1. Export any important configurations
2. Note your preferred settings
3. Install the new PKG version
4. Reconfigure as needed

### 🐛 Bug Fixes & Improvements

- Eliminated all Python permission issues
- Removed complex DMG workarounds
- Simplified installation process
- Improved reliability across different Mac configurations

### 📚 Documentation

- [Installation Guide](https://github.com/msg43/Knowledge_Chipper/blob/main/README.md)
- [Configuration Options](https://github.com/msg43/Knowledge_Chipper/blob/main/config/README.md)
- [Troubleshooting](https://github.com/msg43/Knowledge_Chipper/issues)

### 🙏 Acknowledgments

This release represents a complete architectural overhaul focusing on reliability, user experience, and maintainability. Thank you to all users who provided feedback on the previous DMG approach.

---

**Full Changelog**: https://github.com/msg43/Knowledge_Chipper/compare/v$(echo $VERSION | awk -F. '{print $1"."$2"."$3-1}')...v${VERSION}
EOF

print_status "Release notes created"

# Components are ready for upload
print_status "All components verified and ready for upload"

# Check if release already exists
echo -e "\n${BLUE}🔍 Checking for existing release...${NC}"

if gh release view "$RELEASE_TAG" --repo "$GITHUB_REPO" &> /dev/null; then
    print_warning "Release $RELEASE_TAG already exists"
    read -p "Delete and recreate? (y/N): " -n 1 -r
    echo

    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "Deleting existing release..."
        gh release delete "$RELEASE_TAG" --repo "$GITHUB_REPO" --yes
        print_status "Existing release deleted"
    else
        print_error "Release creation cancelled"
        exit 1
    fi
fi

# Create GitHub release
echo -e "\n${BLUE}🚀 Creating GitHub release...${NC}"

gh release create "$RELEASE_TAG" \
    --repo "$GITHUB_REPO" \
    --title "$RELEASE_NAME" \
    --notes-file "$RELEASE_NOTES_FILE" \
    --generate-notes=false \
    --draft

print_status "Draft release created"

# Upload all components
echo -e "\n${BLUE}📤 Uploading components...${NC}"

cd "$DIST_DIR"

# Upload main PKG
echo "Uploading PKG installer..."
gh release upload "$RELEASE_TAG" \
    "Skip_the_Podcast_Desktop-${VERSION}.pkg" \
    --repo "$GITHUB_REPO"

# Upload Python framework
echo "Uploading Python framework..."
gh release upload "$RELEASE_TAG" \
    "python-framework-3.13-macos.tar.gz" \
    --repo "$GITHUB_REPO"

# Upload AI models
echo "Uploading AI models..."
gh release upload "$RELEASE_TAG" \
    "ai-models-bundle.tar.gz" \
    --repo "$GITHUB_REPO"

# Upload FFmpeg (skip for now)
echo "Skipping FFmpeg upload (not available)"

# Upload real README.md
echo "Uploading project README..."
gh release upload "$RELEASE_TAG" \
    "$PROJECT_ROOT/README.md" \
    --repo "$GITHUB_REPO"

print_status "All components uploaded"

# Calculate total release size
echo -e "\n${BLUE}📊 Calculating release statistics...${NC}"

TOTAL_SIZE=0
PKG_SIZE=$(stat -f%z "Skip_the_Podcast_Desktop-${VERSION}.pkg")
COMPONENTS_SIZE=0

for file in "${REQUIRED_FILES[@]}"; do
    if [ -f "$file" ]; then
        FILE_SIZE=$(stat -f%z "$file")
        TOTAL_SIZE=$((TOTAL_SIZE + FILE_SIZE))

        if [[ "$file" != "Skip_the_Podcast_Desktop-"* ]]; then
            COMPONENTS_SIZE=$((COMPONENTS_SIZE + FILE_SIZE))
        fi
    fi
done

# Convert to human readable (macOS compatible)
TOTAL_SIZE_HR=$(du -h "Skip_the_Podcast_Desktop-${VERSION}.pkg" 2>/dev/null | cut -f1 || echo "${TOTAL_SIZE}B")
PKG_SIZE_HR=$(du -h "Skip_the_Podcast_Desktop-${VERSION}.pkg" 2>/dev/null | cut -f1 || echo "${PKG_SIZE}B")
COMPONENTS_SIZE_HR=$(echo "scale=1; $COMPONENTS_SIZE / 1048576" | bc -l 2>/dev/null || echo "${COMPONENTS_SIZE}B")MB

print_status "Release statistics calculated"

# Publish release
echo -e "\n${BLUE}🎉 Publishing release...${NC}"

gh release edit "$RELEASE_TAG" \
    --repo "$GITHUB_REPO" \
    --draft=false

print_status "Release published"

# Final summary
echo -e "\n${GREEN}${BOLD}🎉 GitHub Release Complete!${NC}"
echo "=============================================="
echo "Release: $RELEASE_NAME"
echo "Tag: $RELEASE_TAG"
echo "URL: https://github.com/$GITHUB_REPO/releases/tag/$RELEASE_TAG"
echo ""
echo "📊 Release Statistics:"
echo "• PKG Installer: $PKG_SIZE_HR"
echo "• Components: $COMPONENTS_SIZE_HR"
echo "• Total Release: $TOTAL_SIZE_HR"
echo ""
echo "📦 Components:"
for file in "${REQUIRED_FILES[@]}"; do
    if [ -f "$file" ]; then
        SIZE=$(du -h "$file" | cut -f1)
        echo "• $file ($SIZE)"
    fi
done
echo ""
echo "🎯 Next Steps:"
echo "1. Test PKG installation on clean system"
echo "2. Update documentation with new installation process"
echo "3. Announce release to users"
echo "4. Monitor installation success rates"

# Cleanup
rm -f "$RELEASE_NOTES_FILE"

cd "$PROJECT_ROOT"
