#!/bin/bash
# build_python_framework.sh - Create Python 3.13 Framework for PKG Installer
# This script downloads, builds, and packages Python 3.13 as a macOS framework

set -e
set -o pipefail

# Configuration
PYTHON_VERSION="3.13.1"
FRAMEWORK_NAME="Python.framework"
BUILD_DIR="$(pwd)/build_framework"
OUTPUT_DIR="$(pwd)/dist"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m' # No Color

echo -e "${BLUE}${BOLD}🐍 Python Framework Builder for PKG Installer${NC}"
echo "=============================================="
echo "Building Python ${PYTHON_VERSION} as relocatable framework"
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

# Check for required tools
if ! command -v curl &> /dev/null; then
    print_error "curl is required but not installed"
    exit 1
fi

if ! command -v tar &> /dev/null; then
    print_error "tar is required but not installed"
    exit 1
fi

if ! command -v make &> /dev/null; then
    print_error "make is required but not installed"
    exit 1
fi

# Check for Xcode command line tools
if ! xcode-select -p &> /dev/null; then
    print_error "Xcode command line tools are required"
    echo "Install with: xcode-select --install"
    exit 1
fi

print_status "All prerequisites satisfied"

# Create build directories
echo -e "\n${BLUE}📁 Setting up build environment...${NC}"
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"
mkdir -p "$OUTPUT_DIR"

cd "$BUILD_DIR"

# Download Python source
echo -e "\n${BLUE}⬇️ Downloading Python ${PYTHON_VERSION} source...${NC}"
PYTHON_URL="https://www.python.org/ftp/python/${PYTHON_VERSION}/Python-${PYTHON_VERSION}.tar.xz"

if ! curl -L -o "Python-${PYTHON_VERSION}.tar.xz" "$PYTHON_URL"; then
    print_error "Failed to download Python source"
    exit 1
fi

print_status "Python source downloaded"

# Extract source
echo -e "\n${BLUE}📦 Extracting Python source...${NC}"
tar -xf "Python-${PYTHON_VERSION}.tar.xz"
cd "Python-${PYTHON_VERSION}"

print_status "Python source extracted"

# Configure build for framework
echo -e "\n${BLUE}⚙️ Configuring Python build for framework...${NC}"

# macOS-specific configuration for relocatable framework
./configure \
    --enable-framework="$BUILD_DIR/framework" \
    --with-universal-archs=universal2 \
    --enable-universalsdk \
    --with-computed-gotos \
    --enable-optimizations \
    --with-lto \
    --prefix="$BUILD_DIR/framework/${FRAMEWORK_NAME}/Versions/${PYTHON_VERSION%.*}" \
    CPPFLAGS="-I$(brew --prefix openssl)/include" \
    LDFLAGS="-L$(brew --prefix openssl)/lib" || {

    print_warning "Failed with Homebrew OpenSSL, trying with system libraries"

    # Fallback configuration without Homebrew paths
    ./configure \
        --enable-framework="$BUILD_DIR/framework" \
        --with-universal-archs=universal2 \
        --enable-universalsdk \
        --with-computed-gotos \
        --enable-optimizations \
        --with-lto \
        --prefix="$BUILD_DIR/framework/${FRAMEWORK_NAME}/Versions/${PYTHON_VERSION%.*}"
}

print_status "Python build configured"

# Build Python
echo -e "\n${BLUE}🔨 Building Python framework (this may take 10-15 minutes)...${NC}"
make -j$(sysctl -n hw.ncpu) || {
    print_error "Python build failed"
    exit 1
}

print_status "Python framework built successfully"

# Install framework
echo -e "\n${BLUE}📦 Installing Python framework...${NC}"
make frameworkinstall || {
    print_error "Framework installation failed"
    exit 1
}

print_status "Python framework installed"

# Verify framework structure
echo -e "\n${BLUE}🔍 Verifying framework structure...${NC}"
FRAMEWORK_PATH="$BUILD_DIR/framework/${FRAMEWORK_NAME}"

if [ ! -d "$FRAMEWORK_PATH" ]; then
    print_error "Framework directory not found: $FRAMEWORK_PATH"
    exit 1
fi

if [ ! -f "$FRAMEWORK_PATH/Versions/${PYTHON_VERSION%.*}/bin/python${PYTHON_VERSION%.*}" ]; then
    print_error "Python executable not found in framework"
    exit 1
fi

print_status "Framework structure verified"

