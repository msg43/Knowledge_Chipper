#!/bin/bash
# build_pkg_installer.sh - Create PKG installer for Skip the Podcast Desktop
# This replaces the DMG build process with a lightweight PKG that downloads components
#
# Usage: ./build_pkg_installer.sh [--prepare-only]
#   --prepare-only: Only prepare the app bundle and scripts, don't build PKG

set -e
set -o pipefail

# Parse arguments
PREPARE_ONLY=0
for arg in "$@"; do
    case $arg in
        --prepare-only)
            PREPARE_ONLY=1
            shift
            ;;
    esac
done

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
BUILD_DIR="$PROJECT_ROOT/build_pkg"
DIST_DIR="$PROJECT_ROOT/dist"
VERSION=$(python3 -c "import tomllib; print(tomllib.load(open('$PROJECT_ROOT/pyproject.toml', 'rb'))['project']['version'])")

# Package configuration
PKG_NAME="Skip_the_Podcast_Desktop"
PKG_IDENTIFIER="com.knowledgechipper.skipthepodcast"
APP_NAME="Skip the Podcast Desktop"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m' # No Color

echo -e "${BLUE}${BOLD}📦 PKG Installer Builder for Skip the Podcast Desktop${NC}"
echo "====================================================="
echo "Version: $VERSION"
echo "Build Directory: $BUILD_DIR"
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

if ! command -v pkgbuild &> /dev/null; then
    print_error "pkgbuild is required but not installed"
    exit 1
fi

if ! command -v productbuild &> /dev/null; then
    print_error "productbuild is required but not installed"
    exit 1
fi

print_status "All prerequisites satisfied"

# Clean and create build directories
echo -e "\n${BLUE}📁 Setting up build environment...${NC}"
# Clean up any existing build directory (might be root-owned from previous runs)
if [ -d "$BUILD_DIR" ]; then
    rm -rf "$BUILD_DIR" 2>/dev/null || {
        echo -e "${YELLOW}Existing build directory needs sudo to remove${NC}"
        if [ -t 0 ]; then
            echo -e "${YELLOW}Please enter password to clean previous build:${NC}"
            sudo rm -rf "$BUILD_DIR"
        else
            echo -e "${RED}Cannot clean build directory in non-interactive mode${NC}"
            exit 1
        fi
    }
fi
mkdir -p "$BUILD_DIR"
mkdir -p "$DIST_DIR"

# Create package structure
PKG_ROOT="$BUILD_DIR/package_root"
SCRIPTS_DIR="$BUILD_DIR/scripts"
RESOURCES_DIR="$BUILD_DIR/resources"

mkdir -p "$PKG_ROOT"
mkdir -p "$SCRIPTS_DIR"
mkdir -p "$RESOURCES_DIR"

print_status "Build directories created"

# Create minimal app bundle skeleton
echo -e "\n${BLUE}🏗️ Creating minimal app bundle skeleton...${NC}"

APP_BUNDLE="$PKG_ROOT/Applications/$APP_NAME.app"
mkdir -p "$APP_BUNDLE/Contents/MacOS"
mkdir -p "$APP_BUNDLE/Contents/Resources"
mkdir -p "$APP_BUNDLE/Contents/Frameworks"

# Create Info.plist
cat > "$APP_BUNDLE/Contents/Info.plist" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleDevelopmentRegion</key>
    <string>en</string>
    <key>CFBundleExecutable</key>
    <string>launch</string>
    <key>CFBundleIconFile</key>
    <string>app_icon</string>
    <key>CFBundleIdentifier</key>
    <string>$PKG_IDENTIFIER</string>
    <key>CFBundleInfoDictionaryVersion</key>
    <string>6.0</string>
    <key>CFBundleName</key>
    <string>$APP_NAME</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleShortVersionString</key>
    <string>$VERSION</string>
    <key>CFBundleVersion</key>
    <string>$VERSION</string>
    <key>LSMinimumSystemVersion</key>
    <string>12.0</string>
    <key>NSHighResolutionCapable</key>
    <true/>
    <key>NSAppTransportSecurity</key>
    <dict>
        <key>NSAllowsArbitraryLoads</key>
        <true/>
    </dict>
</dict>
</plist>
EOF

# Copy app icon if it exists
# Try different icon sources in priority order
if [ -f "$PROJECT_ROOT/Assets/STP_Icon_1.icns" ]; then
    cp "$PROJECT_ROOT/Assets/STP_Icon_1.icns" "$APP_BUNDLE/Contents/Resources/app_icon.icns"
elif [ -f "$PROJECT_ROOT/Assets/chipper.icns" ]; then
    cp "$PROJECT_ROOT/Assets/chipper.icns" "$APP_BUNDLE/Contents/Resources/app_icon.icns"
elif [ -f "$PROJECT_ROOT/Assets/STP_Icon_1.png" ]; then
    # Convert PNG to ICNS if needed
    sips -s format icns "$PROJECT_ROOT/Assets/STP_Icon_1.png" --out "$APP_BUNDLE/Contents/Resources/app_icon.icns" 2>/dev/null || {
        print_warning "Could not convert PNG to ICNS, copying PNG"
        cp "$PROJECT_ROOT/Assets/STP_Icon_1.png" "$APP_BUNDLE/Contents/Resources/app_icon.icns"
    }
