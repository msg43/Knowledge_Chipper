#!/usr/bin/env python3
"""
Prepare Models for GitHub Release Hosting

Downloads all required models and packages them for GitHub release hosting.
This creates a reliable, fast alternative to direct HuggingFace/SpeechBrain downloads.
"""

import hashlib
import os
import shutil
import tarfile
import tempfile
import zipfile
from pathlib import Path

import requests


def download_with_progress(url: str, dest_path: Path, description: str = ""):
    """Download a file with progress bar."""
    print(f"📥 Downloading {description}...")
    print(f"   URL: {url}")
    print(f"   Destination: {dest_path}")

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

    print(f"✅ Downloaded: {dest_path.name} ({dest_path.stat().st_size:,} bytes)")
    return dest_path


def calculate_checksum(file_path: Path) -> str:
    """Calculate SHA256 checksum of a file."""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            sha256_hash.update(chunk)
    return sha256_hash.hexdigest()


def download_huggingface_model(repo_id: str, target_dir: Path, token: str = None):
    """Download a complete HuggingFace model repository."""
    try:
        from huggingface_hub import snapshot_download

        print(f"📦 Downloading HuggingFace model: {repo_id}")
        snapshot_download(
            repo_id=repo_id,
            local_dir=target_dir,
            local_dir_use_symlinks=False,
            token=token,
        )
        print(f"✅ HuggingFace model downloaded: {repo_id}")
        return True

    except ImportError:
        print(
            "❌ huggingface_hub not available. Install with: pip install huggingface_hub"
        )
        return False
    except Exception as e:
        print(f"❌ Error downloading {repo_id}: {e}")
        return False


def create_model_archive(source_dir: Path, archive_path: Path, format: str = "tar.gz"):
    """Create a compressed archive of a model directory."""
    print(f"📦 Creating {format} archive: {archive_path.name}")

    if format == "tar.gz":
        with tarfile.open(archive_path, "w:gz") as tar:
            tar.add(source_dir, arcname=source_dir.name)
    elif format == "zip":
        with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as zip_file:
            for file_path in source_dir.rglob("*"):
                if file_path.is_file():
                    arc_name = file_path.relative_to(source_dir.parent)
                    zip_file.write(file_path, arc_name)
    else:
        raise ValueError(f"Unsupported format: {format}")

    size_mb = archive_path.stat().st_size / (1024 * 1024)
    print(f"✅ Archive created: {archive_path.name} ({size_mb:.1f} MB)")
    return archive_path


