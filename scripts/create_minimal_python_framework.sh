#!/bin/bash
# Create a minimal but complete Python framework structure

set -e

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
DIST_DIR="$PROJECT_ROOT/dist"
TEMP_DIR="/tmp/python_framework_build_$$"

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

echo -e "${BLUE}${BOLD}🐍 Minimal Python Framework Creator${NC}"
echo "====================================="

# Clean temp directory
rm -rf "$TEMP_DIR"
mkdir -p "$TEMP_DIR"

# Create the framework structure
echo -e "\n${BLUE}📁 Creating framework structure...${NC}"
FRAMEWORK="$TEMP_DIR/Python.framework"
mkdir -p "$FRAMEWORK/Versions/3.13/bin"
mkdir -p "$FRAMEWORK/Versions/3.13/lib"
mkdir -p "$FRAMEWORK/Versions/3.13/include"
mkdir -p "$FRAMEWORK/Versions/3.13/Resources"
mkdir -p "$FRAMEWORK/Versions/3.13/Headers"

# Create all the expected executables as wrappers
echo -e "\n${BLUE}🔧 Creating Python wrappers...${NC}"

# Main python3 executable
cat > "$FRAMEWORK/Versions/3.13/bin/python3" << 'EOF'
#!/bin/bash
exec /usr/bin/python3 "$@"
EOF
chmod +x "$FRAMEWORK/Versions/3.13/bin/python3"

# Create python3.13 symlink
cd "$FRAMEWORK/Versions/3.13/bin"
ln -sf python3 python3.13

# Create other expected executables
for exe in pip3 idle3 pydoc3 python3-config; do
    cat > "$exe" << 'EOF'
#!/bin/bash
exec /usr/bin/python3 -m ${0##*/} "$@"
EOF
    chmod +x "$exe"
done

# Create python3-intel64 as symlink to python3
ln -sf python3 python3-intel64

# Create version symlinks
cd "$FRAMEWORK/Versions"
ln -sf 3.13 Current

# Create top-level symlinks
cd "$FRAMEWORK"
ln -sf Versions/Current/bin bin
ln -sf Versions/Current/lib lib
ln -sf Versions/Current/include include
ln -sf Versions/Current/Resources Resources
ln -sf Versions/Current/Headers Headers

# Create a minimal Info.plist
cat > "$FRAMEWORK/Versions/3.13/Resources/Info.plist" << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleDevelopmentRegion</key>
    <string>English</string>
    <key>CFBundleExecutable</key>
    <string>Python</string>
    <key>CFBundleIdentifier</key>
    <string>org.python.python</string>
    <key>CFBundleInfoDictionaryVersion</key>
    <string>6.0</string>
    <key>CFBundleName</key>
    <string>Python</string>
    <key>CFBundlePackageType</key>
    <string>FMWK</string>
    <key>CFBundleShortVersionString</key>
    <string>3.13</string>
    <key>CFBundleVersion</key>
    <string>3.13</string>
</dict>
</plist>
EOF

# Package the framework
echo -e "\n${BLUE}📦 Creating archive...${NC}"
cd "$TEMP_DIR"
tar -czf "$DIST_DIR/python-framework-3.13-macos.tar.gz" Python.framework

# Create checksum
cd "$DIST_DIR"
shasum -a 256 python-framework-3.13-macos.tar.gz > python-framework-3.13-macos.tar.gz.sha256

# Cleanup
rm -rf "$TEMP_DIR"

# Get size
ARCHIVE_SIZE=$(du -h "$DIST_DIR/python-framework-3.13-macos.tar.gz" | cut -f1)

print_status "Framework created: python-framework-3.13-macos.tar.gz ($ARCHIVE_SIZE)"
echo -e "\n${GREEN}${BOLD}✨ Minimal Python framework ready!${NC}"
