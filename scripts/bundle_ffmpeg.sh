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

# Clean and create build directories
echo -e "${BLUE}📁 Setting up build environment...${NC}"
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"
mkdir -p "$OUTPUT_DIR"

print_status "Build directories created"

# Download FFmpeg
echo -e "\n${BLUE}⬇️ Downloading FFmpeg...${NC}"

cd "$BUILD_DIR"

# Try to download from evermeet.cx (reliable Mac builds)
if curl -L -o "ffmpeg.zip" "$FFMPEG_URL"; then
    print_status "FFmpeg downloaded from evermeet.cx"
    unzip ffmpeg.zip

    # Find the FFmpeg binary
    FFMPEG_BIN=$(find . -name "ffmpeg" -type f -executable | head -1)

    if [ -z "$FFMPEG_BIN" ]; then
        print_error "FFmpeg binary not found in download"
        exit 1
    fi

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

    else
        print_error "No fallback method available for FFmpeg download"
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

# Cleanup build directory
echo -e "\n${BLUE}🧹 Cleaning up build directory...${NC}"
rm -rf "$BUILD_DIR"

print_status "Build directory cleaned"

# Final summary
echo -e "\n${GREEN}${BOLD}🎉 FFmpeg Bundle Complete!${NC}"
echo "=============================================="
echo "Archive: $OUTPUT_DIR/ffmpeg-macos-universal.tar.gz"
echo "Size: $ARCHIVE_SIZE"
echo "Version: $FFMPEG_INFO"
echo "Checksum: $OUTPUT_DIR/ffmpeg-macos-universal.tar.gz.sha256"
echo ""
echo "Next steps:"
echo "1. Upload to GitHub releases"
echo "2. Test FFmpeg in PKG installer"
echo "3. Verify media processing capabilities"
