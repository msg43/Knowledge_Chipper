"""Test that preflight failures are visible and prevent app launch."""

import os
import subprocess
import sys
from pathlib import Path


def test_preflight_failure_stops_app_launch():
    """Verify that preflight failures prevent the GUI from launching."""
    # Create a test script that tries to import the GUI with broken deps
    test_script = """
import sys
import os

# Remove ffmpeg from PATH to break preflight
os.environ['PATH'] = '/tmp'

try:
    from knowledge_system.gui import launch_gui
    print("ERROR: App should not have imported successfully!")
    sys.exit(1)
except Exception as e:
    # Preflight should have failed
    error_msg = str(e)
    if "FFmpeg not found" in error_msg or "preflight" in error_msg.lower():
        print(f"✅ Preflight correctly failed: {error_msg}")
        sys.exit(0)
    else:
        print(f"❌ Wrong error: {error_msg}")
        sys.exit(1)
"""
    
    # Run the test script
    result = subprocess.run(
        [sys.executable, "-c", test_script],
        capture_output=True,
        text=True,
        cwd=Path(__file__).parent.parent,  # Run from project root
    )
    
    # Should have exited with code 0 (preflight failed correctly)
    assert result.returncode == 0, f"Test failed: {result.stdout}\n{result.stderr}"
    assert "Preflight correctly failed" in result.stdout


def test_preflight_success_allows_import():
    """Verify that when dependencies exist, the GUI can be imported."""
    test_script = """
import os

# Keep normal PATH (assuming FFmpeg is installed)
# Just test that import works
try:
    # Set testing mode to avoid actually launching GUI
    os.environ['KNOWLEDGE_CHIPPER_TESTING_MODE'] = '1'
    os.environ['QT_QPA_PLATFORM'] = 'offscreen'
    
    from knowledge_system.gui import MainWindow
    print("✅ GUI imported successfully with valid dependencies")
except Exception as e:
    print(f"❌ Import failed: {e}")
    import traceback
    traceback.print_exc()
    raise
"""
    
    result = subprocess.run(
        [sys.executable, "-c", test_script],
        capture_output=True,
        text=True,
        cwd=Path(__file__).parent.parent,
    )
    
    assert result.returncode == 0, f"Import failed: {result.stdout}\n{result.stderr}"
    assert "GUI imported successfully" in result.stdout


def test_preflight_error_message_is_helpful():
    """Verify preflight error messages are clear and actionable."""
    test_script = """
import sys
import os

# Break PATH to cause ffmpeg failure
os.environ['PATH'] = '/tmp'

try:
    from knowledge_system.gui import launch_gui
    sys.exit(1)  # Should not reach here
except Exception as e:
    error_msg = str(e)
    # Check for helpful error message
    if "FFmpeg not found" in error_msg:
        print("✅ Error message mentions FFmpeg")
    if "brew install ffmpeg" in error_msg or "Install" in error_msg:
        print("✅ Error message provides solution")
    sys.exit(0)
"""
    
    result = subprocess.run(
        [sys.executable, "-c", test_script],
        capture_output=True,
        text=True,
        cwd=Path(__file__).parent.parent,
    )
    
    assert result.returncode == 0
    assert "Error message mentions FFmpeg" in result.stdout


if __name__ == "__main__":
    print("Running preflight visibility tests...\n")
    
    print("Test 1: Preflight failure stops app launch")
    test_preflight_failure_stops_app_launch()
    print("✅ PASS\n")
    
    print("Test 2: Valid dependencies allow import")
    test_preflight_success_allows_import()
    print("✅ PASS\n")
    
    print("Test 3: Error messages are helpful")
    test_preflight_error_message_is_helpful()
    print("✅ PASS\n")
    
    print("🎉 All preflight visibility tests passed!")

