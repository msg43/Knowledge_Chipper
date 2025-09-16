#!/usr/bin/env python3
"""
Create a web-based installer that bypasses Gatekeeper entirely.
This script generates an installer that users can run from Terminal.
"""

import os
import sys
from pathlib import Path


def create_web_installer():
    """Generate a web installer script."""

    installer_content = """#!/bin/bash
# Skip the Podcast Desktop - Web Installer
# This installer bypasses Gatekeeper by downloading directly

set -e

# Colors
RED='\\033[0;31m'
GREEN='\\033[0;32m'
BLUE='\\033[0;34m'
YELLOW='\\033[1;33m'
NC='\\033[0m'

echo -e "${BLUE}Skip the Podcast Desktop - Direct Installer${NC}"
echo "==========================================="
echo ""
echo "This installer will:"
echo "✓ Download Skip the Podcast Desktop"
echo "✓ Install to /Applications"
echo "✓ Configure macOS security settings"
echo "✓ Launch the app"
echo ""

# Check if curl is available
if ! command -v curl &> /dev/null; then
    echo -e "${RED}Error: curl is required but not installed${NC}"
    exit 1
fi

# Get latest release URL (replace with your actual URL)
DOWNLOAD_URL="https://github.com/skipthepodcast/desktop/releases/latest/download/Skip_the_Podcast_Desktop.dmg"
# For testing, you can use a direct URL:
# DOWNLOAD_URL="https://your-server.com/Skip_the_Podcast_Desktop.zip"

echo -e "${BLUE}📥 Downloading Skip the Podcast Desktop...${NC}"
echo "   This may take a few minutes depending on your connection"
echo ""

# Create temp directory
TEMP_DIR=$(mktemp -d)
cd "$TEMP_DIR"

# Download with progress bar
if curl -L -# -o "app_download.dmg" "$DOWNLOAD_URL"; then
    echo -e "${GREEN}✓ Download complete${NC}"
else
    echo -e "${RED}❌ Download failed${NC}"
    rm -rf "$TEMP_DIR"
    exit 1
fi

# Mount DMG
echo -e "${BLUE}📂 Mounting installer...${NC}"
MOUNT_POINT=$(hdiutil attach -nobrowse "app_download.dmg" | grep "/Volumes" | awk -F'\\t' '{print $NF}')

if [ -z "$MOUNT_POINT" ]; then
    echo -e "${RED}❌ Failed to mount DMG${NC}"
    rm -rf "$TEMP_DIR"
    exit 1
fi

# Check if app exists
APP_IN_DMG="$MOUNT_POINT/Skip the Podcast Desktop.app"
if [ ! -d "$APP_IN_DMG" ]; then
    echo -e "${RED}❌ App not found in DMG${NC}"
    hdiutil detach "$MOUNT_POINT" -quiet
    rm -rf "$TEMP_DIR"
    exit 1
fi

# Remove old installation if exists
if [ -d "/Applications/Skip the Podcast Desktop.app" ]; then
    echo -e "${YELLOW}⚠️  Removing previous installation...${NC}"
    rm -rf "/Applications/Skip the Podcast Desktop.app"
fi

# Copy to Applications
echo -e "${BLUE}📋 Installing to Applications...${NC}"
cp -R "$APP_IN_DMG" "/Applications/"

# IMPORTANT: No quarantine attribute because we downloaded via curl!
echo -e "${GREEN}✓ Installed without quarantine!${NC}"

# Unmount DMG
hdiutil detach "$MOUNT_POINT" -quiet

# Register with Launch Services
echo -e "${BLUE}🔧 Registering with macOS...${NC}"
/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister \\
    -f "/Applications/Skip the Podcast Desktop.app" 2>/dev/null || true

# Clean up
rm -rf "$TEMP_DIR"

echo ""
echo -e "${GREEN}✅ Installation Complete!${NC}"
echo ""
echo -e "${BLUE}🚀 Launching Skip the Podcast Desktop...${NC}"

# Launch the app
open -a "Skip the Podcast Desktop" --args --first-run

echo ""
echo "Skip the Podcast Desktop has been installed and launched!"
echo "You can find it in your Applications folder."
echo ""
echo -e "${YELLOW}Note: Since this was installed via direct download,${NC}"
echo -e "${YELLOW}      you won't see any Gatekeeper warnings!${NC}"
"""

    # Save the installer
    installer_path = Path("install_skip_the_podcast.sh")
    installer_path.write_text(installer_content)
    installer_path.chmod(0o755)

    # Create a simple Python version too
    python_installer = '''#!/usr/bin/env python3
"""Skip the Podcast Desktop - Python Installer"""

import os
import sys
import urllib.request
import tempfile
import subprocess
import shutil
from pathlib import Path

def download_with_progress(url, filename):
    """Download file with progress indicator."""
    def report_progress(block_num, block_size, total_size):
        downloaded = block_num * block_size
        percent = min(downloaded * 100 / total_size, 100)
        sys.stdout.write(f'\\rDownloading: {percent:.1f}%')
        sys.stdout.flush()

    urllib.request.urlretrieve(url, filename, reporthook=report_progress)
    print()  # New line after progress

def main():
    print("Skip the Podcast Desktop - Direct Installer")
    print("==========================================")
    print()
    print("This installer bypasses Gatekeeper completely!")
    print()

    # URL of your DMG
    dmg_url = "https://github.com/skipthepodcast/desktop/releases/latest/download/Skip_the_Podcast_Desktop.dmg"

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        dmg_path = temp_path / "app.dmg"

        # Download
        print("📥 Downloading Skip the Podcast Desktop...")
        try:
            download_with_progress(dmg_url, str(dmg_path))
            print("✅ Download complete!")
        except Exception as e:
            print(f"❌ Download failed: {e}")
            return 1

        # Mount DMG
        print("📂 Mounting installer...")
        result = subprocess.run(
            ["hdiutil", "attach", "-nobrowse", str(dmg_path)],
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            print("❌ Failed to mount DMG")
            return 1

        # Find mount point
        mount_point = None
        for line in result.stdout.split('\\n'):
            if '/Volumes' in line:
                mount_point = line.split('\\t')[-1].strip()
                break

        if not mount_point:
            print("❌ Could not find mount point")
            return 1

        # Copy app
        app_source = Path(mount_point) / "Skip the Podcast Desktop.app"
        app_dest = Path("/Applications/Skip the Podcast Desktop.app")

        print("📋 Installing to Applications...")

        # Remove old version
        if app_dest.exists():
            shutil.rmtree(app_dest)

        # Copy new version
        shutil.copytree(app_source, app_dest)

        # Unmount
        subprocess.run(["hdiutil", "detach", mount_point, "-quiet"], check=False)

        print("✅ Installation complete!")
        print()
        print("🚀 Launching Skip the Podcast Desktop...")

        # Launch
        subprocess.run(["open", "-a", "Skip the Podcast Desktop"])

        print()
        print("✨ Success! No Gatekeeper warnings!")

    return 0

if __name__ == "__main__":
    sys.exit(main())
'''

    python_installer_path = Path("install_skip_the_podcast.py")
    python_installer_path.write_text(python_installer)
    python_installer_path.chmod(0o755)

    # Create instructions
    instructions = """# Skip the Podcast Desktop - Gatekeeper-Free Installation

## The Problem
Your DMG triggers Gatekeeper because it was downloaded through a browser, which adds a quarantine flag.

## The Solution
Use one of these installers that download directly, bypassing quarantine:

### Option 1: Bash Installer (Recommended)
```bash
curl -sSL https://your-website.com/install_skip_the_podcast.sh | bash
```

Or download and run:
```bash
curl -O https://your-website.com/install_skip_the_podcast.sh
chmod +x install_skip_the_podcast.sh
./install_skip_the_podcast.sh
```

### Option 2: Python Installer
```bash
curl -O https://your-website.com/install_skip_the_podcast.py
python3 install_skip_the_podcast.py
```

### Option 3: Direct Terminal Commands
```bash
# Download DMG without quarantine
curl -L -o skip.dmg "https://github.com/skipthepodcast/desktop/releases/latest/download/Skip_the_Podcast_Desktop.dmg"

# Mount it
hdiutil attach skip.dmg

# Copy to Applications
cp -R "/Volumes/Skip the Podcast Desktop/Skip the Podcast Desktop.app" /Applications/

# Unmount and clean up
hdiutil detach "/Volumes/Skip the Podcast Desktop"
rm skip.dmg

# Launch
open -a "Skip the Podcast Desktop"
```

## Why This Works

1. **No Quarantine**: Files downloaded via `curl` or `urllib` don't get quarantine flags
2. **No Gatekeeper**: Without quarantine, Gatekeeper doesn't check the app
3. **Clean Install**: App appears in Applications and just works

## For Your Website

Add this to your download page:

```html
<h3>Having trouble with security warnings?</h3>
<p>Use our direct installer:</p>
<pre><code>curl -sSL https://your-site.com/install | bash</code></pre>
```

## Testing

1. Upload these installer scripts to your server
2. Test with: `curl -sSL https://your-server/install_skip_the_podcast.sh | bash`
3. App installs and launches with NO Gatekeeper warnings!
"""

    Path("GATEKEEPER_FREE_INSTALLATION.md").write_text(instructions)

    print("✅ Created Gatekeeper-bypass installers:")
    print("   • install_skip_the_podcast.sh (Bash version)")
    print("   • install_skip_the_podcast.py (Python version)")
    print("   • GATEKEEPER_FREE_INSTALLATION.md (Instructions)")
    print()
    print("📝 Next steps:")
    print("1. Update the URLs in the scripts to point to your actual DMG")
    print("2. Upload the installer scripts to your website")
    print("3. Give users the curl command to run")
    print("4. No more Gatekeeper warnings!")


if __name__ == "__main__":
    create_web_installer()
