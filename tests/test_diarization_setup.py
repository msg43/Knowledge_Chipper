#!/usr/bin/env python3
"""
Test Pyannote Diarization Setup
Verifies dependencies and guides through HuggingFace setup
"""

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
TEST_INPUTS_DIR = PROJECT_ROOT / "data" / "test_files" / "Test Inputs"
TEST_OUTPUTS_DIR = (
    PROJECT_ROOT / "data" / "test_files" / "Test Outputs" / "diarization_test"
)

CLI_CMD = [sys.executable, "-m", "knowledge_system"]


def test_dependencies():
    """Test if all diarization dependencies are available."""
    print("🧪 Testing Diarization Dependencies...")

    try:
        import torch

        print(f"✅ PyTorch {torch.__version__}")
    except ImportError:
        print("❌ PyTorch not available")
        return False

    try:
        import transformers

        print(f"✅ Transformers {transformers.__version__}")
    except ImportError:
        print("❌ Transformers not available")
        return False

    try:
        import pyannote.audio

        print(f"✅ pyannote.audio {pyannote.audio.__version__}")
    except ImportError:
        print("❌ pyannote.audio not available")
        return False

    return True


def test_huggingface_setup():
    """Test HuggingFace authentication."""
    print("\n🔑 Testing HuggingFace Setup...")

    # Check for HF token in environment
    import os

    hf_token = os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACE_HUB_TOKEN")

    if hf_token:
        print(f"✅ HuggingFace token found in environment: {hf_token[:8]}...")
    else:
        print("❌ No HuggingFace token found in environment")

    # Check in settings.yaml
    settings_file = PROJECT_ROOT / "config" / "settings.yaml"
    if settings_file.exists():
        with open(settings_file) as f:
            content = f.read()
            if "huggingface_token" in content:
                print("✅ huggingface_token found in config/settings.yaml")
            else:
                print("❌ huggingface_token not found in config/settings.yaml")
    else:
        print("❌ config/settings.yaml not found")

    return bool(hf_token)


def test_model_access():
    """Test if we can load the pyannote diarization model."""
    print("\n🎯 Testing Pyannote Model Access...")

    try:
        from pyannote.audio import Pipeline

        # Try to load the speaker diarization pipeline
        print("Attempting to load pyannote/speaker-diarization-3.1...")
        pipeline = Pipeline.from_pretrained("pyannote/speaker-diarization-3.1")
        print("✅ Pyannote model loaded successfully!")
        return True

    except Exception as e:
        print(f"❌ Failed to load pyannote model: {e}")

        if "401" in str(e) or "authentication" in str(e).lower():
            print("   → This indicates authentication issues")
        elif "gated" in str(e).lower() or "accept" in str(e).lower():
            print("   → This indicates you need to accept the model license")

        return False


def test_diarization_transcription():
    """Test actual diarization transcription."""
    print("\n🎬 Testing Diarization Transcription...")

    # Create output directory
    TEST_OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

    # Test with a short audio file
    cmd = CLI_CMD + [
        "transcribe",
        "--input",
        str(TEST_INPUTS_DIR / "harvard.wav"),
        "--output",
        str(TEST_OUTPUTS_DIR),
        "--model",
        "base",
        "--format",
        "vtt",
        "--speaker-labels",  # Enable diarization
        "--overwrite",
    ]

    print(f"Command: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode == 0:
        print("✅ Diarization transcription successful!")

        # Check output file
        vtt_file = TEST_OUTPUTS_DIR / "harvard_transcript.vtt"
        if vtt_file.exists():
            print(f"📁 VTT file created: {vtt_file}")
            with open(vtt_file) as f:
                content = f.read()
                print("📄 VTT Content Preview:")
                print("=" * 50)
                print(content[:500] + "..." if len(content) > 500 else content)
                print("=" * 50)

                # Check if it contains speaker labels
                if "<v Speaker_" in content:
                    print("🎉 Speaker labels detected in VTT output!")
                    return True
                else:
                    print(
                        "⚠️  No speaker labels detected - may have fallen back to basic transcription"
                    )
                    return False
        else:
            print("❌ VTT file not found")
            return False
    else:
        print(f"❌ Diarization transcription failed")
        print("STDERR:", result.stderr)
        return False


def show_setup_instructions():
    """Show detailed setup instructions."""
    print("\n📋 Complete Diarization Setup Instructions:")
    print("=" * 60)
    print("1. ✅ Dependencies installed (torch, transformers, pyannote.audio)")
    print()
    print("2. 🔑 HuggingFace Setup Required:")
    print("   a) Create account at https://huggingface.co")
    print(
        "   b) Accept license at https://huggingface.co/pyannote/speaker-diarization-3.1"
    )
    print("   c) Get your API token at https://huggingface.co/settings/tokens")
    print()
    print("3. 🔧 Configure Token (choose one method):")
    print()
    print("   METHOD A - Environment Variable:")
    print("   export HF_TOKEN='your_token_here'")
    print("   export HUGGINGFACE_HUB_TOKEN='your_token_here'")
    print()
    print("   METHOD B - Add to config/settings.yaml:")
    print("   api_keys:")
    print("     huggingface_token: 'your_token_here'")
    print()
    print("4. 🎬 Test with VTT format:")
    print("   knowledge-system transcribe audio.wav --format vtt --speaker-labels")
    print()
    print("Expected VTT output:")
    print("   WEBVTT")
    print()
    print("   00:00:01.000 --> 00:00:03.500")
    print("   <v Speaker_1>Hello, this is the first speaker.</v>")
    print()
    print("   00:00:04.000 --> 00:00:06.500")
    print("   <v Speaker_2>And this is the second speaker.</v>")
    print("=" * 60)


def main():
    """Run complete diarization setup test."""
    print("🎯 Pyannote Diarization Setup Test")
    print(f"📁 Test inputs: {TEST_INPUTS_DIR}")
    print(f"📁 Test outputs: {TEST_OUTPUTS_DIR}")

    # Test dependencies
    deps_ok = test_dependencies()
    if not deps_ok:
        print(
            "\n❌ Dependencies missing - install with: pip install torch transformers pyannote.audio"
        )
        return

    # Test HuggingFace setup
    hf_ok = test_huggingface_setup()

    # Test model access
    model_ok = test_model_access()

    # Test actual diarization
    if hf_ok and model_ok:
        diarization_ok = test_diarization_transcription()
        if diarization_ok:
            print("\n🎉 Diarization fully working!")
        else:
            print("\n⚠️  Diarization dependencies OK but transcription failed")
    else:
        print("\n⚠️  Skipping transcription test due to setup issues")

    # Always show setup instructions
    show_setup_instructions()


if __name__ == "__main__":
    main()
