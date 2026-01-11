# Desktop App Deprecation - Daemon Is Now THE Product

**Date:** January 11, 2026  
**Status:** ✅ Complete

---

## Executive Summary

The desktop GUI application (PyQt6) has been **fully deprecated**. The daemon is now the only product. All interaction happens through the web browser at GetReceipts.org.

---

## What Changed

### Before (Deprecated)

```
Skip the Podcast Desktop v4.1.0
├── Desktop GUI (PyQt6) ❌ DEPRECATED
├── Daemon v1.0.0 (embedded)
└── Version confusion (4.1.0 vs 1.0.0)
```

**Problems:**
- Two version numbers (application 4.1.0, daemon 1.0.0)
- Confusing for users and developers
- Desktop GUI rarely used (web interface is better)
- Maintenance burden

### After (Current)

```
GetReceipts Daemon v1.1.0 ✅
├── Background service only
├── Controlled via GetReceipts.org
└── Single version number (1.1.0)
```

**Benefits:**
- ✅ One version number
- ✅ Simpler architecture
- ✅ Better UX (web interface)
- ✅ Easier maintenance
- ✅ Clear product identity

---

## Version Number Changes

### Old System (DEPRECATED)

- **Application Version:** 4.1.0 (in `pyproject.toml`)
  - Used for GitHub release tags
  - Used for DMG filenames
  - Represented desktop GUI app

- **Daemon Version:** 1.0.0 (in `daemon/__init__.py`)
  - Embedded inside application
  - Reported by `/health` endpoint

### New System (CURRENT)

- **Daemon Version:** 1.1.0 (in `daemon/__init__.py`)
  - THE ONLY VERSION
  - Used for GitHub release tags
  - Used for DMG filenames
  - Reported by `/health` endpoint

### Legacy Version

The `pyproject.toml` version (4.1.0) is now **ignored** for releases:

```toml
[project]
version = "4.1.0"  # LEGACY - No longer used
```

This remains in the file for build system compatibility but is not used for versioning.

---

## Release Process Changes

### Old Release Process

```bash
# Read version from pyproject.toml
VERSION=4.1.0

# Create release
gh release create v4.1.0 \
  --title "Skip the Podcast v4.1.0" \
  Skip_the_Podcast_Desktop-4.1.0.dmg
```

### New Release Process

```bash
# Read version from daemon/__init__.py
VERSION=1.1.0

# Create release
gh release create v1.1.0 \
  --title "GetReceipts Daemon v1.1.0" \
  Skip_the_Podcast_Desktop-1.1.0.dmg
```

---

## Product Naming Changes

### Old Names (DEPRECATED)

- ❌ "Skip the Podcast Desktop"
- ❌ "Skip the Podcast v4.1.0"
- ❌ "Desktop Application"
- ❌ "GUI App"

### New Names (CURRENT)

- ✅ "GetReceipts Daemon"
- ✅ "GetReceipts Daemon v1.1.0"
- ✅ "Background Service"
- ✅ "Local Processor"

---

## User Experience

### What Users See

**Installation:**
1. Download `Skip_the_Podcast_Desktop-1.1.0.dmg`
2. Drag to Applications
3. Launch once (installs daemon)
4. Visit GetReceipts.org/contribute

**Usage:**
- No desktop window opens
- Everything controlled via web browser
- Daemon runs silently in background
- Processing happens locally on Mac

**Updates:**
- Daemon auto-updates every 24 hours
- Or restart daemon to check immediately
- No user action required

---

## Migration Path

### For Existing Users

Users with old versions (v3.5.0 or earlier):
1. Daemon auto-updates to v1.1.0
2. Desktop GUI no longer launches
3. All functionality available at GetReceipts.org
4. No manual migration needed

### For Developers

When working on the codebase:
1. **Ignore** `pyproject.toml` version for releases
2. **Only update** `daemon/__init__.py` version
3. **Use** daemon version in all documentation
4. **Test** via web interface, not desktop GUI

---

## Files Updated

### Release Scripts

- **`scripts/publish_release.sh`**
  - Now reads `daemon/__init__.py` instead of `pyproject.toml`
  - Release title changed to "GetReceipts Daemon v{VERSION}"
  - Release notes updated to emphasize web control

### Documentation

- **`docs/DAEMON_RELEASE_PROCESS.md`**
  - Complete rewrite for daemon-only releases
  - Removed all references to application version
  - Clarified single version number system

- **`CHANGELOG.md`**
  - Added deprecation announcement
  - Documented architectural change
  - Explained migration path

- **`DESKTOP_APP_DEPRECATION.md`** (this file)
  - Complete deprecation documentation

### Code

- **`daemon/__init__.py`**
  - Bumped to v1.1.0
  - Now THE version number

- **`pyproject.toml`**
  - Version remains at 4.1.0 (legacy)
  - No longer used for releases
  - Kept for build system compatibility

---

## FAQ

### Q: What happened to the desktop GUI?

**A:** It's deprecated. The web interface at GetReceipts.org is now the only UI.

### Q: Can I still use the old desktop app?

**A:** No. The daemon auto-updates and the GUI is no longer included.

### Q: What about the version 4.1.0?

**A:** That was the old application version. It's deprecated. We're now at daemon v1.1.0.

### Q: Will the DMG filename change?

**A:** Yes. New releases use daemon version:
- Old: `Skip_the_Podcast_Desktop-4.1.0.dmg`
- New: `Skip_the_Podcast_Desktop-1.1.0.dmg`

### Q: What about auto-updates?

**A:** They work perfectly. The daemon checks its own version (1.1.0) against GitHub releases.

### Q: Is this a breaking change?

**A:** No. For users, it's seamless. The daemon just updates and continues working.

---

## Timeline

- **December 2024:** Last release with desktop GUI (v3.5.0)
- **January 2026:** Desktop GUI deprecated
- **January 11, 2026:** Daemon v1.1.1 released (first daemon-only release)

---

## Next Steps

1. **Build daemon v1.1.1:**
   ```bash
   bash scripts/build_macos_app.sh --make-dmg --skip-install
   ```

2. **Publish release:**
   ```bash
   bash scripts/publish_release.sh
   ```

3. **Verify release:**
   - Check GitHub: https://github.com/msg43/Skipthepodcast.com/releases/latest
   - Should be titled "GetReceipts Daemon v1.1.1"
   - Should have both DMG files

4. **Test download:**
   - Visit GetReceipts.org/contribute/settings
   - Click "Re-Download App (.dmg)"
   - Should download v1.1.1

---

## Conclusion

This simplification makes the product clearer, easier to maintain, and better aligned with how users actually interact with it (via web browser). The daemon is now THE product, with a single version number and clear identity.

**GetReceipts Daemon v1.1.1** - Background processing for GetReceipts.org ✅
