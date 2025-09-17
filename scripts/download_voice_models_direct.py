#!/usr/bin/env python3
"""
Download Voice Fingerprinting Models for DMG Bundle

This script downloads Wav2Vec2 and ECAPA-TDNN models directly into the app
bundle for offline voice fingerprinting with 97% accuracy.
"""

import os
import subprocess
import sys
from pathlib import Path


def download_huggingface_model(
    model_name: str, target_dir: Path, token: str | None = None
) -> bool:
    """Download a model from Hugging Face."""
    try:
        from huggingface_hub import snapshot_download

        print(f"📥 Downloading {model_name}...")

        # Download with token if provided
        snapshot_download(
            repo_id=model_name,
            cache_dir=target_dir,
            token=token,
            local_files_only=False,
        )

        print(f"✅ {model_name} downloaded successfully")
        return True

    except ImportError:
        print(
            "❌ huggingface_hub not available. "
            "Install with: pip install huggingface_hub"
        )
        return False
    except Exception as e:
        print(f"❌ Error downloading {model_name}: {e}")
        return False


def download_speechbrain_model(
    model_name: str, target_dir: Path, python_executable: str = None
) -> bool:
    """Download a SpeechBrain model using the specified Python environment."""
    try:
        # Ensure the target directory exists
        target_dir.mkdir(parents=True, exist_ok=True)

        # Use the provided Python executable or fall back to system Python
        if python_executable is None:
            python_executable = sys.executable

        # Create a temporary Python script to download the model
        temp_script = target_dir / "download_speechbrain.py"

        script_content = f"""
import os
import sys
from pathlib import Path

# Set cache directory
cache_dir = Path("{target_dir}") / "speechbrain"
model_dir = cache_dir / "{model_name.split('/')[-1]}"
os.environ["SPEECHBRAIN_CACHE"] = str(cache_dir)

try:
    from huggingface_hub import hf_hub_download

    print("📥 Downloading {model_name} files manually...")

    # List of required model files
    required_files = [
        'embedding_model.ckpt',
        'classifier.ckpt',
        'label_encoder.txt',
        'mean_var_norm_emb.ckpt',
        'hyperparams.yaml',
        'config.json'
    ]

    # Create model directory
    model_dir.mkdir(parents=True, exist_ok=True)

    # Download each required file
    for filename in required_files:
        print(f"  Downloading {{filename}}...")
        try:
            downloaded_path = hf_hub_download(
                repo_id="{model_name}",
                filename=filename,
                cache_dir=str(cache_dir.parent),
                local_dir=str(model_dir),
                local_dir_use_symlinks=False
            )
            print(f"  ✓ {{filename}} downloaded to {{downloaded_path}}")
        except Exception as e:
            print(f"  ❌ Failed to download {{filename}}: {{e}}")
            sys.exit(1)

    print("✅ {model_name} downloaded successfully")

    # Verify all files exist with correct sizes
    missing_files = []
    empty_files = []
    for filename in required_files:
        file_path = model_dir / filename
        if not file_path.exists():
            missing_files.append(filename)
        elif file_path.stat().st_size == 0:
            empty_files.append(filename)
        else:
            print(f"  ✓ {{filename}} verified ({{file_path.stat().st_size}} bytes)")  # noqa: E501

    critical_errors = missing_files + empty_files
    if critical_errors:
        print(f"❌ CRITICAL ERROR: Invalid model files:")
        if missing_files:
            print(f"  Missing files: {{missing_files}}")
        if empty_files:
            print(f"  Empty files: {{empty_files}}")
        print(f"❌ SpeechBrain model download FAILED - core files missing or corrupt")  # noqa: E501
        print(f"   Build must terminate - ALL files are required for voice fingerprinting")  # noqa: E501
        sys.exit(1)
    else:
        print(f"✓ All model files verified in: {{model_dir}}")
        print(f"✓ Model ready for use")

except Exception as e:
    print(f"❌ Error downloading {model_name}: {{e}}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
"""

        with open(temp_script, "w") as f:
            f.write(script_content)

        # Run the script with the specified Python environment

        result = subprocess.run(
            [python_executable, str(temp_script)], capture_output=True, text=True
        )

        # Clean up
        temp_script.unlink()

        if result.returncode == 0:
            print(f"✅ {model_name} downloaded successfully")
            return True
        else:
            print(f"❌ Error downloading {model_name}: {result.stderr}")
            if result.stderr:
                print(f"   stderr: {result.stderr}")
            if result.stdout:
                print(f"   stdout: {result.stdout}")
            return False

    except Exception as e:
        print(f"❌ Error downloading {model_name}: {e}")
        return False


