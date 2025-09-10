#!/usr/bin/env python3
"""Silent Pyannote model installer for .dmg build process.

This bundles the pyannote speaker-diarization model directly into the app
for internal company use where terms have been pre-accepted.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import urllib.request
from collections.abc import Callable
from pathlib import Path

# Model information
PYANNOTE_MODEL = "pyannote/speaker-diarization-3.1"

# Note: This bundling is for internal company use only where HuggingFace
# terms have been accepted on behalf of all users
BUNDLING_NOTE = """
This bundled model is for internal company use only.
Terms have been accepted by the organization administrator.
"""


class SilentPyannoteInstaller:
    """Install pyannote models silently for DMG bundling (internal use)."""

    def __init__(
        self,
        app_support_dir: Path | None = None,
        progress_callback: Callable[[str, int], None] | None = None,
        hf_token: str | None = None,
    ):
        """Initialize installer.

        Args:
            app_support_dir: Application support directory for model storage
            progress_callback: Callback for progress updates (message, percentage)
            hf_token: HuggingFace token for downloading models
        """
        if app_support_dir is None:
            # Default to user's app support
            app_support_dir = (
                Path.home() / "Library" / "Application Support" / "Knowledge_Chipper"
            )

        self.app_support_dir = Path(app_support_dir)
        self.models_dir = self.app_support_dir / "models" / "pyannote"
        self.progress_callback = progress_callback or (lambda msg, pct: None)
        self.hf_token = hf_token or os.environ.get("HF_TOKEN")

    def install(self) -> bool:
        """Copy pre-downloaded model from bundled_models or HF cache.

        Returns:
            True if successful, False otherwise
        """
        try:
            self.progress_callback("Preparing pyannote model for bundling...", 0)

            # Create model directory structure
            self.models_dir.mkdir(parents=True, exist_ok=True)

            # First, check for bundled models in the repo
            bundled_models_dir = (
                Path(__file__).parent.parent
                / "bundled_models"
                / "pyannote"
                / "speaker-diarization-3.1"
            )

            if bundled_models_dir.exists() and any(bundled_models_dir.glob("*.bin")):
                # Copy from bundled models directory
                self.progress_callback("Copying from bundled models directory...", 20)

                dest_dir = self.models_dir / "speaker-diarization-3.1"

                if dest_dir.exists():
                    shutil.rmtree(dest_dir)

                # Copy the entire model directory
                shutil.copytree(bundled_models_dir, dest_dir, symlinks=False)

                self.progress_callback("Model copied from bundled directory", 80)
            else:
                # Fall back to HuggingFace cache
                hf_cache = Path.home() / ".cache" / "huggingface" / "hub"
                model_id = PYANNOTE_MODEL.replace("/", "--")
                cached_models = (
                    list(hf_cache.glob(f"models--{model_id}*"))
                    if hf_cache.exists()
                    else []
                )

                if cached_models:
                    # Copy from HuggingFace cache
                    self.progress_callback("Copying from HuggingFace cache...", 20)

                    source_dir = cached_models[0]
                    dest_dir = self.models_dir / "speaker-diarization-3.1"

                    if dest_dir.exists():
                        shutil.rmtree(dest_dir)

                    # Copy the entire model directory
                    shutil.copytree(source_dir, dest_dir, symlinks=False)

                    self.progress_callback("Model copied from HF cache", 80)
                else:
                    # Create a marker file indicating model needs to be downloaded
                    marker_file = self.models_dir / "REQUIRES_DOWNLOAD.txt"
                    with open(marker_file, "w") as f:
                        f.write("Pyannote model not found in:\n")
                        f.write("1. bundled_models/pyannote/speaker-diarization-3.1/\n")
                        f.write("2. ~/.cache/huggingface/hub/\n\n")
                        f.write("Please run: scripts/prepare_bundled_models.sh\n")

                    self.progress_callback(
                        "Model not found - please run prepare_bundled_models.sh", 50
                    )
                    return False

            # Create bundling info file
            info_path = self.models_dir / "bundling_info.json"
            bundling_info = {
                "model_id": PYANNOTE_MODEL,
                "bundled_for": "internal_company_use",
                "note": BUNDLING_NOTE,
                "bundled_at": str(Path.cwd()),
                "version": "3.1",
            }

            with open(info_path, "w") as f:
                json.dump(bundling_info, f, indent=2)

            self.progress_callback("Pyannote model bundling complete!", 100)
            return True

        except Exception as e:
            self.progress_callback(f"Bundling failed: {e}", 0)
            return False


def install_pyannote_for_dmg(app_bundle_path: Path, quiet: bool = False) -> bool:
    """Install pyannote models into an app bundle during .dmg build.

    This is for internal company use where terms have been pre-accepted.

    Args:
        app_bundle_path: Path to the .app bundle being built
        quiet: If True, suppress all output except errors

    Returns:
        True if installation successful, False otherwise
    """
    try:
        # Calculate paths for app bundle
        contents_path = app_bundle_path / "Contents"
        macos_path = contents_path / "MacOS"

        # Create app support directory for models
        app_support_path = (
            macos_path / "Library" / "Application Support" / "Knowledge_Chipper"
        )

        def progress_func(message: str, percentage: int) -> None:
            if not quiet:
                print(f"[PYANNOTE] [{percentage:3d}%] {message}")

        # Get HF token from environment or credentials
        hf_token = os.environ.get("HF_TOKEN")
        if not hf_token:
            # Try to read from credentials.yaml if available
            cred_path = Path("config/credentials.yaml")
            if cred_path.exists():
                try:
                    import yaml

                    with open(cred_path) as f:
                        creds = yaml.safe_load(f) or {}
                    hf_token = creds.get("api_keys", {}).get("huggingface_token")
                except:
                    pass

        installer = SilentPyannoteInstaller(
            app_support_dir=app_support_path,
            progress_callback=progress_func,
            hf_token=hf_token,
        )

        success = installer.install()

        if success:
            if not quiet:
                print("✅ Pyannote model successfully bundled in app")
                print(f"   Location: {app_support_path / 'models' / 'pyannote'}")
                print("   Note: For internal company use only")

            # Create a setup script to configure the bundled model path
            setup_script = macos_path / "setup_bundled_pyannote.sh"
            with open(setup_script, "w") as f:
                f.write("#!/bin/bash\n")
                f.write("# Setup script for bundled pyannote model (internal use)\n")
                f.write(
                    f'export PYANNOTE_MODEL_PATH="{app_support_path / "models" / "pyannote"}"\n'
                )
                f.write('export PYANNOTE_BUNDLED="true"\n')
                f.write('export PYANNOTE_INTERNAL_USE="true"\n')
            setup_script.chmod(0o755)

            if not quiet:
                print(f"   Setup script: {setup_script}")
        else:
            print("⚠️  Pyannote model not found in cache", file=sys.stderr)
            print(
                "   Please run the app with diarization once to cache the model",
                file=sys.stderr,
            )
            print("   Then rebuild the DMG", file=sys.stderr)

        return success

    except Exception as e:
        print(f"❌ Error bundling pyannote model: {e}", file=sys.stderr)
        return False


def main() -> int:
    """CLI entry point for testing."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Bundle pyannote model for internal company DMG distribution"
    )
    parser.add_argument(
        "--app-bundle", type=Path, help="Path to .app bundle to install into"
    )
    parser.add_argument(
        "--quiet", "-q", action="store_true", help="Suppress output except errors"
    )

    args = parser.parse_args()

    if args.app_bundle:
        success = install_pyannote_for_dmg(args.app_bundle, args.quiet)
    else:
        # Test mode - install to current directory
        test_dir = Path("test_pyannote_bundle")
        test_dir.mkdir(exist_ok=True)

        def progress_func(msg: str, pct: int) -> None:
            print(f"[{pct:3d}%] {msg}")

        installer = SilentPyannoteInstaller(
            app_support_dir=test_dir, progress_callback=progress_func
        )
        success = installer.install()

        if success:
            print(f"\n✅ Test bundling successful in: {test_dir}")
            print("   Note: This is for internal company use only")
        else:
            print("\n⚠️  Model not cached - please run app with diarization first")

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
