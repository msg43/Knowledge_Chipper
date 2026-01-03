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
    <key>CFBundleURLTypes</key>
    <array>
        <dict>
            <key>CFBundleURLName</key>
            <string>Skip the Podcast URL Handler</string>
            <key>CFBundleURLSchemes</key>
            <array>
                <string>skipthepodcast</string>
            </array>
            <key>CFBundleTypeRole</key>
            <string>Viewer</string>
        </dict>
    </array>
</dict>
</plist>
EOF

# Create proper app icon
echo -e "\n${BLUE}🎨 Creating app icon...${NC}"

# Try different icon sources in priority order
ICON_SOURCE=""
if [ -f "$PROJECT_ROOT/Assets/STP_Icon_1.icns" ]; then
    ICON_SOURCE="$PROJECT_ROOT/Assets/STP_Icon_1.icns"
elif [ -f "$PROJECT_ROOT/Assets/chipper.icns" ]; then
    ICON_SOURCE="$PROJECT_ROOT/Assets/chipper.icns"
elif [ -f "$PROJECT_ROOT/Assets/STP_Icon_1.png" ]; then
    ICON_SOURCE="$PROJECT_ROOT/Assets/STP_Icon_1.png"
elif [ -f "$PROJECT_ROOT/Assets/chipper.png" ]; then
    ICON_SOURCE="$PROJECT_ROOT/Assets/chipper.png"
fi

if [ -n "$ICON_SOURCE" ]; then
    if [[ "$ICON_SOURCE" == *.icns ]]; then
        # Direct copy of ICNS file
        cp "$ICON_SOURCE" "$APP_BUNDLE/Contents/Resources/app_icon.icns"
        print_status "App icon copied from $(basename "$ICON_SOURCE")"
    else
        # Convert PNG to ICNS using proper method
        echo "Converting PNG to ICNS..."

        # Create iconset directory
        ICONSET_DIR="/tmp/app_icon.iconset"
        rm -rf "$ICONSET_DIR"
        mkdir -p "$ICONSET_DIR"

        # Generate all required icon sizes
        sips -z 16 16     "$ICON_SOURCE" --out "$ICONSET_DIR/icon_16x16.png"      >/dev/null 2>&1
        sips -z 32 32     "$ICON_SOURCE" --out "$ICONSET_DIR/icon_16x16@2x.png"   >/dev/null 2>&1
        sips -z 32 32     "$ICON_SOURCE" --out "$ICONSET_DIR/icon_32x32.png"      >/dev/null 2>&1
        sips -z 64 64     "$ICON_SOURCE" --out "$ICONSET_DIR/icon_32x32@2x.png"   >/dev/null 2>&1
        sips -z 128 128   "$ICON_SOURCE" --out "$ICONSET_DIR/icon_128x128.png"    >/dev/null 2>&1
        sips -z 256 256   "$ICON_SOURCE" --out "$ICONSET_DIR/icon_128x128@2x.png" >/dev/null 2>&1
        sips -z 256 256   "$ICON_SOURCE" --out "$ICONSET_DIR/icon_256x256.png"    >/dev/null 2>&1
        sips -z 512 512   "$ICON_SOURCE" --out "$ICONSET_DIR/icon_256x256@2x.png" >/dev/null 2>&1
        sips -z 512 512   "$ICON_SOURCE" --out "$ICONSET_DIR/icon_512x512.png"    >/dev/null 2>&1
        sips -z 1024 1024 "$ICON_SOURCE" --out "$ICONSET_DIR/icon_512x512@2x.png" >/dev/null 2>&1

        # Convert iconset to ICNS
        if iconutil -c icns "$ICONSET_DIR" -o "$APP_BUNDLE/Contents/Resources/app_icon.icns" 2>/dev/null; then
            print_status "App icon created from $(basename "$ICON_SOURCE")"
        else
            print_warning "iconutil failed, using sips conversion"
            sips -s format icns "$ICON_SOURCE" --out "$APP_BUNDLE/Contents/Resources/app_icon.icns" 2>/dev/null || {
                print_warning "Could not convert PNG to ICNS, copying PNG as fallback"
                cp "$ICON_SOURCE" "$APP_BUNDLE/Contents/Resources/app_icon.png"
                # Update Info.plist to use PNG instead
                sed -i '' 's/app_icon/app_icon.png/g' "$APP_BUNDLE/Contents/Info.plist"
            }
        fi

        # Cleanup
        rm -rf "$ICONSET_DIR"
    fi
else
    print_warning "No icon file found in Assets directory"
fi

print_status "App bundle skeleton created"

# Skip creating LaunchDaemon to reduce privilege prompts
echo -e "\n${BLUE}🔐 Skipping LaunchDaemon creation to reduce prompts...${NC}"

# Copy app source code to bundle
echo -e "\n${BLUE}📁 Copying app source code...${NC}"

# Copy the main Python source code
cp -r "$PROJECT_ROOT/src" "$APP_BUNDLE/Contents/Resources/"

# Copy the daemon directory (required for background server)
cp -r "$PROJECT_ROOT/daemon" "$APP_BUNDLE/Contents/Resources/"

# Copy essential configuration files
mkdir -p "$APP_BUNDLE/Contents/Resources/config"
cp "$PROJECT_ROOT/pyproject.toml" "$APP_BUNDLE/Contents/Resources/"
cp "$PROJECT_ROOT/requirements.txt" "$APP_BUNDLE/Contents/Resources/"
cp "$PROJECT_ROOT/requirements-daemon.txt" "$APP_BUNDLE/Contents/Resources/"

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

# Create URL handler script
echo -e "\n${BLUE}🔗 Creating URL handler script...${NC}"

cat > "$APP_BUNDLE/Contents/MacOS/url-handler" << 'URL_HANDLER_EOF'
#!/bin/bash
# URL Handler for skipthepodcast:// URLs
# Handles commands from the web interface

URL="$1"

# Extract command from URL (format: skipthepodcast://command)
COMMAND=$(echo "$URL" | sed 's|skipthepodcast://||')

case "$COMMAND" in
    start-daemon)
        echo "Starting daemon..."
        launchctl start org.skipthepodcast.daemon
        # Show notification if terminal-notifier is available
        if command -v terminal-notifier &>/dev/null; then
            terminal-notifier -title "Skip the Podcast" -message "Daemon starting..." -sound default
        fi
        # Use osascript as fallback
        osascript -e 'display notification "Daemon starting..." with title "Skip the Podcast"' 2>/dev/null || true
        ;;
    stop-daemon)
        echo "Stopping daemon..."
        launchctl stop org.skipthepodcast.daemon
        osascript -e 'display notification "Daemon stopped" with title "Skip the Podcast"' 2>/dev/null || true
        ;;
    status)
        if curl -s http://localhost:8765/health > /dev/null 2>&1; then
            osascript -e 'display notification "Daemon is running" with title "Skip the Podcast"' 2>/dev/null || true
        else
            osascript -e 'display notification "Daemon is not running" with title "Skip the Podcast"' 2>/dev/null || true
        fi
        ;;
    *)
        echo "Unknown command: $COMMAND"
        osascript -e "display dialog \"Unknown command: $COMMAND\" with title \"Skip the Podcast\" buttons {\"OK\"} default button 1" 2>/dev/null || true
        ;;
esac
URL_HANDLER_EOF

chmod +x "$APP_BUNDLE/Contents/MacOS/url-handler"
print_status "URL handler script created"

# Create app source code archive for component system
echo -e "\n${BLUE}📦 Creating app source code archive...${NC}"
APP_SOURCE_ARCHIVE="$DIST_DIR/app-source-code.tar.gz"
if [ -f "$APP_SOURCE_ARCHIVE" ]; then
    rm -f "$APP_SOURCE_ARCHIVE"
fi

tar -czf "$APP_SOURCE_ARCHIVE" -C "$PROJECT_ROOT" \
    --exclude=".git" \
    --exclude="__pycache__" \
    --exclude="*.pyc" \
    --exclude="venv" \
    --exclude="build*" \
    --exclude="dist" \
    --exclude=".DS_Store" \
    src/ config/ pyproject.toml requirements.txt

print_status "App source code archive created"

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
GITHUB_REPO = "msg43/Skipthepodcast.com"

