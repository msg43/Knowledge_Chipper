#!/bin/bash
# bundle_deno.sh - Create Deno package for PKG/DMG installer
# Downloads and packages Deno for reliable offline use with yt-dlp
#
# Deno is REQUIRED for yt-dlp 2025.11.12+ to download from YouTube
# This script bundles Deno into the app for offline/portable use

set -e
set -o pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
BUILD_DIR="$PROJECT_ROOT/build_deno"
OUTPUT_DIR="$PROJECT_ROOT/dist"

# Deno configuration
# Auto-detect architecture
ARCH=$(uname -m)
case "$ARCH" in
    x86_64)
        DENO_ARCH="x86_64"
        ;;
    arm64|aarch64)
        DENO_ARCH="aarch64"
        ;;
    *)
        echo "❌ Unsupported architecture: $ARCH"
        exit 1
        ;;
esac

# Deno version to bundle (update this when upgrading)
DENO_VERSION="${DENO_VERSION:-2.5.6}"
DENO_URL="https://github.com/denoland/deno/releases/download/v${DENO_VERSION}/deno-${DENO_ARCH}-apple-darwin.zip"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m' # No Color

echo -e "${BLUE}${BOLD}🦕 Deno Bundle Creator for PKG/DMG Installer${NC}"
echo "=============================================="
echo "Creating Deno package for yt-dlp YouTube support"
echo "Architecture: $ARCH ($DENO_ARCH)"
echo "Deno Version: $DENO_VERSION"
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

# Check for cached Deno download
DENO_CACHE_FILE="$BUILD_DIR/deno-${DENO_VERSION}-${DENO_ARCH}.zip"
DENO_CACHE_CHECKSUM="$BUILD_DIR/deno-${DENO_VERSION}-${DENO_ARCH}.zip.sha256"

print_status "Build directories created"

# Download Deno (with caching)
echo -e "\n${BLUE}⬇️ Checking Deno cache...${NC}"

cd "$BUILD_DIR"

# Check if we have a cached download
USE_CACHED=0
if [ -f "$DENO_CACHE_FILE" ] && [ -f "$DENO_CACHE_CHECKSUM" ]; then
    print_status "Found cached Deno download"
    
    # Verify cached file integrity
    CACHED_CHECKSUM=$(cat "$DENO_CACHE_CHECKSUM")
    CURRENT_CHECKSUM=$(shasum -a 256 "$DENO_CACHE_FILE" | cut -d' ' -f1)
    
    if [ "$CACHED_CHECKSUM" = "$CURRENT_CHECKSUM" ]; then
        print_status "Cached Deno verified - using existing download"
        USE_CACHED=1
    else
        print_warning "Cached Deno checksum mismatch - re-downloading"
        rm -f "$DENO_CACHE_FILE" "$DENO_CACHE_CHECKSUM"
    fi
else
    print_warning "No cached Deno found - downloading fresh copy"
fi

# Download Deno if needed
if [ $USE_CACHED -eq 0 ]; then
    echo -e "\n${BLUE}⬇️ Downloading Deno v${DENO_VERSION} for ${DENO_ARCH}...${NC}"
    echo "   URL: $DENO_URL"
    
    if curl -L -o "$DENO_CACHE_FILE" "$DENO_URL"; then
        print_status "Deno downloaded from GitHub releases"
        
        # Cache the download with checksum
        shasum -a 256 "$DENO_CACHE_FILE" | cut -d' ' -f1 > "$DENO_CACHE_CHECKSUM"
        print_status "Deno cached for future builds"
    else
        print_error "Failed to download Deno from GitHub"
        echo "   URL: $DENO_URL"
        echo "   Please check your internet connection and try again"
        exit 1
    fi
fi

# Extract Deno
echo -e "\n${BLUE}📦 Extracting Deno...${NC}"
unzip -o "$DENO_CACHE_FILE" -d "$BUILD_DIR/extracted"

DENO_BIN="$BUILD_DIR/extracted/deno"

if [ ! -f "$DENO_BIN" ]; then
    print_error "Deno binary not found in download"
    exit 1
fi

print_status "Deno binary located: $DENO_BIN"

# Verify Deno functionality
echo -e "\n${BLUE}🧪 Testing Deno functionality...${NC}"

if ! "$DENO_BIN" --version &> /dev/null; then
    print_error "Deno binary is not functional"
    exit 1
fi

# Get Deno version info
DENO_INFO=$("$DENO_BIN" --version 2>&1 | head -1)
print_status "Deno verified: $DENO_INFO"

# Create Deno package structure
echo -e "\n${BLUE}📦 Creating Deno package...${NC}"

PACKAGE_DIR="$BUILD_DIR/deno_package"
mkdir -p "$PACKAGE_DIR/bin"
mkdir -p "$PACKAGE_DIR/doc"

# Copy Deno binary
cp "$DENO_BIN" "$PACKAGE_DIR/bin/deno"
chmod +x "$PACKAGE_DIR/bin/deno"

