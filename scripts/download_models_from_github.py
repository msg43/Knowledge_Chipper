#!/usr/bin/env python3
"""
Download Models from GitHub Release

Fast, reliable model downloads from our GitHub release instead of external sources.
Includes fallback to original sources if GitHub download fails.
"""

import hashlib
import json
import os
import shutil
import tarfile
import tempfile
import zipfile
from pathlib import Path

import requests


def download_with_progress(
    url: str, dest_path: Path, description: str = "", expected_sha256: str = None
) -> bool:
    """Download a file with progress bar and optional checksum verification."""
    try:
        print(f"📥 Downloading {description}...")
        print(f"   Source: GitHub Release")

        response = requests.get(url, stream=True, timeout=30)
        response.raise_for_status()

        total_size = int(response.headers.get("content-length", 0))
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        with open(dest_path, "wb") as f:
            downloaded = 0
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size > 0:
                        percent = (downloaded / total_size) * 100
                        print(
                            f"\r   Progress: {percent:.1f}% ({downloaded:,}/{total_size:,} bytes)",
                            end="",
                        )
            print()  # New line after progress

        # Verify checksum if provided
        if expected_sha256:
            print("🔒 Verifying file integrity...")
            actual_sha256 = calculate_checksum(dest_path)
            if actual_sha256 != expected_sha256:
                print(f"❌ Checksum mismatch!")
                print(f"   Expected: {expected_sha256}")
                print(f"   Actual:   {actual_sha256}")
                dest_path.unlink()  # Remove corrupted file
                return False
            print("✅ File integrity verified")

        print(f"✅ Downloaded: {description} ({dest_path.stat().st_size:,} bytes)")
        return True

    except Exception as e:
        print(f"❌ Download failed: {e}")
        if dest_path.exists():
            dest_path.unlink()  # Clean up partial download
        return False


def calculate_checksum(file_path: Path) -> str:
    """Calculate SHA256 checksum of a file."""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            sha256_hash.update(chunk)
    return sha256_hash.hexdigest()


def extract_archive(archive_path: Path, extract_to: Path) -> bool:
    """Extract a tar.gz or zip archive."""
    try:
        print(f"📦 Extracting {archive_path.name}...")

        if archive_path.suffix == ".gz" and archive_path.stem.endswith(".tar"):
            # tar.gz file
            with tarfile.open(archive_path, "r:gz") as tar:
                tar.extractall(extract_to)
        elif archive_path.suffix == ".zip":
            # zip file
            with zipfile.ZipFile(archive_path, "r") as zip_file:
                zip_file.extractall(extract_to)
        else:
            print(f"❌ Unsupported archive format: {archive_path}")
            return False

        print(f"✅ Extracted to: {extract_to}")
        return True

    except Exception as e:
        print(f"❌ Extraction failed: {e}")
        return False


