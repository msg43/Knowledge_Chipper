# Voice Fingerprinting Accuracy Testing Guide

## Overview

This guide provides comprehensive instructions for testing the accuracy of the voice fingerprinting system and validating the 97% accuracy claim.

## Testing Framework Components

### 1. **Feature Consistency Testing**
Tests whether feature extraction produces consistent results across multiple runs.

### 2. **Similarity Calculation Testing**  
Tests the accuracy of voice similarity calculations between audio samples.

### 3. **Speaker Verification Testing**
Tests end-to-end accuracy with enrollment and verification scenarios.

### 4. **Performance Benchmarking**
Measures processing speed and resource usage across different audio lengths.

## Quick Start Testing

### Install Dependencies
```bash
# Install voice fingerprinting dependencies
pip install -r requirements-voice.txt

# Test that dependencies are working
knowledge-system voice test-dependencies
```

### Basic Feature Testing
```bash
# Test feature extraction consistency
knowledge-system voice test-consistency your_audio.wav --runs 10

# Test similarity between two files
knowledge-system voice test-similarity speaker1.wav speaker2.wav

# Benchmark performance
knowledge-system voice benchmark-performance ./audio_samples/
```

## Comprehensive Accuracy Testing

### Step 1: Prepare Test Data

Create a directory structure like this:
```
test_data/
├── test_config.json           # Test configuration
├── speaker1_enroll.wav        # Enrollment samples
├── speaker1_test.wav          # Test samples (same speaker)
├── speaker2_enroll.wav        
├── speaker2_test.wav          # Test samples (different speaker)
├── noise_sample.wav           # Low quality samples
└── ...
```

### Step 2: Create Test Configuration

Create `test_config.json` with your test cases:
```json
[
  {
    "enrollment_audio": "speaker1_enroll.wav",
    "test_audio": "speaker1_test.wav",
    "speaker_name": "John Doe",
    "is_same_speaker": true,
    "test_segments": [{"start": 0, "end": 10}]
  },
  {
    "enrollment_audio": "speaker1_enroll.wav", 
    "test_audio": "speaker2_test.wav",
    "speaker_name": "John Doe",
    "is_same_speaker": false,
    "test_segments": [{"start": 0, "end": 10}]
  },
  {
    "enrollment_audio": "speaker2_enroll.wav",
    "test_audio": "speaker2_test.wav", 
    "speaker_name": "Jane Smith",
    "is_same_speaker": true,
    "test_segments": [{"start": 5, "end": 15}]
  }
]
```

### Step 3: Run Accuracy Tests

```bash
# Run comprehensive accuracy testing
knowledge-system voice test-accuracy ./test_data/ --confidence 0.85 --output results.json

# Test with different confidence thresholds
knowledge-system voice test-accuracy ./test_data/ --confidence 0.90
knowledge-system voice test-accuracy ./test_data/ --confidence 0.80
```

### Step 4: Analyze Results

The system will output:
- **Accuracy**: Overall percentage of correct identifications
- **False Acceptance Rate (FAR)**: Percentage of incorrect positive matches
- **False Rejection Rate (FRR)**: Percentage of incorrect negative matches  
- **Equal Error Rate (EER)**: Optimal threshold where FAR = FRR

## Understanding Test Results

### Accuracy Metrics

| Metric | Target | Excellent | Good | Needs Improvement |
|--------|--------|-----------|------|-------------------|
| **Accuracy** | ≥97% | ≥97% | ≥95% | <90% |
| **FAR** | <1% | <1% | <2% | >5% |
| **FRR** | <2% | <2% | <3% | >5% |
| **EER** | <1.5% | <1.5% | <2.5% | >5% |

### Result Interpretation

**🟢 EXCELLENT (97%+ accuracy):**
```
🎯 Accuracy Test Results:
  Accuracy: 0.973 (97.3%)
  False Acceptance Rate: 0.008
  False Rejection Rate: 0.019
  Equal Error Rate: 0.014
  Total tests: 150
🟢 EXCELLENT: 97%+ accuracy achieved!
```

**🟡 GOOD (95%+ accuracy):**
- System performing well but may need fine-tuning
- Check for audio quality issues or threshold adjustments

**🔴 NEEDS IMPROVEMENT (<90% accuracy):**
- Check audio quality (16kHz mono recommended)
- Verify sufficient enrollment data (>10 seconds)
- Consider adjusting confidence thresholds
- Check for missing dependencies (wav2vec2, ECAPA)

## Advanced Testing Scenarios

### Multi-Speaker Testing
Test with multiple speakers in the same audio:
```json
{
  "enrollment_audio": "speaker1_enroll.wav",
  "test_audio": "multi_speaker_conversation.wav", 
  "speaker_name": "Speaker1",
  "is_same_speaker": true,
  "test_segments": [
    {"start": 10, "end": 15},
    {"start": 30, "end": 35},
    {"start": 50, "end": 55}
  ]
}
```

### Noise Robustness Testing
Test with varying audio quality:
```bash
# Test with different noise levels
knowledge-system voice test-similarity clean_audio.wav noisy_audio.wav
knowledge-system voice test-similarity studio_quality.wav phone_quality.wav
```

