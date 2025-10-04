#!/bin/bash
# Fix broken absolute symlinks in Python framework tarball

set -e

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
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

echo -e "${BLUE}${BOLD}🔧 Python Framework Symlink Fixer${NC}"
echo "=================================="

# Check if the tarball exists
if [ ! -f "$DIST_DIR/python-framework-3.13-macos.tar.gz" ]; then
    print_error "Python framework tarball not found at: $DIST_DIR/python-framework-3.13-macos.tar.gz"
    exit 1
fi

# Create temp directory
TEMP_DIR=$(mktemp -d)
trap "rm -rf $TEMP_DIR" EXIT

echo -e "\n${BLUE}📦 Extracting framework...${NC}"
cd "$TEMP_DIR"
tar -xzf "$DIST_DIR/python-framework-3.13-macos.tar.gz"

# Check if extraction was successful
if [ ! -d "framework" ]; then
    print_error "Framework directory not found after extraction"
    exit 1
fi

echo -e "\n${BLUE}🔍 Fixing symbolic links...${NC}"

# Function to convert absolute symlink to relative
fix_symlink() {
    local link="$1"
    local target=$(readlink "$link")
    
    # Check if it's an absolute symlink pointing to the build directory
    if [[ "$target" == /Users/*/Projects/Knowledge_Chipper/build_framework/* ]]; then
        # Extract the relative part after "build_framework/"
        local relative_part="${target#*/build_framework/}"
        
        # Calculate the relative path from the link to the target
        local link_dir=$(dirname "$link")
        local target_file=$(basename "$target")
        
        # For Python framework, the structure is predictable
        # Links in bin/ point to executables in the same directory
        if [[ "$link" == */bin/* ]] && [[ "$target" == */bin/* ]]; then
            # Same directory, just use the filename
            rm "$link"
            ln -s "$(basename "$target")" "$link"
            echo "Fixed: $link -> $(basename "$target")"
        else
            print_warning "Unknown symlink pattern: $link -> $target"
        fi
    fi
}

# Find and fix all symbolic links
find framework -type l | while read -r link; do
    fix_symlink "$link"
done

# Special handling for Python framework structure
if [ -d "framework/Python.framework/Versions/3.13/bin" ]; then
    cd "framework/Python.framework/Versions/3.13/bin"
    
    # Create proper relative symlinks
    print_status "Creating proper symlinks in bin directory"
    
    # python3 should point to the actual executable
    if [ -f "python3.13" ]; then
        rm -f python3
        ln -s python3.13 python3
        print_status "Linked python3 -> python3.13"
    fi
    
    # pip3 should point to pip3.13
    if [ -f "pip3.13" ]; then
        rm -f pip3
        ln -s pip3.13 pip3
        print_status "Linked pip3 -> pip3.13"
    fi
    
    cd "$TEMP_DIR"
fi

echo -e "\n${BLUE}📦 Creating fixed tarball...${NC}"
tar -czf "python-framework-3.13-macos-fixed.tar.gz" framework/

# Move the fixed tarball to dist
mv "python-framework-3.13-macos-fixed.tar.gz" "$DIST_DIR/python-framework-3.13-macos.tar.gz"

# Create checksum
cd "$DIST_DIR"
shasum -a 256 "python-framework-3.13-macos.tar.gz" > "python-framework-3.13-macos.tar.gz.sha256"

print_status "Fixed Python framework tarball created"
echo -e "\n${GREEN}${BOLD}✨ Symlinks fixed successfully!${NC}"
