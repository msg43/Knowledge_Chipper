#!/bin/bash
# build_simple_python_framework.sh - Create a simple working Python framework
# This is a simplified approach that focuses on getting a working PKG

set -e
set -o pipefail

# Configuration
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

echo -e "${BLUE}${BOLD}🐍 Simple Python Framework Builder${NC}"
echo "=================================="
echo "Creating a minimal Python framework for PKG installer"
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

# Create output directory
mkdir -p "$OUTPUT_DIR"

# For now, let's create a placeholder framework that will work with the PKG installer
# We'll use the system Python but package it properly for the app bundle

echo -e "${BLUE}📦 Creating Python framework package...${NC}"

# Create a simple framework structure
FRAMEWORK_DIR="$OUTPUT_DIR/python-framework-3.13"
rm -rf "$FRAMEWORK_DIR"
mkdir -p "$FRAMEWORK_DIR"

# Get the current Python executable and its details
PYTHON_EXE="$(which python3)"
PYTHON_VERSION="$($PYTHON_EXE --version | cut -d' ' -f2)"

print_status "Using Python: $PYTHON_EXE (version $PYTHON_VERSION)"

# Create a simple framework info file
cat > "$FRAMEWORK_DIR/framework_info.json" << EOF
{
  "python_executable": "$PYTHON_EXE",
  "python_version": "$PYTHON_VERSION",
  "build_date": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "framework_type": "system_python",
  "notes": "This framework uses the system Python installation"
}
EOF

# Create a simple installation script
cat > "$FRAMEWORK_DIR/install_framework.sh" << 'EOF'
#!/bin/bash
# Simple Python framework installer for PKG

APP_BUNDLE="$1"
if [ -z "$APP_BUNDLE" ]; then
    echo "Usage: $0 <path-to-app-bundle>"
    exit 1
fi

echo "Installing Python framework to: $APP_BUNDLE"

# Create the Python directory in the app bundle
mkdir -p "$APP_BUNDLE/Contents/Python"

# Create a simple launcher script
cat > "$APP_BUNDLE/Contents/Python/python3" << 'PYTHON_LAUNCHER'
#!/bin/bash
# Python launcher for Skip the Podcast Desktop
exec /usr/bin/python3 "$@"
PYTHON_LAUNCHER

chmod +x "$APP_BUNDLE/Contents/Python/python3"

echo "Python framework installed successfully"
EOF

chmod +x "$FRAMEWORK_DIR/install_framework.sh"

# Create the tarball
echo -e "\n${BLUE}📦 Creating framework archive...${NC}"
cd "$OUTPUT_DIR"
tar -czf "python-framework-3.13-macos.tar.gz" "python-framework-3.13"
ARCHIVE_SIZE=$(du -h "python-framework-3.13-macos.tar.gz" | cut -f1)

print_status "Framework archive created: python-framework-3.13-macos.tar.gz ($ARCHIVE_SIZE)"

# Create checksums
shasum -a 256 "python-framework-3.13-macos.tar.gz" > "python-framework-3.13-macos.tar.gz.sha256"

print_status "Checksums created"

# Cleanup
rm -rf "python-framework-3.13"

echo ""
echo -e "${GREEN}${BOLD}✅ Python Framework Ready!${NC}"
echo "==============================="
echo "Archive: $OUTPUT_DIR/python-framework-3.13-macos.tar.gz"
echo "Size: $ARCHIVE_SIZE"
echo "Type: System Python wrapper"
echo ""
echo "This framework will use the system Python installation"
echo "which is suitable for the PKG installer approach."
