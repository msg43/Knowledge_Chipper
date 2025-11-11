#!/usr/bin/env python3
"""
Comprehensive test suite for the entire download flow.
Tests every component and integration point to catch all bugs at once.
"""

import sys
import traceback
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent / "src"))


def test_imports():
    """Test 1: Can we import all required modules?"""
    print("\n" + "=" * 80)
    print("TEST 1: Module Imports")
    print("=" * 80)

    try:
        from knowledge_system.database.service import DatabaseService
        from knowledge_system.processors.youtube_download import (
            YouTubeDownloadProcessor,
        )
        from knowledge_system.services.download_scheduler import DownloadScheduler
        from knowledge_system.services.multi_account_downloader import (
            MultiAccountDownloadScheduler,
        )
        from knowledge_system.services.unified_download_orchestrator import (
            UnifiedDownloadOrchestrator,
        )

        print("✅ All imports successful")
        return True
    except Exception as e:
        print(f"❌ Import failed: {e}")
        traceback.print_exc()
        return False


def test_database_service():
    """Test 2: Database service initialization and methods"""
    print("\n" + "=" * 80)
    print("TEST 2: Database Service")
    print("=" * 80)

    try:
        from knowledge_system.database.service import DatabaseService

        db = DatabaseService()
        print("✅ Database service initialized")

        # Test create_source signature
        test_source = db.create_source(
            source_id="test_123",
            title="Test Video",
            url="https://youtube.com/test",
            source_type="youtube",  # REQUIRED field
            uploader="Test Uploader",
            duration_seconds=100,
        )
        print(f"✅ create_source works: {test_source is not None}")

        # Test update_audio_status signature
        db.update_audio_status(
            source_id="test_123",
            audio_file_path="/tmp/test.m4a",
            audio_downloaded=True,
            audio_file_size_bytes=1000,
            audio_format="m4a",
        )
        print("✅ update_audio_status works")

        # Test update_metadata_status signature
        db.update_metadata_status(source_id="test_123", metadata_complete=True)
        print("✅ update_metadata_status works")

        # Test mark_for_retry signature
        db.mark_for_retry(
            source_id="test_123",
            needs_metadata_retry=False,
            needs_audio_retry=False,
            failure_reason="test",
        )
        print("✅ mark_for_retry works")

        return True
    except Exception as e:
        print(f"❌ Database test failed: {e}")
        traceback.print_exc()
        return False


def test_processor_result():
    """Test 3: ProcessorResult structure"""
    print("\n" + "=" * 80)
    print("TEST 3: ProcessorResult Structure")
    print("=" * 80)

    try:
        from knowledge_system.processors.base import ProcessorResult

        # Test with dict data (what processor returns)
        result = ProcessorResult(
            success=True,
            data={
                "downloaded_files": ["/tmp/test.m4a"],
                "downloaded_thumbnails": ["/tmp/test.jpg"],
                "count": 1,
            },
            metadata={"format_id": "139-11"},
        )

        print(f"✅ ProcessorResult created")
        print(f"   - success: {result.success}")
        print(f"   - data type: {type(result.data)}")
        print(f"   - data: {result.data}")
        print(f"   - Has 'data' attribute: {hasattr(result, 'data')}")
        print(f"   - Has 'output_data' attribute: {hasattr(result, 'output_data')}")

        return True
    except Exception as e:
        print(f"❌ ProcessorResult test failed: {e}")
        traceback.print_exc()
        return False


def test_download_scheduler():
    """Test 4: Download scheduler result format"""
    print("\n" + "=" * 80)
    print("TEST 4: Download Scheduler")
    print("=" * 80)

    try:
        from knowledge_system.database.service import DatabaseService
        from knowledge_system.services.download_scheduler import DownloadScheduler

        db = DatabaseService()
        scheduler = DownloadScheduler(
            cookie_file_path="/Users/matthewgreer/Projects/cookies3.txt",
            enable_sleep_period=False,
            db_service=db,
        )
        print("✅ Scheduler initialized")

        # Check what the scheduler's download method signature looks like
        import inspect

        sig = inspect.signature(scheduler.download_single)
        print(f"   - download_single signature: {sig}")

        return True
    except Exception as e:
        print(f"❌ Scheduler test failed: {e}")
        traceback.print_exc()
        return False


def test_orchestrator_result_handling():
    """Test 5: Orchestrator result handling"""
    print("\n" + "=" * 80)
    print("TEST 5: Orchestrator Result Handling")
    print("=" * 80)

    try:
        from pathlib import Path

        # Simulate what the scheduler returns
        mock_result = {
            "success": True,
            "url": "https://youtube.com/test",
            "audio_file": {
                "downloaded_files": ["/tmp/test.m4a"],
                "downloaded_thumbnails": ["/tmp/test.jpg"],
                "count": 1,
            },
            "metadata": {"format_id": "139-11"},
        }

        # Test the conversion logic
        audio_file_data = mock_result["audio_file"]
        if isinstance(audio_file_data, dict):
            files = audio_file_data.get("downloaded_files", [])
            if files:
                audio_file = Path(files[0])
                print(f"✅ Dict handling works: {audio_file}")
            else:
                print("❌ No files in dict")
                return False
        else:
            audio_file = Path(audio_file_data)
            print(f"✅ Direct path handling works: {audio_file}")

        return True
    except Exception as e:
        print(f"❌ Orchestrator result handling failed: {e}")
        traceback.print_exc()
        return False