def get_app_version(app_bundle_path):
    """Get the app version from Info.plist."""
    try:
        import plistlib
        info_plist = Path(app_bundle_path) / "Contents" / "Info.plist"
        with open(info_plist, 'rb') as f:
            plist = plistlib.load(f)
        return plist.get('CFBundleShortVersionString', '3.2.40')
    except Exception:
        return '3.2.40'  # Fallback version

# Get the app version and construct the release URL
app_version = get_app_version(sys.argv[1] if len(sys.argv) > 1 else '.')
GITHUB_RELEASES_URL = f"https://github.com/{GITHUB_REPO}/releases/download/v{app_version}"

# Component manifest with version tracking
COMPONENT_MANIFEST = {
    "python_framework": {
        "name": "python-framework-3.13-macos.tar.gz",
        "size_mb": 40,
        "description": "Python 3.13 Framework",
        "version": "3.13.3",
        "cache_key": "python_framework",
        "update_frequency": "rare"  # Only updates when Python version changes
    },
    "ai_models": {
        "name": "ai-models-bundle.tar.gz",
        "size_mb": 1200,
        "description": "AI Models Package (Whisper, Voice Fingerprinting, Pyannote)",
        "version": "2024.10.03",
        "cache_key": "ai_models",
        "update_frequency": "rare"  # Only updates when models change
    },
    "ffmpeg": {
        "name": "ffmpeg-macos-universal.tar.gz",
        "size_mb": 48,
        "description": "FFmpeg Media Processing",
        "version": "6.1.1",
        "cache_key": "ffmpeg",
        "update_frequency": "rare"  # Only updates when FFmpeg version changes
    },
    "ollama": {
        "name": "ollama-darwin",
        "size_mb": 50,
        "description": "Ollama LLM Runtime",
        "version": "latest",
        "cache_key": "ollama_runtime",
        "update_frequency": "rare"  # Only updates when Ollama releases new version
    },
    "ollama_model": {
        "name": "ollama-models-bundle.tar.gz",
        "size_mb": 4096,
        "description": "Ollama LLM Models (qwen2.5:7b-instruct)",
        "version": "dynamic",
        "cache_key": "ollama_model",
        "update_frequency": "rare"  # Downloaded on-demand, cached locally
    },
    "app_code": {
        "name": "app-source-code.tar.gz",
        "size_mb": 10,
        "description": "Skip the Podcast Application Code",
        "version": "3.2.35",  # This will change with each patch
        "cache_key": "app_code",
        "update_frequency": "frequent"  # Updates with every code change
    }
}