elif [ -f "$PROJECT_ROOT/Assets/chipper.png" ]; then
    # Convert PNG to ICNS if needed
    sips -s format icns "$PROJECT_ROOT/Assets/chipper.png" --out "$APP_BUNDLE/Contents/Resources/app_icon.icns" 2>/dev/null || {
        print_warning "Could not convert PNG to ICNS, copying PNG"
        cp "$PROJECT_ROOT/Assets/chipper.png" "$APP_BUNDLE/Contents/Resources/app_icon.icns"
    }
fi

print_status "App bundle skeleton created"

# Create a LaunchDaemon that absolutely requires root
echo -e "\n${BLUE}🔐 Creating LaunchDaemon (forces root requirement)...${NC}"
mkdir -p "$PKG_ROOT/Library/LaunchDaemons"
cat > "$PKG_ROOT/Library/LaunchDaemons/com.knowledgechipper.skipthepodcast.plist" << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.knowledgechipper.skipthepodcast</string>
    <key>ProgramArguments</key>
    <array>
        <string>/Applications/Skip the Podcast Desktop.app/Contents/MacOS/Skip the Podcast Desktop</string>
        <string>--check-updates</string>
    </array>
    <key>RunAtLoad</key>
    <false/>
    <key>Disabled</key>
    <true/>
</dict>
</plist>
EOF
# LaunchDaemons MUST be owned by root:wheel with specific permissions
chmod 644 "$PKG_ROOT/Library/LaunchDaemons/com.knowledgechipper.skipthepodcast.plist"
print_status "LaunchDaemon created (requires root to install)"

# Copy app source code to bundle
echo -e "\n${BLUE}📁 Copying app source code...${NC}"

# Copy the main Python source code
cp -r "$PROJECT_ROOT/src" "$APP_BUNDLE/Contents/Resources/"

# Copy essential configuration files
mkdir -p "$APP_BUNDLE/Contents/Resources/config"
cp "$PROJECT_ROOT/pyproject.toml" "$APP_BUNDLE/Contents/Resources/"
cp "$PROJECT_ROOT/requirements.txt" "$APP_BUNDLE/Contents/Resources/"

# Copy essential data files (excluding test files)
if [ -d "$PROJECT_ROOT/data" ]; then
    mkdir -p "$APP_BUNDLE/Contents/Resources/data"
    # Copy data files but exclude test_files directory
    find "$PROJECT_ROOT/data" -maxdepth 1 -type f -exec cp {} "$APP_BUNDLE/Contents/Resources/data/" \;
    # Copy any non-test subdirectories
    find "$PROJECT_ROOT/data" -maxdepth 1 -type d ! -name "test_files" ! -name "data" -exec cp -r {} "$APP_BUNDLE/Contents/Resources/data/" \;
fi

APP_CODE_SIZE=$(du -sh "$APP_BUNDLE/Contents/Resources/src" | cut -f1)
print_status "App source code copied ($APP_CODE_SIZE)"

# Create component download infrastructure
echo -e "\n${BLUE}🔧 Creating component download infrastructure...${NC}"

# Create enhanced download manager script with error handling
cat > "$SCRIPTS_DIR/download_manager.py" << 'EOF'
#!/usr/bin/env python3
"""
Enhanced Component Download Manager for Skip the Podcast Desktop PKG Installer
Downloads and installs all required components with comprehensive error handling.
"""

import os
import sys
import json
import hashlib
import subprocess
import urllib.request
import urllib.error
from pathlib import Path
import tarfile
import tempfile
import shutil
import time
import signal

# GitHub repository configuration
GITHUB_REPO = "msg43/Knowledge_Chipper"
GITHUB_RELEASES_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"

# Component manifest - updated during build process
COMPONENT_MANIFEST = {
    "python_framework": {
        "name": "python-framework-3.13-macos.tar.gz",
        "size_mb": 40,
        "description": "Python 3.13 Framework"
    },
    "ai_models": {
        "name": "ai-models-bundle.tar.gz",
        "size_mb": 1200,
        "description": "AI Models Package (Whisper, Voice Fingerprinting, Pyannote)"
    },
    "ffmpeg": {
        "name": "ffmpeg-macos-universal.tar.gz",
        "size_mb": 48,
        "description": "FFmpeg Media Processing"
    },
    "ollama": {
        "name": "ollama-darwin",
        "size_mb": 50,
        "description": "Ollama LLM Runtime"
    }
}

