# Obsolete Folders Analysis

**Date:** October 27, 2025  
**Total Size of Obsolete Content:** ~1.35 GB

---

## Summary

Found **9 obsolete or cleanup-worthy folders** consuming significant disk space. Recommendations below for safe removal.

---

## CATEGORY 1: Explicitly Marked for Deletion (CAN DELETE NOW)

### 1. `_to_delete/` - **3.6 MB**
- **Last Modified:** October 14, 2025
- **Contents:** 
  - `backups/` - Old backup files
  - `deprecated_code/` - Empty directory
  - `docs/` - Empty directory
  - `logs/` - Old log files (20 files)
- **Recommendation:** ✅ **DELETE IMMEDIATELY**
- **Command:** `rm -rf _to_delete/`

### 2. `_quarantine/` - **176 KB**
- **Last Modified:** October 24, 2025
- **Contents:**
  - `obsolete_tests/` - 17 old test files with README explaining they're obsolete
  - Tests for old architecture (pre-unification)
- **Recommendation:** ✅ **DELETE AFTER REVIEW**
- **Command:** `rm -rf _quarantine/`

### 3. `.git_backup_20250807_185718/` - **5.2 MB**
- **Created:** August 7, 2025 (3+ months old)
- **Contents:** Git repository backup
- **Recommendation:** ✅ **DELETE** (if current .git is healthy)
- **Verification First:**
  ```bash
  git status  # Ensure .git is healthy
  git fsck    # Check for corruption
  ```
- **Command:** `rm -rf .git_backup_20250807_185718/`

---

## CATEGORY 2: Deprecated Code (KEEP FOR NOW - DELETE DEC 2025)

### 4. `_deprecated/` - **36 KB**
- **Last Modified:** October 26, 2025
- **Contents:**
  - `database/hce_operations.py` - Old storage code
  - `test_hce_operations.py` - Tests for old code
  - `README.md` - Migration guide with rollback instructions
- **Deprecation Timeline:**
  - Deprecated: Oct 23, 2025
  - Planned removal: Nov 23, 2025 (30-day grace)
  - Final deletion: Dec 23, 2025
- **Recommendation:** ⏳ **KEEP UNTIL DEC 2025** (grace period for rollback)
- **Action:** Review in late November to confirm no rollback needed

---

## CATEGORY 3: Build Artifacts - Temporary Working Directories

**IMPORTANT:** The build system uses a two-layer cache:
- `dist/*.tar.gz` = Final cached artifacts (11+ GB) - **KEEP THESE!**
- `build_*/` = Temporary working directories - **SAFE TO DELETE**

When you run `./scripts/build_complete_pkg.sh`:
1. Checks if `dist/python-framework-3.13-macos.tar.gz` exists
2. If exists and script unchanged → Uses cached version (fast!)
3. If missing → Rebuilds to `dist/` using `build_framework/` as temp workspace
4. Final output always goes to `dist/`, temp folders can be deleted anytime

**Result:** Deleting `build_*/` saves disk space with NO impact on rebuild speed!

### 5. `build_framework/` - **706 MB** 🔴 LARGEST
- **Contents:** Python 3.13.1 framework (5,799 files)
- **Purpose:** Temporary workspace for building Python framework
- **Final Output:** `dist/python-framework-3.13-macos.tar.gz` (2.1 KB - kept!)
- **Recommendation:** ✅ **DELETE** (temp workspace, final output cached in dist/)
- **Rebuild:** Auto-regenerates if needed, uses dist/ cache
- **Command:** `rm -rf build_framework/`

### 6. `github_models_prep/` - **502 MB** 🔴 2ND LARGEST
- **Contents:** Model files prepared for GitHub releases (89 files)
- **Purpose:** Temporary staging - sources already bundled in `dist/ai-models-bundle.tar.gz`
- **Final Output:** `dist/ai-models-bundle.tar.gz` (341 MB - kept!)
- **Recommendation:** ✅ **DELETE** (sources already in dist/ cache)
- **Rebuild:** Uses dist/ cache, no need to re-download
- **Command:** `rm -rf github_models_prep/`

### 7. `build_ffmpeg/` - **101 MB**
- **Contents:** FFmpeg binary workspace (4 files, including 80MB executable)
- **Purpose:** Temporary workspace for FFmpeg bundling
- **Final Output:** `dist/ffmpeg-macos-universal.tar.gz` (25 MB - kept!)
- **Recommendation:** ✅ **DELETE** (temp workspace, final output in dist/)
- **Rebuild:** Uses cached dist/ tarball
- **Command:** `rm -rf build_ffmpeg/`