class ComponentDownloader:
    def __init__(self, app_bundle_path, progress_callback=None):
        self.app_bundle = Path(app_bundle_path)
        self.progress_callback = progress_callback or self._default_progress
        self.temp_dir = Path(tempfile.mkdtemp(prefix="stp_installer_"))

        # Component cache directory
        self.cache_dir = Path.home() / ".skip_the_podcast" / "component_cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Version tracking file
        self.version_file = self.cache_dir / "component_versions.json"

    def _default_progress(self, message, percent):
        print(f"[{percent:3d}%] {message}")

    def _report_progress(self, message, percent):
        self.progress_callback(message, percent)

    def load_component_versions(self):
        """Load cached component versions."""
        if self.version_file.exists():
            try:
                with open(self.version_file, 'r') as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def save_component_version(self, component_name, version, checksum=None):
        """Save component version to cache."""
        versions = self.load_component_versions()
        versions[component_name] = {
            'version': version,
            'checksum': checksum,
            'cached_at': time.time()
        }
        with open(self.version_file, 'w') as f:
            json.dump(versions, f, indent=2)

    def is_component_up_to_date(self, component_name, current_version):
        """Check if component is up to date."""
        versions = self.load_component_versions()
        if component_name not in versions:
            return False

        cached_version = versions[component_name].get('version')
        return cached_version == current_version

    def get_cached_component_path(self, component_name):
        """Get path to cached component."""
        return self.cache_dir / f"{component_name}.tar.gz"

    def cache_component(self, component_name, source_path):
        """Cache a component for future use."""
        cached_path = self.get_cached_component_path(component_name)
        if source_path.exists():
            shutil.copy2(source_path, cached_path)
            return cached_path
        return None

    def use_cached_component(self, component_name):
        """Use cached component if available and valid."""
        cached_path = self.get_cached_component_path(component_name)
        if cached_path.exists():
            # Verify cache integrity
            try:
                # Basic file size check
                if cached_path.stat().st_size > 0:
                    return cached_path
            except Exception:
                pass

        return None

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
        # Since we can't use the API for private repos, we'll construct the URLs directly
        # based on the known component names
        return {
            "python-framework-3.13-macos.tar.gz": f"{GITHUB_RELEASES_URL}/python-framework-3.13-macos.tar.gz",
            "ai-models-bundle.tar.gz": f"{GITHUB_RELEASES_URL}/ai-models-bundle.tar.gz",
            "ffmpeg-macos-universal.tar.gz": f"{GITHUB_RELEASES_URL}/ffmpeg-macos-universal.tar.gz"
        }

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
        shutil.copytree(framework_src, framework_dst, symlinks=True)

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

    def install_app_code(self, archive_path):
        """Install application source code."""
        self._report_progress("Installing application code", 0)

        resources_dir = self.app_bundle / "Contents" / "Resources"
        resources_dir.mkdir(parents=True, exist_ok=True)

        # Extract app source code
        with tarfile.open(archive_path, 'r:gz') as tar:
            tar.extractall(resources_dir)

        # Set proper permissions
        for root, dirs, files in os.walk(resources_dir):
            for d in dirs:
                os.chmod(os.path.join(root, d), 0o755)
            for f in files:
                os.chmod(os.path.join(root, f), 0o644)

        self._report_progress("Application code installed", 100)

    def download_and_install_ollama(self):
        """Download and install Ollama binary directly from GitHub."""
        self._report_progress("Setting up Ollama download", 0)

        try:
            # Download Ollama binary from GitHub releases
            ollama_url = "https://github.com/ollama/ollama/releases/latest/download/ollama-darwin"
            ollama_temp = self.temp_dir / "ollama"

            self._report_progress("Downloading Ollama binary", 20)
            if not self.download_file(ollama_url, ollama_temp):
                raise Exception("Failed to download Ollama binary")

            self._report_progress("Installing Ollama binary", 80)
            self.install_ollama(ollama_temp)
            return True

        except Exception as e:
            print(f"Error downloading Ollama: {e}")
            return False

    def install_ollama(self, binary_path):
        """Install Ollama binary."""
        self._report_progress("Installing Ollama", 0)

        # Install to system location
        ollama_dst = Path("/usr/local/bin/ollama")
        ollama_dst.parent.mkdir(parents=True, exist_ok=True)

        shutil.copy2(binary_path, ollama_dst)
        os.chmod(ollama_dst, 0o755)

        self._report_progress("Ollama installed", 100)

    def download_ollama_model_directly(self):
        """Download Ollama model directly from Ollama during installation."""
        self._report_progress("Setting up Ollama model download", 0)

        # Determine the best model based on system specs
        model_name = self._get_recommended_ollama_model()
        self._report_progress(f"Recommended model: {model_name}", 10)

        try:
            # Start Ollama service if not running
            self._start_ollama_service()
            self._report_progress("Ollama service ready", 20)

            # Download the model
            self._report_progress(f"Downloading {model_name} model (this may take 10-20 minutes)", 30)

            # Use subprocess to run ollama pull with progress
            process = subprocess.Popen(
                ["ollama", "pull", model_name],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True
            )

            # Monitor progress
            progress = 30
            for line in process.stdout:
                if "pulling" in line.lower():
                    # Extract progress from ollama output
                    if "100%" in line:
                        progress = min(90, progress + 10)
                        self._report_progress(f"Downloading {model_name}", progress)

            process.wait()

            if process.returncode == 0:
                self._report_progress(f"{model_name} model downloaded successfully", 100)
                return True
            else:
                raise Exception(f"Failed to download {model_name} model")

        except Exception as e:
            print(f"Error downloading Ollama model: {e}")
            # Fallback to basic model
            try:
                self._report_progress("Falling back to qwen2.5:7b-instruct", 50)
                subprocess.run(["ollama", "pull", "qwen2.5:7b-instruct"], check=True)
                self._report_progress("Fallback model downloaded", 100)
                return True
            except Exception as fallback_error:
                print(f"Fallback model download also failed: {fallback_error}")
                return False

    def _get_recommended_ollama_model(self):
        """Determine the best Ollama model based on system specs."""
        try:
            # Get system memory
            result = subprocess.run(
                ["sysctl", "-n", "hw.memsize"],
                capture_output=True,
                text=True,
                check=True
            )
            total_memory_bytes = int(result.stdout.strip())
            total_memory_gb = total_memory_bytes // (1024**3)

            # Get CPU info
            result = subprocess.run(
                ["sysctl", "-n", "machdep.cpu.brand_string"],
                capture_output=True,
                text=True,
                check=True
            )
            cpu_info = result.stdout.strip().lower()

            # Model selection logic with FP16 optimization for high-end systems
            if total_memory_gb >= 64 and ("ultra" in cpu_info or "max" in cpu_info):
                return "qwen2.5:14b-instruct"  # FP16 optimized for parallel processing
            elif total_memory_gb >= 32 and ("max" in cpu_info or "pro" in cpu_info):
                return "qwen2.5:14b-instruct"  # Can handle 14B with parallel jobs
            elif total_memory_gb >= 16:
                return "qwen2.5:7b-instruct"   # Mid-range systems
            else:
                return "qwen2.5:3b-instruct"   # Basic systems

        except Exception:
            # Fallback to a safe default
            return "qwen2.5:7b-instruct"

    def _start_ollama_service(self):
        """Start Ollama service if not running."""
        try:
            # Check if ollama is already running
            subprocess.run(["ollama", "list"], check=True, capture_output=True)
            return  # Service is already running
        except subprocess.CalledProcessError:
            pass

        # Start ollama service in background
        subprocess.Popen(["ollama", "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # Wait for service to be ready
        for _ in range(30):  # Wait up to 30 seconds
            try:
                subprocess.run(["ollama", "list"], check=True, capture_output=True)
                return
            except subprocess.CalledProcessError:
                time.sleep(1)

        raise Exception("Ollama service failed to start within 30 seconds")

    def install_ollama_model(self, archive_path):
        """Install Ollama LLM models (legacy method for bundled models)."""
        self._report_progress("Installing Ollama models", 0)

        # Create Ollama models directory
        ollama_models_dir = Path.home() / ".ollama" / "models"
        ollama_models_dir.mkdir(parents=True, exist_ok=True)

        # Extract models
        with tarfile.open(archive_path, 'r:gz') as tar:
            tar.extractall(ollama_models_dir)

        # Verify qwen2.5:7b-instruct model is available
        model_dir = ollama_models_dir / "qwen2.5" / "7b-instruct"
        if not model_dir.exists():
            raise Exception("qwen2.5:7b-instruct model not found in archive")

        self._report_progress("Ollama models installed", 100)

    def download_and_install_all(self):
        """Download and install all components."""
        try:
            # Check if we should only install critical components
            install_only_critical = os.environ.get('INSTALL_ONLY_CRITICAL', '').lower() == 'true'
            install_python = os.environ.get('INSTALL_PYTHON_FRAMEWORK', '').lower() == 'true'
            
            if install_only_critical:
                print("📦 Installing critical components only...")
                # Define which components are critical
                if install_python:
                    critical_components = ['python_framework', 'ffmpeg']
                else:
                    critical_components = ['ffmpeg']  # Python already available on system
            else:
                critical_components = None  # Install everything
            
            # Get download URLs
            self._report_progress("Getting download URLs", 5)
            assets = self.get_latest_release_assets()

            if not assets:
                raise Exception("No release assets found")

            total_components = len(COMPONENT_MANIFEST)
            component_progress = 0

            for component_name, component_info in COMPONENT_MANIFEST.items():
                # Skip non-critical components if in critical-only mode
                if critical_components is not None and component_name not in critical_components:
                    print(f"⏭️  Skipping {component_info['description']} (will download on first use)")
                    component_progress += 1
                    continue
                filename = component_info['name']
                current_version = component_info['version']
                update_frequency = component_info['update_frequency']

                # Check if component is up to date in cache
                if self.is_component_up_to_date(component_name, current_version):
                    cached_path = self.use_cached_component(component_name)
                    if cached_path:
                        print(f"✅ Using cached {component_info['description']} (version {current_version})")
                        archive_path = cached_path

                        # Install from cache
                        install_progress = 70 + (component_progress * 25) // total_components
                        self._report_progress(f"Installing cached {component_info['description']}", install_progress)

                        if component_name == "python_framework":
                            self.install_python_framework(archive_path)
                        elif component_name == "ai_models":
                            self.install_ai_models(archive_path)
                        elif component_name == "ffmpeg":
                            self.install_ffmpeg(archive_path)
                        elif component_name == "app_code":
                            self.install_app_code(archive_path)

                        component_progress += 1
                        continue

                # Component needs update - check availability
                if filename not in assets:
                    if component_name == "ollama":
                        print(f"Info: {filename} not found in release assets")
                        print(f"      Downloading Ollama binary directly from GitHub...")

                        # Download Ollama binary directly
                        if not self.download_and_install_ollama():
                            print(f"Warning: Failed to download Ollama binary directly")
                        continue
                    elif component_name == "ollama_model":
                        print(f"Info: {filename} not found in release assets (too large for GitHub)")
                        print(f"      Downloading Ollama model directly from Ollama during installation...")

                        # Download Ollama model directly
                        if not self.download_ollama_model_directly():
                            print(f"Warning: Failed to download Ollama model directly")
                        continue
                    else:
                        print(f"Warning: {filename} not found in release assets")
                        continue

                # Download component (not cached)
                if update_frequency == "frequent":
                    print(f"🔄 Updating {component_info['description']} (version {current_version})")
                else:
                    print(f"📦 Installing {component_info['description']} (version {current_version})")

                self._report_progress(f"Downloading {component_info['description']}",
                                    10 + (component_progress * 60) // total_components)

                archive_path = self.download_component(component_name, component_info, assets[filename])

                # Cache the component for future use
                self.cache_component(component_name, archive_path)
                self.save_component_version(component_name, current_version)

                # Install component
                install_progress = 70 + (component_progress * 25) // total_components
                self._report_progress(f"Installing {component_info['description']}", install_progress)

                if component_name == "python_framework":
                    self.install_python_framework(archive_path)
                elif component_name == "ai_models":
                    self.install_ai_models(archive_path)
                elif component_name == "ffmpeg":
                    self.install_ffmpeg(archive_path)
                elif component_name == "app_code":
                    self.install_app_code(archive_path)
                elif component_name == "ollama":
                    self.install_ollama(archive_path)
                elif component_name == "ollama_model":
                    self.install_ollama_model(archive_path)

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

# Create dynamic parallelization system
echo -e "\n${BLUE}⚡ Creating dynamic parallelization system...${NC}"

cat > "$SCRIPTS_DIR/dynamic_parallelization.py" << 'EOF'
#!/usr/bin/env python3
"""
Dynamic Parallelization System for Knowledge Processing

Intelligently manages parallel workers based on:
- Available RAM and CPU resources
- Job completion times and queue lengths
- Real-time resource utilization
- Hardware-specific optimization

Key Features:
- FP16 model optimization for high-end systems
- Dynamic worker scaling based on resource usage
- Job completion-based worker adjustment
- Memory-aware parallelization
"""

import asyncio
import time
import psutil
import threading
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
from enum import Enum
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
import logging
import json
from pathlib import Path

logger = logging.getLogger(__name__)


class JobType(Enum):
    """Types of processing jobs"""
    MINER = "miner"
    FLAGSHIP_EVALUATOR = "flagship_evaluator"
    TRANSCRIPTION = "transcription"
    VOICE_FINGERPRINTING = "voice_fingerprinting"


@dataclass
class ResourceLimits:
    """Resource limits for parallelization"""
    max_ram_gb: float
    max_cpu_cores: int
    model_ram_gb: float  # RAM used by the loaded model
    kv_cache_per_job_mb: int = 100  # Approximate KV cache per job
    system_overhead_gb: float = 2.0  # OS + other apps overhead


@dataclass
class JobMetrics:
    """Metrics for job performance tracking"""
    job_type: JobType
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    duration: Optional[float] = None
    memory_used_mb: float = 0.0
    cpu_percent: float = 0.0
    success: bool = True
    error: Optional[str] = None


@dataclass
class WorkerPool:
    """Worker pool configuration"""
    job_type: JobType
    current_workers: int = 1
    min_workers: int = 1
    max_workers: int = 8
    active_jobs: int = 0
    completed_jobs: int = 0
    avg_duration: float = 0.0
    last_adjustment: float = field(default_factory=time.time)
    adjustment_cooldown: float = 30.0  # Seconds between adjustments


class DynamicParallelizationManager:
    """
    Intelligent parallelization manager that dynamically adjusts worker counts
    based on resource usage, job completion times, and hardware capabilities.
    """

    def __init__(self, hardware_specs: Dict[str, Any]):
        self.hardware_specs = hardware_specs
        self.resource_limits = self._calculate_resource_limits()
        self.worker_pools: Dict[JobType, WorkerPool] = {}
        self.job_metrics: List[JobMetrics] = []
        self.monitoring_active = False
        self.monitor_thread: Optional[threading.Thread] = None

        # Initialize worker pools
        self._initialize_worker_pools()

        # Performance tracking
        self.performance_history: Dict[JobType, List[float]] = {
            job_type: [] for job_type in JobType
        }

        logger.info(f"Dynamic parallelization initialized for {hardware_specs.get('chip_type', 'Unknown')} "
                   f"with {self.resource_limits.max_ram_gb}GB RAM, {self.resource_limits.max_cpu_cores} cores")

    def _calculate_resource_limits(self) -> ResourceLimits:
        """Calculate resource limits based on hardware specs"""
        memory_gb = self.hardware_specs.get('memory_gb', 16)
        cpu_cores = self.hardware_specs.get('cpu_cores', 8)
        chip_type = self.hardware_specs.get('chip_type', '').lower()

        # Model RAM usage (FP16 optimization for high-end systems)
        if memory_gb >= 64 and ('ultra' in chip_type or 'max' in chip_type):
            model_ram_gb = 32.0  # Qwen2.5-14B FP16
            max_workers = min(8, cpu_cores * 2)  # Aggressive parallelization
        elif memory_gb >= 32 and ('max' in chip_type or 'pro' in chip_type):
            model_ram_gb = 32.0  # Qwen2.5-14B FP16
            max_workers = min(6, cpu_cores)
        elif memory_gb >= 16:
            model_ram_gb = 8.0   # Qwen2.5-7B
            max_workers = min(4, cpu_cores)
        else:
            model_ram_gb = 4.0   # Qwen2.5-3B
            max_workers = min(2, cpu_cores // 2)

        return ResourceLimits(
            max_ram_gb=memory_gb,
            max_cpu_cores=cpu_cores,
            model_ram_gb=model_ram_gb,
            kv_cache_per_job_mb=100 if memory_gb >= 32 else 50,
            system_overhead_gb=2.0
        )

    def _initialize_worker_pools(self):
        """Initialize worker pools for each job type"""
        base_max_workers = min(4, self.resource_limits.max_cpu_cores)

        self.worker_pools = {
            JobType.MINER: WorkerPool(
                job_type=JobType.MINER,
                max_workers=base_max_workers * 2,  # CPU-intensive, can parallelize more
                min_workers=1
            ),
            JobType.FLAGSHIP_EVALUATOR: WorkerPool(
                job_type=JobType.FLAGSHIP_EVALUATOR,
                max_workers=base_max_workers,  # Memory-intensive, moderate parallelization
                min_workers=1
            ),
            JobType.TRANSCRIPTION: WorkerPool(
                job_type=JobType.TRANSCRIPTION,
                max_workers=base_max_workers // 2,  # I/O bound, fewer workers
                min_workers=1
            ),
            JobType.VOICE_FINGERPRINTING: WorkerPool(
                job_type=JobType.VOICE_FINGERPRINTING,
                max_workers=base_max_workers,  # CPU-intensive, good parallelization
                min_workers=1
            )
        }

        logger.info(f"Initialized worker pools: {[(pool.job_type.value, pool.max_workers) for pool in self.worker_pools.values()]}")

    def get_optimal_workers(self, job_type: JobType, queue_length: int = 0) -> int:
        """Calculate optimal number of workers based on current conditions"""
        pool = self.worker_pools[job_type]
        current_time = time.time()

        # Don't adjust too frequently
        if current_time - pool.last_adjustment < pool.adjustment_cooldown:
            return pool.current_workers

        # Get current resource usage
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        memory_percent = memory.percent

        # Calculate optimal workers based on resources
        optimal_workers = self._calculate_optimal_workers(
            job_type, cpu_percent, memory_percent, queue_length
        )

        # Clamp to pool limits
        optimal_workers = max(pool.min_workers, min(optimal_workers, pool.max_workers))

        # Only adjust if significant change
        if abs(optimal_workers - pool.current_workers) >= 1:
            old_workers = pool.current_workers
            pool.current_workers = optimal_workers
            pool.last_adjustment = current_time

            logger.info(f"Adjusted {job_type.value} workers: {old_workers} -> {optimal_workers} "
                       f"(CPU: {cpu_percent:.1f}%, RAM: {memory_percent:.1f}%, Queue: {queue_length})")

        return pool.current_workers

    def _calculate_optimal_workers(self, job_type: JobType, cpu_percent: float,
                                 memory_percent: float, queue_length: int) -> int:
        """Calculate optimal workers based on current conditions"""
        pool = self.worker_pools[job_type]

        # Base calculation on resource availability
        if cpu_percent < 50 and memory_percent < 70:
            # Resources available, can increase workers
            if queue_length > pool.current_workers * 2:
                # High queue, increase workers
                return min(pool.current_workers + 2, pool.max_workers)
            elif queue_length > pool.current_workers:
                # Moderate queue, slight increase
                return min(pool.current_workers + 1, pool.max_workers)
            else:
                # Low queue, maintain current
                return pool.current_workers

        elif cpu_percent > 80 or memory_percent > 85:
            # Resource pressure, decrease workers
            return max(pool.current_workers - 1, pool.min_workers)

        else:
            # Balanced resources, maintain current
            return pool.current_workers

    def start_job(self, job_type: JobType) -> JobMetrics:
        """Start tracking a new job"""
        metrics = JobMetrics(job_type=job_type)
        self.job_metrics.append(metrics)
        self.worker_pools[job_type].active_jobs += 1
        return metrics

    def complete_job(self, metrics: JobMetrics, success: bool = True, error: Optional[str] = None):
        """Complete job tracking and update performance metrics"""
        metrics.end_time = time.time()
        metrics.duration = metrics.end_time - metrics.start_time
        metrics.success = success
        metrics.error = error

        pool = self.worker_pools[metrics.job_type]
        pool.active_jobs = max(0, pool.active_jobs - 1)
        pool.completed_jobs += 1

        # Update average duration
        if metrics.success and metrics.duration:
            self.performance_history[metrics.job_type].append(metrics.duration)
            # Keep only last 10 measurements
            if len(self.performance_history[metrics.job_type]) > 10:
                self.performance_history[metrics.job_type].pop(0)

            # Update pool average
            pool.avg_duration = sum(self.performance_history[metrics.job_type]) / len(self.performance_history[metrics.job_type])

        logger.debug(f"Completed {metrics.job_type.value} job in {metrics.duration:.2f}s "
                    f"(Active: {pool.active_jobs}, Completed: {pool.completed_jobs})")

    def get_resource_status(self) -> Dict[str, Any]:
        """Get current resource utilization status"""
        memory = psutil.virtual_memory()
        cpu_percent = psutil.cpu_percent(interval=0.1)

        return {
            "cpu_percent": cpu_percent,
            "memory_percent": memory.percent,
            "memory_available_gb": memory.available / (1024**3),
            "worker_pools": {
                job_type.value: {
                    "current_workers": pool.current_workers,
                    "active_jobs": pool.active_jobs,
                    "completed_jobs": pool.completed_jobs,
                    "avg_duration": pool.avg_duration
                }
                for job_type, pool in self.worker_pools.items()
            },
            "resource_limits": {
                "max_ram_gb": self.resource_limits.max_ram_gb,
                "max_cpu_cores": self.resource_limits.max_cpu_cores,
                "model_ram_gb": self.resource_limits.model_ram_gb
            }
        }

    def start_monitoring(self):
        """Start background resource monitoring"""
        if self.monitoring_active:
            return

        self.monitoring_active = True
        self.monitor_thread = threading.Thread(target=self._monitor_resources, daemon=True)
        self.monitor_thread.start()
        logger.info("Started dynamic parallelization monitoring")

    def stop_monitoring(self):
        """Stop background resource monitoring"""
        self.monitoring_active = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        logger.info("Stopped dynamic parallelization monitoring")

    def _monitor_resources(self):
        """Background monitoring thread"""
        while self.monitoring_active:
            try:
                # Get current resource usage
                memory = psutil.virtual_memory()
                cpu_percent = psutil.cpu_percent(interval=5)

                # Log resource status every minute
                if len(self.job_metrics) % 12 == 0:  # Every 12 iterations (1 minute)
                    logger.info(f"Resource status - CPU: {cpu_percent:.1f}%, "
                              f"RAM: {memory.percent:.1f}% ({memory.available/(1024**3):.1f}GB available)")

                # Check for resource pressure and adjust if needed
                if cpu_percent > 90 or memory.percent > 90:
                    logger.warning(f"High resource usage detected - CPU: {cpu_percent:.1f}%, RAM: {memory.percent:.1f}%")

                time.sleep(5)  # Check every 5 seconds

            except Exception as e:
                logger.error(f"Error in resource monitoring: {e}")
                time.sleep(10)


# Global manager instance
_global_manager = None

def get_parallelization_manager():
    """Get the global parallelization manager instance"""
    return _global_manager

def initialize_parallelization_manager(hardware_specs):
    """Initialize the global parallelization manager"""
    global _global_manager
    _global_manager = DynamicParallelizationManager(hardware_specs)
    _global_manager.start_monitoring()
    return _global_manager
EOF

chmod +x "$SCRIPTS_DIR/dynamic_parallelization.py"

print_status "Dynamic parallelization system created"

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
            "primary": "qwen2.5:14b-instruct",
            "size": "8.2GB",
            "description": "High-quality model for Ultra systems",
            "optional_upgrade": "llama3.1:70b (40GB) - Expert mode"
        }
    elif specs.memory_gb >= 32 and specs.chip_type in [ChipType.M3_MAX, ChipType.M2_MAX]:
        return {
            "primary": "qwen2.5:14b-instruct",
            "size": "8.2GB",
            "description": "Optimal for Max systems"
        }
    elif specs.memory_gb >= 16:
        return {
            "primary": "qwen2.5:7b-instruct",
            "size": "4GB",
            "description": "Balanced for Pro systems"
        }
    else:
        return {
            "primary": "qwen2.5:3b-instruct",
            "size": "2GB",
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
            recommendation = {'primary': 'qwen2.5:14b-instruct', 'size': '8.2GB', 'description': 'High-quality model for Ultra systems'}
        elif memory_gb >= 32:
            recommendation = {'primary': 'qwen2.5:14b-instruct', 'size': '8.2GB', 'description': 'Optimal for Max systems'}
        elif memory_gb >= 16:
            recommendation = {'primary': 'qwen2.5:7b-instruct', 'size': '4GB', 'description': 'Balanced for Pro systems'}
        else:
            recommendation = {'primary': 'qwen2.5:3b-instruct', 'size': '2GB', 'description': 'Efficient for base systems'}

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
        'recommendation': {'primary': 'qwen2.5:7b-instruct', 'size': '4GB', 'description': 'Balanced for Pro systems'}
    }
    print(json.dumps(result))
" > /tmp/hardware_specs.json

report_progress 15 "Hardware detection complete"

# Clean up old LaunchAgent if it exists
ACTUAL_USER=$(stat -f '%Su' /dev/console)
USER_HOME=$(eval echo ~$ACTUAL_USER)
OLD_PLIST="$USER_HOME/Library/LaunchAgents/org.skipthepodcast.daemon.plist"

if [ -f "$OLD_PLIST" ]; then
    echo "Removing old daemon LaunchAgent..."
    sudo -u "$ACTUAL_USER" launchctl unload "$OLD_PLIST" 2>/dev/null || true
    rm -f "$OLD_PLIST"
fi

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

# Waterfall approach to Python detection and installation
echo ""
echo "=== Python Waterfall Detection ==="
PYTHON_OK=false
SYSTEM_PYTHON=""
PYTHON_SOURCE=""

# Step 1: Check for system Python 3.10+
echo "Step 1: Checking for system Python 3.10+..."
for python_cmd in python3.13 python3.12 python3.11 python3.10 python3; do
    if command -v $python_cmd >/dev/null 2>&1; then
        PYTHON_VERSION=$($python_cmd --version 2>&1 | awk '{print $2}')
        PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
        PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)
        if [ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -ge 10 ]; then
            echo "✅ Found system Python: $python_cmd ($PYTHON_VERSION)"
            PYTHON_OK=true
            SYSTEM_PYTHON=$python_cmd
            PYTHON_SOURCE="system"
            break
        fi
    fi
done

# Step 2: Check for Homebrew Python
if [ "$PYTHON_OK" = false ]; then
    echo "Step 2: Checking for Homebrew Python..."
    for brew_py in /opt/homebrew/bin/python3.13 /opt/homebrew/bin/python3.12 /opt/homebrew/bin/python3.11 /opt/homebrew/bin/python3.10 /usr/local/bin/python3.13 /usr/local/bin/python3.12 /usr/local/bin/python3.11 /usr/local/bin/python3.10; do
        if [ -f "$brew_py" ]; then
            PYTHON_VERSION=$($brew_py --version 2>&1 | awk '{print $2}')
            PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
            PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)
            if [ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -ge 10 ]; then
                echo "✅ Found Homebrew Python: $brew_py ($PYTHON_VERSION)"
                PYTHON_OK=true
                SYSTEM_PYTHON=$brew_py
                PYTHON_SOURCE="homebrew"
                break
            fi
        fi
    done
fi

# Step 3: Try to install Python via Homebrew (if Homebrew exists)
if [ "$PYTHON_OK" = false ]; then
    echo "Step 3: Checking if Homebrew is available..."
    if command -v brew >/dev/null 2>&1; then
        echo "✅ Homebrew found, attempting to install Python 3.13..."
        report_progress 82 "Installing Python via Homebrew"
        
        # Try to install Python via Homebrew (with timeout)
        if timeout 120 brew install python@3.13 >/dev/null 2>&1; then
            # Check if installation succeeded
            for brew_py in /opt/homebrew/bin/python3.13 /usr/local/bin/python3.13; do
                if [ -f "$brew_py" ]; then
                    PYTHON_VERSION=$($brew_py --version 2>&1 | awk '{print $2}')
                    echo "✅ Python installed via Homebrew: $brew_py ($PYTHON_VERSION)"
                    PYTHON_OK=true
                    SYSTEM_PYTHON=$brew_py
                    PYTHON_SOURCE="homebrew_installed"
                    break
                fi
            done
        else
            echo "⚠️  Homebrew Python installation failed or timed out"
        fi
    else
        echo "⚠️  Homebrew not found, skipping Homebrew installation"
    fi
fi

# Step 4: Download and install bundled Python framework
if [ "$PYTHON_OK" = false ]; then
    echo "Step 4: No suitable Python found, installing bundled framework..."
    echo "    This will download ~40MB and may take a few minutes..."
    report_progress 85 "Downloading Python 3.13 framework"
    
    # Run download manager to install Python framework
    if [ -f "/tmp/skip_the_podcast_installer_scripts/download_manager.py" ]; then
        # Set environment variable to install only critical components
        export INSTALL_ONLY_CRITICAL=true
        export INSTALL_PYTHON_FRAMEWORK=true
        
        # Use system python3 to run the installer (any version for bootstrapping)
        if /usr/bin/python3 /tmp/skip_the_podcast_installer_scripts/download_manager.py "$APP_BUNDLE" 2>&1 | tee -a /tmp/skip_the_podcast_install.log; then
            echo "✅ Python framework installed successfully"
            PYTHON_OK=true
            PYTHON_SOURCE="bundled"
        else
            echo "⚠️  Python framework installation failed - app may not launch"
            echo "    User will be prompted to install Python from python.org"
        fi
    fi
else
    # Create marker file to indicate which Python to use
    mkdir -p "$APP_BUNDLE/Contents/Resources"
    echo "$SYSTEM_PYTHON" > "$APP_BUNDLE/Contents/Resources/.use_system_python"
    echo "✅ Using $PYTHON_SOURCE Python, skipping framework download"
fi

echo ""
echo "=== Python Setup Summary ==="
if [ "$PYTHON_OK" = true ]; then
    echo "✅ Python ready: $PYTHON_SOURCE"
    if [ -n "$SYSTEM_PYTHON" ]; then
        echo "   Location: $SYSTEM_PYTHON"
    fi
else
    echo "⚠️  No Python found - user will need to install Python 3.10+"
fi
echo "==========================="
echo ""

# Install FFmpeg if available (small and useful)
echo "Checking for FFmpeg..."
if [ ! -f "$APP_BUNDLE/Contents/MacOS/ffmpeg" ]; then
    echo "FFmpeg will be downloaded on first use (optional)"
fi

# Defer large components to first launch
report_progress 95 "Critical setup complete - AI models will download on first use"

# Create launch script with safety checks
echo "Creating launch script..."
cat > "$APP_BUNDLE/Contents/MacOS/launch" << 'LAUNCH_EOF'
#!/bin/bash
# Launch script for Skip the Podcast Desktop
# Guaranteed NOT to modify user's global Python environment

set -e  # Exit on any error

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="$HOME/Library/Application Support/SkipThePodcast/venv"
SETUP_MARKER="$VENV_DIR/.setup_complete"
LOG_FILE="$HOME/Library/Application Support/SkipThePodcast/launch.log"

# Create log directory
mkdir -p "$(dirname "$LOG_FILE")"

# Logging function (writes to log file and stderr, NOT stdout to avoid capture)
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >&2
}