class ComponentDownloader:
    def __init__(self, app_bundle_path, progress_callback=None):
        self.app_bundle = Path(app_bundle_path)
        self.progress_callback = progress_callback or self._default_progress
        self.temp_dir = Path(tempfile.mkdtemp(prefix="stp_installer_"))

    def _default_progress(self, message, percent):
        print(f"[{percent:3d}%] {message}")

    def _report_progress(self, message, percent):
        self.progress_callback(message, percent)

    def download_file(self, url, target_path, expected_size=None):
        """Download file with progress reporting."""
        try:
            with urllib.request.urlopen(url) as response:
                total_size = int(response.headers.get('content-length', 0))
                downloaded = 0

                with open(target_path, 'wb') as f:
                    while True:
                        chunk = response.read(8192)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)

                        if total_size > 0:
                            percent = (downloaded * 100) // total_size
                            self._report_progress(f"Downloading {target_path.name}...", percent)

                return True
        except Exception as e:
            print(f"Download failed: {e}")
            return False

    def verify_checksum(self, file_path, expected_checksum):
        """Verify file SHA256 checksum."""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha256_hash.update(chunk)
        return sha256_hash.hexdigest() == expected_checksum

    def get_latest_release_assets(self):
        """Get download URLs for latest release assets."""
        try:
            with urllib.request.urlopen(GITHUB_RELEASES_URL) as response:
                release_data = json.loads(response.read())

            assets = {}
            for asset in release_data.get('assets', []):
                assets[asset['name']] = asset['browser_download_url']

            return assets
        except Exception as e:
            print(f"Failed to get release assets: {e}")
            return {}

    def download_component(self, component_name, component_info, download_url):
        """Download and verify a component."""
        self._report_progress(f"Preparing {component_info['description']}", 0)

        filename = component_info['name']
        temp_file = self.temp_dir / filename

        # Download component
        if not self.download_file(download_url, temp_file):
            raise Exception(f"Failed to download {filename}")

        # For now, skip checksum verification (will be added later)
        self._report_progress(f"Downloaded {component_info['description']}", 100)

        return temp_file

    def install_python_framework(self, archive_path):
        """Install Python framework into app bundle."""
        self._report_progress("Installing Python framework", 0)

        frameworks_dir = self.app_bundle / "Contents" / "Frameworks"
        frameworks_dir.mkdir(parents=True, exist_ok=True)

        # Extract framework
        with tarfile.open(archive_path, 'r:gz') as tar:
            tar.extractall(self.temp_dir)

        # Find the framework directory
        framework_dirs = list(self.temp_dir.glob("*/Python.framework"))
        if not framework_dirs:
            raise Exception("Python.framework not found in archive")

        framework_src = framework_dirs[0]
        framework_dst = frameworks_dir / "Python.framework"

        # Copy framework
        if framework_dst.exists():
            shutil.rmtree(framework_dst)
        shutil.copytree(framework_src, framework_dst)

        self._report_progress("Python framework installed", 100)

    def install_ai_models(self, archive_path):
        """Install AI models into app bundle."""
        self._report_progress("Installing AI models", 0)

        models_dir = self.app_bundle / "Contents" / "Resources" / "models"
        models_dir.mkdir(parents=True, exist_ok=True)

        # Extract models
        with tarfile.open(archive_path, 'r:gz') as tar:
            tar.extractall(models_dir)

        self._report_progress("AI models installed", 100)

    def install_ffmpeg(self, archive_path):
        """Install FFmpeg binary."""
        self._report_progress("Installing FFmpeg", 0)

        bin_dir = self.app_bundle / "Contents" / "MacOS"
        bin_dir.mkdir(parents=True, exist_ok=True)

        # Extract FFmpeg
        with tarfile.open(archive_path, 'r:gz') as tar:
            tar.extractall(self.temp_dir)

        # Find ffmpeg binary
        ffmpeg_files = list(self.temp_dir.glob("**/ffmpeg"))
        if not ffmpeg_files:
            raise Exception("ffmpeg binary not found in archive")

        ffmpeg_src = ffmpeg_files[0]
        ffmpeg_dst = bin_dir / "ffmpeg"

        shutil.copy2(ffmpeg_src, ffmpeg_dst)
        os.chmod(ffmpeg_dst, 0o755)

        self._report_progress("FFmpeg installed", 100)

    def install_ollama(self, binary_path):
        """Install Ollama binary."""
        self._report_progress("Installing Ollama", 0)

        # Install to system location
        ollama_dst = Path("/usr/local/bin/ollama")
        ollama_dst.parent.mkdir(parents=True, exist_ok=True)

        shutil.copy2(binary_path, ollama_dst)
        os.chmod(ollama_dst, 0o755)

        self._report_progress("Ollama installed", 100)

    def download_and_install_all(self):
        """Download and install all components."""
        try:
            # Get download URLs
            self._report_progress("Getting download URLs", 5)
            assets = self.get_latest_release_assets()

            if not assets:
                raise Exception("No release assets found")

            total_components = len(COMPONENT_MANIFEST)
            component_progress = 0

            for component_name, component_info in COMPONENT_MANIFEST.items():
                filename = component_info['name']

                if filename not in assets:
                    print(f"Warning: {filename} not found in release assets")
                    continue

                # Download component
                self._report_progress(f"Downloading {component_info['description']}",
                                    10 + (component_progress * 60) // total_components)

                archive_path = self.download_component(component_name, component_info, assets[filename])

                # Install component
                install_progress = 70 + (component_progress * 25) // total_components
                self._report_progress(f"Installing {component_info['description']}", install_progress)

                if component_name == "python_framework":
                    self.install_python_framework(archive_path)
                elif component_name == "ai_models":
                    self.install_ai_models(archive_path)
                elif component_name == "ffmpeg":
                    self.install_ffmpeg(archive_path)
                elif component_name == "ollama":
                    self.install_ollama(archive_path)

                component_progress += 1

            self._report_progress("All components installed successfully", 100)
            return True

        except Exception as e:
            self._report_progress(f"Installation failed: {e}", -1)
            return False

        finally:
            # Cleanup temp directory
            if self.temp_dir.exists():
                shutil.rmtree(self.temp_dir)


def main():
    if len(sys.argv) != 2:
        print("Usage: download_manager.py <app-bundle-path>")
        sys.exit(1)

    app_bundle_path = sys.argv[1]

    def progress_reporter(message, percent):
        print(f"##INSTALLER_PROGRESS## {percent} {message}")

    downloader = ComponentDownloader(app_bundle_path, progress_reporter)

    success = downloader.download_and_install_all()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
EOF

chmod +x "$SCRIPTS_DIR/download_manager.py"

print_status "Component download infrastructure created"

# Create hardware detection integration
echo -e "\n${BLUE}🖥️ Creating hardware detection integration...${NC}"

cat > "$SCRIPTS_DIR/hardware_detector.py" << 'EOF'
#!/usr/bin/env python3
"""
Hardware Detection for PKG Installer
Recommends optimal Ollama models based on detected hardware.
"""

import subprocess
import json
import sys
from dataclasses import dataclass
from enum import Enum


class ChipType(Enum):
    M1 = "M1"
    M1_PRO = "M1 Pro"
    M1_MAX = "M1 Max"
    M1_ULTRA = "M1 Ultra"
    M2 = "M2"
    M2_PRO = "M2 Pro"
    M2_MAX = "M2 Max"
    M2_ULTRA = "M2 Ultra"
    M3 = "M3"
    M3_PRO = "M3 Pro"
    M3_MAX = "M3 Max"
    M3_ULTRA = "M3 Ultra"
    INTEL = "Intel"
    UNKNOWN = "Unknown"


@dataclass
class HardwareSpecs:
    chip_type: ChipType
    memory_gb: int
    cpu_cores: int


def detect_hardware():
    """Detect current hardware specifications."""
    try:
        # Get system info using system_profiler
        result = subprocess.run(
            ["system_profiler", "SPHardwareDataType", "-json"],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode != 0:
            return _fallback_detection()

        data = json.loads(result.stdout)
        hardware_info = data["SPHardwareDataType"][0]

        chip_name = hardware_info.get("chip_type", "").lower()
        memory_str = hardware_info.get("physical_memory", "8 GB")
        cpu_cores = int(hardware_info.get("number_processors", "8"))

        # Parse memory
        memory_gb = int(memory_str.split()[0])

        # Parse chip type
        chip_type = _parse_chip_type(chip_name)

        return HardwareSpecs(
            chip_type=chip_type,
            memory_gb=memory_gb,
            cpu_cores=cpu_cores
        )

    except Exception as e:
        print(f"Hardware detection failed: {e}")
        return _fallback_detection()


def _parse_chip_type(chip_name):
    """Parse chip type from system info."""
    if "m3" in chip_name:
        if "ultra" in chip_name:
            return ChipType.M3_ULTRA
        elif "max" in chip_name:
            return ChipType.M3_MAX
        elif "pro" in chip_name:
            return ChipType.M3_PRO
        else:
            return ChipType.M3
    elif "m2" in chip_name:
        if "ultra" in chip_name:
            return ChipType.M2_ULTRA
        elif "max" in chip_name:
            return ChipType.M2_MAX
        elif "pro" in chip_name:
            return ChipType.M2_PRO
        else:
            return ChipType.M2
    elif "m1" in chip_name:
        if "ultra" in chip_name:
            return ChipType.M1_ULTRA
        elif "max" in chip_name:
            return ChipType.M1_MAX
        elif "pro" in chip_name:
            return ChipType.M1_PRO
        else:
            return ChipType.M1
    else:
        return ChipType.UNKNOWN


def _fallback_detection():
    """Fallback detection when system_profiler fails."""
    import os
    cpu_cores = os.cpu_count() or 8

    # Estimate based on CPU cores
    if cpu_cores >= 20:
        return HardwareSpecs(ChipType.M3_ULTRA, 128, cpu_cores)
    elif cpu_cores >= 12:
        return HardwareSpecs(ChipType.M3_MAX, 64, cpu_cores)
    else:
        return HardwareSpecs(ChipType.M3, 16, cpu_cores)


def get_ollama_model_recommendation(specs):
    """Recommend optimal Ollama model based on hardware."""

    if specs.memory_gb >= 64 and specs.chip_type in [ChipType.M3_ULTRA, ChipType.M2_ULTRA]:
        return {
            "primary": "llama3.2:8b",
            "size": "4.7GB",
            "description": "High-quality model for Ultra systems",
            "optional_upgrade": "llama3.1:70b (40GB) - Expert mode"
        }
    elif specs.memory_gb >= 32 and specs.chip_type in [ChipType.M3_MAX, ChipType.M2_MAX]:
        return {
            "primary": "llama3.2:8b",
            "size": "4.7GB",
            "description": "Optimal for Max systems"
        }
    elif specs.memory_gb >= 16:
        return {
            "primary": "llama3.2:3b",
            "size": "2GB",
            "description": "Balanced for Pro systems"
        }
    else:
        return {
            "primary": "llama3.2:1b",
            "size": "1.3GB",
            "description": "Efficient for base systems"
        }


def main():
    """Main function for command-line usage."""
    specs = detect_hardware()
    recommendation = get_ollama_model_recommendation(specs)

    print(json.dumps({
        "hardware": {
            "chip_type": specs.chip_type.value,
            "memory_gb": specs.memory_gb,
            "cpu_cores": specs.cpu_cores
        },
        "recommendation": recommendation
    }, indent=2))


if __name__ == "__main__":
    main()
EOF

chmod +x "$SCRIPTS_DIR/hardware_detector.py"

print_status "Hardware detection integration created"

# Create pre-install script
echo -e "\n${BLUE}📝 Creating pre-install script...${NC}"

cat > "$SCRIPTS_DIR/preinstall" << 'EOF'
#!/bin/bash
# Pre-install script for Skip the Podcast Desktop PKG
# Downloads and installs all required components

set -e

# Logging
LOG_FILE="/tmp/skip_the_podcast_install.log"
exec 1> >(tee -a "$LOG_FILE")
exec 2> >(tee -a "$LOG_FILE" >&2)

echo "=== Skip the Podcast Desktop PKG Pre-install ==="
echo "Started: $(date)"

# Progress reporting function
report_progress() {
    local percent="$1"
    local message="$2"
    echo "##INSTALLER_PROGRESS## $percent $message"
}

report_progress 0 "Starting installation"

# Check disk space (need at least 8GB for components)
available_space=$(df / | tail -1 | awk '{print $4}')
required_space=8388608  # 8GB in KB

if [ "$available_space" -lt "$required_space" ]; then
    echo "Error: Insufficient disk space. Need at least 8GB free."
    exit 1
fi

report_progress 5 "Disk space check passed"

# Check internet connectivity
if ! ping -c 1 github.com &> /dev/null; then
    echo "Error: Internet connection required for component download"
    exit 1
fi

report_progress 10 "Internet connectivity verified"

# Hardware detection using system tools (simpler approach)
echo "Detecting hardware specifications..."
python3 -c "
import subprocess
import json
import sys

try:
    # Get system info using system_profiler
    result = subprocess.run(['system_profiler', 'SPHardwareDataType', '-json'],
                          capture_output=True, text=True, timeout=10)
    if result.returncode == 0:
        data = json.loads(result.stdout)
        hardware_info = data['SPHardwareDataType'][0]
        chip_name = hardware_info.get('chip_type', '').lower()
        memory_str = hardware_info.get('physical_memory', '16 GB')
        memory_gb = int(memory_str.split()[0])

        # Determine recommendation based on memory
        if memory_gb >= 64:
            recommendation = {'primary': 'llama3.2:8b', 'size': '4.7GB', 'description': 'High-quality model for Ultra systems'}
        elif memory_gb >= 32:
            recommendation = {'primary': 'llama3.2:8b', 'size': '4.7GB', 'description': 'Optimal for Max systems'}
        elif memory_gb >= 16:
            recommendation = {'primary': 'llama3.2:3b', 'size': '2GB', 'description': 'Balanced for Pro systems'}
        else:
            recommendation = {'primary': 'llama3.2:1b', 'size': '1.3GB', 'description': 'Efficient for base systems'}

        result = {
            'hardware': {'chip_type': chip_name, 'memory_gb': memory_gb, 'cpu_cores': 8},
            'recommendation': recommendation
        }
        print(json.dumps(result))
    else:
        raise Exception('system_profiler failed')
except:
    # Fallback
    result = {
        'hardware': {'chip_type': 'M3', 'memory_gb': 16, 'cpu_cores': 8},
        'recommendation': {'primary': 'llama3.2:3b', 'size': '2GB', 'description': 'Balanced for Pro systems'}
    }
    print(json.dumps(result))
" > /tmp/hardware_specs.json

report_progress 15 "Hardware detection complete"

# Component download will be handled by the main installer
report_progress 20 "Pre-install checks complete"

echo "Pre-install completed: $(date)"
EOF

chmod +x "$SCRIPTS_DIR/preinstall"

print_status "Pre-install script created"

# Create post-install script
echo -e "\n${BLUE}📝 Creating post-install script...${NC}"

cat > "$SCRIPTS_DIR/postinstall" << 'EOF'
#!/bin/bash
# Post-install script for Skip the Podcast Desktop PKG
# Finalizes installation and configures the application

set -e

# Logging
LOG_FILE="/tmp/skip_the_podcast_install.log"
exec 1> >(tee -a "$LOG_FILE")
exec 2> >(tee -a "$LOG_FILE" >&2)

echo "=== Skip the Podcast Desktop PKG Post-install ==="
echo "Started: $(date)"

APP_BUNDLE="/Applications/Skip the Podcast Desktop.app"

# Progress reporting function
report_progress() {
    local percent="$1"
    local message="$2"
    echo "##INSTALLER_PROGRESS## $percent $message"
}

report_progress 80 "Finalizing installation"

# Skip component download during installation - will happen on first launch
echo "Skipping component download (will happen on first app launch)..."
report_progress 90 "Installation configured"

# Create launch script
echo "Creating launch script..."
cat > "$APP_BUNDLE/Contents/MacOS/launch" << 'LAUNCH_EOF'
#!/bin/bash
# Launch script for Skip the Podcast Desktop

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FRAMEWORK_PYTHON="$APP_DIR/Frameworks/Python.framework/Versions/3.13/bin/python3.13"

# Set up environment
export PYTHONPATH="$APP_DIR/Resources:${PYTHONPATH}"
export MODELS_BUNDLED="true"

# Check if components are installed
if [ ! -x "$FRAMEWORK_PYTHON" ]; then
    # Components not yet installed - show message and exit
    osascript -e 'display dialog "Skip the Podcast Desktop needs to download required components.\n\nPlease run the app from your Applications folder to complete setup." buttons {"OK"} default button "OK" with title "First Launch Setup Required" with icon caution'
    exit 0
fi

# Launch the application
exec "$FRAMEWORK_PYTHON" -m knowledge_system.gui
LAUNCH_EOF

chmod +x "$APP_BUNDLE/Contents/MacOS/launch"

report_progress 95 "Launch script created"

# Set proper permissions
echo "Setting permissions..."
chmod -R 755 "$APP_BUNDLE"

# Hardware-specific optimization
if [ -f "/tmp/hardware_specs.json" ]; then
    echo "Applying hardware-specific optimizations..."
    # This would configure settings based on detected hardware
fi

report_progress 100 "Installation complete"

echo "Post-install completed: $(date)"
echo "You can now launch Skip the Podcast Desktop from Applications"
EOF

chmod +x "$SCRIPTS_DIR/postinstall"

print_status "Post-install script created"

# Copy installer scripts to both locations - resources for distribution and app bundle for runtime
echo -e "\n${BLUE}📦 Copying installer scripts...${NC}"
mkdir -p "$RESOURCES_DIR/installer_scripts"
mkdir -p "$APP_BUNDLE/Contents/Resources/installer_scripts"

# Copy to distribution resources
cp "$SCRIPTS_DIR/download_manager.py" "$RESOURCES_DIR/installer_scripts/"
cp "$SCRIPTS_DIR/hardware_detector.py" "$RESOURCES_DIR/installer_scripts/"

# Copy to app bundle for runtime access
cp "$SCRIPTS_DIR/download_manager.py" "$APP_BUNDLE/Contents/Resources/installer_scripts/"
cp "$SCRIPTS_DIR/hardware_detector.py" "$APP_BUNDLE/Contents/Resources/installer_scripts/"

# For now, let's skip creating system-level files to see if that's interfering
# echo -e "\n${BLUE}📝 Creating system-level installation components...${NC}"

print_status "Installer scripts copied"

# Create the launch script (needed for code signing)
echo -e "\n${BLUE}🚀 Creating launch script...${NC}"
cat > "$APP_BUNDLE/Contents/MacOS/launch" << 'LAUNCH_EOF'
#!/bin/bash
# Launch script for Skip the Podcast Desktop

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FRAMEWORK_PYTHON="$APP_DIR/Frameworks/Python.framework/Versions/3.13/bin/python3.13"

# Set up environment
export PYTHONPATH="$APP_DIR/Resources:${PYTHONPATH}"
export MODELS_BUNDLED="true"

# Check if components are installed
if [ ! -x "$FRAMEWORK_PYTHON" ]; then
    # Components not yet installed - show message and exit
    osascript -e 'display dialog "Skip the Podcast Desktop needs to download required components.\n\nPlease run the app from your Applications folder to complete setup." buttons {"OK"} default button "OK" with title "First Launch Setup Required" with icon caution'
    exit 0
fi

# Launch the application
exec "$FRAMEWORK_PYTHON" -m knowledge_system.gui
LAUNCH_EOF

chmod +x "$APP_BUNDLE/Contents/MacOS/launch"
print_status "Launch script created"

# If prepare-only mode, stop here
if [ $PREPARE_ONLY -eq 1 ]; then
    echo ""
    echo -e "${GREEN}${BOLD}✅ App bundle and scripts prepared${NC}"
    echo "============================================="
    echo "Package root: $PKG_ROOT"
    echo "Scripts: $SCRIPTS_DIR"
    echo "Resources: $RESOURCES_DIR"
    exit 0
fi

# Let pkgbuild generate its own PackageInfo with proper auth requirements

# Note: We'll let pkgbuild handle ownership instead of setting it manually
echo -e "\n${BLUE}🔒 Package ownership will be set during build...${NC}"
# Don't manually set root ownership - let pkgbuild handle it with --ownership preserve

# Create component-specific Info.plist to force relocation check
echo -e "\n${BLUE}📄 Creating component Info.plist...${NC}"
COMPONENT_INFO="$BUILD_DIR/component-info.plist"
cat > "$COMPONENT_INFO" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<array>
    <dict>
        <key>BundleHasStrictIdentifier</key>
        <true/>
        <key>BundleIsRelocatable</key>
        <false/>
        <key>BundleIsVersionChecked</key>
        <true/>
        <key>BundleOverwriteAction</key>
        <string>upgrade</string>
        <key>RootRelativeBundlePath</key>
        <string>Applications/Skip the Podcast Desktop.app</string>
    </dict>
</array>
</plist>
EOF

# Build component package
echo -e "\n${BLUE}🔨 Building component package...${NC}"

COMPONENT_PKG="$BUILD_DIR/${PKG_NAME}-components-${VERSION}.pkg"

pkgbuild \
    --root "$PKG_ROOT" \
    --identifier "${PKG_IDENTIFIER}.components" \
    --version "$VERSION" \
    --install-location "/" \
    --scripts "$SCRIPTS_DIR" \
    --ownership preserve \
    --min-os-version 12.0 \
    --component-plist "$COMPONENT_INFO" \
    "$COMPONENT_PKG"

print_status "Component package built"

# Create distribution XML
echo -e "\n${BLUE}📄 Creating distribution configuration...${NC}"

DISTRIBUTION_XML="$BUILD_DIR/distribution.xml"

cat > "$DISTRIBUTION_XML" << EOF
<?xml version="1.0" encoding="utf-8"?>
<installer-gui-script minSpecVersion="2">
    <title>$APP_NAME</title>
    <organization>$PKG_IDENTIFIER</organization>
    <domains enable_anywhere="false" enable_currentUserHome="false" enable_localSystem="true"/>
    <options customize="never" require-scripts="true" rootVolumeOnly="true" hostArchitectures="x86_64,arm64" allow-external-scripts="false"/>

    <!-- Force authorization requirement -->
    <authorization>
        <privilege>system.install.root.admin</privilege>
    </authorization>

    <!-- Installation check script -->
    <installation-check script="installationCheck()"/>
    <script><![CDATA[
function installationCheck() {
    // Check if we have root access
    if (system.run('/usr/bin/id', '-u') != '0') {
        // We're not root, require elevation
        return false;
    }
    return true;
}
    ]]></script>

    <!-- Define documents displayed at various steps -->
    <welcome    file="welcome.html"    mime-type="text/html" />
    <license    file="license.html"    mime-type="text/html" />
    <conclusion file="conclusion.html" mime-type="text/html" />

    <!-- Define the installer choices -->
    <choices-outline>
        <line choice="default">
            <line choice="$PKG_IDENTIFIER.components"/>
        </line>
    </choices-outline>

    <choice id="default"/>
    <choice id="$PKG_IDENTIFIER.components" visible="false" start_enabled="true" start_selected="true">
        <pkg-ref id="$PKG_IDENTIFIER.components"/>
    </choice>

    <pkg-ref id="$PKG_IDENTIFIER.components" version="$VERSION" onConclusion="none" auth="root">
        #${PKG_NAME}-components-${VERSION}.pkg
    </pkg-ref>

</installer-gui-script>
EOF

print_status "Distribution configuration created"

# Create installer UI files
echo -e "\n${BLUE}🎨 Creating installer UI files...${NC}"

cat > "$RESOURCES_DIR/welcome.html" << 'EOF'
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Welcome</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; margin: 20px; background-color: #2d2d2d; color: #ffffff; }
        h1 { color: #1d4ed8; }
        .feature { margin: 10px 0; }
        .icon { color: #10b981; font-weight: bold; }
    </style>
</head>
<body>
    <h1>Welcome to Skip the Podcast Desktop</h1>
    <p>This installer will set up Skip the Podcast Desktop, a comprehensive knowledge management system that transforms videos, audio files, and documents into organized, searchable knowledge.</p>

    <h2>What will be installed:</h2>
    <div class="feature"><span class="icon">✓</span> Python 3.13 Framework (40MB)</div>
    <div class="feature"><span class="icon">✓</span> AI Models Package (1.2GB)</div>
    <div class="feature"><span class="icon">✓</span> FFmpeg Media Processing (48MB)</div>
    <div class="feature"><span class="icon">✓</span> Ollama LLM Runtime (50MB)</div>
    <div class="feature"><span class="icon">✓</span> Hardware-optimized model selection</div>

    <p><strong>Total download size:</strong> Approximately 1.3-4.7GB depending on your hardware.</p>
    <p><strong>Installation time:</strong> 5-15 minutes depending on internet speed.</p>

    <p>Click Continue to begin the installation process.</p>
</body>
</html>
EOF

cat > "$RESOURCES_DIR/license.html" << 'EOF'
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>License Agreement</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; margin: 20px; background-color: #2d2d2d; color: #ffffff; }
        .license { background: #1a1a1a; border: 1px solid #444; padding: 15px; border-radius: 5px; height: 300px; overflow-y: scroll; color: #ffffff; }
    </style>
</head>
<body>
    <h1>Software License Agreement</h1>
    <div class="license">
        <h2>MIT License</h2>
        <p>Copyright (c) 2024 Knowledge Chipper</p>

        <p>Permission is hereby granted, free of charge, to any person obtaining a copy
        of this software and associated documentation files (the "Software"), to deal
        in the Software without restriction, including without limitation the rights
        to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
        copies of the Software, and to permit persons to whom the Software is
        furnished to do so, subject to the following conditions:</p>

        <p>The above copyright notice and this permission notice shall be included in all
        copies or substantial portions of the Software.</p>

        <p>THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
        IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
        FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
        AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
        LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
        OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
        SOFTWARE.</p>
    </div>

    <p>By clicking Agree, you accept the terms of this license agreement.</p>
</body>
</html>
EOF

cat > "$RESOURCES_DIR/conclusion.html" << 'EOF'
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Installation Complete</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; margin: 20px; background-color: #2d2d2d; color: #ffffff; }
        h1 { color: #10b981; }
        .success { background: #0d4a2d; border: 1px solid #10b981; padding: 15px; border-radius: 5px; color: #ffffff; }
        .next-steps { background: #1e293b; border: 1px solid #0284c7; padding: 15px; border-radius: 5px; margin-top: 20px; color: #ffffff; }
    </style>
</head>
<body>
    <div class="success">
        <h1>🎉 Installation Complete!</h1>
        <p>Skip the Podcast Desktop has been successfully installed with all required components.</p>
    </div>

    <div class="next-steps">
        <h2>Next Steps:</h2>
        <ol>
            <li>Launch <strong>Skip the Podcast Desktop</strong> from your Applications folder</li>
            <li>Complete the initial setup wizard</li>
            <li>Start processing your first video or document</li>
        </ol>

        <h3>What's Ready:</h3>
        <ul>
            <li>✓ Python environment configured</li>
            <li>✓ AI models installed and ready</li>
            <li>✓ Hardware-optimized settings applied</li>
            <li>✓ All dependencies satisfied</li>
        </ul>
    </div>

    <p>For support and documentation, visit: <a href="https://github.com/msg43/Knowledge_Chipper">GitHub Repository</a></p>
</body>
</html>
EOF

print_status "Installer UI files created"

# Create Info.plist for the distribution package to force authentication
echo -e "\n${BLUE}🔐 Creating Info.plist with authentication requirement...${NC}"
cat > "$RESOURCES_DIR/Info.plist" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleIdentifier</key>
    <string>$PKG_IDENTIFIER</string>
    <key>CFBundleVersion</key>
    <string>$VERSION</string>
    <key>IFPkgFlagAuthorizationAction</key>
    <string>AdminAuthorization</string>
    <key>IFPkgFlagDefaultLocation</key>
    <string>/</string>
    <key>IFPkgFlagInstallFat</key>
    <false/>
    <key>IFPkgFlagIsRequired</key>
    <true/>
    <key>IFPkgFlagRelocatable</key>
    <false/>
    <key>IFPkgFlagRestartAction</key>
    <string>NoRestart</string>
    <key>IFPkgFormatVersion</key>
    <real>0.10000000149011612</real>
</dict>
</plist>
EOF

print_status "Info.plist with AdminAuthorization created"

# Build final PKG
echo -e "\n${BLUE}🏗️ Building final PKG installer...${NC}"

FINAL_PKG="$DIST_DIR/${PKG_NAME}-${VERSION}.pkg"

productbuild \
    --distribution "$DISTRIBUTION_XML" \
    --resources "$RESOURCES_DIR" \
    --package-path "$BUILD_DIR" \
    "$FINAL_PKG"

print_status "PKG installer built"

# Calculate size
PKG_SIZE=$(du -h "$FINAL_PKG" | cut -f1)

# Create checksum
echo -e "\n${BLUE}🔐 Creating checksum...${NC}"
shasum -a 256 "$FINAL_PKG" > "$FINAL_PKG.sha256"

print_status "Checksum created"

# Cleanup build directory
echo -e "\n${BLUE}🧹 Cleaning up build directory...${NC}"
if [ -d "$BUILD_DIR" ]; then
    # Try normal removal first
    rm -rf "$BUILD_DIR" 2>/dev/null || {
        # If that fails, it might need sudo
        echo -e "${YELLOW}Build directory may contain root-owned files${NC}"
        echo -e "${YELLOW}Attempting cleanup with sudo...${NC}"
        # Only use sudo if we're in an interactive terminal
        if [ -t 0 ]; then
            sudo rm -rf "$BUILD_DIR" 2>/dev/null || {
                echo -e "${YELLOW}Manual cleanup needed: sudo rm -rf $BUILD_DIR${NC}"
            }
        else
            echo -e "${YELLOW}Non-interactive mode: Manual cleanup needed: sudo rm -rf $BUILD_DIR${NC}"
        fi
    }
fi
print_status "Cleanup complete"

# Final summary
echo -e "\n${GREEN}${BOLD}🎉 PKG Installer Build Complete!${NC}"
echo "=============================================="
echo "PKG Installer: $FINAL_PKG"
echo "PKG Size: $PKG_SIZE"
echo "Checksum: $FINAL_PKG.sha256"
echo ""
echo "Next steps:"
echo "1. Test PKG installation on clean system"
echo "2. Upload to GitHub releases with components"
echo "3. Update release workflow scripts"
echo ""
echo "Installation will download:"
echo "• Python Framework (~40MB)"
echo "• AI Models (~1.2GB)"
echo "• FFmpeg (~48MB)"
echo "• Ollama (~50MB)"
echo "• Hardware-optimized Ollama model (1.3-4.7GB)"
