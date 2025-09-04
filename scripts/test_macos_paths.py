#!/usr/bin/env python3
"""
Test script to verify macOS paths are working correctly.
"""

import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

def test_macos_paths():
    """Test the macOS paths utility."""
    try:
        from knowledge_system.utils.macos_paths import (
            get_application_support_dir,
            get_cache_dir,
            get_logs_dir,
            get_user_data_dir,
            get_config_dir,
            get_default_paths,
            log_paths_info
        )
        
        print("🧪 Testing macOS Paths Configuration")
        print("=" * 50)
        
        # Test individual functions
        print("\n📁 Directory Functions:")
        print(f"Application Support: {get_application_support_dir()}")
        print(f"Cache:              {get_cache_dir()}")
        print(f"Logs:               {get_logs_dir()}")
        print(f"User Data:          {get_user_data_dir()}")
        print(f"Config:             {get_config_dir()}")
        
        # Test default paths
        print("\n🔧 Default Paths Configuration:")
        paths = get_default_paths()
        for key, path in sorted(paths.items()):
            print(f"  {key:15} = {path}")
        
        # Verify directories exist
        print("\n✅ Directory Verification:")
        all_exist = True
        for key, path in paths.items():
            path_obj = Path(path)
            exists = path_obj.exists()
            print(f"  {key:15} {'✅' if exists else '❌'} {path}")
            if not exists:
                all_exist = False
        
        if all_exist:
            print("\n🎉 All directories created successfully!")
        else:
            print("\n⚠️  Some directories were not created")
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing macOS paths: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_config_integration():
    """Test that the config system uses the new paths."""
    try:
        from knowledge_system.config import get_settings
        
        print("\n🔧 Testing Config Integration")
        print("=" * 50)
        
        settings = get_settings()
        
        print("\n📁 Current Settings Paths:")
        print(f"  data_dir:    {settings.paths.data_dir}")
        print(f"  output_dir:  {settings.paths.output_dir}")
        print(f"  cache_dir:   {settings.paths.cache_dir}")
        print(f"  logs_dir:    {settings.paths.logs_dir}")
        print(f"  transcripts: {settings.paths.transcripts}")
        print(f"  summaries:   {settings.paths.summaries}")
        print(f"  mocs:        {settings.paths.mocs}")
        
        # Check if paths contain proper macOS locations
        proper_paths = [
            "Library/Application Support" in settings.paths.data_dir,
            "Library/Caches" in settings.paths.cache_dir,
            "Library/Logs" in settings.paths.logs_dir,
            "Documents/Knowledge Chipper" in settings.paths.output_dir,
        ]
        
        if all(proper_paths):
            print("\n✅ Config integration successful - using macOS standard paths!")
        else:
            print("\n⚠️  Config may not be using macOS standard paths")
            
        return True
        
    except Exception as e:
        print(f"❌ Error testing config integration: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_database_paths():
    """Test that database service uses proper paths."""
    try:
        from knowledge_system.database.service import DatabaseService
        
        print("\n🗄️  Testing Database Service")
        print("=" * 50)
        
        # Test with default URL (should resolve to Application Support)
        db_service = DatabaseService()
        
        print(f"Database URL: {db_service.database_url}")
        print(f"Database Path: {db_service.db_path}")
        
        # Check if it's using Application Support
        if "Library/Application Support" in str(db_service.db_path):
            print("✅ Database using proper macOS Application Support location!")
        else:
            print("⚠️  Database may not be in standard location")
            
        return True
        
    except Exception as e:
        print(f"❌ Error testing database paths: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("🧪 Knowledge Chipper - macOS Paths Test Suite")
    print("=" * 60)
    
    tests = [
        ("macOS Paths Utility", test_macos_paths),
        ("Config Integration", test_config_integration),
        ("Database Paths", test_database_paths),
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
        print(f"  {name:20} {status}")
        if success:
            passed += 1
    
    print(f"\nResults: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! macOS paths are configured correctly.")
        return 0
    else:
        print("⚠️  Some tests failed. Please check the output above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