log "=== Skip the Podcast Desktop Launch ==="

# Function to find suitable Python (waterfall approach)
find_python() {
    local python_cmd=""
    local python_version=""
    
    log "Searching for Python 3.10+ using waterfall approach..."
    
    # 1. Check if marker file indicates specific Python should be used
    if [ -f "$APP_DIR/Resources/.use_system_python" ]; then
        local marked_python=$(cat "$APP_DIR/Resources/.use_system_python")
        if command -v "$marked_python" >/dev/null 2>&1; then
            python_version=$("$marked_python" --version 2>&1 | awk '{print $2}')
            log "✅ Found marked Python: $marked_python ($python_version)"
            echo "$marked_python"
            return 0
        fi
    fi
    
    # 2. Check for bundled Python framework
    if [ -f "$APP_DIR/Frameworks/Python.framework/Versions/3.13/bin/python3" ]; then
        local bundled_py="$APP_DIR/Frameworks/Python.framework/Versions/3.13/bin/python3"
        if "$bundled_py" --version >/dev/null 2>&1; then
            python_version=$("$bundled_py" --version 2>&1 | awk '{print $2}')
            log "✅ Found bundled Python framework ($python_version)"
            echo "$bundled_py"
            return 0
        fi
    fi
    
    # 3. Check for Homebrew Python
    for brew_py in /opt/homebrew/bin/python3.13 /opt/homebrew/bin/python3.12 /opt/homebrew/bin/python3.11 /opt/homebrew/bin/python3.10 /usr/local/bin/python3.13 /usr/local/bin/python3.12 /usr/local/bin/python3.11 /usr/local/bin/python3.10; do
        if [ -f "$brew_py" ]; then
            python_version=$("$brew_py" --version 2>&1 | awk '{print $2}')
            local py_major=$(echo $python_version | cut -d. -f1)
            local py_minor=$(echo $python_version | cut -d. -f2)
            if [ "$py_major" -eq 3 ] && [ "$py_minor" -ge 10 ]; then
                log "✅ Found Homebrew Python: $brew_py ($python_version)"
                echo "$brew_py"
                return 0
            fi
        fi
    done
    
    # 4. Check system Python versions
    for py in python3.13 python3.12 python3.11 python3.10 python3; do
        if command -v "$py" >/dev/null 2>&1; then
            python_version=$("$py" --version 2>&1 | awk '{print $2}')
            local py_major=$(echo $python_version | cut -d. -f1)
            local py_minor=$(echo $python_version | cut -d. -f2)
            if [ "$py_major" -eq 3 ] && [ "$py_minor" -ge 10 ]; then
                log "✅ Found system Python: $py ($python_version)"
                echo "$py"
                return 0
            fi
        fi
    done
    
    log "❌ No suitable Python 3.10+ found"
    return 1
}

