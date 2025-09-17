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

    def get_whisper_cpp_source_url(self) -> tuple[str, str]:
        """Get whisper.cpp source code URL for compilation."""
        # Use stable release source code
        version = "v1.7.6"
        base_url = f"https://github.com/ggerganov/whisper.cpp/archive/refs/tags/{version}.tar.gz"
        filename = f"whisper.cpp-{version}.tar.gz"
        return base_url, filename

    def download_and_compile(self, url: str, filename: str) -> bool:
        """Download whisper.cpp source and compile for macOS."""
        try:
            self.log(f"Downloading whisper.cpp source from {url}")

            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                tarball_path = temp_path / filename

                # Download source
                urllib.request.urlretrieve(url, tarball_path)
                self.log(
                    f"Downloaded {filename} ({tarball_path.stat().st_size // 1024}KB)"
                )

                # Extract source
                extract_path = temp_path / "extracted"
                extract_path.mkdir()

                # Extract tarball
                import tarfile

                with tarfile.open(tarball_path, "r:gz") as tar:
                    tar.extractall(extract_path)

                # Find the source directory
                source_dirs = list(extract_path.glob("whisper.cpp-*"))
                if not source_dirs:
                    self.log(
                        "❌ CRITICAL: Could not find whisper.cpp source directory",
                        force=True,
                    )
                    return False

                source_dir = source_dirs[0]
                self.log(f"Found source directory: {source_dir}")

                # Check for required build tools
                if not shutil.which("make"):
                    self.log("❌ CRITICAL: 'make' command not found", force=True)
                    self.log(
                        "   Install Xcode Command Line Tools: xcode-select --install",
                        force=True,
                    )
                    return False

                if not shutil.which("g++") and not shutil.which("clang++"):
                    self.log("❌ CRITICAL: No C++ compiler found", force=True)
                    self.log(
                        "   Install Xcode Command Line Tools: xcode-select --install",
                        force=True,
                    )
                    return False

                # Build whisper.cpp
                self.log("Compiling whisper.cpp for macOS...")
                build_result = subprocess.run(
                    ["make", "-j", str(os.cpu_count() or 4)],
                    cwd=source_dir,
                    capture_output=True,
                    text=True,
                )

                if build_result.returncode != 0:
                    self.log("❌ CRITICAL: whisper.cpp compilation failed", force=True)
                    self.log(f"   Build stdout: {build_result.stdout}", force=True)
                    self.log(f"   Build stderr: {build_result.stderr}", force=True)
                    return False

                # Find the compiled binary - check in build directory
                build_dir = source_dir / "build" / "bin"
                possible_binaries = ["whisper-cli", "main", "whisper"]
                whisper_binary = None

                # First check in build/bin directory (modern CMake build)
                if build_dir.exists():
                    for binary_name in possible_binaries:
                        candidate = build_dir / binary_name
                        if candidate.exists() and candidate.is_file():
                            whisper_binary = candidate
                            self.log(f"Found compiled binary: build/bin/{binary_name}")
                            break

                # Fallback to root directory (old make builds)
                if not whisper_binary:
                    for binary_name in possible_binaries:
                        candidate = source_dir / binary_name
                        if candidate.exists() and candidate.is_file():
                            whisper_binary = candidate
                            self.log(f"Found compiled binary: {binary_name}")
                            break

                if not whisper_binary:
                    self.log(
                        "❌ CRITICAL: Compiled whisper binary not found", force=True
                    )
                    self.log(
                        f"   Checked for: {', '.join(possible_binaries)}", force=True
                    )
                    self.log(
                        f"   In directories: {source_dir}, {build_dir}", force=True
                    )
                    # List what binaries were actually created
                    if build_dir.exists():
                        binaries_found = [
                            f.name
                            for f in build_dir.iterdir()
                            if f.is_file() and f.stat().st_mode & 0o111
                        ]
                        self.log(
                            f"   Found build/bin executables: {binaries_found}",
                            force=True,
                        )
                    root_binaries = [
                        f.name
                        for f in source_dir.iterdir()
                        if f.is_file() and f.stat().st_mode & 0o111
                    ]
                    self.log(f"   Found root executables: {root_binaries}", force=True)
                    return False

                # Verify the binary works
                try:
                    test_result = subprocess.run(
                        [str(whisper_binary), "--help"],
                        capture_output=True,
                        text=True,
                        timeout=10,
                    )
                    if test_result.returncode != 0:
                        self.log(
                            "❌ CRITICAL: Compiled whisper binary doesn't work",
                            force=True,
                        )
                        return False
                except subprocess.TimeoutExpired:
                    self.log("❌ CRITICAL: Compiled whisper binary hangs", force=True)
                    return False

                # Create bin directory and copy binary
                self.bin_path.mkdir(parents=True, exist_ok=True)
                dest_path = self.bin_path / "whisper"

                shutil.copy2(whisper_binary, dest_path)
                dest_path.chmod(0o755)

                # Get binary info
                arch = self.detect_architecture()
                file_size = dest_path.stat().st_size // 1024

                self.log(f"✅ whisper.cpp compiled and installed successfully")
                self.log(f"   Binary: {dest_path} ({file_size}KB)")
                self.log(f"   Architecture: {arch}")
                return True

        except Exception as e:
            self.log(f"❌ CRITICAL: Error compiling whisper.cpp: {e}", force=True)
            return False

    def create_bundled_whisper_script(self) -> None:
        """Create setup script for bundled whisper.cpp binary."""
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
            self.log("❌ CRITICAL: This installer is for macOS only", force=True)
            return False

        self.log("Installing whisper.cpp binary for DMG distribution...")

        url, filename = self.get_whisper_cpp_source_url()

        if self.download_and_compile(url, filename):
            self.create_bundled_whisper_script()
            self.log("✅ whisper.cpp installation complete!")
            self.log(f"   Binary location: {self.bin_path / 'whisper'}")
            return True
        else:
            # Check if whisper.cpp is available via system installation
            import shutil

            system_whisper = shutil.which("whisper")
            if system_whisper:
                self.log(
                    "⚠️ Pre-built whisper.cpp not available, but found system installation"
                )
                self.log(f"   System whisper.cpp: {system_whisper}")
                # Create symlink or copy to app bundle
                import os

                try:
                    target_path = self.bin_path / "whisper"
                    os.makedirs(self.bin_path, exist_ok=True)
                    if os.path.exists(target_path):
                        os.remove(target_path)
                    shutil.copy2(system_whisper, target_path)
                    os.chmod(target_path, 0o755)
                    self.create_bundled_whisper_script()
                    self.log("✅ whisper.cpp copied from system installation")
                    return True
                except Exception as e:
                    self.log(f"❌ Failed to copy system whisper.cpp: {e}", force=True)

            self.log("❌ CRITICAL: whisper.cpp installation failed", force=True)
            self.log(
                "   Neither pre-built binaries nor system installation available",
                force=True,
            )
            self.log(
                "   Build terminated - whisper.cpp is a core requirement", force=True
            )
            return False  # Fail the build - no fallbacks allowed


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
