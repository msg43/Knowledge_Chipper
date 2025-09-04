#!/usr/bin/env python3
"""
Test script to verify the build script works with new macOS paths.
"""

import sys
import subprocess
from pathlib import Path

def test_build_script_compatibility():
    """Test that the build script includes proper macOS path configuration."""
    try:
        print("🧪 Testing Build Script with macOS Paths")
        print("=" * 50)
        
        project_root = Path(__file__).parent.parent
        build_script = project_root / "scripts" / "build_macos_app.sh"
        
        if not build_script.exists():
            print(f"❌ Build script not found: {build_script}")
            return False
        
        # Test 1: Check script content for macOS integration
        print("🔍 Checking build script for macOS integration...")
        with open(build_script, 'r') as f:
            content = f.read()
        
        # Check for key components
        checks = [
            ("macOS paths initialization", "macos_paths" in content),
            ("Standard log location", "Library/Logs/Knowledge Chipper" in content),
            ("Config documentation", "MACOS_CONFIGURATION.md" in content),
            ("Launch script updates", "Initializing macOS standard paths" in content),
        ]
        
        all_passed = True
        for name, check in checks:
            if check:
                print(f"✅ {name}")
            else:
                print(f"❌ {name}")
                all_passed = False
        
        if not all_passed:
            print("⚠️  Some build script checks failed")
            return False
        
        # Test 2: Verify we can import the macOS paths module
        print(f"\n🐍 Testing macOS paths module import...")
        try:
            sys.path.insert(0, str(project_root / "src"))
            from knowledge_system.utils.macos_paths import get_default_paths
            paths = get_default_paths()
            print(f"✅ macOS paths module imported successfully")
            print(f"✅ Default paths configured: {len(paths)} paths")
        except Exception as e:
            print(f"❌ Failed to import macOS paths module: {e}")
            return False
        
        # Test 3: Check if a test build would work (dry run simulation)
        print(f"\n🔨 Simulating build process...")
        
        # Check Python 3.13 availability
        try:
            result = subprocess.run(
                ["python3.13", "--version"], 
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                print(f"✅ Python 3.13 available: {result.stdout.strip()}")
            else:
                print(f"⚠️  Python 3.13 not found (needed for build)")
        except Exception as e:
            print(f"⚠️  Could not check Python 3.13: {e}")
        
        # Check required tools
        tools = ["rsync", "hdiutil", "iconutil", "sips"]
        for tool in tools:
            try:
                result = subprocess.run(
                    ["which", tool],
                    capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0:
                    print(f"✅ {tool} available")
                else:
                    print(f"❌ {tool} not found")
                    all_passed = False
            except Exception:
                print(f"❌ Could not check {tool}")
                all_passed = False
        
        return all_passed
        
    except Exception as e:
        print(f"❌ Error testing build script: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_config_migration():
    """Test that config system properly handles the transition."""
    try:
        print(f"\n📁 Testing Configuration Migration")
        print("=" * 50)
        
        sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
        from knowledge_system.config import get_settings
        from knowledge_system.utils.macos_paths import get_config_dir, get_default_paths
        
        # Test settings loading
        settings = get_settings()
        print(f"✅ Settings loaded successfully")
        print(f"✅ Auto-update setting: {settings.app.auto_check_updates}")
        
        # Test paths
        paths = get_default_paths()
        config_dir = get_config_dir()
        
        print(f"✅ Config directory: {config_dir}")
        print(f"✅ Default paths count: {len(paths)}")
        
        # Verify key paths exist
        key_paths = ["data_dir", "output_dir", "cache_dir", "logs_dir"]
        for key in key_paths:
            if key in paths and Path(paths[key]).exists():
                print(f"✅ {key}: {paths[key]}")
            else:
                print(f"ℹ️  {key}: {paths[key]} (will be created)")
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing config migration: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("🧪 Knowledge Chipper - Build Script Test Suite")
    print("=" * 60)
    
    tests = [
        ("Build Script Compatibility", test_build_script_compatibility),
        ("Configuration Migration", test_config_migration),
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
        print("🎉 All tests passed! Build script is ready for macOS paths.")
        print("\n📋 Ready for:")
        print("• Building apps with proper macOS file locations")
        print("• DMG creation with standard data handling")
        print("• User data preservation across updates")
        return 0
    else:
        print("⚠️  Some tests failed. Please check the output above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
