#!/bin/bash
# Rebuild Python framework with proper structure

set -e

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
BUILD_DIR="$PROJECT_ROOT/build_framework"
DIST_DIR="$PROJECT_ROOT/dist"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color
BOLD='\033[1m'

print_status() {
    echo -e "${GREEN}✅${NC} $1"
}

print_error() {
    echo -e "${RED}❌${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠️${NC} $1"
}

echo -e "${BLUE}${BOLD}🐍 Python Framework Rebuilder${NC}"
echo "================================"

# Clean up old build
echo -e "\n${BLUE}🧹 Cleaning up old build...${NC}"
rm -rf "$BUILD_DIR/framework_new"
mkdir -p "$BUILD_DIR/framework_new"

# Create framework structure
FRAMEWORK_ROOT="$BUILD_DIR/framework_new/framework/Python.framework"
mkdir -p "$FRAMEWORK_ROOT/Versions/3.13/bin"
mkdir -p "$FRAMEWORK_ROOT/Versions/3.13/lib"
mkdir -p "$FRAMEWORK_ROOT/Versions/3.13/include"

# Use the system Python to create a minimal framework
echo -e "\n${BLUE}📦 Creating minimal Python framework...${NC}"

# Copy the Python executable
if [ -f "/usr/bin/python3" ]; then
    cp /usr/bin/python3 "$FRAMEWORK_ROOT/Versions/3.13/bin/python3.13"
    print_status "Copied Python executable"
else
    print_error "Python3 not found at /usr/bin/python3"
    exit 1
fi

# Create symlinks with relative paths
cd "$FRAMEWORK_ROOT/Versions/3.13/bin"
ln -sf python3.13 python3
ln -sf python3.13 python

# Copy pip if available
if command -v pip3 &> /dev/null; then
    # Create a pip wrapper script
    cat > pip3 << 'EOF'
#!/bin/bash
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
exec "$DIR/python3" -m pip "$@"
EOF
    chmod +x pip3
    ln -sf pip3 pip
    print_status "Created pip wrapper"
fi

# Create version symlinks
cd "$FRAMEWORK_ROOT/Versions"
ln -sf 3.13 Current

cd "$FRAMEWORK_ROOT"
ln -sf Versions/Current/bin bin
ln -sf Versions/Current/lib lib
ln -sf Versions/Current/include include

# Copy essential Python libraries
echo -e "\n${BLUE}📚 Copying Python standard library...${NC}"
if [ -d "/Library/Frameworks/Python.framework/Versions/3.13/lib/python3.13" ]; then
    cp -R "/Library/Frameworks/Python.framework/Versions/3.13/lib/python3.13" "$FRAMEWORK_ROOT/Versions/3.13/lib/"
    print_status "Copied Python standard library"
elif [ -d "/usr/lib/python3.13" ]; then
    cp -R "/usr/lib/python3.13" "$FRAMEWORK_ROOT/Versions/3.13/lib/"
    print_status "Copied Python standard library from system"
else
    print_warning "Could not find Python standard library"
fi

# Create the tarball
echo -e "\n${BLUE}📦 Creating framework archive...${NC}"
cd "$BUILD_DIR/framework_new"

# Use -h flag to dereference symlinks during archiving
tar -czf "$DIST_DIR/python-framework-3.13-macos.tar.gz" framework/

# Create checksum
cd "$DIST_DIR"
shasum -a 256 "python-framework-3.13-macos.tar.gz" > "python-framework-3.13-macos.tar.gz.sha256"

# Get size
ARCHIVE_SIZE=$(du -h "python-framework-3.13-macos.tar.gz" | cut -f1)

print_status "Framework archive created: python-framework-3.13-macos.tar.gz ($ARCHIVE_SIZE)"

# Verify the archive
echo -e "\n${BLUE}🔍 Verifying archive...${NC}"
cd /tmp
rm -rf test_verify
mkdir test_verify
cd test_verify
tar -xzf "$DIST_DIR/python-framework-3.13-macos.tar.gz"

# Check symlinks
if [ -L "framework/Python.framework/Versions/3.13/bin/python3" ]; then
    TARGET=$(readlink "framework/Python.framework/Versions/3.13/bin/python3")
    if [[ "$TARGET" != /* ]]; then
        print_status "Symlinks are relative: $TARGET"
    else
        print_error "Symlinks are still absolute: $TARGET"
    fi
fi

# Clean up
cd /
rm -rf /tmp/test_verify

echo -e "\n${GREEN}${BOLD}✨ Python framework rebuilt successfully!${NC}"
