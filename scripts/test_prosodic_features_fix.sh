#!/bin/bash
#
# Test script for prosodic features fix
# Tests that extract_prosodic_features handles tempo correctly
#

set -e

echo "Testing prosodic features extraction fix..."

# Create a simple Python test
python3 << 'EOF'
import numpy as np
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from knowledge_system.voice.voice_fingerprinting import VoiceFeatureExtractor

# Create test audio (1 second of random noise at 16kHz)
sample_rate = 16000
duration = 1.0
audio = np.random.randn(int(sample_rate * duration)).astype(np.float32)

# Create feature extractor
extractor = VoiceFeatureExtractor(sample_rate=sample_rate)

print("Extracting prosodic features...")
try:
    features = extractor.extract_prosodic_features(audio)
    print(f"✓ Prosodic features extracted successfully")
    print(f"  Shape: {features.shape}")
    print(f"  Expected shape: (5,)")
    
    # Verify shape
    if features.shape == (5,):
        print("✓ Shape is correct (5 features: mean, std, min, max pitch + tempo)")
    else:
        print(f"✗ Shape is incorrect! Expected (5,), got {features.shape}")
        sys.exit(1)
    
    # Verify all features are scalars (1D array with 5 elements)
    if features.ndim == 1 and len(features) == 5:
        print("✓ All features are properly formatted as 1D array")
    else:
        print(f"✗ Features are not properly formatted!")
        sys.exit(1)
    
    print("\n✓ All tests passed!")
    
except Exception as e:
    print(f"✗ Error extracting prosodic features: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
EOF

echo ""
echo "✓ Prosodic features fix verified successfully!"

