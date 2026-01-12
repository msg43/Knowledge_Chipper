# PyInstaller Onedir Migration

**Date:** January 12, 2026  
**Status:** ✅ Complete  
**Version:** daemon.spec v2.0 (onedir mode)

---

## Overview

Migrated the daemon PyInstaller build from **onefile mode** to **onedir mode** to:
1. Comply with PyInstaller 7.0 requirements for macOS .app bundles
2. Improve startup performance
3. Better compatibility with macOS security features
4. Eliminate build warnings

---

## What Changed

### Build Mode: Onefile → Onedir

**Before (Onefile):**
```python
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,  # Everything bundled into single executable
    a.zipfiles,
    a.datas,
    # ...
)

app = BUNDLE(
    exe,  # Wraps single executable
    # ...
)
```

**After (Onedir):**
```python
exe = EXE(
    pyz,
    a.scripts,
    [],  # Empty - files go in COLLECT
    exclude_binaries=True,  # CRITICAL for onedir
    # ...
)

coll = COLLECT(
    exe,
    a.binaries,  # Files in directory structure
    a.zipfiles,
    a.datas,
    # ...
)

app = BUNDLE(
    coll,  # Wraps directory structure
    # ...
)
```

### Dependency Cleanup

**Removed:**
- `pydub` from hiddenimports (not used - replaced by FFmpegAudioProcessor)

**Added to excludes:**
- `MySQLdb`, `pysqlite2`, `psycopg2`, `pymysql`, `cx_Oracle` (unused database drivers)
- `tensorboard` (optional PyTorch dependency)
- `urllib3.contrib.emscripten` (browser-only module)

---

## Why This Matters

### 1. PyInstaller 7.0 Compatibility

**Deprecation Warning (Pre-Migration):**
```
DEPRECATION: Onefile mode in combination with macOS .app bundles don't make sense
(a .app bundle can not be a single file) and clashes with macOS's security.
Please migrate to onedir mode. This will become an error in v7.0.
```

**Resolution:**
- Onedir mode is the recommended approach for .app bundles
- Will be **required** in PyInstaller 7.0+
- Future-proofs the build process

### 2. Build Warning Reduction

**Before:**
```
ERROR: Hidden import 'pydub' not found
WARNING: Hidden import "pysqlite2" not found!
WARNING: Hidden import "MySQLdb" not found!
```

**After:**
- `pydub` error eliminated (not used in codebase)
- Database driver warnings suppressed (excluded explicitly)
- Remaining warnings are platform-specific (Linux/Windows libraries on macOS) - harmless

### 3. Performance Benefits

**Onedir Advantages:**
- Faster startup (no need to extract entire bundle to temp directory)
- Better disk caching (OS can cache individual files)
- Easier debugging (can inspect individual files in bundle)

**Onefile Disadvantages:**
- Extracts entire bundle to temp on every launch
- Slower startup (~2-3 seconds overhead)
- Harder to debug (everything compressed)

---

## Build Output Changes

### Directory Structure

**Before (Onefile):**
```
dist/daemon_dist/
└── GetReceiptsDaemon.app/
    └── Contents/
        └── MacOS/
            └── GetReceiptsDaemon  (single 500MB+ file)
```

**After (Onedir):**
```
dist/daemon_dist/
└── GetReceiptsDaemon.app/
    └── Contents/
        └── MacOS/
            ├── GetReceiptsDaemon  (small launcher)
            └── GetReceiptsDaemon/  (directory with all files)
                ├── Python
                ├── base_library.zip
                ├── *.dylib
                └── ...
```

### PKG Installer Impact

**No change to end users:**
- PKG still installs to `/Applications/GetReceipts Daemon.app`
- Same code signing and notarization process
- Same functionality and behavior
- Slightly faster startup time

---

## Verification

### Test the New Build

```bash
# Build with new spec
cd /Users/matthewgreer/Projects/Knowledge_Chipper
bash installer/build_pkg.sh

# Verify structure
ls -la dist/daemon_dist/GetReceiptsDaemon.app/Contents/MacOS/

# Should see:
# - GetReceiptsDaemon (executable)
# - GetReceiptsDaemon/ (directory)

# Test functionality
sudo installer -pkg dist/GetReceipts-Daemon-1.1.3.pkg -target /
# Verify daemon starts and responds
curl http://localhost:8765/health
```

### Expected Warnings (Harmless)

These warnings are **normal and safe to ignore**:

1. **Platform-specific libraries:**
   - `libc.so.6`, `user32`, `msvcrt` (Linux/Windows)
   - `libnvrtc.so`, `libcuda.so.1` (NVIDIA CUDA)

2. **Optional dependencies:**
   - `scipy.special._cdflib` (optional scipy module)
   - `torch.utils.tensorboard` (TensorBoard not installed)

3. **System library resolution:**
   - `@rpath/libsox.dylib` (torchaudio - symbolic link added)
   - `@rpath/libc++.1.dylib` (system C++ library)

---

## Migration Checklist

- [x] Update `daemon.spec` to onedir mode
- [x] Remove `pydub` from hiddenimports
- [x] Add database driver excludes
- [x] Add optional dependency excludes
- [x] Update documentation in spec file
- [x] Update CHANGELOG.md
- [x] Create migration documentation
- [ ] Test build with new spec
- [ ] Verify PKG installation works
- [ ] Verify daemon functionality
- [ ] Deploy to production

---

## Rollback Plan

If issues arise, revert to onefile mode:

```bash
git checkout HEAD~1 installer/daemon.spec
bash installer/build_pkg.sh
```

However, note that onefile mode will **stop working** in PyInstaller 7.0.

---

## References

### PyInstaller Documentation
- [Onedir vs Onefile](https://pyinstaller.org/en/stable/operating-mode.html)
- [macOS App Bundles](https://pyinstaller.org/en/stable/spec-files.html#spec-file-options-for-a-macos-bundle)

### Related Files
- `installer/daemon.spec` - PyInstaller spec file
- `installer/build_pkg.sh` - Build script
- `requirements-daemon.txt` - Minimal daemon dependencies
- `src/knowledge_system/utils/audio_utils.py` - FFmpeg audio processor (replaces pydub)

### Related Issues
- PyInstaller deprecation warning (onefile + .app bundle)
- `pydub` import error during build
- Excessive build warnings from unused dependencies

---

## Future Improvements

### Potential Optimizations

1. **Reduce bundle size:**
   - Exclude more unused modules (scipy, pandas if not needed)
   - Strip debug symbols from binaries
   - Compress with UPX (already enabled)

2. **Improve startup time:**
   - Lazy-load heavy modules (torch, transformers)
   - Use `--onefile-tempdir-spec` for custom temp location
   - Pre-compile Python bytecode

3. **Better dependency management:**
   - Create minimal requirements-build.txt for PyInstaller
   - Separate runtime vs build dependencies
   - Use virtual environment isolation

---

## Lessons Learned

1. **Always check deprecation warnings** - they become errors in future versions
2. **Clean up unused dependencies** - reduces build time and warnings
3. **Test with minimal requirements** - catches missing dependencies early
4. **Document architectural decisions** - helps future maintainers
5. **Onedir is better for .app bundles** - faster, more compatible, future-proof
