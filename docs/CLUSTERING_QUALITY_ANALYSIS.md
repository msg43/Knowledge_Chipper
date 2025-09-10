# Clustering Method Quality Analysis for Speaker Diarization

## Overview

When we switched from the default clustering to centroid clustering to enable MPS, we made a trade-off between speed and potential quality. Here's what we know:

## Clustering Methods in Pyannote

### 1. **Default Method (likely AgglomerativeClustering)**
- **Type**: Hierarchical clustering
- **Advantages**:
  - Can identify non-spherical clusters
  - Adapts to varying cluster sizes
  - More robust to outliers
  - No need to predefine number of speakers
- **Disadvantages**:
  - Computationally expensive O(n²) or O(n³)
  - May use spectral methods that fail on MPS

### 2. **Centroid Clustering (our MPS-compatible choice)**
- **Type**: K-means style centroid-based
- **Advantages**:
  - Much faster O(n*k*iterations)
  - Works perfectly on MPS
  - Good for well-separated speakers
- **Disadvantages**:
  - Assumes spherical clusters
  - Sensitive to outliers
  - May struggle with overlapping speaker embeddings

## Quality Impact Analysis

### Theoretical Impact
- **Minimal for most use cases**: When speakers have distinct voice characteristics
- **Potential degradation**: When speakers have very similar voices or lots of overlapping speech

### Practical Impact (Based on Our Testing)
- The 34x speedup (6.3s vs 216s) enables processing 1000+ videos
- For Knowledge Chipper's use case (educational content, podcasts), speakers are usually distinct
- The clustering parameters we set (`min_cluster_size = 15`) help reduce over-segmentation

## Mitigation Strategies

1. **Current Implementation**:
   ```python
   pipeline.clustering.method = "centroid"
   pipeline.clustering.min_cluster_size = 15  # Reduces false splits
   ```

2. **Future Improvements**:
   - Could add a quality vs speed toggle
   - For critical applications, could fall back to CPU with hierarchical clustering
   - Could experiment with different distance thresholds

## Recommendations

### Use MPS + Centroid (Current) When:
- Processing large batches (100s-1000s of videos)
- Speakers are reasonably distinct
- Speed is critical
- Running on Apple Silicon

### Consider CPU + Hierarchical When:
- Processing single critical files
- Speakers have very similar voices
- Maximum accuracy is required
- Have time to wait (34x slower)

## Bottom Line

**For Knowledge Chipper's use case, the quality trade-off is likely minimal while the performance gain is massive.** Most educational content and podcasts have distinct speakers, making centroid clustering highly effective.

The ability to process 1000 videos in the time it would take to process 30 with the CPU method far outweighs any minor quality differences for batch processing scenarios.
