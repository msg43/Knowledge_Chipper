# DMG Size Issue Fix & GitHub 2GB Compliance

## Problem Summary
The public DMG build script was creating 700MB DMG files instead of the expected size. This was caused by the bundle script copying **ALL** Ollama models (125GB total) from the user's system instead of just the specific model needed. Additionally, GitHub has a **2GB file size limit** for release assets, requiring a new strategy.

## Root Cause
In `scripts/bundle_all_models.sh`, lines 47-55 were copying the entire `~/.ollama/models/blobs` and `~/.ollama/models/manifests` directories, which included every model the user had downloaded (in this case, 125GB worth of models).

## Solution
Modified the strategy to create a **GitHub 2GB-compliant "Full Package"**:

1. **Skip Ollama Bundling**: Don't bundle Ollama/LLM models in DMG (saves ~2GB)
2. **Auto-Install Configuration**: Create marker file for first-launch MVP LLM setup
3. **Essential Models Only**: Bundle Whisper, Pyannote, and voice fingerprinting models
4. **Guaranteed MVP LLM**: Ollama + llama3.2:3b download automatically on first launch
5. **Size Compliance**: Final DMG ~1.8GB (under GitHub's 2GB limit)

## Changes Made

### Modified Files:
- `scripts/bundle_all_models.sh` - Selective model bundling logic
- `scripts/release_dmg_to_public.sh` - Updated size estimate to ~3.2GB

### Key Improvements:
- **Before**: Copied all 125GB of models → DMG failed or was too large
- **After**: Skip Ollama bundling + auto-download → DMG is ~1.8GB (GitHub compliant)

## Expected DMG Breakdown (New Strategy)
- Base app + dependencies: ~500MB
- Whisper model: ~300MB  
- Pyannote model: ~400MB
- Voice fingerprinting models: ~410MB
- Ollama auto-install config: <1MB
- **Total: ~1.8GB** ✅ (Under GitHub 2GB limit)

### Auto-Downloads on First Launch:
- Ollama binary: ~50MB
- llama3.2:3b model: ~1.9GB
- **Total first-launch download: ~2GB**

## Testing Instructions

### Before Testing:
1. Ensure `llama3.2:3b` model is downloaded:
   ```bash
   ollama pull llama3.2:3b
   ```

2. Verify the model exists:
   ```bash
   ls ~/.ollama/models/manifests/registry.ollama.ai/library/llama3.2/3b
   ```

### Test the Fix:
1. Run the public DMG build:
   ```bash
   bash scripts/release_dmg_to_public.sh
   ```

2. Monitor the bundling output for:
   - "Copying specific Ollama model: llama3.2:3b (~2GB)..."
   - "✓ Copied blob: sha256-..." messages (should be 6 blobs)
   - "✅ Ollama model llama3.2:3b bundled successfully"

3. Check final DMG size:
   ```bash
   ls -lh dist/Skip_the_Podcast_Desktop-*.dmg
   ```
   Should be approximately 3.2GB instead of 700MB or 125GB.

### Verification:
The bundled DMG should contain:
- `Contents/MacOS/bin/ollama` (Ollama binary)
- `Contents/MacOS/.ollama/models/blobs/` (6 blob files, ~1.9GB total)
- `Contents/MacOS/.ollama/models/manifests/registry.ollama.ai/library/llama3.2/3b`

## Potential Issues

### If the script reports "Model llama3.2:3b not found":
```bash
ollama pull llama3.2:3b
```

### If blob files are missing:
The user may have a corrupted Ollama installation. Try:
```bash
ollama rm llama3.2:3b
ollama pull llama3.2:3b
```

### If DMG is still too small:
Check if other bundling steps (Whisper, voice models) are working correctly.

## GitHub Size Limitation

⚠️ **Important:** GitHub has a **2GB file size limit** for release assets. The full 3.2GB DMG will fail to upload with this error:
```
HTTP 422: Validation Failed
size must be less than or equal to 2147483648
```

### Solutions:

#### Option 1: Minimal DMG (Recommended)
Use the existing minimal DMG script:
```bash
bash scripts/release_minimal_dmg.sh
```
- Size: ~1GB (under limit)
- Models download on first use
- Perfect for GitHub releases

#### Option 2: Selective Bundling
Modify bundling to include only essential models:
- Base app + Whisper + Pyannote: ~1.2GB
- Skip Ollama bundling (downloads on first use)
- Still under 2GB limit

#### Option 3: Alternative Distribution
For full 3.2GB DMG:
- Host on Google Drive/Dropbox
- Use self-hosted server
- Split distribution (GitHub minimal + separate full download)

## Future Improvements
- Could add support for bundling alternative models if llama3.2:3b isn't available
- Could add validation to ensure all required blobs are present before building
- Could implement automatic model cleanup to remove unused models before bundling
- Could create a hybrid distribution strategy with both minimal and full DMG options
