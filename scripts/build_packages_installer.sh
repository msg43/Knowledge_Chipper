#!/bin/bash
# build_packages_installer.sh - Build installer using Packages.app
#
# This script requires Packages.app to be installed:
# Download from: http://s.sudre.free.fr/Software/Packages/about.html

set -e
set -o pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color
BOLD='\033[1m'

# Script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
BUILD_DIR="$PROJECT_ROOT/build_packages"

# Print colored status
print_status() {
    echo -e "${GREEN}✅${NC} $1"
}

print_error() {
    echo -e "${RED}❌${NC} $1" >&2
}

print_warning() {
    echo -e "${YELLOW}⚠️${NC} $1"
}

echo -e "${BLUE}${BOLD}📦 Packages.app Installer Builder for Skip the Podcast Desktop${NC}"
echo "====================================================="

# Check if Packages.app is installed
if [ ! -d "/Applications/Packages.app" ]; then
    print_error "Packages.app is not installed!"
    echo ""
    echo "Please install Packages.app first:"
    echo "1. Download from: http://s.sudre.free.fr/Software/Packages/about.html"
    echo "2. Drag Packages.app to your Applications folder"
    echo "3. Run this script again"
    exit 1
fi

# Check if packagesbuild command is available
if ! command -v packagesbuild &> /dev/null; then
    print_error "packagesbuild command not found!"
    echo "Installing Packages.app command line tools..."
    # Try to install command line tools
    if [ -f "/Applications/Packages.app/Contents/Resources/packages_cli_installer.pkg" ]; then
        sudo installer -pkg "/Applications/Packages.app/Contents/Resources/packages_cli_installer.pkg" -target /
    else
        print_error "Could not find Packages CLI installer"
        echo "Please install from Packages.app menu: Packages → Install Command Line Tools"
        exit 1
    fi
fi

# Get version from pyproject.toml
VERSION=$(python3 -c "import tomllib; print(tomllib.load(open('$PROJECT_ROOT/pyproject.toml', 'rb'))['project']['version'])")
echo "Version: $VERSION"

# Clean and create build directory
echo -e "\n${BLUE}📁 Setting up build environment...${NC}"
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"
mkdir -p "$PROJECT_ROOT/dist"

# First, build the app bundle using the existing script
echo -e "\n${BLUE}🏗️ Building app bundle...${NC}"
"$SCRIPT_DIR/build_pkg_installer.sh" --prepare-only || {
    print_error "Failed to prepare app bundle"
    exit 1
}

# The app bundle should now be in build_pkg/package_root
if [ ! -d "$PROJECT_ROOT/build_pkg/package_root/Applications/Skip the Podcast Desktop.app" ]; then
    print_error "App bundle not found in expected location"
    exit 1
fi

# Create Packages project file
echo -e "\n${BLUE}📄 Creating Packages project file...${NC}"
PKGPROJ_FILE="$BUILD_DIR/SkipThePodcast.pkgproj"

