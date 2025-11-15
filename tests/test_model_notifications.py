#!/usr/bin/env python3
"""Test script to verify model download notifications work."""
import os
import shutil
import sys
from pathlib import Path

import pytest

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))


@pytest.mark.manual
@pytest.mark.skip(reason="Interactive script - requires manual execution. Run directly: python tests/test_model_notifications.py")
def test_missing_models():
    """Test the notification system by temporarily hiding models."""
    print("🧪 Model Notification Test Script")
    print("=" * 50)

    # Backup existing models
    whisper_dir = Path.home() / ".cache" / "whisper-cpp"
    whisper_backup = Path.home() / ".cache" / "whisper-cpp-backup"

    print(f"\n1. Current Whisper models in {whisper_dir}:")
    if whisper_dir.exists():
        for model in whisper_dir.glob("*.bin"):
            size_mb = model.stat().st_size / (1024 * 1024)
            print(f"   - {model.name}: {size_mb:.1f} MB")

    # Check model validator
    from knowledge_system.utils.model_validator import get_model_validator

    validator = get_model_validator()

    print("\n2. Model validation status:")
    print(validator.get_model_status_report())

    print("\n3. Missing models check:")
    missing = validator.get_missing_models()
    if missing:
        print(f"   Missing models: {missing}")
    else:
        print("   ✅ No missing models detected")

    # Option to temporarily rename models
    response = input(
        "\n🔧 Would you like to temporarily hide models to test notifications? (y/n): "
    )
    if response.lower() == "y":
        try:
            # Backup whisper models
            if whisper_dir.exists() and not whisper_backup.exists():
                print(f"\n📦 Moving models to backup: {whisper_backup}")
                shutil.move(str(whisper_dir), str(whisper_backup))
                whisper_dir.mkdir(parents=True, exist_ok=True)

                # Re-check
                validator = get_model_validator()
                missing = validator.get_missing_models()
                print(f"\n✅ Models hidden. Missing models now: {missing}")
                print("\n🚀 Launch the app now to see download notifications!")
                print(
                    "\n⚠️  To restore models later, run this script again and choose 'r'"
                )
            else:
                print("⚠️  Backup already exists or no models to hide")

        except Exception as e:
            print(f"❌ Error: {e}")

    elif response.lower() == "r":
        # Restore models
        if whisper_backup.exists():
            print(f"\n📦 Restoring models from: {whisper_backup}")
            if whisper_dir.exists():
                shutil.rmtree(whisper_dir)
            shutil.move(str(whisper_backup), str(whisper_dir))
            print("✅ Models restored!")
        else:
            print("⚠️  No backup found to restore")

    print("\n4. Testing notification widget directly:")
    print("   To see the notification widget in action:")
    print("   1. Hide models using option 'y' above")
    print("   2. Launch the app")
    print("   3. Try to transcribe a file")
    print("   4. You should see the download notification appear!")


if __name__ == "__main__":
    test_missing_models()
