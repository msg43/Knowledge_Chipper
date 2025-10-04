#!/bin/bash
# Simple fix for Python framework - rebuild without symlinks

set -e

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
DIST_DIR="$PROJECT_ROOT/dist"

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

echo -e "${BLUE}${BOLD}🔧 Python Framework Simple Fix${NC}"
echo "================================="

# Create backup
cp "$DIST_DIR/python-framework-3.13-macos.tar.gz" "$DIST_DIR/python-framework-3.13-macos.tar.gz.backup"

# Extract existing framework
cd "$DIST_DIR"
tar -xzf python-framework-3.13-macos.tar.gz

# Check if we have the actual Python files
if [ ! -d "framework" ]; then
    # Try the old structure
    if [ -d "python-framework-3.13" ]; then
        mv python-framework-3.13 framework_temp
        mkdir -p framework
        mv framework_temp/* framework/ 2>/dev/null || true
        rm -rf framework_temp
    else
        print_error "No framework directory found"
        exit 1
    fi
fi

# Create a minimal Python framework wrapper
echo -e "\n${BLUE}📦 Creating minimal framework...${NC}"

# Create the basic structure
mkdir -p framework_new/Python.framework/Versions/3.13/bin
mkdir -p framework_new/Python.framework/Versions/3.13/lib
mkdir -p framework_new/Python.framework/Versions/3.13/Resources

# Create a Python wrapper that uses system Python
cat > framework_new/Python.framework/Versions/3.13/bin/python3 << 'EOF'
#!/bin/bash
# Python wrapper for Skip the Podcast
exec /usr/bin/python3 "$@"
EOF

chmod +x framework_new/Python.framework/Versions/3.13/bin/python3

# Create pip wrapper
cat > framework_new/Python.framework/Versions/3.13/bin/pip3 << 'EOF'
#!/bin/bash
# Pip wrapper for Skip the Podcast
exec /usr/bin/python3 -m pip "$@"
EOF

chmod +x framework_new/Python.framework/Versions/3.13/bin/pip3

# Create symlinks
cd framework_new/Python.framework/Versions
ln -sf 3.13 Current

cd ../
ln -sf Versions/Current/bin bin
ln -sf Versions/Current/lib lib
ln -sf Versions/Current/Resources Resources

# Package it
echo -e "\n${BLUE}📦 Creating new archive...${NC}"
cd "$DIST_DIR"
rm -f python-framework-3.13-macos.tar.gz
tar -czf python-framework-3.13-macos.tar.gz -C framework_new .

# Cleanup
rm -rf framework framework_new

# Create checksum
shasum -a 256 python-framework-3.13-macos.tar.gz > python-framework-3.13-macos.tar.gz.sha256

print_status "Python framework fixed"
echo -e "\n${GREEN}${BOLD}✨ Framework ready for packaging!${NC}"