# Test framework Python
echo -e "\n${BLUE}🧪 Testing framework Python...${NC}"
FRAMEWORK_PYTHON="$FRAMEWORK_PATH/Versions/${PYTHON_VERSION%.*}/bin/python${PYTHON_VERSION%.*}"

if ! "$FRAMEWORK_PYTHON" -c "import sys; print(f'Python {sys.version}')"; then
    print_error "Framework Python test failed"
    exit 1
fi

print_status "Framework Python working"

# Install essential packages for the framework
echo -e "\n${BLUE}📦 Installing essential packages in framework...${NC}"

# Get pip for the framework Python
"$FRAMEWORK_PYTHON" -m ensurepip --upgrade || {
    print_warning "ensurepip failed, trying to download pip manually"
    curl -O https://bootstrap.pypa.io/get-pip.py
    "$FRAMEWORK_PYTHON" get-pip.py
}

# Install wheel and setuptools
"$FRAMEWORK_PYTHON" -m pip install --upgrade pip setuptools wheel

print_status "Essential packages installed"

# Create relocatable framework package
echo -e "\n${BLUE}📦 Creating relocatable framework package...${NC}"

# Copy framework to output directory with proper structure
PACKAGE_FRAMEWORK_DIR="$OUTPUT_DIR/python-framework-${PYTHON_VERSION%.*}"
rm -rf "$PACKAGE_FRAMEWORK_DIR"
mkdir -p "$PACKAGE_FRAMEWORK_DIR"

# Copy the entire framework
cp -R "$FRAMEWORK_PATH" "$PACKAGE_FRAMEWORK_DIR/"

# Create version info file
cat > "$PACKAGE_FRAMEWORK_DIR/version_info.json" << EOF
{
  "python_version": "${PYTHON_VERSION}",
  "framework_version": "${PYTHON_VERSION%.*}",
  "build_date": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "architecture": "universal2",
  "features": [
    "optimizations",
    "lto",
    "computed-gotos",
    "universal-binary"
  ]
}
EOF

# Create installation script for the framework
cat > "$PACKAGE_FRAMEWORK_DIR/install_framework.sh" << 'EOF'
#!/bin/bash
# Install Python Framework into Skip the Podcast Desktop.app

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

FRAMEWORKS_DIR="$APP_BUNDLE/Contents/Frameworks"
mkdir -p "$FRAMEWORKS_DIR"

echo "Installing Python framework to: $FRAMEWORKS_DIR"
cp -R Python.framework "$FRAMEWORKS_DIR/"

echo "✅ Python framework installed successfully"
EOF

chmod +x "$PACKAGE_FRAMEWORK_DIR/install_framework.sh"

print_status "Framework package created"

# Create compressed archive
echo -e "\n${BLUE}🗜️ Creating compressed archive...${NC}"
cd "$OUTPUT_DIR"
tar -czf "python-framework-${PYTHON_VERSION%.*}-macos.tar.gz" "python-framework-${PYTHON_VERSION%.*}"

# Calculate size
ARCHIVE_SIZE=$(du -h "python-framework-${PYTHON_VERSION%.*}-macos.tar.gz" | cut -f1)
print_status "Archive created: python-framework-${PYTHON_VERSION%.*}-macos.tar.gz (${ARCHIVE_SIZE})"

# Create checksum
echo -e "\n${BLUE}🔐 Creating checksum...${NC}"
shasum -a 256 "python-framework-${PYTHON_VERSION%.*}-macos.tar.gz" > "python-framework-${PYTHON_VERSION%.*}-macos.tar.gz.sha256"

print_status "Checksum created"

# Cleanup build directory
echo -e "\n${BLUE}🧹 Cleaning up build directory...${NC}"
rm -rf "$BUILD_DIR"

print_status "Build directory cleaned"

# Final summary
echo -e "\n${GREEN}${BOLD}🎉 Python Framework Build Complete!${NC}"
echo "=============================================="
echo "Framework archive: $OUTPUT_DIR/python-framework-${PYTHON_VERSION%.*}-macos.tar.gz"
echo "Archive size: $ARCHIVE_SIZE"
echo "Checksum: $OUTPUT_DIR/python-framework-${PYTHON_VERSION%.*}-macos.tar.gz.sha256"
echo ""
echo "Next steps:"
echo "1. Upload to GitHub releases"
echo "2. Test framework installation in PKG installer"
echo "3. Verify framework isolation"
echo ""
echo "Framework features:"
echo "• Universal binary (Intel + Apple Silicon)"
echo "• Optimized build with LTO"
echo "• Relocatable framework structure"
echo "• Essential packages included"