def download_voice_models_for_dmg(
    app_bundle_path: Path, hf_token: str | None = None
) -> bool:
    """
    Download voice fingerprinting models directly into the app bundle.

    Args:
        app_bundle_path: Path to the app bundle
        hf_token: Optional Hugging Face token

    Returns:
        True if successful, False otherwise
    """
    print("🎙️ Downloading voice fingerprinting models for DMG bundle...")

    # Create voice models directory in app bundle
    macos_path = app_bundle_path / "Contents" / "MacOS"
    voice_models_dir = macos_path / ".cache" / "knowledge_chipper" / "voice_models"
    voice_models_dir.mkdir(parents=True, exist_ok=True)

    # Get the app bundle's Python executable (required for SpeechBrain)
    app_python_bin = macos_path / "venv" / "bin" / "python"
    if not app_python_bin.exists():
        print(
            f"❌ CRITICAL: App bundle Python environment not found at "
            f"{app_python_bin}"
        )
        print("   Cannot download SpeechBrain models without app bundle " "environment")
        return False

    success_count = 0
    total_models = 2

    # 1. Download Wav2Vec2 model (Facebook)
    wav2vec2_dir = voice_models_dir / "wav2vec2"
    if download_huggingface_model(
        "facebook/wav2vec2-base-960h", wav2vec2_dir, hf_token
    ):
        success_count += 1

    # 2. Download ECAPA-TDNN model (SpeechBrain) - REQUIRES app bundle Python
    ecapa_dir = voice_models_dir / "speechbrain"
    if download_speechbrain_model(
        "speechbrain/spkrec-ecapa-voxceleb", ecapa_dir, str(app_python_bin)
    ):
        success_count += 1

    # Create voice models setup script
    setup_script = macos_path / "setup_voice_models.sh"
    setup_content = """#!/bin/bash
# Set up environment for bundled voice models

APP_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Voice models cache
VOICE_CACHE="$APP_DIR/.cache/knowledge_chipper/voice_models"
export VOICE_MODELS_CACHE="$VOICE_CACHE"
export HF_HOME="$VOICE_CACHE/wav2vec2"
export SPEECHBRAIN_CACHE="$VOICE_CACHE/speechbrain"

# Let the app know voice models are bundled
export VOICE_MODELS_BUNDLED="true"

# Set voice fingerprinting as default enabled
export VOICE_FINGERPRINTING_ENABLED="true"
"""

    with open(setup_script, "w") as f:
        f.write(setup_content)

    setup_script.chmod(0o755)

    # Update the main setup script to include voice models
    main_setup_script = macos_path / "setup_bundled_models.sh"
    if main_setup_script.exists():
        with open(main_setup_script, "a") as f:
            f.write("\n# Voice fingerprinting models\n")
            f.write('source "$APP_DIR/setup_voice_models.sh"\n')

    # Calculate approximate sizes
    total_size_mb = 0
    if (voice_models_dir / "wav2vec2").exists():
        total_size_mb += 360  # Approximate Wav2Vec2 size
    if (voice_models_dir / "speechbrain").exists():
        total_size_mb += 45  # Approximate ECAPA-TDNN size

    if success_count == total_models:
        print(
            f"✅ All voice fingerprinting models downloaded successfully "
            f"(~{total_size_mb}MB)"
        )
        print("🎯 97% accuracy voice fingerprinting will be available offline")
        return True
    else:
        print(
            f"❌ CRITICAL: Voice model download failed "
            f"({success_count}/{total_models} models)"
        )
        print("   All voice models are required for core functionality")
        print("   Build terminated - all dependencies must succeed")
        return False