def main():
    """Main function to prepare all models for GitHub hosting."""
    print("🎯 Preparing Models for GitHub Release Hosting")
    print("=" * 60)

    # Setup directories
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    models_prep_dir = project_root / "github_models_prep"

    # Clean and create prep directory
    if models_prep_dir.exists():
        shutil.rmtree(models_prep_dir)
    models_prep_dir.mkdir()

    print(f"📁 Preparation directory: {models_prep_dir}")

    # Get HF token if available
    hf_token = os.environ.get("HF_TOKEN")
    if not hf_token:
        print("⚠️  No HF_TOKEN found - some models may fail to download")

    # Track what we're creating
    model_info = {}

    # 1. Download Whisper model (direct download)
    print("\n🎤 1. Whisper Base Model")
    print("-" * 30)
    whisper_file = models_prep_dir / "whisper-base" / "ggml-base.bin"
    try:
        download_with_progress(
            "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.bin",
            whisper_file,
            "Whisper Base Model (ggml-base.bin)",
        )
        whisper_checksum = calculate_checksum(whisper_file)
        model_info["whisper-base"] = {
            "file": whisper_file.name,
            "size": whisper_file.stat().st_size,
            "sha256": whisper_checksum,
            "description": "Whisper Base Model for speech transcription",
        }
    except Exception as e:
        print(f"❌ Failed to download Whisper model: {e}")

    # 2. Download Pyannote model
    print("\n🎙️ 2. Pyannote Speaker Diarization")
    print("-" * 35)
    pyannote_dir = models_prep_dir / "pyannote-speaker-diarization-3.1"
    if download_huggingface_model(
        "pyannote/speaker-diarization-3.1", pyannote_dir, hf_token
    ):
        # Create archive
        pyannote_archive = models_prep_dir / "pyannote-speaker-diarization-3.1.tar.gz"
        create_model_archive(pyannote_dir, pyannote_archive)
        pyannote_checksum = calculate_checksum(pyannote_archive)
        model_info["pyannote-speaker-diarization"] = {
            "file": pyannote_archive.name,
            "size": pyannote_archive.stat().st_size,
            "sha256": pyannote_checksum,
            "description": "Pyannote speaker diarization model v3.1",
        }

    # 3. Download Wav2Vec2 model
    print("\n🗣️ 3. Wav2Vec2 Base Model")
    print("-" * 25)
    wav2vec2_dir = models_prep_dir / "wav2vec2-base-960h"
    if download_huggingface_model(
        "facebook/wav2vec2-base-960h", wav2vec2_dir, hf_token
    ):
        # Create archive
        wav2vec2_archive = models_prep_dir / "wav2vec2-base-960h.tar.gz"
        create_model_archive(wav2vec2_dir, wav2vec2_archive)
        wav2vec2_checksum = calculate_checksum(wav2vec2_archive)
        model_info["wav2vec2-base"] = {
            "file": wav2vec2_archive.name,
            "size": wav2vec2_archive.stat().st_size,
            "sha256": wav2vec2_checksum,
            "description": "Facebook Wav2Vec2 base model for voice features",
        }

    # 4. Download ECAPA-TDNN model
    print("\n🎯 4. ECAPA-TDNN Speaker Model")
    print("-" * 30)
    ecapa_dir = models_prep_dir / "spkrec-ecapa-voxceleb"
    if download_huggingface_model(
        "speechbrain/spkrec-ecapa-voxceleb", ecapa_dir, hf_token
    ):
        # Create archive
        ecapa_archive = models_prep_dir / "spkrec-ecapa-voxceleb.tar.gz"
        create_model_archive(ecapa_dir, ecapa_archive)
        ecapa_checksum = calculate_checksum(ecapa_archive)
        model_info["ecapa-tdnn"] = {
            "file": ecapa_archive.name,
            "size": ecapa_archive.stat().st_size,
            "sha256": ecapa_checksum,
            "description": "SpeechBrain ECAPA-TDNN speaker recognition model",
        }

    # 5. Download Whisper Large model
    print("\n🎤 5. Whisper Large Model")
    print("-" * 25)
    whisper_large_file = models_prep_dir / "whisper-large" / "ggml-large-v3.bin"
    try:
        download_with_progress(
            "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3.bin",
            whisper_large_file,
            "Whisper Large Model (ggml-large-v3.bin)",
        )
        whisper_large_checksum = calculate_checksum(whisper_large_file)
        model_info["whisper-large"] = {
            "file": whisper_large_file.name,
            "size": whisper_large_file.stat().st_size,
            "sha256": whisper_large_checksum,
            "description": "Whisper Large Model for best transcription quality",
        }
    except Exception as e:
        print(f"❌ Failed to download Whisper Large model: {e}")

    # 6. Download Ollama models
    print("\n🤖 6. Ollama 3.2-3B Model")
    print("-" * 25)
    ollama_3b_file = models_prep_dir / "ollama-3b" / "llama3.2-3b-instruct-q4_0.gguf"
    try:
        download_with_progress(
            "https://huggingface.co/bartowski/Llama-3.2-3B-Instruct-GGUF/resolve/main/Llama-3.2-3B-Instruct-Q4_0.gguf",
            ollama_3b_file,
            "Ollama 3.2-3B Model",
        )
        ollama_3b_checksum = calculate_checksum(ollama_3b_file)
        model_info["ollama-3b"] = {
            "file": ollama_3b_file.name,
            "size": ollama_3b_file.stat().st_size,
            "sha256": ollama_3b_checksum,
            "description": "Ollama 3.2-3B Instruct model for fast local LLM",
        }
    except Exception as e:
        print(f"❌ Failed to download Ollama 3B model: {e}")

    print("\n🤖 7. Ollama 3.2-30B Model")
    print("-" * 26)
    ollama_30b_file = models_prep_dir / "ollama-30b" / "llama3.2-30b-instruct-q4_0.gguf"
    try:
        download_with_progress(
            "https://huggingface.co/bartowski/Llama-3.2-30B-Instruct-GGUF/resolve/main/Llama-3.2-30B-Instruct-Q4_0.gguf",
            ollama_30b_file,
            "Ollama 3.2-30B Model",
        )
        ollama_30b_checksum = calculate_checksum(ollama_30b_file)
        model_info["ollama-30b"] = {
            "file": ollama_30b_file.name,
            "size": ollama_30b_file.stat().st_size,
            "sha256": ollama_30b_checksum,
            "description": "Ollama 3.2-30B Instruct model for best local LLM quality",
        }
    except Exception as e:
        print(f"❌ Failed to download Ollama 30B model: {e}")

    # 5. Create manifest file
    print("\n📋 5. Creating Model Manifest")
    print("-" * 30)
    manifest_file = models_prep_dir / "models_manifest.json"
    import json

    manifest = {
        "version": "1.0",
        "created": "2024-09-18",
        "description": "Skip the Podcast Desktop - Pre-bundled AI Models",
        "models": model_info,
        "total_size": sum(info["size"] for info in model_info.values()),
        "installation_notes": [
            "Extract archives to your app's models directory",
            "Verify checksums before use",
            "Models are ready for offline use",
        ],
    }

    with open(manifest_file, "w") as f:
        json.dump(manifest, f, indent=2)

    # 6. Create README for the release
    readme_content = f"""# Skip the Podcast Desktop - AI Models v1.0

This release contains pre-bundled AI models for Skip the Podcast Desktop, providing fast and reliable offline functionality.

## 📦 Included Models

### 🎤 Whisper Base Model
- **File:** `{model_info.get('whisper-base', {}).get('file', 'N/A')}`
- **Size:** {model_info.get('whisper-base', {}).get('size', 0) / (1024*1024):.1f} MB
- **Purpose:** Speech transcription
- **Source:** OpenAI Whisper (ggml format)

### 🎙️ Pyannote Speaker Diarization
- **File:** `{model_info.get('pyannote-speaker-diarization', {}).get('file', 'N/A')}`
- **Size:** {model_info.get('pyannote-speaker-diarization', {}).get('size', 0) / (1024*1024):.1f} MB
- **Purpose:** Speaker separation and identification
- **Source:** pyannote/speaker-diarization-3.1

### 🗣️ Wav2Vec2 Base Model
- **File:** `{model_info.get('wav2vec2-base', {}).get('file', 'N/A')}`
- **Size:** {model_info.get('wav2vec2-base', {}).get('size', 0) / (1024*1024):.1f} MB
- **Purpose:** Voice feature extraction
- **Source:** facebook/wav2vec2-base-960h

### 🎯 ECAPA-TDNN Speaker Model
- **File:** `{model_info.get('ecapa-tdnn', {}).get('file', 'N/A')}`
- **Size:** {model_info.get('ecapa-tdnn', {}).get('size', 0) / (1024*1024):.1f} MB
- **Purpose:** Speaker recognition and verification
- **Source:** speechbrain/spkrec-ecapa-voxceleb

## 📥 Installation

The Skip the Podcast Desktop app will automatically download these models from this GitHub release on first use. No manual installation required!

## 🔒 Verification

Each model includes SHA256 checksums in `models_manifest.json` for integrity verification.

## 📄 Licensing

All models retain their original licenses:
- Whisper: MIT License
- Pyannote: MIT License
- Wav2Vec2: CC-BY-NC 4.0
- ECAPA-TDNN: Apache 2.0

Total download size: **{sum(info['size'] for info in model_info.values()) / (1024*1024):.1f} MB**
"""

    readme_file = models_prep_dir / "README.md"
    with open(readme_file, "w") as f:
        f.write(readme_content)

    # Summary
    print("\n🎉 Model Preparation Complete!")
    print("=" * 50)
    print(f"📁 All files ready in: {models_prep_dir}")
    print(
        f"📦 Total size: {sum(info['size'] for info in model_info.values()) / (1024*1024):.1f} MB"
    )
    print(f"📄 Files prepared: {len(list(models_prep_dir.glob('*')))} files")

    print("\n📤 Next Steps:")
    print("1. Create a new GitHub release")
    print("2. Upload all files from the prep directory as release assets")
    print("3. Update download scripts to use GitHub URLs")
    print("4. Test the new download system")

    return True


if __name__ == "__main__":
    main()
