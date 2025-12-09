#!/usr/bin/env python3
"""
Silent Deno Installer for Skip the Podcast Desktop

Downloads and installs Deno into the app bundle for yt-dlp YouTube support.
Deno is REQUIRED for yt-dlp >= 2025.11.12 to download from YouTube.

Usage:
    python silent_deno_installer.py --app-bundle /path/to/App.app [--quiet]
"""

import argparse
import hashlib
import json
import os
import platform
import shutil
import stat
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path


# Deno version to install (update when upgrading)
DENO_VERSION = "2.5.6"

# GitHub release URL pattern
DENO_URL_TEMPLATE = "https://github.com/denoland/deno/releases/download/v{version}/deno-{arch}-apple-darwin.zip"


def get_architecture() -> str:
    """Get the CPU architecture for download URL."""
    machine = platform.machine().lower()
    if machine in ("x86_64", "amd64"):
        return "x86_64"
    elif machine in ("arm64", "aarch64"):
        return "aarch64"
    else:
        raise RuntimeError(f"Unsupported architecture: {machine}")


def download_deno(dest_dir: Path, quiet: bool = False) -> Path:
    """Download Deno binary from GitHub releases."""
    arch = get_architecture()
    url = DENO_URL_TEMPLATE.format(version=DENO_VERSION, arch=arch)
    
    if not quiet:
        print(f"🦕 Downloading Deno v{DENO_VERSION} for {arch}...")
        print(f"   URL: {url}")
    
    zip_path = dest_dir / f"deno-{DENO_VERSION}-{arch}.zip"
    
    try:
        urllib.request.urlretrieve(url, zip_path)
    except Exception as e:
        raise RuntimeError(f"Failed to download Deno: {e}")
    
    if not quiet:
        print(f"   ✅ Downloaded to: {zip_path}")
    
    return zip_path


