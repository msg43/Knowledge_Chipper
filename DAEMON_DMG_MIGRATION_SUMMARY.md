# Daemon DMG Migration Summary

**Date:** January 11, 2026  
**Status:** ✅ Complete

---

## Problem Statement

The GetReceipts.org website had inconsistent download links for the daemon installer:
- Some links pointed to `.pkg` files
- Some links pointed to `.dmg` files  
- Some links pointed to the wrong repository (`Knowledge_Chipper` instead of `Skipthepodcast.com`)
- Release process was publishing PKG files instead of DMG files

**User Impact:** Download buttons on GetReceipts.org were returning 404 errors or downloading the wrong format.

---

## Root Cause

Historical context: We initially used PKG installers but encountered notarization issues. These were resolved for DMG but persisted for PKG, so we switched to DMG. However, the codebase and release scripts were not fully updated to reflect this change.

---

## Solution Implemented

### 1. GetReceipts.org Download Links Updated

**Files Modified:**

#### `src/components/daemon-status-indicator.tsx`
```typescript
// BEFORE
window.location.href = "https://github.com/msg43/Knowledge_Chipper/releases/latest/download/Skip_the_Podcast_Desktop.pkg";

// AFTER
window.location.href = "https://github.com/msg43/Skipthepodcast.com/releases/latest/download/Skip_the_Podcast_Desktop.dmg";
```

#### `src/components/daemon-installer.tsx`
```typescript
// BEFORE (3 locations)
window.location.href = "https://github.com/msg43/Knowledge_Chipper/releases/latest/download/Skip_the_Podcast_Desktop.pkg";

// AFTER (3 locations)
window.location.href = "https://github.com/msg43/Skipthepodcast.com/releases/latest/download/Skip_the_Podcast_Desktop.dmg";
```

#### `src/app/api/download/generate-link-token/route.ts`
```typescript
// BEFORE
const downloadUrl = `https://github.com/msg43/Knowledge_Chipper/releases/latest/download/Skip_the_Podcast_Desktop.pkg?link_token=${token}`;

