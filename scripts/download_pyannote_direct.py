#!/usr/bin/env python3
"""Direct pyannote model downloader for DMG build process.
Downloads directly during build - no pre-caching needed.
"""

import os
import shutil
import sys
import tempfile
from pathlib import Path


def download_pyannote_for_dmg(app_bundle_path: Path, hf_token: str = None) -> bool:
    """Download pyannote model directly into DMG during build.

    This eliminates the need for pre-caching or bundled_models directory.
    """
    try:
        from huggingface_hub import snapshot_download

        print("📥 Downloading pyannote model directly for DMG...")

        # Get token from environment or parameter
        token = hf_token or os.environ.get("HF_TOKEN")
        if not token:
            # Try credentials file
            cred_path = Path("config/credentials.yaml")
            if cred_path.exists():
                try:
                    import yaml

                    with open(cred_path) as f:
                        creds = yaml.safe_load(f) or {}
                    token = creds.get("api_keys", {}).get("huggingface_token")
                except:
                    pass

        if not token or token == "your_huggingface_token_here":
            print("❌ No HuggingFace token found!")
            print("   Set HF_TOKEN env var or add to config/credentials.yaml")
            return False

        # Calculate destination in app bundle
        contents_path = app_bundle_path / "Contents"
        macos_path = contents_path / "MacOS"
        models_dir = (
            macos_path
            / "Library"
            / "Application Support"
            / "Knowledge_Chipper"
            / "models"
            / "pyannote"
        )
        models_dir.mkdir(parents=True, exist_ok=True)

        # Download directly to app bundle
        model_path = models_dir / "speaker-diarization-3.1"

        print(f"⬇️  Downloading to: {model_path}")
        print("   This is a one-time ~400MB download...")

        # Download the model
        snapshot_download(
            repo_id="pyannote/speaker-diarization-3.1",
            token=token,
            local_dir=model_path,
            local_dir_use_symlinks=False,
            ignore_patterns=["*.md", "*.txt", ".git*"],
        )

        print("✅ Pyannote model downloaded successfully!")

        # Create setup script
        setup_script = macos_path / "setup_bundled_pyannote.sh"
        with open(setup_script, "w") as f:
            f.write("#!/bin/bash\n")
            f.write("# Setup script for bundled pyannote model\n")
            f.write(f'export PYANNOTE_MODEL_PATH="{models_dir}"\n')
            f.write('export PYANNOTE_BUNDLED="true"\n')
            f.write('export PYANNOTE_INTERNAL_USE="true"\n')
        setup_script.chmod(0o755)

        # Create info file
        import json

        info_path = models_dir / "bundling_info.json"
        with open(info_path, "w") as f:
            json.dump(
                {
                    "model_id": "pyannote/speaker-diarization-3.1",
                    "bundled_for": "internal_company_use",
                    "downloaded_during_build": True,
                },
                f,
                indent=2,
            )

        return True

    except ImportError:
        print("❌ huggingface_hub not installed!")
        print("   Run: pip install huggingface_hub")
        return False
    except Exception as e:
        print(f"❌ Download failed: {e}")
        return False


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Download pyannote model directly during DMG build"
    )
    parser.add_argument(
        "--app-bundle", type=Path, required=True, help="Path to .app bundle"
    )
    parser.add_argument("--token", help="HuggingFace token (or use HF_TOKEN env var)")

    args = parser.parse_args()

    success = download_pyannote_for_dmg(args.app_bundle, args.token)
    sys.exit(0 if success else 1)
