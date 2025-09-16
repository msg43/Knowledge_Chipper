#!/usr/bin/env python3
"""
Install whisper.cpp binary for DMG distribution
This ensures the DMG has everything needed for local transcription on any machine.
"""

import os
import platform
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path
from typing import Optional


class WhisperCppInstaller:
    """Install whisper.cpp binary for bundling in DMG."""

    def __init__(self, app_bundle_path: Path, quiet: bool = False):
        self.app_bundle_path = Path(app_bundle_path)
        self.quiet = quiet
        self.macos_path = self.app_bundle_path / "Contents" / "MacOS"
        self.bin_path = self.macos_path / "bin"

        # Ensure bin directory exists
        self.bin_path.mkdir(parents=True, exist_ok=True)

    def log(self, message: str, force: bool = False) -> None:
        """Log message if not in quiet mode."""
        if not self.quiet or force:
            print(f"[WhisperCpp] {message}")

    def detect_architecture(self) -> str:
        """Detect system architecture."""
        machine = platform.machine().lower()
        if machine in ["arm64", "aarch64"]:
            return "arm64"
        elif machine in ["x86_64", "amd64"]:
            return "x86_64"
        else:
            self.log(
                f"Unknown architecture: {machine}, defaulting to x86_64", force=True
            )
            return "x86_64"

    def get_whisper_cpp_release_url(self) -> tuple[str, str]:
        """Get the appropriate whisper.cpp release URL for macOS."""
        arch = self.detect_architecture()

        # Use stable release from whisper.cpp GitHub releases
        base_url = "https://github.com/ggerganov/whisper.cpp/releases/download/v1.5.4"

        if arch == "arm64":
            # Apple Silicon (M1/M2/M3)
            filename = "whisper-v1.5.4-bin-macos-arm64.zip"
        else:
            # Intel Mac
            filename = "whisper-v1.5.4-bin-macos-x64.zip"

        return f"{base_url}/{filename}", filename

    def download_and_extract(self, url: str, filename: str) -> bool:
        """Download and extract whisper.cpp binary."""
        try:
            self.log(f"Downloading whisper.cpp from {url}")

            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                zip_path = temp_path / filename

                # Download
                urllib.request.urlretrieve(url, zip_path)
                self.log(f"Downloaded {filename} ({zip_path.stat().st_size // 1024}KB)")

                # Extract
                extract_path = temp_path / "extracted"
                extract_path.mkdir()

                # Use system unzip command
                subprocess.run(
                    ["unzip", "-q", str(zip_path), "-d", str(extract_path)], check=True
                )

                # Find the whisper binary (could be in subdirectory)
                whisper_binary = None
                for binary_path in extract_path.rglob("whisper"):
                    if binary_path.is_file() and os.access(binary_path, os.X_OK):
                        whisper_binary = binary_path
                        break

                if not whisper_binary:
                    self.log(
                        "Error: whisper binary not found in downloaded package",
                        force=True,
                    )
                    return False

                # Copy to app bundle
                target_path = self.bin_path / "whisper"
                shutil.copy2(whisper_binary, target_path)
                target_path.chmod(0o755)

                self.log(f"✅ Installed whisper binary to {target_path}")

                # Verify the binary works
                try:
                    result = subprocess.run(
                        [str(target_path), "--help"],
                        capture_output=True,
                        text=True,
                        timeout=10,
                    )
                    if result.returncode == 0:
                        self.log("✅ Binary verification successful")
                        return True
                    else:
                        self.log(
                            f"⚠️ Binary verification failed (exit code {result.returncode})",
                            force=True,
                        )
                        return False
                except subprocess.TimeoutExpired:
                    self.log("⚠️ Binary verification timeout", force=True)
                    return False

        except Exception as e:
            self.log(f"Error downloading whisper.cpp: {e}", force=True)
            return False

    def create_bundled_whisper_script(self) -> None:
        """Create setup script for bundled whisper.cpp."""
        setup_script = self.macos_path / "setup_bundled_whisper.sh"

        script_content = """#!/bin/bash
# Setup script to add bundled whisper.cpp to PATH
# Get the directory where this script is located
APP_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
export WHISPER_CPP_PATH="$APP_DIR/bin/whisper"
export PATH="$APP_DIR/bin:$PATH"

# Let the app know whisper.cpp is bundled
export WHISPER_CPP_BUNDLED="true"
"""

        with open(setup_script, "w") as f:
            f.write(script_content)
        setup_script.chmod(0o755)

        self.log(f"✅ Created setup script: {setup_script}")

    def install(self) -> bool:
        """Install whisper.cpp binary for DMG distribution."""
        if platform.system() != "Darwin":
            self.log("Error: This installer is for macOS only", force=True)
            return False

        self.log("Installing whisper.cpp binary for DMG distribution...")

        url, filename = self.get_whisper_cpp_release_url()

        if self.download_and_extract(url, filename):
            self.create_bundled_whisper_script()
            self.log("✅ whisper.cpp installation complete!")
            self.log(f"   Binary location: {self.bin_path / 'whisper'}")
            return True
        else:
            self.log("❌ whisper.cpp installation failed", force=True)
            return False


def install_whisper_cpp_for_dmg(app_bundle_path: Path, quiet: bool = False) -> bool:
    """Install whisper.cpp binary into an app bundle during .dmg build.

    Args:
        app_bundle_path: Path to the .app bundle being built
        quiet: If True, suppress all output except errors

    Returns:
        True if installation successful, False otherwise
    """
    try:
        installer = WhisperCppInstaller(app_bundle_path, quiet)
        return installer.install()
    except Exception as e:
        if not quiet:
            print(f"❌ Error installing whisper.cpp: {e}", file=sys.stderr)
        return False


def main() -> int:
    """CLI entry point for testing the installer."""
    import argparse

    parser = argparse.ArgumentParser(description="Install whisper.cpp binary for DMG")
    parser.add_argument("--app-bundle", required=True, help="Path to app bundle")
    parser.add_argument("--quiet", action="store_true", help="Suppress output")

    args = parser.parse_args()

    success = install_whisper_cpp_for_dmg(Path(args.app_bundle), args.quiet)
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