### 8. `build_pkg/` - **11 MB**
- **Contents:** PKG installer artifacts (341 files)
- **Purpose:** Temporary build workspace for final .pkg assembly
- **Final Output:** `dist/SkipThePodcast-*.pkg` (created on demand)
- **Recommendation:** ✅ **DELETE** (regenerated each build)
- **Rebuild:** Auto-regenerates during PKG build
- **Command:** `rm -rf build_pkg/`

### 9. `build_app_template/` - **4.9 MB**
- **Contents:** App template with 281 files
- **Purpose:** Temporary template workspace
- **Recommendation:** ✅ **DELETE** (regenerated during build)
- **Rebuild:** Auto-regenerates during PKG build
- **Command:** `rm -rf build_app_template/`

### 10. `build_packages/` - **8 KB**
- **Contents:** Old Packages.app project file
- **Purpose:** Legacy installer (now using SkipThePodcast.pkgproj in root)
- **Recommendation:** ✅ **DELETE** (superseded, unused)
- **Command:** `rm -rf build_packages/`

---

## CATEGORY 4: Test/Coverage Artifacts (CAN DELETE)

### 11. `htmlcov/` - **19 MB**
- **Contents:** HTML code coverage reports (174 files)
- **Purpose:** Test coverage visualization
- **Recommendation:** ✅ **DELETE** (regenerated by pytest)
- **Regenerate Command:** `pytest --cov=src --cov-report=html`
- **Command:** `rm -rf htmlcov/`

### 12. `test-results/` - **104 KB**
- **Contents:** Test result artifacts
- **Purpose:** Pytest output files
- **Recommendation:** ✅ **DELETE** (regenerated on test runs)
- **Command:** `rm -rf test-results/`

---

## CATEGORY 5: Old Database Backups (ARCHIVE OR DELETE)

### 13. Database Backup Files - **1.4 MB total**
```
knowledge_system.db.backup.20251024_195602          (368 KB)
knowledge_system.db.pre_unification.20251022_234552 (368 KB)
knowledge_system.db.pre_unification.20251022_234602 (368 KB)
knowledge_system.db.pre_unification.20251022_234622 (368 KB)
```

- **Purpose:** Backups before unification migration
- **Recommendation:** 
  - ⏳ **KEEP** `db.backup.20251024_195602` (most recent)
  - ✅ **DELETE** the three `pre_unification` duplicates (5 days old, same content)
- **Commands:**
  ```bash
  # Keep only the most recent backup
  rm knowledge_system.db.pre_unification.*
  
  # Optional: Move backup to backups folder
  mkdir -p backups/database
  mv knowledge_system.db.backup.* backups/database/
  ```

### 14. Config Backup Files - **6.4 KB total**
```
pyproject.toml.backup     (4.8 KB)
requirements.txt.backup   (1.5 KB)
```

- **Recommendation:** ✅ **DELETE** (git tracks all changes)
- **Command:** `rm *.backup`

---

## CATEGORY 6: Empty/Minimal Folders (KEEP FOR NOW)

### `tmp/` - **Empty**
- **Purpose:** Temporary file storage (actively used)
- **Recommendation:** 👍 **KEEP** (working directory)

### `state/` - **24 KB**
- **Contents:** `application_state.json.backup` (1 KB)
- **Recommendation:** 
  - Delete the .backup file: `rm state/application_state.json.backup`
  - Keep the `state/` directory (used by application)

### `Reports/` - **8 KB**
- **Contents:** Empty `Logs/` subdirectory
- **Purpose:** Unknown/obsolete
- **Recommendation:** ⚠️ **DELETE** (appears unused)
- **Command:** `rm -rf Reports/`

---

## CATEGORY 7: Working Directories (KEEP)

### `data/` - **870 MB**
- **Contents:** Test files (84 files) and working data
- **Recommendation:** 👍 **KEEP** (active test data)

### `output/` - **Variable size**
- **Contents:** Generated summaries and transcripts (50+ files)
- **Recommendation:** 👍 **KEEP** (user-generated content)

---

## Cleanup Summary

### Safe to Delete Immediately (~1.35 GB)

**⚠️ IMPORTANT: Keep `dist/` directory - it contains cached build artifacts (11+ GB) that save hours of rebuild time!**

```bash
# Delete explicitly marked folders
rm -rf _to_delete/ _quarantine/ .git_backup_20250807_185718/

# Delete TEMPORARY build workspaces (final outputs cached in dist/)
rm -rf build_framework/ github_models_prep/ build_ffmpeg/ 
rm -rf build_pkg/ build_app_template/ build_packages/

# Delete test artifacts (regenerate on demand)
rm -rf htmlcov/ test-results/

# Delete obsolete reports
rm -rf Reports/

# Delete duplicate/old database backups
rm knowledge_system.db.pre_unification.*

# Delete config backups
rm *.backup

# Clean up state backup
rm state/application_state.json.backup
```