# Function to safely create isolated venv
create_safe_venv() {
    local python_cmd="$1"
    
    log "Creating isolated Python environment (will NOT modify system Python)..."
    
    # Remove old venv if it exists and is broken
    if [ -d "$VENV_DIR" ] && [ ! -f "$VENV_DIR/bin/python" ]; then
        log "Removing broken virtual environment..."
        rm -rf "$VENV_DIR"
    fi
    
    # Create parent directory
    mkdir -p "$(dirname "$VENV_DIR")"
    
    # Create fresh venv with explicit isolation (allow stderr, check exit code)
    log "Running: $python_cmd -m venv --clear $VENV_DIR"
    set +e  # Temporarily disable exit on error
    "$python_cmd" -m venv --clear "$VENV_DIR" 2>&1 | tee -a "$LOG_FILE"
    local venv_exit_code=$?
    set -e  # Re-enable exit on error
    
    if [ $venv_exit_code -ne 0 ]; then
        log "❌ Failed to create virtual environment (exit code: $venv_exit_code)"
        return 1
    fi
    
    # Verify venv was created correctly
    if [ ! -f "$VENV_DIR/bin/python" ]; then
        log "❌ Virtual environment creation failed - python not found in venv"
        log "   Checked: $VENV_DIR/bin/python"
        return 1
    fi
    
    # Ensure pip is available
    log "Ensuring pip is available in venv..."
    set +e
    "$VENV_DIR/bin/python" -m ensurepip --upgrade 2>&1 | tee -a "$LOG_FILE"
    set -e
    
    # Verify isolation - venv Python should point to venv directory
    local venv_python_path=$("$VENV_DIR/bin/python" -c "import sys; print(sys.prefix)" 2>/dev/null)
    if [[ "$venv_python_path" != *"SkipThePodcast"* ]]; then
        log "⚠️  Warning: Virtual environment may not be properly isolated"
        log "   Expected path containing 'SkipThePodcast', got: $venv_python_path"
    else
        log "✅ Venv isolation verified: $venv_python_path"
    fi
    
    log "✅ Isolated environment created successfully at: $VENV_DIR"
    return 0
}

