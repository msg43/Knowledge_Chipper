#!/usr/bin/env python3
"""
Quick check script to verify cookie persistence status.
Run this to see if cookies are saved and if they would load.
"""

import json
from pathlib import Path


def main():
    session_file = Path.home() / ".knowledge_system" / "gui_session.json"

    if not session_file.exists():
        print("❌ No session file found!")
        print(f"   Expected at: {session_file}")
        return

    with open(session_file) as f:
        data = json.load(f)

    tab_settings = data.get("tab_settings", {})
    local_trans = tab_settings.get("Local Transcription", {})
    cookie_files = local_trans.get("cookie_files", [])

    print("=" * 70)
    print("COOKIE PERSISTENCE STATUS")
    print("=" * 70)
    print(f"\nSession file: {session_file}")
    print(f"Last saved: {data.get('last_saved', 'Unknown')}")
    print(f"\nCookie files in session: {len(cookie_files)}")

    if cookie_files:
        print("\nCookie files:")
        for idx, cf in enumerate(cookie_files, 1):
            exists = Path(cf).exists()
            status = "✅" if exists else "❌"
            print(f"  {idx}. {status} {cf}")
            if exists:
                size = Path(cf).stat().st_size
                print(f"      Size: {size:,} bytes")

        print("\n" + "=" * 70)
        print("✅ COOKIE FILES ARE PERSISTED")
        print("=" * 70)
        print("\nIf you're not seeing these in the GUI, the issue is with LOADING,")
        print("not with SAVING. The files are correctly saved to the session.")
        print("\nTroubleshooting steps:")
        print("1. Launch the GUI")
        print("2. Go to the Transcribe tab")
        print("3. Scroll down to the 'Cookie Authentication' section")
        print("4. Check if the cookie file paths are shown")
        print("\nIf they're NOT shown:")
        print("- Check the logs for any errors during settings load")
        print("- Try adding a cookie file manually and see if it persists")
        print("- The 200ms timer might not be enough on slower systems")
    else:
        print("\n" + "=" * 70)
        print("⚠️  NO COOKIE FILES IN SESSION")
        print("=" * 70)
        print("\nThis means either:")
        print("1. You haven't added any cookie files yet")
        print("2. Cookie files were added but not saved")
        print("3. The session file was cleared/reset")
        print("\nTo test persistence:")
        print("1. Launch the GUI")
        print("2. Go to Transcribe tab")
        print("3. Add a cookie file")
        print("4. Close the GUI")
        print("5. Run this script again")


if __name__ == "__main__":
    main()