# Create version info
cat > "$PACKAGE_DIR/version_info.json" << EOF
{
  "deno_version": "$DENO_VERSION",
  "deno_info": "$DENO_INFO",
  "build_date": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "architecture": "$ARCH",
  "deno_arch": "$DENO_ARCH",
  "source": "github.com/denoland/deno",
  "purpose": "JavaScript runtime for yt-dlp YouTube support",
  "required_for": "yt-dlp >= 2025.11.12"
}
EOF

# Create README
cat > "$PACKAGE_DIR/README.md" << 'EOF'
# Deno for Skip the Podcast Desktop

This package contains the Deno JavaScript runtime required for yt-dlp YouTube downloads.

## What's Included

- **deno**: Deno binary for macOS
- **version_info.json**: Build and version information

## Why Deno?

Starting with yt-dlp version 2025.11.12, an external JavaScript runtime is required
to download from YouTube. This is because YouTube's signature extraction and format
decryption now use complex JavaScript that requires a full JS runtime.

Deno is the recommended runtime due to:
- Security: Sandboxed execution of untrusted code
- Performance: Fast startup and execution
- Ease of use: No configuration required

## Installation

The PKG installer will automatically:
1. Extract deno to the app bundle
2. Set proper executable permissions
3. Add to the app's PATH

## Usage

yt-dlp automatically detects Deno if it's in PATH. No configuration needed.

## License

Deno is MIT licensed. See https://deno.land for details.

## Source

Binary downloaded from official GitHub releases:
https://github.com/denoland/deno/releases
EOF

# Create installation script
cat > "$PACKAGE_DIR/install_deno.sh" << 'EOF'
#!/bin/bash
# Install Deno into Skip the Podcast Desktop app bundle

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

BIN_DIR="$APP_BUNDLE/Contents/MacOS/bin"
mkdir -p "$BIN_DIR"

echo "Installing Deno to: $BIN_DIR"
cp bin/deno "$BIN_DIR/deno"
chmod +x "$BIN_DIR/deno"

# Test installation
if "$BIN_DIR/deno" --version &> /dev/null; then
    echo "✅ Deno installed and verified"
else
    echo "❌ Deno installation verification failed"
    exit 1
fi
EOF

chmod +x "$PACKAGE_DIR/install_deno.sh"

# Create setup script for app bundle (sources environment variables)
cat > "$PACKAGE_DIR/setup_bundled_deno.sh" << 'EOF'
#!/bin/bash
# Setup bundled Deno for yt-dlp
# Source this script to configure Deno environment

APP_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
DENO_BIN="$APP_DIR/bin/deno"

if [ -f "$DENO_BIN" ]; then
    export DENO_BUNDLED="true"
    export PATH="$APP_DIR/bin:$PATH"
    # yt-dlp will auto-detect Deno in PATH
fi
EOF

chmod +x "$PACKAGE_DIR/setup_bundled_deno.sh"

print_status "Deno package structure created"

# Create compressed archive
echo -e "\n${BLUE}🗜️ Creating Deno archive...${NC}"

cd "$BUILD_DIR"
tar -czf "$OUTPUT_DIR/deno-macos-${DENO_ARCH}.tar.gz" deno_package/

# Calculate size
ARCHIVE_SIZE=$(du -h "$OUTPUT_DIR/deno-macos-${DENO_ARCH}.tar.gz" | cut -f1)

print_status "Deno archive created: $ARCHIVE_SIZE"

# Create checksum
echo -e "\n${BLUE}🔐 Creating checksum...${NC}"
cd "$OUTPUT_DIR"
shasum -a 256 "deno-macos-${DENO_ARCH}.tar.gz" > "deno-macos-${DENO_ARCH}.tar.gz.sha256"

print_status "Checksum created"

# Cleanup build directory (preserve cache)
echo -e "\n${BLUE}🧹 Cleaning up build directory...${NC}"

# Remove extracted files but keep cached downloads
rm -rf "$BUILD_DIR/extracted" "$BUILD_DIR/deno_package"
print_status "Build directory cleaned (cache preserved)"

# Final summary
echo -e "\n${GREEN}${BOLD}🎉 Deno Bundle Complete!${NC}"
echo "=============================================="
echo "Archive: $OUTPUT_DIR/deno-macos-${DENO_ARCH}.tar.gz"
echo "Size: $ARCHIVE_SIZE"
echo "Version: $DENO_VERSION"
echo "Architecture: $DENO_ARCH"
echo "Checksum: $OUTPUT_DIR/deno-macos-${DENO_ARCH}.tar.gz.sha256"
echo ""
if [ $USE_CACHED -eq 1 ]; then
    echo -e "${GREEN}💾 Used cached Deno download (faster rebuilds)${NC}"
else
    echo -e "${BLUE}💾 Deno cached for future builds${NC}"
fi
echo ""
echo "Next steps:"
echo "1. Run build_macos_app.sh to include in DMG"
echo "2. Deno will be available for yt-dlp automatically"
echo "3. No user configuration required"
