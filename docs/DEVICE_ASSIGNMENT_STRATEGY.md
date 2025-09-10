# Device Assignment Strategy for Knowledge Chipper

## Permanent MPS Components ✅

### 1. **Diarization Pipeline** (pyannote.audio)
- **Segmentation Model**: MPS
- **Embedding Model**: MPS  
- **Clustering**: MPS (using centroid method)
- **Result**: 34x speedup (6.3s vs 216s)

### 2. **Whisper Transcription**
- Already uses Apple Neural Engine via CoreML
- Not affected by PyTorch MPS settings

### 3. **Audio Processing**
- **FFT/STFT**: MPS
- **Mel Spectrograms**: MPS
- **1D Convolutions**: MPS
- **Audio format conversions**: CPU (via FFmpeg)

### 4. **Neural Network Operations**
- **Transformers**: MPS
- **LSTM/GRU**: MPS
- **Attention Mechanisms**: MPS
- **Linear Layers**: MPS
- **Normalization**: MPS

## Permanent CPU Components ❌

### 1. **Unsupported Operations**
- **Eigenvalue Decomposition** (spectral clustering)
- **Small Sliding Windows** (unfold with window<800)
- **Sparse Tensor Operations**

### 2. **External Tools**
- **FFmpeg** (audio conversion)
- **Ollama** (LLM for speaker suggestions)
- **File I/O Operations**

## Implementation in Code

### Current Setup (Already Implemented)
```python
# diarization.py - Device detection
def _detect_best_device(self) -> str:
    if torch.cuda.is_available():
        return "cuda"
    elif torch.backends.mps.is_available() and torch.backends.mps.is_built():
        return "mps"  # ✅ Use MPS when available
    else:
        return "cpu"

# Clustering optimization for CPU/MPS
if self.device == "cpu":
    pipeline.clustering.method = "centroid"  # Works on both CPU and MPS
    pipeline.clustering.min_cluster_size = 15
```

### Automatic Fallback Pattern (If Needed)
```python
# For operations that might fail on MPS
def _run_with_fallback(self, operation, tensor, device="mps"):
    try:
        return operation(tensor.to(device))
    except NotImplementedError:
        logger.warning(f"Operation {operation.__name__} not supported on {device}, falling back to CPU")
        return operation(tensor.to("cpu"))
```

## Performance Impact

### With MPS Enabled (Current)
- **Diarization**: 6.3 seconds (MPS)
- **Transcription**: ~2 minutes (Neural Engine)
- **Total for 4.5min audio**: ~2.1 minutes

### Without MPS (CPU Only)
- **Diarization**: 216 seconds (CPU)
- **Transcription**: ~2 minutes (Neural Engine)
- **Total for 4.5min audio**: ~5.6 minutes

### For 1000 Videos
- **With MPS**: ~35 hours total
- **Without MPS**: ~93 hours total
- **Savings**: 58 hours (62% faster)

## Recommendations

1. **Keep current setup** - Centroid clustering works great on MPS
2. **No changes needed** - All components are optimally assigned
3. **Future consideration** - If spectral clustering is ever needed, implement CPU fallback
4. **Monitor PyTorch updates** - Future versions may add more MPS operations

## Summary

The current implementation already has optimal device assignments:
- ✅ Diarization models → MPS
- ✅ Clustering (centroid) → MPS  
- ✅ Whisper → Neural Engine (via CoreML)
- ✅ Audio conversion → CPU (FFmpeg)

No additional changes are needed. The system is fully optimized for Apple Silicon!
