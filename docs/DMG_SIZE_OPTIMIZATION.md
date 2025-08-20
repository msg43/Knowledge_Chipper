# 📦 DMG Size Optimization

## Overview

Knowledge Chipper now uses a **lightweight core installation** strategy that dramatically reduces the initial DMG download size from **1.4GB to ~200-300MB** (an 83% reduction!).

## What's Excluded from the DMG

### 🧠 **Large ML Dependencies** (Auto-download when needed)
- **torch**: ~382MB 
- **transformers**: ~105MB
- **sentence-transformers**: ~50MB
- **Total ML savings**: ~537MB

### 🎙️ **Whisper Models** (Auto-download when used)
- **tiny**: ~75MB
- **base**: ~142MB (recommended default)
- **small**: ~466MB
- **medium**: ~1.5GB
- **large**: ~3.1GB
- **Total possible model savings**: Up to 5GB+

### ⚡ **Diarization Dependencies** (Install on demand)
- **pyannote.audio**: ~2MB
- **Associated models**: ~50-100MB
- **Total diarization savings**: ~102MB

## How Runtime Downloads Work

### 🚀 **First Launch Experience**
1. App launches immediately with core functionality
2. **First-run setup dialog** appears automatically to guide users through model download
3. Users can choose which models to download (tiny ~75MB, base ~142MB, small ~466MB)
4. **Smart defaults**: Base model is pre-selected for best balance of speed/accuracy
5. **Skip option**: Users can skip setup and download models later from settings

### 🎯 **Smart Caching**
- Models download to `~/.cache/whisper-cpp/` (not inside app bundle)
- ML dependencies install to user's Python environment
- Cached files persist across app updates

### 🔄 **Lazy Loading**
- **HCE features**: Install torch/transformers when first used
- **Diarization**: Install pyannote.audio when speaker separation requested
- **Whisper models**: Download specific model when transcription starts

## Installation Options

### 📱 **Default (Lightweight)**
```bash
# Normal app installation - smallest download
# Downloads: ~200-300MB
```

### 🔧 **Manual Heavy Install** (Optional)
```bash
# For users who want everything pre-installed
pip install -e ".[full]"  # In app's Python environment
```

### 📊 **Feature-Specific Installs**
```bash
pip install -e ".[diarization]"  # Speaker diarization
pip install -e ".[hce]"          # Hybrid Claim Extractor
pip install -e ".[gui]"          # GUI components (already included)
```

## Benefits

### 👨‍💻 **For Users**
- ✅ **83% smaller** initial download
- ✅ **Faster** app distribution and updates
- ✅ **Immediate** core functionality
- ✅ **On-demand** advanced features

### 🔧 **For Development**
- ✅ **Faster** CI/CD builds
- ✅ **Smaller** GitHub releases
- ✅ **Reduced** bandwidth costs
- ✅ **Better** user experience

## Migration Notes

### 🔄 **Existing Users**
- Existing installations are not affected
- Cached models and dependencies remain available
- Next app update will be much smaller

### ⚠️ **First-Time Setup**
- First transcription may take longer due to model download
- Internet connection required for downloading models
- Clear progress indicators show download status

This optimization makes Knowledge Chipper much more accessible while maintaining full functionality through intelligent lazy loading.
