#!/bin/bash
# bundle_ffmpeg.sh - Create FFmpeg package for PKG installer
# Downloads and packages FFmpeg for reliable self-hosting

set -e
set -o pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
BUILD_DIR="$PROJECT_ROOT/build_ffmpeg"
OUTPUT_DIR="$PROJECT_ROOT/dist"

# FFmpeg configuration
FFMPEG_VERSION="6.1.1"
FFMPEG_URL="https://evermeet.cx/ffmpeg/getrelease/zip"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m' # No Color

echo -e "${BLUE}${BOLD}🎬 FFmpeg Bundle Creator for PKG Installer${NC}"
echo "=============================================="
echo "Creating FFmpeg package for self-hosting"
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

# Setup build directories
echo -e "${BLUE}📁 Setting up build environment...${NC}"
mkdir -p "$BUILD_DIR"
mkdir -p "$OUTPUT_DIR"

# Check for cached FFmpeg download
FFMPEG_CACHE_FILE="$BUILD_DIR/ffmpeg.zip"
FFMPEG_CACHE_CHECKSUM="$BUILD_DIR/ffmpeg.zip.sha256"

print_status "Build directories created"

# Download FFmpeg (with caching)
echo -e "\n${BLUE}⬇️ Checking FFmpeg cache...${NC}"

cd "$BUILD_DIR"

# Check if we have a cached download
if [ -f "$FFMPEG_CACHE_FILE" ] && [ -f "$FFMPEG_CACHE_CHECKSUM" ]; then
    print_status "Found cached FFmpeg download"

    # Verify cached file integrity
    CACHED_CHECKSUM=$(cat "$FFMPEG_CACHE_CHECKSUM")
    CURRENT_CHECKSUM=$(shasum -a 256 "$FFMPEG_CACHE_FILE" | cut -d' ' -f1)

    if [ "$CACHED_CHECKSUM" = "$CURRENT_CHECKSUM" ]; then
        print_status "Cached FFmpeg verified - using existing download"
        USE_CACHED=1
    else
        print_warning "Cached FFmpeg checksum mismatch - re-downloading"
        rm -f "$FFMPEG_CACHE_FILE" "$FFMPEG_CACHE_CHECKSUM"
        USE_CACHED=0
    fi
else
    print_warning "No cached FFmpeg found - downloading fresh copy"
    USE_CACHED=0
fi

# Download FFmpeg if needed
if [ $USE_CACHED -eq 0 ]; then
    echo -e "\n${BLUE}⬇️ Downloading FFmpeg from evermeet.cx...${NC}"

    # Try to download from evermeet.cx (reliable Mac builds)
    if curl -L -o "ffmpeg.zip" "$FFMPEG_URL"; then
        print_status "FFmpeg downloaded from evermeet.cx"

        # Cache the download with checksum
        shasum -a 256 "ffmpeg.zip" | cut -d' ' -f1 > "ffmpeg.zip.sha256"
        print_status "FFmpeg cached for future builds"
    else
        print_error "Failed to download FFmpeg from evermeet.cx"
        print_warning "Trying alternative download method..."

        # Fallback: try to build from Homebrew
        if command -v brew &> /dev/null; then
            echo "Using Homebrew FFmpeg as fallback..."

            # Create temporary brew environment
            export HOMEBREW_NO_AUTO_UPDATE=1
            brew install ffmpeg --quiet

            # Copy FFmpeg binary
            FFMPEG_BIN="$(brew --prefix)/bin/ffmpeg"

            if [ ! -f "$FFMPEG_BIN" ]; then
                print_error "Homebrew FFmpeg not found"
                exit 1
            fi

            cp "$FFMPEG_BIN" "./ffmpeg"
            FFMPEG_BIN="./ffmpeg"

            # Skip the zip extraction process for Homebrew fallback
            print_status "Using Homebrew FFmpeg binary"
        else
            print_error "No fallback method available for FFmpeg download"
            exit 1
        fi
    fi
fi

# Extract FFmpeg if we downloaded it (not Homebrew fallback)
if [ -z "$FFMPEG_BIN" ]; then
    echo -e "\n${BLUE}📦 Extracting FFmpeg...${NC}"
    unzip -o ffmpeg.zip

    # Find the FFmpeg binary
    FFMPEG_BIN=$(find . -name "ffmpeg" -type f -perm +111 | head -1)

    if [ -z "$FFMPEG_BIN" ]; then
        print_error "FFmpeg binary not found in download"
        exit 1
    fi
fi

print_status "FFmpeg binary located: $FFMPEG_BIN"

# Verify FFmpeg functionality
echo -e "\n${BLUE}🧪 Testing FFmpeg functionality...${NC}"

if ! "$FFMPEG_BIN" -version &> /dev/null; then
    print_error "FFmpeg binary is not functional"
    exit 1
fi

# Get FFmpeg version info
FFMPEG_INFO=$("$FFMPEG_BIN" -version 2>&1 | head -1)
print_status "FFmpeg verified: $FFMPEG_INFO"

# Create FFmpeg package structure
echo -e "\n${BLUE}📦 Creating FFmpeg package...${NC}"