def extract_deno(zip_path: Path, dest_dir: Path, quiet: bool = False) -> Path:
    """Extract Deno binary from zip archive."""
    import zipfile
    
    if not quiet:
        print("📦 Extracting Deno...")
    
    extract_dir = dest_dir / "extracted"
    extract_dir.mkdir(exist_ok=True)
    
    with zipfile.ZipFile(zip_path, 'r') as zf:
        zf.extractall(extract_dir)
    
    deno_bin = extract_dir / "deno"
    
    if not deno_bin.exists():
        raise RuntimeError("Deno binary not found in archive")
    
    # Make executable
    deno_bin.chmod(deno_bin.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    
    if not quiet:
        print(f"   ✅ Extracted to: {deno_bin}")
    
    return deno_bin


def verify_deno(deno_path: Path, quiet: bool = False) -> str:
    """Verify Deno binary works and return version info."""
    if not quiet:
        print("🧪 Verifying Deno installation...")
    
    try:
        result = subprocess.run(
            [str(deno_path), "--version"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode != 0:
            raise RuntimeError(f"Deno verification failed: {result.stderr}")
        
        version_info = result.stdout.strip().split('\n')[0]
        if not quiet:
            print(f"   ✅ {version_info}")
        return version_info
        
    except subprocess.TimeoutExpired:
        raise RuntimeError("Deno verification timed out")
    except Exception as e:
        raise RuntimeError(f"Deno verification failed: {e}")


def install_to_app_bundle(deno_bin: Path, app_bundle: Path, quiet: bool = False) -> Path:
    """Install Deno binary into app bundle."""
    if not quiet:
        print(f"📁 Installing Deno to app bundle...")
    
    # Install to Contents/MacOS/bin (alongside other bundled binaries)
    bin_dir = app_bundle / "Contents" / "MacOS" / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    
    dest_path = bin_dir / "deno"
    
    # Copy binary
    shutil.copy2(deno_bin, dest_path)
    
    # Ensure executable
    dest_path.chmod(dest_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    
    if not quiet:
        print(f"   ✅ Installed to: {dest_path}")
    
    return dest_path


def create_setup_script(app_bundle: Path, quiet: bool = False) -> Path:
    """Create setup script for bundled Deno."""
    if not quiet:
        print("📝 Creating Deno setup script...")
    
    macos_dir = app_bundle / "Contents" / "MacOS"
    setup_script = macos_dir / "setup_bundled_deno.sh"
    
    script_content = '''#!/bin/bash
# Setup bundled Deno for yt-dlp YouTube support
# Source this script to configure Deno environment
# Deno is REQUIRED for yt-dlp >= 2025.11.12

APP_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
DENO_BIN="$APP_DIR/bin/deno"

if [ -f "$DENO_BIN" ]; then
    export DENO_BUNDLED="true"
    export DENO_PATH="$DENO_BIN"
    # Add bundled bin to PATH so yt-dlp can find Deno
    export PATH="$APP_DIR/bin:$PATH"
    echo "Deno configured: $DENO_BIN"
else
    export DENO_BUNDLED="false"
    echo "Warning: Bundled Deno not found at $DENO_BIN"
fi
'''
    
    setup_script.write_text(script_content)
    setup_script.chmod(setup_script.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    
    if not quiet:
        print(f"   ✅ Created: {setup_script}")
    
    return setup_script


def create_version_info(app_bundle: Path, version_info: str, quiet: bool = False) -> Path:
    """Create version info JSON for bundled Deno."""
    if not quiet:
        print("📋 Creating version info...")
    
    resources_dir = app_bundle / "Contents" / "Resources"
    resources_dir.mkdir(parents=True, exist_ok=True)
    
    info_file = resources_dir / "deno_version_info.json"
    
    import datetime
    
    info = {
        "deno_version": DENO_VERSION,
        "deno_info": version_info,
        "architecture": get_architecture(),
        "installed_date": datetime.datetime.utcnow().isoformat() + "Z",
        "purpose": "JavaScript runtime for yt-dlp YouTube support",
        "required_for": "yt-dlp >= 2025.11.12",
        "source": "github.com/denoland/deno"
    }
    
    info_file.write_text(json.dumps(info, indent=2))
    
    if not quiet:
        print(f"   ✅ Created: {info_file}")
    
    return info_file


def main():
    parser = argparse.ArgumentParser(
        description="Install Deno into Skip the Podcast Desktop app bundle"
    )
    parser.add_argument(
        "--app-bundle",
        required=True,
        help="Path to the .app bundle"
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress output except errors"
    )
    parser.add_argument(
        "--version",
        default=DENO_VERSION,
        help=f"Deno version to install (default: {DENO_VERSION})"
    )
    
    args = parser.parse_args()
    
    # Override version if specified
    global DENO_VERSION
    DENO_VERSION = args.version
    
    app_bundle = Path(args.app_bundle)
    quiet = args.quiet
    
    if not app_bundle.exists():
        print(f"❌ App bundle not found: {app_bundle}", file=sys.stderr)
        sys.exit(1)
    
    if not app_bundle.suffix == ".app":
        print(f"❌ Not an app bundle: {app_bundle}", file=sys.stderr)
        sys.exit(1)
    
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Download
            zip_path = download_deno(temp_path, quiet)
            
            # Extract
            deno_bin = extract_deno(zip_path, temp_path, quiet)
            
            # Verify
            version_info = verify_deno(deno_bin, quiet)
            
            # Install to app bundle
            installed_path = install_to_app_bundle(deno_bin, app_bundle, quiet)
            
            # Create setup script
            create_setup_script(app_bundle, quiet)
            
            # Create version info
            create_version_info(app_bundle, version_info, quiet)
            
            # Final verification
            verify_deno(installed_path, quiet)
        
        if not quiet:
            print("\n🎉 Deno installation complete!")
            print(f"   Version: {DENO_VERSION}")
            print(f"   Location: {installed_path}")
            print("   yt-dlp will auto-detect Deno in PATH")
        
        sys.exit(0)
        
    except Exception as e:
        print(f"❌ Installation failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