**Total space saved: ~1.35 GB**

**Build performance after cleanup:**
- With `dist/` cache: ~2 minutes to rebuild PKG
- Without `dist/`: ~1 hour (re-downloads 11GB models, recompiles Python)

### Keep For Now
- `_deprecated/` - Keep until Dec 2025 (rollback grace period)
- `data/` - Active test data
- `output/` - User-generated content
- `tmp/` - Working directory
- `state/` - Application state (after removing .backup)
- **`dist/` - Build cache (11+ GB) - CRITICAL: Saves hours of rebuild time!**
  - `dist/python-framework-3.13-macos.tar.gz` (2.1 KB)
  - `dist/ai-models-bundle.tar.gz` (341 MB)
  - `dist/ffmpeg-macos-universal.tar.gz` (25 MB)
  - `dist/ollama-models-bundle.tar.gz` (11 GB!)
  - Hash cache files (`.python_framework_hash`, etc.)
- Most recent DB backup: `knowledge_system.db.backup.20251024_195602`

---

## Verification Steps

Before deletion, verify:

1. **Git is healthy:**
   ```bash
   git status
   git fsck
   ```

2. **Builds work:**
   ```bash
   # Verify you can rebuild if needed
   ./scripts/build_complete_pkg.sh --dry-run  # If available
   ```

3. **Recent backups exist:**
   ```bash
   ls -lh knowledge_system.db*
   # Ensure at least one recent backup exists
   ```

4. **No active builds:**
   ```bash
   # Ensure no build processes are running
   ps aux | grep -E "build|make|pkg"
   ```

---

## Post-Cleanup Actions

After cleanup:

1. **Update .gitignore** to prevent regeneration of deleted folders:
   ```gitignore
   # Build artifacts
   build_framework/
   build_ffmpeg/
   build_pkg/
   build_app_template/
   build_packages/
   github_models_prep/
   
   # Test artifacts
   htmlcov/
   test-results/
   
   # Backups
   *.backup
   .git_backup*/
   ```

2. **Document build process** in README.md under "Development" section:
   ```markdown
   ## Building the PKG Installer
   
   The build system uses intelligent caching for fast rebuilds:
   
   ```bash
   ./scripts/build_complete_pkg.sh
   ```
   
   **Build Cache (`dist/` directory):**
   - Keeps final build artifacts (11+ GB)
   - Enables 2-minute rebuilds vs 1-hour full builds
   - Safe to keep, saves significant time
   
   **Temporary Workspaces (`build_*/` directories):**
   - Created during build process
   - Safe to delete anytime
   - Auto-regenerate when needed
   
   **Rebuild times:**
   - With cache: ~2 minutes (just packaging)
   - Without cache: ~1 hour (downloads 11GB models, compiles Python)
   ```

---

## Recommended Cleanup Command

**Safe, comprehensive cleanup:**

```bash
#!/bin/bash
# Safe cleanup of obsolete folders

cd /Users/matthewgreer/Projects/Knowledge_Chipper

echo "🧹 Cleaning up obsolete folders..."

# Explicitly marked for deletion
echo "  Removing _to_delete, _quarantine, .git_backup..."
rm -rf _to_delete/ _quarantine/ .git_backup_20250807_185718/

# Build artifacts
echo "  Removing build artifacts (1.3 GB)..."
rm -rf build_framework/ github_models_prep/ build_ffmpeg/ 
rm -rf build_pkg/ build_app_template/ build_packages/

# Test artifacts
echo "  Removing test artifacts..."
rm -rf htmlcov/ test-results/ Reports/

# Old backups
echo "  Removing old database backups..."
rm -f knowledge_system.db.pre_unification.*

# Config backups
echo "  Removing config backups..."
rm -f *.backup

# State backup
echo "  Cleaning state folder..."
rm -f state/*.backup

echo "✅ Cleanup complete! Freed ~1.35 GB of disk space."
echo ""
echo "Kept:"
echo "  - _deprecated/ (until Dec 2025)"
echo "  - data/ (test files)"
echo "  - output/ (user content)"
echo "  - knowledge_system.db.backup.20251024_195602 (recent backup)"
```

Save this as `scripts/cleanup_obsolete.sh` and run with:
```bash
chmod +x scripts/cleanup_obsolete.sh
./scripts/cleanup_obsolete.sh
```