PACKAGE_DIR="$BUILD_DIR/ffmpeg_package"
mkdir -p "$PACKAGE_DIR/bin"
mkdir -p "$PACKAGE_DIR/doc"

# Copy FFmpeg binary
cp "$FFMPEG_BIN" "$PACKAGE_DIR/bin/ffmpeg"
chmod +x "$PACKAGE_DIR/bin/ffmpeg"

# Create version info
cat > "$PACKAGE_DIR/version_info.json" << EOF
{
  "ffmpeg_version": "$FFMPEG_INFO",
  "build_date": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "architecture": "$(uname -m)",
  "source": "evermeet.cx",
  "capabilities": [
    "video_processing",
    "audio_extraction",
    "format_conversion",
    "codec_support"
  ]
}
EOF

# Create README
cat > "$PACKAGE_DIR/README.md" << 'EOF'
# FFmpeg for Skip the Podcast Desktop

This package contains a statically-linked FFmpeg binary optimized for macOS.

## What's Included

- **ffmpeg**: Complete FFmpeg binary with all standard codecs
- **version_info.json**: Build and version information

## Installation

The PKG installer will automatically:
1. Extract ffmpeg to the app bundle
2. Set proper executable permissions
3. Verify functionality

## License

FFmpeg is licensed under the LGPL/GPL. See https://ffmpeg.org/legal.html for details.

## Source

Binary downloaded from evermeet.cx, a trusted source for macOS FFmpeg builds.
EOF

# Create installation script
cat > "$PACKAGE_DIR/install_ffmpeg.sh" << 'EOF'
#!/bin/bash
# Install FFmpeg into Skip the Podcast Desktop app bundle

set -e

APP_BUNDLE="$1"
if [ -z "$APP_BUNDLE" ]; then
    echo "Usage: $0 <path-to-app-bundle>"
    exit 1
fi

if [ ! -d "$APP_BUNDLE" ]; then
    echo "Error: App bundle not found: $APP_BUNDLE"
    exit 1
fi

BIN_DIR="$APP_BUNDLE/Contents/MacOS"
mkdir -p "$BIN_DIR"

echo "Installing FFmpeg to: $BIN_DIR"
cp bin/ffmpeg "$BIN_DIR/ffmpeg"
chmod +x "$BIN_DIR/ffmpeg"

# Test installation
if "$BIN_DIR/ffmpeg" -version &> /dev/null; then
    echo "✅ FFmpeg installed and verified"
else
    echo "❌ FFmpeg installation verification failed"
    exit 1
fi
EOF

chmod +x "$PACKAGE_DIR/install_ffmpeg.sh"

print_status "FFmpeg package structure created"

# Create compressed archive
echo -e "\n${BLUE}🗜️ Creating FFmpeg archive...${NC}"

cd "$BUILD_DIR"
tar -czf "$OUTPUT_DIR/ffmpeg-macos-universal.tar.gz" ffmpeg_package/

# Calculate size
ARCHIVE_SIZE=$(du -h "$OUTPUT_DIR/ffmpeg-macos-universal.tar.gz" | cut -f1)

print_status "FFmpeg archive created: $ARCHIVE_SIZE"

# Create checksum
echo -e "\n${BLUE}🔐 Creating checksum...${NC}"
cd "$OUTPUT_DIR"
shasum -a 256 "ffmpeg-macos-universal.tar.gz" > "ffmpeg-macos-universal.tar.gz.sha256"

print_status "Checksum created"

# Cleanup build directory (preserve cache)
echo -e "\n${BLUE}🧹 Cleaning up build directory...${NC}"

# Remove extracted files but keep cached downloads
if [ -f "$BUILD_DIR/ffmpeg.zip" ]; then
    # Keep the cached zip file and checksum
    find "$BUILD_DIR" -maxdepth 1 -type f ! -name "ffmpeg.zip*" -delete
    find "$BUILD_DIR" -maxdepth 1 -type d ! -name "." -exec rm -rf {} + 2>/dev/null || true
    print_status "Build directory cleaned (cache preserved)"
else
    # No cache to preserve, clean everything
    rm -rf "$BUILD_DIR"
    print_status "Build directory cleaned"
fi

# Final summary
echo -e "\n${GREEN}${BOLD}🎉 FFmpeg Bundle Complete!${NC}"
echo "=============================================="
echo "Archive: $OUTPUT_DIR/ffmpeg-macos-universal.tar.gz"
echo "Size: $ARCHIVE_SIZE"
echo "Version: $FFMPEG_INFO"
echo "Checksum: $OUTPUT_DIR/ffmpeg-macos-universal.tar.gz.sha256"
echo ""
if [ $USE_CACHED -eq 1 ]; then
    echo -e "${GREEN}💾 Used cached FFmpeg download (faster rebuilds)${NC}"
else
    echo -e "${BLUE}💾 FFmpeg cached for future builds${NC}"
fi
echo ""
echo "Next steps:"
echo "1. Upload to GitHub releases"
echo "2. Test FFmpeg in PKG installer"
echo "3. Verify media processing capabilities"