class GitHubModelDownloader:
    """Download models from GitHub releases with fallback to original sources."""

    # GitHub release configuration
    GITHUB_REPO = "matthewgreer/Knowledge_Chipper"  # Update with your repo
    RELEASE_TAG = "models-v1.0"  # Update with your release tag
    BASE_URL = f"https://github.com/{GITHUB_REPO}/releases/download/{RELEASE_TAG}"

    # Model configurations with tiers
    MODELS = {
        "whisper-base": {
            "github_file": "ggml-base.bin",
            "github_url": f"{BASE_URL}/ggml-base.bin",
            "fallback_url": "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.bin",
            "local_path": "models/whisper/ggml-base.bin",
            "description": "Whisper Base Model (Fast, Good Quality)",
            "tier": "base",
            "size_mb": 141,
            "required": True,
        },
        "whisper-large": {
            "github_file": "ggml-large-v3.bin",
            "github_url": f"{BASE_URL}/ggml-large-v3.bin",
            "fallback_url": "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3.bin",
            "local_path": "models/whisper/ggml-large-v3.bin",
            "description": "Whisper Large Model (Best Quality)",
            "tier": "premium",
            "size_mb": 1550,
            "required": False,
        },
        "ollama-3b": {
            "github_file": "llama3.2-3b-instruct-q4_0.gguf",
            "github_url": f"{BASE_URL}/llama3.2-3b-instruct-q4_0.gguf",
            "fallback_url": "https://huggingface.co/bartowski/Llama-3.2-3B-Instruct-GGUF/resolve/main/Llama-3.2-3B-Instruct-Q4_0.gguf",
            "local_path": "models/ollama/llama3.2-3b-instruct-q4_0.gguf",
            "description": "Ollama 3.2-3B (Fast Local LLM)",
            "tier": "base",
            "size_mb": 1700,
            "required": True,
        },
        "ollama-30b": {
            "github_file": "llama3.2-30b-instruct-q4_0.gguf",
            "github_url": f"{BASE_URL}/llama3.2-30b-instruct-q4_0.gguf",
            "fallback_url": "https://huggingface.co/bartowski/Llama-3.2-30B-Instruct-GGUF/resolve/main/Llama-3.2-30B-Instruct-Q4_0.gguf",
            "local_path": "models/ollama/llama3.2-30b-instruct-q4_0.gguf",
            "description": "Ollama 3.2-30B (Best Local LLM)",
            "tier": "premium",
            "size_mb": 17000,
            "required": False,
        },
        "wav2vec2-base": {
            "github_file": "wav2vec2-base-960h.tar.gz",
            "github_url": f"{BASE_URL}/wav2vec2-base-960h.tar.gz",
            "local_path": "models/wav2vec2",
            "description": "Wav2Vec2 Base Model (Voice Features)",
            "tier": "base",
            "size_mb": 631,
            "extract": True,
            "required": True,
            "fallback_hf_repo": "facebook/wav2vec2-base-960h",
        },
        "ecapa-tdnn": {
            "github_file": "spkrec-ecapa-voxceleb.tar.gz",
            "github_url": f"{BASE_URL}/spkrec-ecapa-voxceleb.tar.gz",
            "local_path": "models/speechbrain",
            "description": "ECAPA-TDNN Speaker Model (Voice ID)",
            "tier": "base",
            "size_mb": 79,
            "extract": True,
            "required": True,
            "fallback_hf_repo": "speechbrain/spkrec-ecapa-voxceleb",
        },
        "pyannote-diarization": {
            "github_file": "pyannote-speaker-diarization-3.1.tar.gz",
            "github_url": f"{BASE_URL}/pyannote-speaker-diarization-3.1.tar.gz",
            "local_path": "models/pyannote",
            "description": "Pyannote Speaker Diarization (Who Spoke When)",
            "tier": "base",
            "size_mb": 400,
            "extract": True,
            "required": True,
            "fallback_hf_repo": "pyannote/speaker-diarization-3.1",
        },
    }

    def __init__(self, app_bundle_path: Path):
        self.app_bundle_path = Path(app_bundle_path)
        self.models_dir = self.app_bundle_path / "Contents" / "Resources" / "models"
        self.models_dir.mkdir(parents=True, exist_ok=True)

        # Load manifest if available
        self.manifest = self._load_manifest()

    def _load_manifest(self) -> dict:
        """Load the models manifest from GitHub for checksums."""
        try:
            manifest_url = f"{self.BASE_URL}/models_manifest.json"
            response = requests.get(manifest_url, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception:
            print("⚠️  Could not load models manifest - proceeding without checksums")
            return {}

    def download_model(self, model_name: str, force: bool = False) -> bool:
        """Download a specific model from GitHub with fallback."""
        if model_name not in self.MODELS:
            print(f"❌ Unknown model: {model_name}")
            return False

        model_config = self.MODELS[model_name]
        local_path = self.models_dir / model_config["local_path"]

        # Check if already exists
        if not force and local_path.exists():
            print(f"✅ {model_config['description']} already exists")
            return True

        print(f"\n🎯 {model_config['description']}")
        print("-" * 50)

        # Get checksum from manifest
        expected_checksum = None
        if self.manifest and model_name in self.manifest.get("models", {}):
            expected_checksum = self.manifest["models"][model_name].get("sha256")

        # Try GitHub download first
        success = self._try_github_download(model_name, model_config, expected_checksum)

        # Fallback to original source if GitHub fails
        if not success:
            print("🔄 Falling back to original source...")
            success = self._try_fallback_download(model_name, model_config)

        if success:
            print(f"✅ {model_config['description']} ready for use")
        else:
            print(f"❌ Failed to download {model_config['description']}")

        return success

    def _try_github_download(
        self, model_name: str, config: dict, expected_checksum: str = None
    ) -> bool:
        """Try downloading from GitHub release."""
        try:
            if config.get("extract"):
                # Download archive to temp location
                with tempfile.NamedTemporaryFile(
                    suffix=".tar.gz", delete=False
                ) as tmp_file:
                    tmp_path = Path(tmp_file.name)

                if download_with_progress(
                    config["github_url"],
                    tmp_path,
                    config["description"],
                    expected_checksum,
                ):
                    # Extract to target location
                    target_path = self.models_dir / config["local_path"]
                    target_path.parent.mkdir(parents=True, exist_ok=True)

                    if extract_archive(tmp_path, target_path.parent):
                        tmp_path.unlink()  # Clean up temp file
                        return True

                # Clean up on failure
                if tmp_path.exists():
                    tmp_path.unlink()
                return False
            else:
                # Direct file download
                target_path = self.models_dir / config["local_path"]
                return download_with_progress(
                    config["github_url"],
                    target_path,
                    config["description"],
                    expected_checksum,
                )

        except Exception as e:
            print(f"❌ GitHub download failed: {e}")
            return False

    def _try_fallback_download(self, model_name: str, config: dict) -> bool:
        """Fallback to original HuggingFace/direct download."""
        try:
            if "fallback_url" in config:
                # Direct URL fallback (like Whisper)
                target_path = self.models_dir / config["local_path"]
                return download_with_progress(
                    config["fallback_url"],
                    target_path,
                    f"{config['description']} (fallback)",
                )

            elif "fallback_hf_repo" in config:
                # HuggingFace repo fallback
                print(f"📦 Downloading from HuggingFace: {config['fallback_hf_repo']}")
                try:
                    from huggingface_hub import snapshot_download

                    target_path = self.models_dir / config["local_path"]
                    target_path.mkdir(parents=True, exist_ok=True)

                    snapshot_download(
                        repo_id=config["fallback_hf_repo"],
                        local_dir=target_path,
                        local_dir_use_symlinks=False,
                        token=os.environ.get("HF_TOKEN"),
                    )

                    print(
                        f"✅ Downloaded from HuggingFace: {config['fallback_hf_repo']}"
                    )
                    return True

                except ImportError:
                    print("❌ huggingface_hub not available for fallback")
                    return False
                except Exception as e:
                    print(f"❌ HuggingFace fallback failed: {e}")
                    return False

            else:
                print("❌ No fallback method configured")
                return False

        except Exception as e:
            print(f"❌ Fallback download failed: {e}")
            return False

    def download_tier(self, tier: str = "base", force: bool = False) -> bool:
        """Download models for a specific tier (base or premium)."""
        tier_models = [
            name
            for name, config in self.MODELS.items()
            if config.get("tier") == tier or config.get("required", False)
        ]

        if not tier_models:
            print(f"❌ No models found for tier: {tier}")
            return False

        # Calculate total size
        total_size = sum(self.MODELS[name].get("size_mb", 0) for name in tier_models)

        print(f"🚀 Downloading {tier.title()} Tier AI Models")
        print("=" * 60)
        print(f"📦 Package: {tier.title()} Quality")
        print(f"📏 Total Size: ~{total_size:,} MB ({total_size/1024:.1f} GB)")
        print(f"🎯 Models: {len(tier_models)} models")
        print()

        # Show what's included
        for model_name in tier_models:
            config = self.MODELS[model_name]
            print(f"   • {config['description']} - {config.get('size_mb', '?')} MB")
        print()

        success_count = 0
        for model_name in tier_models:
            if self.download_model(model_name, force):
                success_count += 1

        print(f"\n📊 Download Summary")
        print("-" * 30)
        print(f"✅ Successful: {success_count}/{len(tier_models)}")

        if success_count == len(tier_models):
            print(f"🎉 {tier.title()} tier models ready for offline use!")
            return True
        else:
            print("⚠️  Some models failed to download")
            return False

    def download_all_models(self, force: bool = False) -> bool:
        """Download all required models."""
        print("🚀 Downloading AI Models from GitHub Release")
        print("=" * 60)

        success_count = 0
        total_count = len(self.MODELS)

        for model_name in self.MODELS:
            if self.download_model(model_name, force):
                success_count += 1

        print(f"\n📊 Download Summary")
        print("-" * 30)
        print(f"✅ Successful: {success_count}/{total_count}")

        if success_count == total_count:
            print("🎉 All models ready for offline use!")
            return True
        else:
            print("⚠️  Some models failed to download")
            print("   App will attempt runtime downloads for missing models")
            return False

    def get_tier_info(self) -> dict:
        """Get information about available tiers."""
        tiers = {}
        for name, config in self.MODELS.items():
            tier = config.get("tier", "base")
            if tier not in tiers:
                tiers[tier] = {"models": [], "total_size_mb": 0, "description": ""}

            tiers[tier]["models"].append(
                {
                    "name": name,
                    "description": config["description"],
                    "size_mb": config.get("size_mb", 0),
                }
            )
            tiers[tier]["total_size_mb"] += config.get("size_mb", 0)

        # Add descriptions
        tiers["base"][
            "description"
        ] = "Fast downloads, good quality - perfect for most users"
        tiers["premium"][
            "description"
        ] = "Larger downloads, best quality - for power users"

        return tiers


def main():
    """Main function for command-line usage."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Download AI models from GitHub release"
    )
    parser.add_argument(
        "--app-bundle", type=Path, required=True, help="Path to the app bundle"
    )
    parser.add_argument(
        "--model",
        type=str,
        choices=GitHubModelDownloader.MODELS.keys(),
        help="Download a specific model",
    )
    parser.add_argument(
        "--tier",
        type=str,
        choices=["base", "premium"],
        help="Download models for a specific tier (base or premium)",
    )
    parser.add_argument(
        "--info",
        action="store_true",
        help="Show information about available tiers and models",
    )
    parser.add_argument(
        "--force", action="store_true", help="Force re-download even if model exists"
    )

    args = parser.parse_args()

    if not args.app_bundle.exists():
        print(f"❌ App bundle not found: {args.app_bundle}")
        return 1

    downloader = GitHubModelDownloader(args.app_bundle)

    if args.info:
        # Show tier information
        print("🎯 Available Model Tiers")
        print("=" * 50)
        tiers = downloader.get_tier_info()

        for tier_name, tier_info in tiers.items():
            print(f"\n📦 {tier_name.title()} Tier")
            print(f"   {tier_info['description']}")
            print(
                f"   Total Size: {tier_info['total_size_mb']:,} MB ({tier_info['total_size_mb']/1024:.1f} GB)"
            )
            print("   Models:")
            for model in tier_info["models"]:
                print(f"     • {model['description']} - {model['size_mb']} MB")

        return 0

    if args.model:
        success = downloader.download_model(args.model, args.force)
    elif args.tier:
        success = downloader.download_tier(args.tier, args.force)
    else:
        # Default to base tier for bundling
        success = downloader.download_tier("base", args.force)

    return 0 if success else 1


if __name__ == "__main__":
    exit(main())