# Note: Using EOF without quotes to allow variable expansion
cat > "$PKGPROJ_FILE" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>PROJECT</key>
    <dict>
        <key>PACKAGE_FILES</key>
        <dict>
            <key>DEFAULT_INSTALL_LOCATION</key>
            <string>/</string>
            <key>HIERARCHY</key>
            <dict>
                <key>CHILDREN</key>
                <array>
                    <dict>
                        <key>CHILDREN</key>
                        <array/>
                        <key>GID</key>
                        <integer>80</integer>
                        <key>PATH</key>
                        <string>$PROJECT_ROOT/build_pkg/package_root/Applications</string>
                        <key>PATH_TYPE</key>
                        <integer>0</integer>
                        <key>PERMISSIONS</key>
                        <integer>509</integer>
                        <key>TYPE</key>
                        <integer>2</integer>
                        <key>UID</key>
                        <integer>0</integer>
                    </dict>
                </array>
                <key>GID</key>
                <integer>0</integer>
                <key>PATH</key>
                <string>/</string>
                <key>PATH_TYPE</key>
                <integer>0</integer>
                <key>PERMISSIONS</key>
                <integer>493</integer>
                <key>TYPE</key>
                <integer>1</integer>
                <key>UID</key>
                <integer>0</integer>
            </dict>
            <key>PAYLOAD_TYPE</key>
            <integer>0</integer>
            <key>SHOW_INVISIBLE</key>
            <false/>
            <key>SPLIT_FORKS</key>
            <true/>
            <key>TREAT_MISSING_FILES_AS_WARNING</key>
            <false/>
            <key>VERSION</key>
            <integer>5</integer>
        </dict>
        <key>PACKAGE_SCRIPTS</key>
        <dict>
            <key>POSTINSTALL_PATH</key>
            <dict>
                <key>PATH</key>
                <string>$PROJECT_ROOT/build_pkg/scripts/postinstall</string>
                <key>PATH_TYPE</key>
                <integer>0</integer>
            </dict>
            <key>PREINSTALL_PATH</key>
            <dict>
                <key>PATH</key>
                <string>$PROJECT_ROOT/build_pkg/scripts/preinstall</string>
                <key>PATH_TYPE</key>
                <integer>0</integer>
            </dict>
            <key>RESOURCES</key>
            <array/>
        </dict>
        <key>PACKAGE_SETTINGS</key>
        <dict>
            <key>AUTHENTICATION</key>
            <integer>1</integer>
            <key>CONCLUSION_ACTION</key>
            <integer>0</integer>
            <key>FOLLOW_SYMBOLIC_LINKS</key>
            <false/>
            <key>IDENTIFIER</key>
            <string>com.knowledgechipper.skipthepodcast</string>
            <key>INSTALL_LOCATION</key>
            <string>/</string>
            <key>NAME</key>
            <string>Skip the Podcast Desktop</string>
            <key>OVERWRITE_PERMISSIONS</key>
            <true/>
            <key>RELOCATABLE</key>
            <false/>
            <key>USE_HFS_COMPRESSION</key>
            <false/>
            <key>VERSION</key>
            <string>VERSION_PLACEHOLDER</string>
        </dict>
        <key>PROJECT_PRESENTATION</key>
        <dict>
            <key>BACKGROUND</key>
            <dict>
                <key>ALIGNMENT</key>
                <integer>4</integer>
                <key>BACKGROUND_PATH</key>
                <dict/>
                <key>CUSTOM</key>
                <false/>
                <key>SCALING</key>
                <integer>0</integer>
            </dict>
            <key>INSTALLATION_TYPE</key>
            <dict>
                <key>HIERARCHIES</key>
                <dict>
                    <key>INSTALLER</key>
                    <dict>
                        <key>LIST</key>
                        <array>
                            <dict>
                                <key>DESCRIPTION</key>
                                <array/>
                                <key>OPTIONS</key>
                                <dict>
                                    <key>HIDDEN</key>
                                    <false/>
                                    <key>STATE</key>
                                    <integer>1</integer>
                                </dict>
                                <key>PACKAGE_UUID</key>
                                <string>DEFAULT_PACKAGE</string>
                                <key>TITLE</key>
                                <array>
                                    <dict>
                                        <key>LANGUAGE</key>
                                        <string>English</string>
                                        <key>VALUE</key>
                                        <string>Skip the Podcast Desktop</string>
                                    </dict>
                                </array>
                                <key>TOOLTIP</key>
                                <array/>
                                <key>TYPE</key>
                                <integer>0</integer>
                                <key>UUID</key>
                                <string>COMPONENT_UUID</string>
                            </dict>
                        </array>
                    </dict>
                </dict>
                <key>MODE</key>
                <integer>0</integer>
            </dict>
            <key>INSTALLATION_STEPS</key>
            <array>
                <dict>
                    <key>ICPRESENTATION_CHAPTER_VIEW_CONTROLLER_CLASS</key>
                    <string>ICPresentationViewIntroductionController</string>
                    <key>INSTALLER_PLUGIN</key>
                    <string>Introduction</string>
                    <key>LIST_TITLE_KEY</key>
                    <string>InstallerSectionTitle</string>
                </dict>
                <dict>
                    <key>ICPRESENTATION_CHAPTER_VIEW_CONTROLLER_CLASS</key>
                    <string>ICPresentationViewLicenseController</string>
                    <key>INSTALLER_PLUGIN</key>
                    <string>License</string>
                    <key>LIST_TITLE_KEY</key>
                    <string>InstallerSectionTitle</string>
                </dict>
                <dict>
                    <key>ICPRESENTATION_CHAPTER_VIEW_CONTROLLER_CLASS</key>
                    <string>ICPresentationViewInstallationTypeController</string>
                    <key>INSTALLER_PLUGIN</key>
                    <string>InstallationType</string>
                    <key>LIST_TITLE_KEY</key>
                    <string>InstallerSectionTitle</string>
                </dict>
                <dict>
                    <key>ICPRESENTATION_CHAPTER_VIEW_CONTROLLER_CLASS</key>
                    <string>ICPresentationViewInstallationController</string>
                    <key>INSTALLER_PLUGIN</key>
                    <string>Installation</string>
                    <key>LIST_TITLE_KEY</key>
                    <string>InstallerSectionTitle</string>
                </dict>
                <dict>
                    <key>ICPRESENTATION_CHAPTER_VIEW_CONTROLLER_CLASS</key>
                    <string>ICPresentationViewSummaryController</string>
                    <key>INSTALLER_PLUGIN</key>
                    <string>Summary</string>
                    <key>LIST_TITLE_KEY</key>
                    <string>InstallerSectionTitle</string>
                </dict>
            </array>
            <key>INTRODUCTION</key>
            <dict>
                <key>LOCALIZATIONS</key>
                <array>
                    <dict>
                        <key>LANGUAGE</key>
                        <string>English</string>
                        <key>VALUE</key>
                        <dict>
                            <key>PATH</key>
                            <string>$PROJECT_ROOT/build_pkg/resources/welcome.html</string>
                            <key>PATH_TYPE</key>
                            <integer>0</integer>
                        </dict>
                    </dict>
                </array>
            </dict>
            <key>LICENSE</key>
            <dict>
                <key>KEYWORDS</key>
                <dict/>
                <key>LOCALIZATIONS</key>
                <array>
                    <dict>
                        <key>LANGUAGE</key>
                        <string>English</string>
                        <key>VALUE</key>
                        <dict>
                            <key>PATH</key>
                            <string>$PROJECT_ROOT/build_pkg/resources/license.html</string>
                            <key>PATH_TYPE</key>
                            <integer>0</integer>
                        </dict>
                    </dict>
                </array>
                <key>MODE</key>
                <integer>0</integer>
            </dict>
            <key>TITLE</key>
            <dict>
                <key>LOCALIZATIONS</key>
                <array>
                    <dict>
                        <key>LANGUAGE</key>
                        <string>English</string>
                        <key>VALUE</key>
                        <string>Skip the Podcast Desktop</string>
                    </dict>
                </array>
            </dict>
        </dict>
        <key>PROJECT_REQUIREMENTS</key>
        <dict>
            <key>LIST</key>
            <array/>
            <key>POSTINSTALL_PATH</key>
            <dict/>
            <key>PREINSTALL_PATH</key>
            <dict/>
            <key>RESOURCES</key>
            <array/>
            <key>ROOT_VOLUME_ONLY</key>
            <true/>
        </dict>
        <key>PROJECT_SETTINGS</key>
        <dict>
            <key>BUILD_PATH</key>
            <dict>
                <key>PATH</key>
                <string>$BUILD_DIR</string>
                <key>PATH_TYPE</key>
                <integer>0</integer>
            </dict>
            <key>EXCLUDED_FILES</key>
            <array>
                <dict>
                    <key>PATTERNS_ARRAY</key>
                    <array>
                        <dict>
                            <key>REGULAR_EXPRESSION</key>
                            <false/>
                            <key>STRING</key>
                            <string>.DS_Store</string>
                            <key>TYPE</key>
                            <integer>0</integer>
                        </dict>
                    </array>
                    <key>TYPE</key>
                    <integer>3</integer>
                </dict>
            </array>
            <key>NAME</key>
            <string>Skip the Podcast Desktop</string>
            <key>PACKAGE_UUID</key>
            <string>DEFAULT_PACKAGE</string>
        </dict>
    </dict>
    <key>TYPE</key>
    <integer>1</integer>
    <key>VERSION</key>
    <integer>2</integer>
