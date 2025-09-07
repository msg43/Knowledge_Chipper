#!/usr/bin/env python3
"""
Setup HuggingFace Token for Diarization
Interactive script to help set up the HuggingFace token for pyannote diarization
"""

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
SETTINGS_FILE = PROJECT_ROOT / "config" / "settings.yaml"


def check_current_token_setup():
    """Check current token configuration."""
    print("🔍 Checking Current Token Setup...")

    # Check environment variables
    env_token = os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACE_HUB_TOKEN")
    if env_token:
        print(f"✅ Found token in environment: {env_token[:8]}...")
        return True
    else:
        print("❌ No token found in environment variables")

    # Check settings.yaml
    if SETTINGS_FILE.exists():
        with open(SETTINGS_FILE) as f:
            content = f.read()
            if "huggingface_token:" in content and "your_token_here" not in content:
                print("✅ Found token in config/settings.yaml")
                return True
            else:
                print("❌ No valid token found in config/settings.yaml")
    else:
        print("❌ config/settings.yaml doesn't exist")

    return False


def setup_instructions():
    """Show setup instructions."""
    print("\n📋 HuggingFace Token Setup Instructions:")
    print("=" * 60)
    print("1. 🌐 Create HuggingFace Account:")
    print("   - Go to https://huggingface.co")
    print("   - Sign up for a free account")
    print()
    print("2. 📜 Accept Model License:")
    print("   - Visit https://huggingface.co/pyannote/speaker-diarization-3.1")
    print("   - Click 'Agree and access repository'")
    print("   - This step is REQUIRED for diarization to work")
    print()
    print("3. 🔑 Get API Token:")
    print("   - Go to https://huggingface.co/settings/tokens")
    print("   - Click 'New token'")
    print("   - Choose 'Read' access")
    print("   - Copy the token (starts with 'hf_')")
    print()
    print("4. 🔧 Configure Token (choose one method):")
    print()
    print("   METHOD A - Environment Variable (Temporary):")
    print("   export HF_TOKEN='your_token_here'")
    print()
    print("   METHOD B - Settings File (Persistent):")
    print("   Add to config/settings.yaml:")
    print("   api_keys:")
    print("     huggingface_token: 'your_token_here'")
    print("=" * 60)


def create_minimal_settings():
    """Create a minimal settings.yaml with api_keys section."""
    print("\n🔧 Creating minimal settings.yaml...")

    settings_content = """# Minimal configuration for diarization
api_keys:
  huggingface_token: "your_token_here"  # Replace with your HF token

# YouTube processing optimizations
youtube_processing:
  disable_delays_with_proxy: true
  metadata_delay_min: 0.0
  metadata_delay_max: 0.0
  transcript_delay_min: 0.0
  transcript_delay_max: 0.0
  api_batch_delay_min: 0.0
  api_batch_delay_max: 0.0
  use_proxy_delays: false
"""

    # Backup existing settings if they exist
    if SETTINGS_FILE.exists():
        backup_file = SETTINGS_FILE.with_suffix(".yaml.backup")
        print(f"   Backing up existing settings to {backup_file}")
        import shutil

        shutil.copy2(SETTINGS_FILE, backup_file)

    # Create directory if it doesn't exist
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)

    # Write new settings
    with open(SETTINGS_FILE, "w") as f:
        f.write(settings_content)

    print(f"✅ Created {SETTINGS_FILE}")
    print(
        "⚠️  Remember to replace 'your_token_here' with your actual HuggingFace token!"
    )


def test_with_environment_token():
    """Test diarization with an environment token."""
    print("\n🧪 Quick Test with Environment Token...")

    token = input("Enter your HuggingFace token (or press Enter to skip): ").strip()
    if not token:
        print("Skipping environment token test")
        return False

    if not token.startswith("hf_"):
        print("⚠️  Warning: HuggingFace tokens typically start with 'hf_'")

    # Set environment variable temporarily
    os.environ["HF_TOKEN"] = token
    os.environ["HUGGINGFACE_HUB_TOKEN"] = token

    print(f"Set environment token: {token[:8]}...")

    # Test diarization
    try:
        print("Testing pyannote model access...")
        from pyannote.audio import Pipeline

        pipeline = Pipeline.from_pretrained("pyannote/speaker-diarization-3.1")
        print("✅ Pyannote model loaded successfully with your token!")
        return True
    except Exception as e:
        print(f"❌ Failed to load pyannote model: {e}")
        if "401" in str(e) or "authentication" in str(e).lower():
            print("   → Authentication failed - check your token")
        elif "gated" in str(e).lower() or "accept" in str(e).lower():
            print("   → You need to accept the model license at:")
            print("     https://huggingface.co/pyannote/speaker-diarization-3.1")
        return False


def main():
    """Main setup flow."""
    print("🎯 HuggingFace Token Setup for Pyannote Diarization")
    print(f"📁 Project root: {PROJECT_ROOT}")
    print(f"⚙️  Settings file: {SETTINGS_FILE}")

    # Check current setup
    has_token = check_current_token_setup()

    if has_token:
        print("\n✅ Token appears to be configured!")
        print("Try running: python test_diarization_setup.py")
    else:
        print("\n❌ No HuggingFace token found")

        # Show instructions
        setup_instructions()

        # Ask if user wants to create minimal settings
        print("\n" + "=" * 60)
        response = input(
            "Create minimal settings.yaml with token placeholder? (y/n): "
        ).lower()
        if response in ["y", "yes"]:
            create_minimal_settings()

        # Ask if user wants to test with environment token
        print("\n" + "=" * 60)
        response = input("Test with environment token now? (y/n): ").lower()
        if response in ["y", "yes"]:
            success = test_with_environment_token()
            if success:
                print("\n🎉 Token working! You can now run:")
                print("   python test_diarization_setup.py")
                print(
                    "   knowledge-system transcribe audio.wav --format vtt --speaker-labels"
                )


if __name__ == "__main__":
    main()
