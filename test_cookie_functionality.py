#!/usr/bin/env python3
"""
Simple test for cookie and multi-account functionality.
Bypasses file_generation import to avoid unrelated syntax error.
"""

import asyncio
import logging
import sys
from http.cookiejar import MozillaCookieJar
from pathlib import Path

# Test cookie file validation
def test_cookie_file(cookie_file: str) -> tuple[bool, str]:
    """Test if a cookie file is valid"""
    try:
        if not Path(cookie_file).exists():
            return False, "File not found"
        
        jar = MozillaCookieJar(cookie_file)
        jar.load(ignore_discard=True, ignore_expires=True)
        
        youtube_cookies = [
            c for c in jar
            if 'youtube.com' in c.domain or 'google.com' in c.domain
        ]
        
        if youtube_cookies:
            return True, f"Valid ({len(youtube_cookies)} cookies)"
        else:
            return False, "No YouTube/Google cookies found"
    
    except Exception as e:
        return False, f"Error: {str(e)[:100]}"


def test_imports():
    """Test if all required modules can be imported"""
    print("="*60)
    print("IMPORT TEST")
    print("="*60)
    
    results = {}
    
    # Test DownloadScheduler
    try:
        sys.path.insert(0, str(Path(__file__).parent / "src"))
        from knowledge_system.services.download_scheduler import DownloadScheduler
        print("✅ DownloadScheduler imported successfully")
        results["DownloadScheduler"] = True
    except Exception as e:
        print(f"❌ DownloadScheduler import failed: {e}")
        results["DownloadScheduler"] = False
    
    # Test MultiAccountDownloadScheduler
    try:
        from knowledge_system.services.multi_account_downloader import MultiAccountDownloadScheduler
        print("✅ MultiAccountDownloadScheduler imported successfully")
        results["MultiAccountDownloadScheduler"] = True
    except Exception as e:
        print(f"❌ MultiAccountDownloadScheduler import failed: {e}")
        results["MultiAccountDownloadScheduler"] = False
    
    # Test CookieFileManager
    try:
        from knowledge_system.gui.widgets.cookie_file_manager import CookieFileManager
        print("✅ CookieFileManager imported successfully")
        results["CookieFileManager"] = True
    except Exception as e:
        print(f"❌ CookieFileManager import failed: {e}")
        results["CookieFileManager"] = False
    
    # Test deduplication
    try:
        from knowledge_system.utils.deduplication import VideoDeduplicationService
        print("✅ VideoDeduplicationService imported successfully")
        results["VideoDeduplicationService"] = True
    except Exception as e:
        print(f"❌ VideoDeduplicationService import failed: {e}")
        results["VideoDeduplicationService"] = False
    
    print(f"\nResults: {sum(results.values())}/{len(results)} imports successful")
    return all(results.values())


def test_cookie_validation(cookie_files: list[str]):
    """Test cookie file validation"""
    print("\n" + "="*60)
    print("COOKIE VALIDATION TEST")
    print("="*60)
    
    for idx, cookie_file in enumerate(cookie_files, 1):
        print(f"\nAccount {idx}: {cookie_file}")
        is_valid, message = test_cookie_file(cookie_file)
        
        if is_valid:
            print(f"  ✅ {message}")
        else:
            print(f"  ❌ {message}")
    
    print("\n")


def main():
    """Run tests"""
    import argparse
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--cookies", nargs="+", help="Cookie files to test")
    args = parser.parse_args()
    
    print("\n" + "="*60)
    print("MULTI-ACCOUNT FUNCTIONALITY TEST")
    print("="*60 + "\n")
    
    # Test 1: Imports
    imports_ok = test_imports()
    
    # Test 2: Cookie validation
    if args.cookies:
        test_cookie_validation(args.cookies)
    else:
        print("⚠️ No cookie files provided")
        print("   Use: python test_cookie_functionality.py --cookies cookie1.txt cookie2.txt\n")
    
    # Summary
    print("="*60)
    if imports_ok:
        print("✅ ALL IMPORTS SUCCESSFUL")
    else:
        print("❌ SOME IMPORTS FAILED")
    print("="*60 + "\n")
    
    return 0 if imports_ok else 1


if __name__ == "__main__":
    sys.exit(main())

