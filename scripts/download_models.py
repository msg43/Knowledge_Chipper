#!/usr/bin/env python3
"""
Download Models Script

Downloads all required models for Knowledge_Chipper to avoid delays during processing.
Can be run standalone after installation.
"""

import argparse
import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from knowledge_system.logger import get_logger

logger = get_logger(__name__)


def download_whisper_model(model_name: str = "base") -> bool:
    """Download Whisper.cpp model."""
    try:
        print(f"\n🎤 Downloading Whisper {model_name} model...")
        from knowledge_system.processors.whisper_cpp_transcribe import (
            WhisperCppTranscribeProcessor,
        )

        processor = WhisperCppTranscribeProcessor(model=model_name)
        model_path = processor._download_model(model_name)

        if model_path.exists():
            print(f"✅ Whisper {model_name} model downloaded to: {model_path}")
            return True
        else:
            print(f"❌ Failed to download Whisper {model_name} model")
            return False

    except Exception as e:
        print(f"❌ Error downloading Whisper model: {e}")
        return False


def download_diarization_model() -> bool:
    """Download Pyannote diarization model."""
    try:
        print("\n🎙️ Downloading speaker diarization model...")
        print("This requires a HuggingFace token and may take several minutes...")

        from knowledge_system.utils.model_downloader import (
            check_diarization_model_status,
            pre_download_diarization_model,
        )

        # Check status first
        status = check_diarization_model_status()
        if status.get("is_cached"):
            print("✅ Diarization model already downloaded")
            return True

        if not status.get("has_hf_token"):
            print("❌ No HuggingFace token found")
            print("   1. Get a token from: https://huggingface.co/settings/tokens")
            print(
                "   2. Accept the license at: https://huggingface.co/pyannote/speaker-diarization"
            )
            print("   3. Add your token to config/credentials.yaml")
            return False

        if not status.get("dependencies_installed"):
            print("❌ Diarization dependencies not installed")
            print("   Run: pip install -e '.[diarization]'")
            return False

        # Download the model
        def progress_callback(msg, percent=0):
            print(f"   {msg}")

        success = pre_download_diarization_model(progress_callback)

        if success:
            print("✅ Diarization model downloaded successfully")
        else:
            print("❌ Failed to download diarization model")
            print("   Check the error messages above")

        return success

    except ImportError:
        print("❌ Diarization dependencies not installed")
        print("   Run: pip install -e '.[diarization]'")
        return False
    except Exception as e:
        print(f"❌ Error downloading diarization model: {e}")
        return False


def download_ollama_model(model_name: str = "llama3.2:3b") -> bool:
    """Download Ollama model."""
    try:
        print(f"\n🤖 Downloading Ollama {model_name} model...")

        from knowledge_system.utils.ollama_manager import get_ollama_manager

        manager = get_ollama_manager()

        # Check if Ollama is installed
        if not manager.is_installed()[0]:
            print("❌ Ollama is not installed")
            print("   Run the setup.sh script or install manually:")
            print("   brew install ollama")
            return False

        # Check if service is running
        if not manager.is_service_running():
            print("Starting Ollama service...")
            success, msg = manager.start_service()
            if not success:
                print(f"❌ Failed to start Ollama: {msg}")
                return False

        # Check if model exists
        if manager.model_exists(model_name):
            print(f"✅ Ollama {model_name} model already downloaded")
            return True

        # Download the model
        print(f"Downloading {model_name} (this may take a while)...")

        def progress_callback(progress):
            if hasattr(progress, "status"):
                print(f"   {progress.status}")

        success = manager.download_model(model_name, progress_callback)

        if success:
            print(f"✅ Ollama {model_name} model downloaded successfully")
        else:
            print(f"❌ Failed to download Ollama {model_name} model")

        return success

    except Exception as e:
        print(f"❌ Error downloading Ollama model: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Download all required models for Knowledge_Chipper"
    )
    parser.add_argument(
        "--whisper-model",
        default="base",
        choices=["tiny", "base", "small", "medium", "large"],
        help="Whisper model size to download (default: base)",
    )
    parser.add_argument(
        "--skip-whisper", action="store_true", help="Skip Whisper model download"
    )
    parser.add_argument(
        "--skip-diarization",
        action="store_true",
        help="Skip diarization model download",
    )
    parser.add_argument(
        "--skip-ollama", action="store_true", help="Skip Ollama model download"
    )
    parser.add_argument(
        "--ollama-model",
        default="llama3.2:3b",
        help="Ollama model to download (default: llama3.2:3b)",
    )

    args = parser.parse_args()

    print("🚀 Knowledge_Chipper Model Downloader")
    print("=====================================")
    print("This will download all required models to avoid delays during processing.\n")

    success_count = 0
    total_count = 0

    # Download Whisper model
    if not args.skip_whisper:
        total_count += 1
        if download_whisper_model(args.whisper_model):
            success_count += 1

    # Download diarization model
    if not args.skip_diarization:
        total_count += 1
        if download_diarization_model():
            success_count += 1

    # Download Ollama model
    if not args.skip_ollama:
        total_count += 1
        if download_ollama_model(args.ollama_model):
            success_count += 1

    # Summary
    print(f"\n{'='*50}")
    print(f"✅ Downloaded {success_count}/{total_count} models successfully")

    if success_count < total_count:
        print("\n⚠️  Some models failed to download.")
        print("   Check the error messages above and try again.")
        sys.exit(1)
    else:
        print("\n🎉 All models downloaded successfully!")
        print("   Knowledge_Chipper is ready to use without delays.")
        sys.exit(0)


if __name__ == "__main__":
    main()