def install_voice_dependencies_in_bundle(app_bundle_path: Path) -> bool:
    """Install voice fingerprinting dependencies in the app bundle."""
    try:
        macos_path = app_bundle_path / "Contents" / "MacOS"
        python_bin = macos_path / "venv" / "bin" / "python"

        if not python_bin.exists():
            print("❌ CRITICAL: Python environment not found in app bundle")
            print(f"   Expected: {python_bin}")
            print("   Cannot install voice fingerprinting dependencies")
            return False

        print("📦 Installing voice fingerprinting dependencies...")

        # Voice fingerprinting requirements (most already installed via
        # diarization)
        # Format: (import_name, package_name, version)
        voice_requirements = [
            ("librosa", "librosa", ">=0.10.0"),
            ("torch", "torch", ">=2.0.0"),
            ("torchaudio", "torchaudio", ">=2.0.0"),
            ("transformers", "transformers", ">=4.35.0"),
            ("speechbrain", "speechbrain", ">=0.5.0"),
            ("sklearn", "scikit-learn", ">=1.3.0"),
            ("soundfile", "soundfile", ">=0.12.0"),
            ("huggingface_hub", "huggingface_hub", ">=0.16.0"),
        ]

        failed_deps = []

        for import_name, package_name, version in voice_requirements:
            # First check if package is already installed
            check_result = subprocess.run(
                [
                    str(python_bin),
                    "-c",
                    f"import {import_name}; "
                    f"print(f'{package_name} already available')",
                ],
                capture_output=True,
                text=True,
            )

            if check_result.returncode == 0:
                print(f"  ✅ {package_name} already available")
                continue

            # Install if not available
            requirement = f"{package_name}{version}"
            print(f"  Installing {requirement}...")
            result = subprocess.run(
                [
                    str(python_bin),
                    "-m",
                    "pip",
                    "install",
                    requirement,
                    "--quiet",
                    "--no-warn-script-location",
                ],
                capture_output=True,
                text=True,
            )

            if result.returncode != 0:
                print(f"❌ Failed to install {requirement}")
                stderr_output = result.stderr.strip()
                if "externally-managed-environment" in stderr_output:
                    print(
                        "   Error: Using wrong Python environment "
                        "(system instead of app bundle)"
                    )
                    print("   This indicates the venv is misconfigured")
                else:
                    print(f"   Error: {stderr_output}")
                failed_deps.append(requirement)

        if failed_deps:
            print(
                f"❌ CRITICAL: Failed to install {len(failed_deps)}/"
                f"{len(voice_requirements)} voice dependencies:"
            )
            for dep in failed_deps:
                print(f"   - {dep}")
            print("   Voice fingerprinting will not work offline")
            return False

        print("✅ Voice fingerprinting dependencies installed successfully")
        return True

    except Exception as e:
        print(f"❌ CRITICAL: Error installing voice dependencies: {e}")
        return False


def main():
    """Main function for command-line usage."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Download voice fingerprinting models for DMG bundle"
    )
    parser.add_argument(
        "--app-bundle", type=Path, required=True, help="Path to the app bundle"
    )
    parser.add_argument(
        "--hf-token", type=str, help="HuggingFace token for model downloads"
    )
    parser.add_argument(
        "--install-deps",
        action="store_true",
        help="Install voice fingerprinting dependencies",
    )

    args = parser.parse_args()

    if not args.app_bundle.exists():
        print(f"❌ App bundle not found: {args.app_bundle}")
        sys.exit(1)

    # Get HF token from environment if not provided
    hf_token = args.hf_token or os.environ.get("HF_TOKEN")

    # Process arguments and call main function

    # Install dependencies if requested
    if args.install_deps:
        if not install_voice_dependencies_in_bundle(args.app_bundle):
            print("❌ CRITICAL: Voice dependency installation failed")
            print("   Build must terminate - all dependencies must succeed")
            sys.exit(1)

    # Download models
    if not download_voice_models_for_dmg(args.app_bundle, hf_token):
        print("❌ CRITICAL: Voice model download failed")
        print("   Build must terminate - all models must be bundled")
        sys.exit(1)

    print("🎉 Voice fingerprinting models ready for DMG bundle!")
    print("   Users will have 97% accuracy voice matching out of the box")
    sys.exit(0)


if __name__ == "__main__":
    main()
