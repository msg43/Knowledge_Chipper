#!/usr/bin/env python3
"""Skip the Podcast Desktop - Python Installer"""

import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path


def download_with_progress(url, filename):
    """Download file with progress indicator."""

    def report_progress(block_num, block_size, total_size):
        downloaded = block_num * block_size
        percent = min(downloaded * 100 / total_size, 100)
        sys.stdout.write(f"\rDownloading: {percent:.1f}%")
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
            text=True,
        )

        if result.returncode != 0:
            print("❌ Failed to mount DMG")
            return 1

        # Find mount point
        mount_point = None
        for line in result.stdout.split("\n"):
            if "/Volumes" in line:
                mount_point = line.split("\t")[-1].strip()
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
