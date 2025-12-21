#!/usr/bin/env python3
"""
Install Playwright and required browsers.
Called automatically on first use or manually by users.
"""
import subprocess
import sys
from pathlib import Path


def ensure_playwright_installed():
    """Ensure Playwright is installed with Chromium browser."""
    try:
        import playwright
        print("✅ Playwright already installed")
        
        # Check if browsers are installed
        result = subprocess.run(
            [sys.executable, "-m", "playwright", "install", "--dry-run", "chromium"],
            capture_output=True,
            text=True
        )
        
        if "is already installed" not in result.stdout:
            print("📥 Installing Chromium browser (~50 MB)...")
            subprocess.run(
                [sys.executable, "-m", "playwright", "install", "chromium"],
                check=True
            )
            print("✅ Chromium installed")
        else:
            print("✅ Chromium already installed")
            
        return True
        
    except ImportError:
        print("📦 Installing Playwright...")
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "playwright"],
            check=True
        )
        print("📥 Installing Chromium browser...")
        subprocess.run(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            check=True
        )
        print("✅ Playwright setup complete")
        return True
        
    except Exception as e:
        print(f"❌ Failed to install Playwright: {e}")
        return False


if __name__ == "__main__":
    ensure_playwright_installed()