</dict>
</plist>
EOF

# Update version in project file
echo -e "\n${BLUE}🔄 Updating version to $VERSION...${NC}"
/usr/libexec/PlistBuddy -c "Set :PROJECT:PACKAGE_SETTINGS:VERSION $VERSION" "$PKGPROJ_FILE"

# Build the package
echo -e "\n${BLUE}🔨 Building installer package with Packages.app...${NC}"
packagesbuild "$PKGPROJ_FILE" || {
    print_error "Package build failed"
    exit 1
}

# The output should be in the build directory
PKG_NAME="Skip the Podcast Desktop.pkg"
if [ -f "$BUILD_DIR/$PKG_NAME" ]; then
    # Move to dist directory with version
    FINAL_PKG="$PROJECT_ROOT/dist/Skip_the_Podcast_Desktop-${VERSION}.pkg"
    mv "$BUILD_DIR/$PKG_NAME" "$FINAL_PKG"
    print_status "Package built successfully"

    # Create checksum
    echo -e "\n${BLUE}🔐 Creating checksum...${NC}"
    shasum -a 256 "$FINAL_PKG" | awk '{print $1}' > "${FINAL_PKG}.sha256"
    print_status "Checksum created"

    # Clean up
    echo -e "\n${BLUE}🧹 Cleaning up...${NC}"
    rm -rf "$BUILD_DIR"
    rm -rf "$PROJECT_ROOT/build_pkg"

    echo ""
    echo -e "${GREEN}${BOLD}🎉 Packages.app Build Complete!${NC}"
    echo "=============================================="
    echo "PKG Installer: $FINAL_PKG"
    echo "PKG Size: $(du -h "$FINAL_PKG" | cut -f1)"
    echo ""
    echo "This package will:"
    echo "• Always prompt for administrator password"
    echo "• Install Skip the Podcast Desktop to /Applications"
    echo "• Run pre/post installation scripts with root privileges"
    echo ""
else
    print_error "Package not found after build"
    exit 1
fi