### Cross-Session Testing
Test speaker recognition across different recording sessions:
```json
{
  "enrollment_audio": "speaker1_session1.wav",
  "test_audio": "speaker1_session2.wav",
  "speaker_name": "Speaker1", 
  "is_same_speaker": true
}
```

## Creating Your Own Test Dataset

### Option 1: Use Your Own Audio
1. Record speakers saying different phrases
2. Create enrollment samples (10-30 seconds each)
3. Create test samples (5-15 seconds each)
4. Include same-speaker and different-speaker pairs

### Option 2: Use Public Datasets

**VoxCeleb1 Dataset:**
- 100,000+ utterances from 1,251 celebrities
- High-quality audio from YouTube videos
- Standard benchmark for speaker verification

**LibriSpeech:**
- 1000 hours of English speech
- Multiple speakers reading audiobooks
- Good for cross-session testing

**Common Voice:**
- Mozilla's open-source voice dataset
- Multiple languages and accents
- Real-world recording conditions

### Audio Quality Guidelines

**Optimal Audio Characteristics:**
- **Sample Rate**: 16kHz (exactly)
- **Channels**: Mono
- **Format**: WAV (uncompressed)
- **Duration**: 5-30 seconds per sample
- **Quality**: Clear speech, minimal background noise

**Prepare Audio with FFmpeg:**
```bash
# Convert to optimal format
ffmpeg -i input.mp3 -ar 16000 -ac 1 -c:a pcm_s16le output.wav

# Extract segment
ffmpeg -i input.wav -ss 10 -t 15 -ar 16000 -ac 1 segment.wav
```

## Continuous Testing and Monitoring

### Automated Testing Pipeline
```bash
#!/bin/bash
# automated_voice_testing.sh

# Set up test environment
TEST_DIR="./voice_accuracy_tests"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
RESULTS_DIR="./test_results_$TIMESTAMP"

# Run all tests
echo "Running voice fingerprinting accuracy tests..."

# 1. Dependency check
knowledge-system voice test-dependencies > "$RESULTS_DIR/dependencies.log"

# 2. Feature consistency
for audio_file in $TEST_DIR/*.wav; do
    echo "Testing consistency: $audio_file"
    knowledge-system voice test-consistency "$audio_file" --runs 10 >> "$RESULTS_DIR/consistency.log"
done

# 3. Comprehensive accuracy test
knowledge-system voice test-accuracy "$TEST_DIR" --confidence 0.85 --output "$RESULTS_DIR/accuracy_results.json"

# 4. Performance benchmark
knowledge-system voice benchmark-performance "$TEST_DIR" >> "$RESULTS_DIR/performance.log"

echo "Testing complete. Results in: $RESULTS_DIR"
```

### Regression Testing
Run tests after code changes:
```bash
# Before making changes
knowledge-system voice test-accuracy ./baseline_test_data/ --output baseline_results.json

# After making changes  
knowledge-system voice test-accuracy ./baseline_test_data/ --output updated_results.json

# Compare results
python compare_results.py baseline_results.json updated_results.json
```

## Troubleshooting Common Issues

### Low Accuracy Issues

**1. Audio Quality Problems:**
```bash
# Check audio format
ffprobe input.wav

# Expected output should show:
# - Sample rate: 16000 Hz
# - Channels: 1 (mono)
# - Bit depth: 16-bit
```

**2. Insufficient Enrollment Data:**
- Use at least 10 seconds of clear speech for enrollment
- Include varied speech patterns (different phrases, emotions)
- Avoid repetitive content

**3. Threshold Tuning:**
```bash
# Test different thresholds
for threshold in 0.75 0.80 0.85 0.90 0.95; do
    echo "Testing threshold: $threshold"
    knowledge-system voice test-accuracy ./test_data/ --confidence $threshold
done
```

**4. Missing Advanced Features:**
```bash
# Check which features are available
knowledge-system voice test-dependencies

# Install missing dependencies
pip install transformers>=4.35.0 speechbrain>=0.5.0
```

### Performance Issues

**1. Slow Processing:**
- Enable GPU acceleration (MPS/CUDA)
- Reduce audio segment length
- Disable unused feature types

**2. Memory Issues:**
- Process shorter audio segments
- Clear model cache between tests
- Use batch processing for multiple files

## Expected Test Results

### Baseline Performance
With properly configured dependencies and quality audio:

```
🎯 Accuracy Test Results:
  Accuracy: 0.970+ (97.0%+)
  False Acceptance Rate: <0.010
  False Rejection Rate: <0.020
  Equal Error Rate: <0.015
```

### Feature Availability
```
✅ librosa: Available
✅ torch: Available (MPS acceleration)
✅ transformers: Available
✅ speechbrain: Available
✅ Voice fingerprinting module: Available
```

### Performance Benchmarks
```
⚡ Performance Benchmark Results:
  5s segments:
    Avg processing time: 0.234s
    Avg features extracted: 5.0
  
  10s segments: 
    Avg processing time: 0.401s
    Avg features extracted: 5.0
```

## Conclusion

The voice fingerprinting system should consistently achieve 97%+ accuracy when:
1. Using 16kHz mono WAV audio
2. Having sufficient enrollment data (10+ seconds)
3. Using quality audio with minimal noise
4. Having all advanced dependencies installed
5. Using appropriate confidence thresholds (0.85-0.90)

Regular testing with this framework ensures the system maintains its high accuracy standards across different scenarios and use cases.
