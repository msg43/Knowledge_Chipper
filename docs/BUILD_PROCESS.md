# Build Process for Knowledge Chipper DMG

This document explains how to build the Knowledge Chipper DMG with all models bundled for internal company distribution.

## Prerequisites

1. **macOS** development machine
2. **Python 3.13+** installed
3. **HuggingFace token** (one-time setup)
4. **All dependencies** installed (`pip install -e ".[full]"`)

## One-Time Setup

### 1. Prepare Bundled Models

Before your first build (or when updating models):

```bash
# Set your HuggingFace token (or add to config/credentials.yaml)
export HF_TOKEN="hf_your_token_here"

# Download all models to bundled_models/ directory
./scripts/prepare_bundled_models.sh
```

This downloads:
- Pyannote speaker-diarization model (~400MB)
- Stores in `bundled_models/` directory
- Only binary files are gitignored

### 2. Verify Models

Check that models are downloaded:

```bash
ls -la bundled_models/pyannote/speaker-diarization-3.1/
# Should see .bin files and config files
```

## Building the DMG

### Build Options

```bash
# Full Build (Default - ~4GB DMG with all models)
./scripts/build_macos_app.sh --dmg

# Minimal Build (~1GB DMG, models download on first use)
./scripts/build_macos_app.sh --dmg --no-bundle

# With specific options
./scripts/build_macos_app.sh --dmg --with-hce --with-diarization
```

### What Happens During Build

1. **Python Environment**: Creates clean venv in app bundle
2. **Dependencies**: Installs all required packages
3. **FFMPEG**: Bundles FFMPEG binary (automatic)
4. **Pyannote Model**: Copies from `bundled_models/` into app
5. **Configuration**: Sets up environment variables
6. **DMG Creation**: Packages everything into distributable DMG

## Build Output

- **DMG Location**: `dist/Skip the Podcast Desktop-{version}.dmg`
- **Size**: ~2.5GB (includes all models)
- **Contents**:
  - Complete Python environment
  - FFMPEG binary
  - Whisper models (downloaded on first use)
  - Pyannote diarization model (pre-bundled)
  - Ollama (downloaded on first use)

## CI/CD Considerations

For automated builds:

1. **Store Models in CI**:
   ```yaml
   # Example GitHub Actions
   - name: Restore bundled models
     uses: actions/cache@v3
     with:
       path: bundled_models/
       key: bundled-models-v1
   ```

2. **Or Download Fresh**:
   ```yaml
   - name: Prepare models
     env:
       HF_TOKEN: ${{ secrets.HF_TOKEN }}
     run: ./scripts/prepare_bundled_models.sh
   ```

## Troubleshooting

### "Model not found" during build

Run `./scripts/prepare_bundled_models.sh` first.

### Build fails at pyannote step

Check:
1. Models exist in `bundled_models/pyannote/`
2. Binary files (*.bin) are present
3. Disk space available (need ~3GB free)

### DMG is smaller than expected

The pyannote model might not be bundled. Check build logs for:
```
✅ Pyannote model successfully bundled (internal use only)
```

## Updating Models

When pyannote releases a new version:

1. Update model version in scripts if needed
2. Delete old models: `rm -rf bundled_models/pyannote/`
3. Re-run: `./scripts/prepare_bundled_models.sh`
4. Test the app with new model
5. Rebuild DMG

## Security Notes

- Models in `bundled_models/` are gitignored (too large)
- Each developer needs to run `prepare_bundled_models.sh`
- For team builds, consider shared model storage
- This bundling is for internal use where terms are pre-accepted

## Quick Build Checklist

- [ ] HuggingFace token configured
- [ ] Run `./scripts/prepare_bundled_models.sh` 
- [ ] Verify models in `bundled_models/`
- [ ] Run `./scripts/build_macos_app.sh --dmg`
- [ ] Test DMG on clean machine
- [ ] Verify speaker diarization works offline