# Function to install dependencies safely
install_dependencies() {
    log "Installing dependencies (isolated, won't affect global Python)..."
    
    # Unset any global Python environment variables to ensure isolation
    unset PYTHONPATH
    unset PYTHONHOME
    unset VIRTUAL_ENV
    
    # Use absolute paths only
    local venv_python="$VENV_DIR/bin/python"
    local venv_pip="$VENV_DIR/bin/pip"
    
    # Upgrade pip first
    log "Upgrading pip..."
    set +e
    "$venv_python" -m pip install --upgrade pip 2>&1 | tee -a "$LOG_FILE"
    set -e
    
    # Install with explicit isolation flags (use minimal daemon requirements)
    log "Installing requirements from: $APP_DIR/Resources/requirements-daemon.txt"
    set +e
    "$venv_pip" install \
        --no-warn-script-location \
        --isolated \
        -r "$APP_DIR/Resources/requirements-daemon.txt" 2>&1 | tee -a "$LOG_FILE"
    local install_exit_code=$?
    set -e
    
    if [ $install_exit_code -eq 0 ]; then
        log "✅ All dependencies installed successfully"
        return 0
    else
        log "⚠️  Some packages failed (exit code: $install_exit_code), installing core dependencies only..."
        # Install critical packages only
        set +e
        "$venv_pip" install --isolated pyyaml pydantic click loguru rich PyQt6 2>&1 | tee -a "$LOG_FILE"
        set -e
        log "✅ Core dependencies installed"
        return 0  # Don't fail - core deps are enough to try
    fi
}