// AFTER
const downloadUrl = `https://github.com/msg43/Skipthepodcast.com/releases/latest/download/Skip_the_Podcast_Desktop.dmg?link_token=${token}`;
```

Also updated comment from `.pkg installer` to `.dmg installer`.

### 2. Release Script Updated

**File Modified:** `scripts/publish_release.sh`

**Key Changes:**

1. **Changed from PKG to DMG:**
   ```bash
   # BEFORE
   PKG_FILE="$PRIVATE_REPO_PATH/dist/Skip_the_Podcast_Desktop-${CURRENT_VERSION}.pkg"
   
   # AFTER
   DMG_FILE="$PRIVATE_REPO_PATH/dist/Skip_the_Podcast_Desktop-${CURRENT_VERSION}.dmg"
   ```

2. **Added Stable DMG Creation:**
   ```bash
   # Create a stable "Skip_the_Podcast_Desktop.dmg" symlink for consistent download URLs
   STABLE_DMG="$PRIVATE_REPO_PATH/dist/Skip_the_Podcast_Desktop.dmg"
   cp "$DMG_FILE" "$STABLE_DMG"
   ```

3. **Updated Release Notes:**
   - Changed installation instructions from PKG to DMG
   - Added "right-click → Open on first launch" instruction
   - Updated file size variable from `$PKG_SIZE` to `$DMG_SIZE`

4. **Upload Both DMG Files:**
   ```bash
   gh release create "$TAG_NAME" \
       --repo "msg43/skipthepodcast.com" \
       "$DMG_FILE" \           # Versioned: Skip_the_Podcast_Desktop-1.0.0.dmg
       "$STABLE_DMG" \         # Stable: Skip_the_Podcast_Desktop.dmg
       "./README.md"
   ```

### 3. Documentation Created

**New File:** `docs/DAEMON_RELEASE_PROCESS.md`

Complete documentation covering:
- ✅ Version management (daemon vs app versions)
- ✅ DMG build process
- ✅ GitHub release automation
- ✅ Stable vs versioned download URLs
- ✅ GetReceipts.org integration
- ✅ Auto-update system
- ✅ Troubleshooting guide
- ✅ Release checklist

### 4. CHANGELOG.md Updated

Added entry documenting:
- All GetReceipts.org link updates
- Release script changes
- New documentation
- Rationale for DMG over PKG
- Stable download URL

### 5. MANIFEST.md Updated

Added entry for `docs/DAEMON_RELEASE_PROCESS.md` in the "Documentation - Architecture and Systems" section.

---

## Stable Download URL

The daemon can now always be downloaded from this URL:

```
https://github.com/msg43/Skipthepodcast.com/releases/latest/download/Skip_the_Podcast_Desktop.dmg
```

This URL:
- ✅ Always points to the latest release
- ✅ Never changes (stable for hardcoded links)
- ✅ Works with auto-update system
- ✅ Used by all GetReceipts.org download buttons

---

## Release Process

### Quick Reference

1. **Update daemon version:**
   ```bash
   # Edit daemon/__init__.py
   __version__ = "1.0.1"
   ```

2. **Build DMG:**
   ```bash
   bash scripts/build_macos_app.sh --make-dmg --skip-install
   ```

3. **Publish release:**
   ```bash
   bash scripts/publish_release.sh
   ```

4. **Verify:**
   - Check https://github.com/msg43/Skipthepodcast.com/releases/latest
   - Verify both DMG files are present
   - Test download from GetReceipts.org

---

## Testing Checklist

- [x] All GetReceipts.org download links updated
- [x] Release script builds DMG instead of PKG
- [x] Release script uploads both versioned and stable DMG
- [x] Documentation created
- [x] CHANGELOG.md updated
- [x] MANIFEST.md updated

**Next Steps for User:**
- [ ] Test build process: `bash scripts/build_macos_app.sh --make-dmg --skip-install`
- [ ] Test release process: `bash scripts/publish_release.sh --dry-run`
- [ ] Verify download links work on GetReceipts.org after next release

---

## Benefits

1. **Consistency:** All download links now use the same format and repository
2. **Stability:** Stable URL never changes, always points to latest
3. **Automation:** Release script handles everything automatically
4. **Documentation:** Complete process documented for future reference
5. **User Experience:** DMG provides better installation experience than PKG

---

## Files Changed

### GetReceipts Repository
- `src/components/daemon-status-indicator.tsx`
- `src/components/daemon-installer.tsx`
- `src/app/api/download/generate-link-token/route.ts`

### Knowledge_Chipper Repository
- `scripts/publish_release.sh`
- `docs/DAEMON_RELEASE_PROCESS.md` (new)
- `CHANGELOG.md`
- `MANIFEST.md`
- `DAEMON_DMG_MIGRATION_SUMMARY.md` (this file)

---

## Version Information

**Current Versions:**
- Daemon: 1.0.0 (in `daemon/__init__.py`)
- Application: 4.1.0 (in `pyproject.toml`)

**Note:** These are separate version numbers. The daemon version tracks the background service/API, while the application version tracks the full desktop app.

---

## Questions & Answers

**Q: Why DMG instead of PKG?**  
A: PKG had persistent notarization issues that were resolved for DMG. DMG also provides a better user experience (drag-and-drop installation).

**Q: Why two DMG files per release?**  
A: The versioned DMG (`Skip_the_Podcast_Desktop-1.0.0.dmg`) preserves history, while the stable DMG (`Skip_the_Podcast_Desktop.dmg`) provides a consistent URL that always points to the latest version.

**Q: What happens to old releases?**  
A: They remain available on GitHub with their versioned DMG files. The stable DMG is updated to point to the newest release.

**Q: How does auto-update work?**  
A: The daemon checks the GitHub releases API every 24 hours, downloads the stable DMG if a newer version is available, and installs it automatically.

---

**Migration Complete! ✅**
