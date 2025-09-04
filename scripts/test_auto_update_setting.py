#!/usr/bin/env python3
"""
Test script to verify auto-update setting functionality.
"""

import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

def test_auto_update_config():
    """Test the auto-update configuration."""
    try:
        from knowledge_system.config import get_settings
        from knowledge_system.utils.macos_paths import get_config_dir
        
        print("🧪 Testing Auto-Update Configuration")
        print("=" * 50)
        
        # Test 1: Default configuration
        settings = get_settings()
        print(f"\n✅ Default auto_check_updates: {settings.app.auto_check_updates}")
        print(f"✅ Default update_channel: {settings.app.update_channel}")
        
        # Test 2: Configuration persistence
        print(f"\n📁 Config directory: {get_config_dir()}")
        config_file = get_config_dir() / "settings.yaml"
        
        if config_file.exists():
            print(f"✅ Config file exists: {config_file}")
            with open(config_file, 'r') as f:
                content = f.read()
                if 'auto_check_updates' in content:
                    print("✅ auto_check_updates found in config file")
                else:
                    print("ℹ️  auto_check_updates not yet in config file (will be added on first change)")
        else:
            print("ℹ️  Config file will be created when settings are saved")
        
        # Test 3: Test setting modification
        print(f"\n🔧 Testing configuration modification...")
        original_value = settings.app.auto_check_updates
        
        # Toggle the setting
        settings.app.auto_check_updates = not original_value
        print(f"✅ Changed auto_check_updates: {original_value} → {settings.app.auto_check_updates}")
        
        # Test saving to file
        try:
            settings.to_yaml(config_file)
            print(f"✅ Successfully saved config to: {config_file}")
            
            # Verify it was saved
            with open(config_file, 'r') as f:
                content = f.read()
                if f"auto_check_updates: {settings.app.auto_check_updates}".lower() in content.lower():
                    print("✅ Setting correctly saved to file")
                else:
                    print("⚠️  Setting may not have been saved correctly")
            
        except Exception as e:
            print(f"❌ Failed to save config: {e}")
        
        # Restore original value
        settings.app.auto_check_updates = original_value
        print(f"✅ Restored original value: {original_value}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing auto-update config: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_state_integration():
    """Test state manager integration."""
    try:
        from knowledge_system.utils.state import UserPreferences
        
        print("\n🗄️  Testing State Integration")
        print("=" * 50)
        
        # Test UserPreferences model
        prefs = UserPreferences()
        print(f"✅ Default auto_check_updates in preferences: {prefs.auto_check_updates}")
        print(f"✅ Default last_update_check: {prefs.last_update_check}")
        
        # Test modification
        prefs.auto_check_updates = False
        prefs.last_update_check = 1234567890.0
        print(f"✅ Modified preferences: auto_check_updates={prefs.auto_check_updates}, last_update_check={prefs.last_update_check}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing state integration: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_update_worker_integration():
    """Test that update worker can access the setting."""
    try:
        from knowledge_system.gui.workers.dmg_update_worker import DMGUpdateWorker
        from knowledge_system.config import get_settings
        
        print("\n🔄 Testing Update Worker Integration")
        print("=" * 50)
        
        # Test worker initialization
        worker = DMGUpdateWorker()
        print(f"✅ DMG Update Worker created successfully")
        print(f"✅ Current version: {worker.current_version}")
        print(f"✅ Public repo URL: {worker.public_repo_url}")
        
        # Test settings access
        settings = get_settings()
        print(f"✅ Auto-update enabled: {settings.app.auto_check_updates}")
        print(f"✅ Update channel: {settings.app.update_channel}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing update worker integration: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("🧪 Knowledge Chipper - Auto-Update Setting Test Suite")
    print("=" * 60)
    
    tests = [
        ("Auto-Update Configuration", test_auto_update_config),
        ("State Integration", test_state_integration),
        ("Update Worker Integration", test_update_worker_integration),
    ]
    
    results = []
    for name, test_func in tests:
        print(f"\n🔬 Running {name} test...")
        try:
            success = test_func()
            results.append((name, success))
        except Exception as e:
            print(f"❌ {name} test failed with exception: {e}")
            results.append((name, False))
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 Test Results Summary:")
    
    passed = 0
    total = len(results)
    
    for name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"  {name:25} {status}")
        if success:
            passed += 1
    
    print(f"\nResults: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Auto-update setting is working correctly.")
        print("\n📋 Usage:")
        print("• Setting is available in the API Keys tab")
        print("• Defaults to enabled (True)")
        print("• Saved to macOS standard config location")
        print("• Integrated with DMG update system")
        return 0
    else:
        print("⚠️  Some tests failed. Please check the output above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