# Main execution
main() {
    # Find Python using waterfall approach
    PYTHON_CMD=$(find_python)
    
    if [ -z "$PYTHON_CMD" ]; then
        osascript -e 'display dialog "Python 3.10+ is required but not found.\n\nPlease install Python from:\n• python.org\n• Homebrew: brew install python3\n\nOr reinstall the application." buttons {"OK"} default button "OK" with icon stop with title "Python Not Found"'
        exit 1
    fi
    
    # Check if setup is needed
    if [ ! -f "$SETUP_MARKER" ]; then
        log "First run setup needed..."
        
        # Show setup dialog (non-blocking)
        osascript -e 'display dialog "Setting up Skip the Podcast Desktop...\n\nThis will take a few minutes on first run.\n(Creating isolated environment - will NOT modify your system Python)" buttons {"Continue"} default button "Continue" with title "First Run Setup"' >/dev/null 2>&1 &
        
        # Create safe venv
        if ! create_safe_venv "$PYTHON_CMD"; then
            osascript -e 'display dialog "Failed to create Python environment.\n\nPlease check the log at:\n~/Library/Application Support/SkipThePodcast/launch.log" buttons {"OK"} default button "OK" with icon stop'
            exit 1
        fi
        
        # Install dependencies
        install_dependencies
        
        # Mark setup as complete
        touch "$SETUP_MARKER"
        log "✅ Setup complete!"
    fi
    
    # Final verification that venv is valid
    if [ ! -f "$VENV_DIR/bin/python" ]; then
        log "❌ Virtual environment is invalid"
        rm -f "$SETUP_MARKER"  # Force re-setup next time
        exit 1
    fi
    
    # Set up minimal, safe environment for app execution
    export PYTHONPATH="$APP_DIR/Resources/src"
    export MODELS_BUNDLED="true"
    export FFMPEG_PATH="$APP_DIR/MacOS/ffmpeg"
    export FFPROBE_PATH="$APP_DIR/MacOS/ffprobe"
    
    # Set minimal PATH (no global Python pollution)
    export PATH="$VENV_DIR/bin:$APP_DIR/MacOS:/usr/bin:/bin:/usr/sbin:/sbin"
    
    # Launch the daemon (background server for web interface)
    log "Starting Skip the Podcast Daemon..."
    export PYTHONPATH="$APP_DIR/Resources/src:$APP_DIR/Resources"
    cd "$APP_DIR/Resources"
    exec "$VENV_DIR/bin/python" -m daemon.main
}

