#!/usr/bin/env python3
"""
Run HCE replacement tests to verify the system is working correctly.
"""

import subprocess
import sys
from pathlib import Path


def run_test(test_name, test_file):
    """Run a specific test file and report results."""
    print(f"\n{'='*60}")
    print(f"Running {test_name}...")
    print(f"{'='*60}\n")

    result = subprocess.run(
        [sys.executable, "-m", "pytest", test_file, "-v"],
        capture_output=True,
        text=True,
    )

    if result.returncode == 0:
        print(f"✅ {test_name} PASSED")
    else:
        print(f"❌ {test_name} FAILED")
        print("\nOutput:")
        print(result.stdout)
        print("\nErrors:")
        print(result.stderr)

    return result.returncode == 0


def main():
    """Run all HCE tests."""
    print("HCE Replacement Test Suite")
    print("=" * 60)

    # Get test directory
    test_dir = Path(__file__).parent

    # Define tests to run
    tests = [
        ("HCE Summarizer Tests", test_dir / "test_summarizer_hce.py"),
        ("HCE MOC Tests", test_dir / "test_moc_hce.py"),
        ("HCE Acceptance Tests", test_dir / "test_hce_acceptance.py"),
    ]

    # Run each test
    results = []
    for test_name, test_file in tests:
        if test_file.exists():
            success = run_test(test_name, str(test_file))
            results.append((test_name, success))
        else:
            print(f"\n⚠️  {test_name} - Test file not found: {test_file}")
            results.append((test_name, False))

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    passed = sum(1 for _, success in results if success)
    total = len(results)

    for test_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{test_name:.<50} {status}")

    print(f"\nTotal: {passed}/{total} tests passed")

    # Return non-zero if any tests failed
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
