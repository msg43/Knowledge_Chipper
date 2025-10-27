#!/usr/bin/env python3
"""
Test script to diagnose whisper-cli issues
"""

import os
import shutil
import subprocess
import sys


def test_whisper_cli():
    """Test if whisper-cli is working properly"""

    print("=== Testing whisper-cli ===")

    # Check if whisper-cli exists
    whisper_path = shutil.which("whisper-cli")
    if not whisper_path:
        print("❌ whisper-cli not found in PATH")
        return

    print(f"✅ Found whisper-cli at: {whisper_path}")

    # Check version/help
    print("\n--- Testing whisper-cli --help ---")
    try:
        result = subprocess.run(
            [whisper_path, "--help"], capture_output=True, text=True, timeout=10
        )
        print(f"Return code: {result.returncode}")
        if result.stdout:
            print(f"STDOUT (first 500 chars):\n{result.stdout[:500]}")
        if result.stderr:
            print(f"STDERR (first 500 chars):\n{result.stderr[:500]}")
    except subprocess.TimeoutExpired:
        print("❌ whisper-cli --help timed out after 10 seconds")
    except Exception as e:
        print(f"❌ Error running whisper-cli --help: {e}")

    # Test with a simple command
    print("\n--- Testing whisper-cli version ---")
    try:
        result = subprocess.run(
            [whisper_path, "--version"], capture_output=True, text=True, timeout=10
        )
        print(f"Return code: {result.returncode}")
        if result.stdout:
            print(f"STDOUT: {result.stdout}")
        if result.stderr:
            print(f"STDERR: {result.stderr}")
    except subprocess.TimeoutExpired:
        print("❌ whisper-cli --version timed out after 10 seconds")
    except Exception as e:
        print(f"❌ Error running whisper-cli --version: {e}")

    # Check if it's actually whisper.cpp or something else
    print("\n--- Checking whisper-cli type ---")
    try:
        # Run with no args to see what happens
        result = subprocess.run(
            [whisper_path], capture_output=True, text=True, timeout=5
        )
        print(f"Return code: {result.returncode}")
        if result.stdout:
            print(f"STDOUT (first 200 chars): {result.stdout[:200]}")
        if result.stderr:
            print(f"STDERR (first 200 chars): {result.stderr[:200]}")

        # Check if it mentions whisper.cpp
        output = (result.stdout + result.stderr).lower()
        if "whisper.cpp" in output:
            print("✅ Appears to be whisper.cpp")
        elif "openai" in output:
            print("⚠️  Might be OpenAI's whisper, not whisper.cpp")
        else:
            print("❓ Unknown whisper implementation")

    except subprocess.TimeoutExpired:
        print("❌ whisper-cli (no args) timed out")
    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    test_whisper_cli()