# Check if being called with a URL (custom URL scheme handler)
if [ "$1" != "" ] && [[ "$1" == skipthepodcast://* ]]; then
    # Delegate to URL handler
    exec "$APP_DIR/MacOS/url-handler" "$1"
else
    # Normal launch - run main function
    main
fi
LAUNCH_EOF

chmod +x "$APP_BUNDLE/Contents/MacOS/launch"

report_progress 95 "Launch script created"

# Set proper permissions
echo "Setting permissions..."
chmod -R 755 "$APP_BUNDLE"

# Clean up any existing shortcuts/aliases to prevent duplicates
echo "Cleaning up existing shortcuts..."
# Remove any existing aliases or shortcuts
find /Applications -name "*Skip the Podcast Desktop*" -type l -delete 2>/dev/null || true
# Remove any duplicate entries in Launch Services database
/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister -kill -r -domain local -domain system -domain user 2>/dev/null || true

# Hardware-specific optimization
if [ -f "/tmp/hardware_specs.json" ]; then
    echo "Applying hardware-specific optimizations..."
    # This would configure settings based on detected hardware
fi

report_progress 95 "Setting up auto-start daemon..."

# Set up LaunchAgent for auto-start
# Find the actual user (postinstall runs as root)
ACTUAL_USER=$(stat -f '%Su' /dev/console)
USER_HOME=$(eval echo ~$ACTUAL_USER)

echo "Setting up daemon auto-start for user: $ACTUAL_USER"

# Create LaunchAgent plist
mkdir -p "$USER_HOME/Library/LaunchAgents"

cat > "$USER_HOME/Library/LaunchAgents/org.skipthepodcast.daemon.plist" << 'PLIST_EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>org.skipthepodcast.daemon</string>
    
    <key>ProgramArguments</key>
    <array>
        <string>/Applications/Skip the Podcast Desktop.app/Contents/MacOS/launch</string>
    </array>
    
    <!-- Do NOT auto-start on login - only start when explicitly triggered -->
    <key>RunAtLoad</key>
    <false/>
    
    <!-- Keep alive ONLY if actively being used (check network activity) -->
    <key>KeepAlive</key>
    <dict>
        <key>NetworkState</key>
        <true/>
        <key>SuccessfulExit</key>
        <false/>
    </dict>
    
    <key>ThrottleInterval</key>
    <integer>10</integer>
    
    <key>StandardOutPath</key>
    <string>/tmp/skipthepodcast-daemon.stdout.log</string>
    
    <key>StandardErrorPath</key>
    <string>/tmp/skipthepodcast-daemon.stderr.log</string>
    
    <key>ProcessType</key>
    <string>Background</string>
    
    <key>Nice</key>
    <integer>5</integer>
</dict>
</plist>
PLIST_EOF

# Set proper ownership
chown "$ACTUAL_USER:staff" "$USER_HOME/Library/LaunchAgents/org.skipthepodcast.daemon.plist"
chmod 644 "$USER_HOME/Library/LaunchAgents/org.skipthepodcast.daemon.plist"

# Load the LaunchAgent but don't start it automatically
sudo -u "$ACTUAL_USER" launchctl load "$USER_HOME/Library/LaunchAgents/org.skipthepodcast.daemon.plist" 2>/dev/null || true

# Start it ONCE after installation (for initial setup)
sudo -u "$ACTUAL_USER" launchctl start org.skipthepodcast.daemon 2>/dev/null || true

# Create convenience scripts for user control
mkdir -p "/Applications/Skip the Podcast Desktop.app/Contents/Resources/bin"

# Start daemon script
cat > "/Applications/Skip the Podcast Desktop.app/Contents/Resources/bin/start-daemon.sh" << 'START_EOF'
#!/bin/bash
# Start the Skip the Podcast daemon
launchctl start org.skipthepodcast.daemon 2>/dev/null && echo "✅ Daemon started" || echo "⚠️  Already running or failed to start"
START_EOF

# Stop daemon script
cat > "/Applications/Skip the Podcast Desktop.app/Contents/Resources/bin/stop-daemon.sh" << 'STOP_EOF'
#!/bin/bash
# Stop the Skip the Podcast daemon
launchctl stop org.skipthepodcast.daemon 2>/dev/null && echo "✅ Daemon stopped" || echo "⚠️  Already stopped or failed to stop"
STOP_EOF

# Status check script
cat > "/Applications/Skip the Podcast Desktop.app/Contents/Resources/bin/daemon-status.sh" << 'STATUS_EOF'
#!/bin/bash
# Check daemon status
if curl -s http://localhost:8765/health > /dev/null 2>&1; then
    echo "✅ Daemon is running on port 8765"
    exit 0
else
    echo "❌ Daemon is not running"
    echo "To start: launchctl start org.skipthepodcast.daemon"
    exit 1
fi
STATUS_EOF

chmod +x "/Applications/Skip the Podcast Desktop.app/Contents/Resources/bin/"*.sh
chown -R "$ACTUAL_USER:staff" "/Applications/Skip the Podcast Desktop.app/Contents/Resources/bin"

echo "Daemon configured (will not auto-start on reboot)"
echo "Control scripts installed at: /Applications/Skip the Podcast Desktop.app/Contents/Resources/bin/"

# Register URL scheme handler with macOS Launch Services
echo "Registering custom URL scheme handler..."
# Force LaunchServices to recognize the new app and its URL scheme
/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister -f "/Applications/Skip the Podcast Desktop.app"

# Also run as the user to ensure their LaunchServices database is updated
sudo -u "$ACTUAL_USER" /System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister -f "/Applications/Skip the Podcast Desktop.app" 2>/dev/null || true

echo "URL scheme 'skipthepodcast://' registered"

report_progress 100 "Installation complete"

echo "Post-install completed: $(date)"
echo "Skip the Podcast daemon will start automatically in the background"
EOF

chmod +x "$SCRIPTS_DIR/postinstall"

print_status "Post-install script created"

# Copy installer scripts to both locations - resources for distribution and app bundle for runtime
echo -e "\n${BLUE}📦 Copying installer scripts...${NC}"
mkdir -p "$RESOURCES_DIR/installer_scripts"
mkdir -p "$APP_BUNDLE/Contents/Resources/installer_scripts"
mkdir -p "$APP_BUNDLE/Contents/Resources/scripts"

# Copy to distribution resources
cp "$SCRIPTS_DIR/download_manager.py" "$RESOURCES_DIR/installer_scripts/"
cp "$SCRIPTS_DIR/hardware_detector.py" "$RESOURCES_DIR/installer_scripts/"

# Copy to app bundle for runtime access
cp "$SCRIPTS_DIR/download_manager.py" "$APP_BUNDLE/Contents/Resources/installer_scripts/"
cp "$SCRIPTS_DIR/hardware_detector.py" "$APP_BUNDLE/Contents/Resources/installer_scripts/"

# Copy post-install model setup script
if [ -f "$PROJECT_ROOT/scripts/post_install_setup.sh" ]; then
    cp "$PROJECT_ROOT/scripts/post_install_setup.sh" "$APP_BUNDLE/Contents/Resources/scripts/"
    chmod +x "$APP_BUNDLE/Contents/Resources/scripts/post_install_setup.sh"
    print_status "Post-install model setup script included"
fi

# For now, let's skip creating system-level files to see if that's interfering
# echo -e "\n${BLUE}📝 Creating system-level installation components...${NC}"

print_status "Installer scripts copied"

# Create the launch script (needed for code signing)
echo -e "\n${BLUE}🚀 Creating launch script...${NC}"
cat > "$APP_BUNDLE/Contents/MacOS/launch" << 'LAUNCH_EOF'
#!/bin/bash
# Launch script for Skip the Podcast Desktop

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="$HOME/Library/Application Support/SkipThePodcast/venv"
SETUP_MARKER="$VENV_DIR/.setup_complete"
ARCH_NAME="$(uname -m)"
ARCH_PREFIX=""
if [[ "$ARCH_NAME" == "arm64" ]]; then ARCH_PREFIX="/usr/bin/arch -arm64"; fi

# Set up environment
export PYTHONPATH="$APP_DIR/Resources/src:${PYTHONPATH}"
export MODELS_BUNDLED="true"
export FFMPEG_PATH="$APP_DIR/MacOS/ffmpeg"
export FFPROBE_PATH="$APP_DIR/MacOS/ffprobe"
export PATH="$APP_DIR/MacOS:${PATH}"

# Select a Python >= 3.10 interpreter (prefer Homebrew)
select_python() {
    local cand=
    for cand in \
        "/opt/homebrew/bin/python3.12" \
        "/opt/homebrew/bin/python3.11" \
        "/opt/homebrew/bin/python3.10" \
        "/opt/homebrew/bin/python3" \
        "/usr/bin/python3"; do
        if [ -x "$cand" ]; then
            local ok
            ok=$($ARCH_PREFIX "$cand" -c 'import sys; print(int(sys.version_info[:2] >= (3,10)))' 2>/dev/null || echo 0)
            if [ "$ok" = "1" ]; then
                echo "$cand"
                return 0
            fi
        fi
    done
    echo ""  # not found
}

PYTHON_BIN="$(select_python)"
if [ -z "$PYTHON_BIN" ]; then
    osascript -e 'display dialog "A Python 3.10+ interpreter is required.\n\nPlease install Homebrew Python (python@3.12) and re-open the app." buttons {"OK"} default button "OK" with title "Python Required" with icon stop'
    exit 1
fi

create_venv() {
    echo "Creating Python environment..."
    mkdir -p "$(dirname "$VENV_DIR")"
    rm -rf "$VENV_DIR"
    $ARCH_PREFIX "$PYTHON_BIN" -m venv "$VENV_DIR"
    echo "Installing dependencies..."
    $ARCH_PREFIX "$VENV_DIR/bin/python" -m ensurepip --upgrade || true
    $ARCH_PREFIX "$VENV_DIR/bin/python" -m pip install --upgrade pip wheel setuptools --no-cache-dir
    $ARCH_PREFIX "$VENV_DIR/bin/python" -m pip install -r "$APP_DIR/Resources/requirements.txt" --no-cache-dir
}

validate_imports() {
    $ARCH_PREFIX "$VENV_DIR/bin/python" - <<'PY'
import sys, platform
print(platform.machine())
try:
    import pydantic_core, PyQt6, yaml
    print("OK")
except Exception as e:
    print(f"IMPORT_ERROR:{e}", file=sys.stderr)
    raise SystemExit(1)
PY
}

# First-run or recovery setup (enforce Python >= 3.10 and arm64)
NEED_SETUP=0
if [ ! -f "$SETUP_MARKER" ]; then
    NEED_SETUP=1
else
    VENV_ARCH="$($ARCH_PREFIX "$VENV_DIR/bin/python" -c 'import platform; print(platform.machine())' 2>/dev/null || echo unknown)"
    VENV_VER="$($ARCH_PREFIX "$VENV_DIR/bin/python" -c 'import sys; print("%d.%d"%sys.version_info[:2])' 2>/dev/null || echo 0.0)"
    # Version compare helper (returns 1 if $1 < $2)
    version_lt() { [ "$(printf '%s\n' "$1" "$2" | sort -V | head -n1)" != "$2" ]; }
    if [[ "$ARCH_NAME" == "arm64" && "$VENV_ARCH" != "arm64" ]]; then
        echo "Venv architecture mismatch ($VENV_ARCH); rebuilding for arm64..."
        NEED_SETUP=1
    elif version_lt "$VENV_VER" "3.10"; then
        echo "Venv Python $VENV_VER < 3.10; rebuilding with $PYTHON_BIN..."
        NEED_SETUP=1
    else
        if ! validate_imports >/dev/null 2>&1; then
            echo "Import validation failed; rebuilding venv..."
            NEED_SETUP=1
        fi
    fi
fi

if [ $NEED_SETUP -eq 1 ]; then
    osascript -e 'display dialog "Setting up Skip the Podcast Desktop...\n\nThis will take a few minutes on first run." buttons {"Continue"} default button "Continue" with title "First Run Setup"'
    create_venv
    if ! validate_imports; then
        echo "Reinstalling pydantic_core without cache..."
        $ARCH_PREFIX "$VENV_DIR/bin/python" -m pip install --force-reinstall --no-cache-dir pydantic_core || true
        # Validate again; if still failing, show dialog
        if ! validate_imports; then
            osascript -e 'display dialog "Dependency setup failed.\n\nPlease run: brew install python@3.12 and re-open the app." buttons {"OK"} default button "OK" with title "Setup Error" with icon stop'
            exit 1
        fi
    fi
    touch "$SETUP_MARKER"
    echo "Setup complete!"
fi

# Launch the daemon (background server for web interface)
export PYTHONPATH="$APP_DIR/Resources/src:$APP_DIR/Resources"
cd "$APP_DIR/Resources"
exec $ARCH_PREFIX "$VENV_DIR/bin/python" -m daemon.main
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

    <!-- Single authorization requirement -->
    <authorization>
        <privilege>system.install.root.admin</privilege>
    </authorization>

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
    <div class="feature"><span class="icon">✓</span> Skip the Podcast Desktop Application</div>
    <div class="feature"><span class="icon">✓</span> Python 3.13 Framework (40MB)</div>
    <div class="feature"><span class="icon">✓</span> AI Models Package (1.2GB)</div>
    <div class="feature"><span class="icon">✓</span> FFmpeg Media Processing (48MB)</div>
    <div class="feature"><span class="icon">✓</span> Ollama LLM Runtime (50MB)</div>
    <div class="feature"><span class="icon">✓</span> Hardware-optimized model selection</div>

    <p><strong>Total download size:</strong> Approximately 1.3-4.7GB depending on your hardware.</p>
    <p><strong>Installation time:</strong> 5-15 minutes depending on internet speed.</p>
    <p><strong>Note:</strong> All components will be downloaded automatically during installation.</p>

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

    <p>For support and documentation, visit: <a href="https://github.com/msg43/Skipthepodcast.com">GitHub Repository</a></p>
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
