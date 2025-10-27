# dist/ Folder Cleanup

**Date:** October 27, 2025

## Current State

The `dist/` folder contains **14 GB** of files:

### Essential Build Cache (KEEP - 11.4 GB):
```
✅ python-framework-3.13-macos.tar.gz      2.1 KB
✅ ai-models-bundle.tar.gz                 341 MB
✅ ffmpeg-macos-universal.tar.gz           25 MB
✅ ollama-models-bundle.tar.gz             11 GB    ← Critical: saves 1 hour rebuild time
✅ app-source-code.tar.gz                  1.0 MB
✅ .python_framework_hash                  65 bytes
✅ .ai_models_hash                         65 bytes
```

### Old PKG Files (CAN DELETE - 2.3 GB):
```
❌ Skip_the_Podcast_Desktop-3.2.22.pkg through 3.2.82.pkg
   - 61 old version PKGs
   - Sizes: 2.4 MB - 4.1 MB each
   - Total: ~2.3 GB
```

**Only need:**
- ✅ Latest version PKG (currently 3.2.82.pkg)
- ✅ Latest signed PKG (currently 3.2.81-signed.pkg or 3.2.82-signed.pkg if exists)

### Test PKG Files (CAN DELETE - 10 KB):
```
❌ test-auth.pkg                           3.4 KB
❌ test-root-minimal.pkg                   3.2 KB
❌ test-system.pkg                         3.2 KB
```

## Recommended Cleanup

### Option 1: Keep Only Latest PKG (~2.3 GB freed)
```bash
cd dist/

# Find the latest version number
LATEST_VERSION=$(ls -1 Skip_the_Podcast_Desktop-*.pkg | grep -v signed | sed 's/Skip_the_Podcast_Desktop-//' | sed 's/.pkg//' | sort -V | tail -1)

echo "Keeping version: $LATEST_VERSION"

# Delete all PKGs except latest unsigned and latest signed
find . -name "Skip_the_Podcast_Desktop-*.pkg" \
  ! -name "Skip_the_Podcast_Desktop-${LATEST_VERSION}.pkg" \
  ! -name "Skip_the_Podcast_Desktop-*-signed.pkg" \
  -delete

# Delete old signed versions except latest
LATEST_SIGNED=$(ls -1 Skip_the_Podcast_Desktop-*-signed.pkg 2>/dev/null | sort -V | tail -1)
if [ -n "$LATEST_SIGNED" ]; then
  find . -name "Skip_the_Podcast_Desktop-*-signed.pkg" \
    ! -name "$LATEST_SIGNED" \
    -delete
fi

# Delete test PKGs
rm -f test-*.pkg

echo "✅ Cleaned dist/ - kept only latest builds"
```

### Option 2: Delete ALL PKGs (they rebuild in 2 minutes)
```bash
cd dist/

# Keep only the build cache tarballs
rm -f Skip_the_Podcast_Desktop-*.pkg
rm -f test-*.pkg

echo "✅ All PKG files deleted - rebuild with ./scripts/build_complete_pkg.sh"
```

## Why It's Safe

**PKG files are output, not cache:**
- Generated from the cached tarballs (`.tar.gz` files)
- Rebuild in ~2 minutes using cached artifacts
- No need to keep every version

**The important cache files:**
- `*.tar.gz` files contain the expensive-to-build artifacts
- These take 1+ hour to rebuild from scratch
- Must keep these!

## Automated Cleanup Script

Add to `scripts/cleanup_obsolete.sh`:

```bash
# Clean old PKG files in dist/
if [ -d "dist" ]; then
    echo ""
    echo "🗑️  Cleaning old PKG files from dist/..."
    
    cd dist/
    
    # Count PKG files
    PKG_COUNT=$(ls -1 Skip_the_Podcast_Desktop-*.pkg 2>/dev/null | wc -l)
    
    if [ "$PKG_COUNT" -gt 2 ]; then
        echo "  Found $PKG_COUNT PKG files"
        
        # Find latest version
        LATEST_VERSION=$(ls -1 Skip_the_Podcast_Desktop-*.pkg | grep -v signed | sed 's/Skip_the_Podcast_Desktop-//' | sed 's/.pkg//' | sort -V | tail -1)
        
        # Delete old unsigned versions
        find . -name "Skip_the_Podcast_Desktop-*.pkg" \
          ! -name "Skip_the_Podcast_Desktop-${LATEST_VERSION}.pkg" \
          ! -name "Skip_the_Podcast_Desktop-*-signed.pkg" \
          -delete
        
        # Delete old signed versions except latest
        LATEST_SIGNED=$(ls -1 Skip_the_Podcast_Desktop-*-signed.pkg 2>/dev/null | sort -V | tail -1)
        if [ -n "$LATEST_SIGNED" ]; then
          find . -name "Skip_the_Podcast_Desktop-*-signed.pkg" \
            ! -name "$LATEST_SIGNED" \
            -delete
        fi
        
        echo "  ✓ Kept only latest PKG: $LATEST_VERSION"
    else
        echo "  ✓ PKG count is reasonable ($PKG_COUNT files)"
    fi
    
    # Delete test PKGs
    if ls test-*.pkg 1> /dev/null 2>&1; then
        rm -f test-*.pkg
        echo "  ✓ Deleted test PKGs"
    fi
    
    cd ..
fi
```

## Space Summary

| Category | Current Size | After Cleanup | Savings |
|----------|--------------|---------------|---------|
| Old PKG files | 2.3 GB | 8 MB | 2.29 GB |
| Build cache tarballs | 11.4 GB | 11.4 GB | 0 (keep!) |
| **Total** | **13.7 GB** | **11.4 GB** | **2.29 GB** |

## After Cleanup

```
dist/
├── Skip_the_Podcast_Desktop-3.2.82.pkg          4.0 MB (latest)
├── Skip_the_Podcast_Desktop-3.2.81-signed.pkg   4.1 MB (latest signed)
├── python-framework-3.13-macos.tar.gz           2.1 KB ✅
├── ai-models-bundle.tar.gz                      341 MB ✅
├── ffmpeg-macos-universal.tar.gz                25 MB ✅
├── ollama-models-bundle.tar.gz                  11 GB ✅
├── app-source-code.tar.gz                       1.0 MB ✅
├── .python_framework_hash                       65 bytes
└── .ai_models_hash                              65 bytes

Total: ~11.4 GB (was 14 GB)
```

**Build performance maintained:**
- Still has all cached artifacts
- 2-minute rebuilds (unchanged)
- Only removed old output files