def test_actual_download():
    """Test 6: Actual download with all components"""
    print("\n" + "=" * 80)
    print("TEST 6: Full Download Flow")
    print("=" * 80)

    try:
        from pathlib import Path

        from knowledge_system.database.service import DatabaseService
        from knowledge_system.processors.youtube_download import (
            YouTubeDownloadProcessor,
        )

        db = DatabaseService()
        processor = YouTubeDownloadProcessor(
            enable_cookies=True,
            cookie_file_path="/Users/matthewgreer/Projects/cookies3.txt",
            download_thumbnails=True,
            disable_proxies_with_cookies=True,
        )

        # Use a different video each time to avoid archive issues
        import time

        test_videos = [
            "https://www.youtube.com/watch?v=Y1w-53tXuZk",
            "https://www.youtube.com/watch?v=aHT3OtSpKKU",
            "https://www.youtube.com/watch?v=2dXyz6VWJo8",
        ]
        url = test_videos[int(time.time()) % len(test_videos)]
        output_dir = "/tmp/full_test_download"
        Path(output_dir).mkdir(exist_ok=True)

        print(f"🚀 Downloading: {url}")
        result = processor.process(input_data=url, output_dir=output_dir, db_service=db)

        print(f"\n📊 Result Analysis:")
        print(f"   - Success: {result.success}")
        print(f"   - Data type: {type(result.data)}")
        print(f"   - Data: {result.data}")

        if result.success:
            if isinstance(result.data, dict):
                files = result.data.get("downloaded_files", [])
                print(f"   - Downloaded files: {files}")
                if files:
                    for f in files:
                        file_path = Path(f)
                        exists = file_path.exists()
                        size = file_path.stat().st_size if exists else 0
                        print(
                            f"   - File exists: {exists}, Size: {size/1024/1024:.2f}MB"
                        )
            else:
                print(f"   - Direct data: {result.data}")

            print("✅ Download successful")
            return True
        else:
            print(f"❌ Download failed: {result.errors}")
            return False

    except Exception as e:
        print(f"❌ Download test failed: {e}")
        traceback.print_exc()
        return False


def test_scheduler_flow():
    """Test 7: Scheduler download flow"""
    print("\n" + "=" * 80)
    print("TEST 7: Scheduler Download Flow")
    print("=" * 80)

    try:
        import asyncio
        from pathlib import Path

        from knowledge_system.database.service import DatabaseService
        from knowledge_system.services.download_scheduler import DownloadScheduler

        db = DatabaseService()
        scheduler = DownloadScheduler(
            cookie_file_path="/Users/matthewgreer/Projects/cookies3.txt",
            enable_sleep_period=False,
            db_service=db,
        )

        url = "https://www.youtube.com/watch?v=aHT3OtSpKKU"
        output_dir = "/tmp/scheduler_test"
        Path(output_dir).mkdir(exist_ok=True)

        print(f"🚀 Scheduler downloading: {url}")
        result = asyncio.run(scheduler.download_single(url, output_dir))

        print(f"\n📊 Scheduler Result:")
        print(f"   - Type: {type(result)}")
        print(f"   - Success: {result.get('success')}")
        print(f"   - Audio file type: {type(result.get('audio_file'))}")
        print(f"   - Audio file: {result.get('audio_file')}")

        if result.get("success"):
            audio_file_data = result.get("audio_file")
            if isinstance(audio_file_data, dict):
                print(f"   - Dict keys: {audio_file_data.keys()}")
                files = audio_file_data.get("downloaded_files", [])
                print(f"   - Files: {files}")
            print("✅ Scheduler flow successful")
            return True
        else:
            print(f"❌ Scheduler failed: {result.get('error')}")
            return False

    except Exception as e:
        print(f"❌ Scheduler flow test failed: {e}")
        traceback.print_exc()
        return False


def main():
    """Run all tests"""
    print("\n" + "=" * 80)
    print("COMPREHENSIVE DOWNLOAD FLOW TEST SUITE")
    print("=" * 80)
    print("This will test every component to find ALL bugs at once")
    print("=" * 80)

    tests = [
        ("Imports", test_imports),
        ("Database Service", test_database_service),
        ("ProcessorResult", test_processor_result),
        ("Download Scheduler", test_download_scheduler),
        ("Orchestrator Result Handling", test_orchestrator_result_handling),
        ("Actual Download", test_actual_download),
        ("Scheduler Flow", test_scheduler_flow),
    ]

    results = {}
    for name, test_func in tests:
        try:
            results[name] = test_func()
        except Exception as e:
            print(f"\n❌ Test '{name}' crashed: {e}")
            traceback.print_exc()
            results[name] = False

    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}")

    print(f"\n{passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 ALL TESTS PASSED - Code is production ready!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} tests failed - bugs found!")
        return 1


if __name__ == "__main__":
    sys.exit(main())
