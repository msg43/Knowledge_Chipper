#!/usr/bin/env python3
"""
Script to fix the app icon issue in Knowledge Chipper.
This script will:
1. Add proper organization info to the main window
2. Test icon availability
3. Clear icon cache on macOS
"""

import platform
import subprocess
import sys
from pathlib import Path


def add_organization_info():
    """Add organization info to main_window_pyqt6.py"""
    main_window_file = Path("src/knowledge_system/gui/main_window_pyqt6.py")

    if not main_window_file.exists():
        print(f"❌ File not found: {main_window_file}")
        return False

    # Read the file
    with open(main_window_file, encoding="utf-8") as f:
        content = f.read()

    # Check if organization info is already added
    if "setOrganizationName" in content:
        print("✅ Organization info already present")
        return True

    # Add organization info after setApplicationVersion
    old_section = """        app.setApplicationName("Knowledge_Chipper")
        app.setApplicationDisplayName("Knowledge_Chipper")
        app.setApplicationVersion("1.0")"""

    new_section = """        app.setApplicationName("Knowledge_Chipper")
        app.setApplicationDisplayName("Knowledge_Chipper")
        app.setApplicationVersion("1.0")
        app.setOrganizationName("Knowledge_Chipper")
        app.setOrganizationDomain("knowledge-chipper.local")"""

    if old_section in content:
        content = content.replace(old_section, new_section)

        # Write back to file
        with open(main_window_file, "w", encoding="utf-8") as f:
            f.write(content)

        print("✅ Added organization info to main window")
        return True
    else:
        print("❌ Could not find the expected section to modify")
        return False


def test_icon_availability():
    """Test if icons are available"""
    try:
        # Add src to path
        sys.path.insert(0, str(Path(__file__).parent / "src"))
        from knowledge_system.gui.assets.icons import get_app_icon, get_icon_path

        icon_path = get_icon_path()
        if icon_path:
            print(f"✅ Icon found at: {icon_path}")
            print(f"   File size: {icon_path.stat().st_size} bytes")
            return True
        else:
            print("❌ No icon found")
            return False

    except Exception as e:
        print(f"❌ Error testing icon: {e}")
        return False


def clear_icon_cache_macos():
    """Clear icon cache on macOS"""
    if platform.system() != "Darwin":
        print("ℹ️  Icon cache clearing is only needed on macOS")
        return True

    try:
        print("🧹 Clearing macOS icon cache...")

        # Clear icon services cache
        subprocess.run(
            ["sudo", "rm", "-rf", "/Library/Caches/com.apple.iconservices.store"],
            check=False,
        )

        # Clear dock icon cache
        subprocess.run(
            [
                "sudo",
                "find",
                "/private/var/folders/",
                "-name",
                "com.apple.dock.iconcache",
                "-exec",
                "rm",
                "{}",
                ";",
            ],
            check=False,
        )

        # Restart Dock
        subprocess.run(["killall", "Dock"], check=False)

        # Restart Finder
        subprocess.run(["killall", "Finder"], check=False)

        print("✅ Icon cache cleared and Dock/Finder restarted")
        return True

    except Exception as e:
        print(f"❌ Error clearing cache: {e}")
        return False


def improve_icon_format_preference():
    """Improve icon format preference for better compatibility"""
    icons_file = Path("src/knowledge_system/gui/assets/icons.py")

    if not icons_file.exists():
        print(f"❌ Icons file not found: {icons_file}")
        return False

    # Read the file
    with open(icons_file, encoding="utf-8") as f:
        content = f.read()

    # Check if already optimized
    if 'icon_names = ["chipper.png", "chipper.ico"]' in content:
        print("✅ Icon format preference already optimized")
        return True

    # Update icon preference order (PNG first for better macOS compatibility)
    old_line = '    icon_names = ["chipper.ico", "chipper.png"]'
    new_line = '    icon_names = ["chipper.png", "chipper.ico"]  # PNG first for better macOS compatibility'

    if old_line in content:
        content = content.replace(old_line, new_line)

        # Write back to file
        with open(icons_file, "w", encoding="utf-8") as f:
            f.write(content)

        print("✅ Updated icon format preference (PNG first)")
        return True
    else:
        print("❌ Could not find icon_names line to update")
        return False


def main():
    """Main function to fix icon issues"""
    print("🔧 Fixing Knowledge Chipper Icon Issues...")
    print("=" * 50)

    success_count = 0

    # Step 1: Add organization info
    if add_organization_info():
        success_count += 1

    # Step 2: Improve icon format preference
    if improve_icon_format_preference():
        success_count += 1

    # Step 3: Test icon availability
    if test_icon_availability():
        success_count += 1

    # Step 4: Clear icon cache (macOS only)
    if clear_icon_cache_macos():
        success_count += 1

    print("=" * 50)
    print(f"✅ Completed {success_count}/4 fixes")

    if success_count >= 3:
        print("\n🎉 Icon fixes applied successfully!")
        print("\n📝 Next steps:")
        print("1. Restart the Knowledge Chipper application")
        print("2. If still seeing Python icon, try restarting your computer")
        print("3. The custom chipper icon should now appear")
    else:
        print("\n⚠️  Some fixes failed. You may need to apply them manually.")


if __name__ == "__main__":
    main()
