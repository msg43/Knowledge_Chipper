#!/bin/bash
# Create a Python framework with all dependencies pre-installed

set -e

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
DIST_DIR="$PROJECT_ROOT/dist"
BUILD_DIR="$PROJECT_ROOT/build_framework"
TEMP_DIR="/tmp/python_framework_bundled_$$"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color
BOLD='\033[1m'

print_status() {
    echo -e "${GREEN}✅${NC} $1"
}

print_error() {
    echo -e "${RED}❌${NC} $1"
}

echo -e "${BLUE}${BOLD}🐍 Bundled Python Framework Creator${NC}"
echo "======================================"

# Clean up temp directory
rm -rf "$TEMP_DIR"
mkdir -p "$TEMP_DIR"

# Create a virtual environment to get dependencies
echo -e "\n${BLUE}📦 Creating virtual environment...${NC}"
cd "$TEMP_DIR"
python3 -m venv venv
source venv/bin/activate

# Install all dependencies from requirements.txt
echo -e "\n${BLUE}📥 Installing dependencies...${NC}"
pip install --upgrade pip
pip install -r "$PROJECT_ROOT/requirements.txt"

# Create framework structure
echo -e "\n${BLUE}📁 Creating framework structure...${NC}"
FRAMEWORK="$TEMP_DIR/framework/Python.framework"
mkdir -p "$FRAMEWORK/Versions/3.13/"{bin,lib,include,Resources,Headers}

# Copy Python and dependencies
echo -e "\n${BLUE}🔧 Copying Python and dependencies...${NC}"
# Copy the entire site-packages
cp -R venv/lib/python*/site-packages "$FRAMEWORK/Versions/3.13/lib/"

# Create wrapper scripts
echo -e "\n${BLUE}📝 Creating wrapper scripts...${NC}"
cat > "$FRAMEWORK/Versions/3.13/bin/python3" << 'EOFPY'
#!/bin/bash
FRAMEWORK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
export PYTHONPATH="$FRAMEWORK_DIR/lib/site-packages:${PYTHONPATH}"
exec /usr/bin/python3 "$@"
EOFPY

chmod +x "$FRAMEWORK/Versions/3.13/bin/python3"

# Create symlinks
ln -s python3 "$FRAMEWORK/Versions/3.13/bin/python3.13"
ln -s python3 "$FRAMEWORK/Versions/3.13/bin/python"

# Create other expected executables
for cmd in pip3 idle3 pydoc3 python3-config python3-intel64; do
    ln -s python3 "$FRAMEWORK/Versions/3.13/bin/$cmd"
done

# Create Current symlink
cd "$FRAMEWORK/Versions" && ln -s 3.13 Current
cd "$FRAMEWORK" && ln -s Versions/Current/Headers Headers

# Create the tarball
echo -e "\n${BLUE}📦 Creating tarball...${NC}"
cd "$TEMP_DIR"
tar -czf "$DIST_DIR/python-framework-3.13-macos.tar.gz" framework/

# Calculate checksum
cd "$DIST_DIR"
shasum -a 256 python-framework-3.13-macos.tar.gz > python-framework-3.13-macos.tar.gz.sha256

# Get size
SIZE=$(du -h python-framework-3.13-macos.tar.gz | cut -f1)

# Clean up
deactivate
rm -rf "$TEMP_DIR"

print_status "Bundled Python framework created"
echo -e "\n${GREEN}${BOLD}✅ Framework Details:${NC}"
echo "File: $DIST_DIR/python-framework-3.13-macos.tar.gz"
echo "Size: $SIZE"
echo "Dependencies: All requirements.txt packages included"
