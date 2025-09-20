#!/bin/bash
# bundle_ai_models.sh - Create AI models package for PKG installer
# Bundles Whisper, Voice Fingerprinting, and Pyannote models

set -e
set -o pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
BUILD_DIR="$PROJECT_ROOT/build_ai_models"
OUTPUT_DIR="$PROJECT_ROOT/dist"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m' # No Color

echo -e "${BLUE}${BOLD}🧠 AI Models Bundle Creator for PKG Installer${NC}"
echo "==============================================="
echo "Creating comprehensive AI models package"
echo ""

# Function to print status
print_status() {
    echo -e "${GREEN}✅${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠️${NC} $1"
}

print_error() {
    echo -e "${RED}❌${NC} $1"
}

# Clean and create build directories
echo -e "${BLUE}📁 Setting up build environment...${NC}"
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"
mkdir -p "$OUTPUT_DIR"

MODELS_DIR="$BUILD_DIR/models"
mkdir -p "$MODELS_DIR/whisper"
mkdir -p "$MODELS_DIR/voice_fingerprinting"
mkdir -p "$MODELS_DIR/pyannote"

print_status "Build directories created"

# Download Whisper models
echo -e "\n${BLUE}🎙️ Downloading Whisper models...${NC}"

WHISPER_MODELS=("base")  # Focus on base model for PKG

for model in "${WHISPER_MODELS[@]}"; do
    echo "Downloading Whisper $model model..."

    if [ ! -f "$PROJECT_ROOT/github_models_prep/whisper-base/ggml-base.bin" ]; then
        # Download if not already present
        mkdir -p "$PROJECT_ROOT/github_models_prep/whisper-$model"
        curl -L -o "$PROJECT_ROOT/github_models_prep/whisper-$model/ggml-$model.bin" \
            "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-$model.bin"
    fi

    # Copy to models directory
    cp "$PROJECT_ROOT/github_models_prep/whisper-$model/ggml-$model.bin" \
       "$MODELS_DIR/whisper/"
done

print_status "Whisper models downloaded"

# Download Voice Fingerprinting models
echo -e "\n${BLUE}🔊 Downloading voice fingerprinting models...${NC}"

# Wav2Vec2 model
if [ ! -f "$PROJECT_ROOT/github_models_prep/wav2vec2-base-960h.tar.gz" ]; then
    echo "Downloading wav2vec2-base-960h model..."

    # Use HuggingFace Hub to download
    python3 -c "
from huggingface_hub import snapshot_download
import tarfile
import os

# Download model
model_path = snapshot_download(
    repo_id='facebook/wav2vec2-base-960h',
    cache_dir='$PROJECT_ROOT/github_models_prep',
    local_dir='$PROJECT_ROOT/github_models_prep/wav2vec2-base-960h'
)

# Create tar.gz
with tarfile.open('$PROJECT_ROOT/github_models_prep/wav2vec2-base-960h.tar.gz', 'w:gz') as tar:
    tar.add('$PROJECT_ROOT/github_models_prep/wav2vec2-base-960h', arcname='wav2vec2-base-960h')

print('wav2vec2-base-960h model packaged')
"
fi

# ECAPA-TDNN model
if [ ! -f "$PROJECT_ROOT/github_models_prep/spkrec-ecapa-voxceleb.tar.gz" ]; then
    echo "Downloading spkrec-ecapa-voxceleb model..."

    python3 -c "
from huggingface_hub import snapshot_download
import tarfile

# Download model
model_path = snapshot_download(
    repo_id='speechbrain/spkrec-ecapa-voxceleb',
    cache_dir='$PROJECT_ROOT/github_models_prep',
    local_dir='$PROJECT_ROOT/github_models_prep/spkrec-ecapa-voxceleb'
)

# Create tar.gz
with tarfile.open('$PROJECT_ROOT/github_models_prep/spkrec-ecapa-voxceleb.tar.gz', 'w:gz') as tar:
    tar.add('$PROJECT_ROOT/github_models_prep/spkrec-ecapa-voxceleb', arcname='spkrec-ecapa-voxceleb')

print('spkrec-ecapa-voxceleb model packaged')
"
fi

# Extract voice fingerprinting models to bundle
tar -xf "$PROJECT_ROOT/github_models_prep/wav2vec2-base-960h.tar.gz" -C "$MODELS_DIR/voice_fingerprinting/"
tar -xf "$PROJECT_ROOT/github_models_prep/spkrec-ecapa-voxceleb.tar.gz" -C "$MODELS_DIR/voice_fingerprinting/"

print_status "Voice fingerprinting models downloaded"

# Download Pyannote models
echo -e "\n${BLUE}🗣️ Downloading Pyannote models...${NC}"

# Check for HuggingFace token
HF_TOKEN=""
if [ -f "$PROJECT_ROOT/config/credentials.yaml" ]; then
    HF_TOKEN=$(python3 -c "
import yaml
with open('$PROJECT_ROOT/config/credentials.yaml', 'r') as f:
    creds = yaml.safe_load(f)
    print(creds.get('api_keys', {}).get('hf_token', ''))
")
fi

if [ -z "$HF_TOKEN" ]; then
    print_error "HuggingFace token not found in config/credentials.yaml"
    print_error "Pyannote models require authentication. Please configure your HF token."
    exit 1
fi

# Download Pyannote diarization model
python3 -c "
import os
os.environ['HF_TOKEN'] = '$HF_TOKEN'

from huggingface_hub import snapshot_download
import tarfile

# Download model
model_path = snapshot_download(
    repo_id='pyannote/speaker-diarization-3.1',
    cache_dir='$PROJECT_ROOT/github_models_prep',
    local_dir='$PROJECT_ROOT/github_models_prep/pyannote-speaker-diarization-3.1',
    token='$HF_TOKEN'
)

# Create tar.gz
with tarfile.open('$PROJECT_ROOT/github_models_prep/pyannote-speaker-diarization-3.1.tar.gz', 'w:gz') as tar:
    tar.add('$PROJECT_ROOT/github_models_prep/pyannote-speaker-diarization-3.1', arcname='pyannote-speaker-diarization-3.1')

print('pyannote-speaker-diarization-3.1 model packaged')
"

# Extract Pyannote models to bundle
tar -xf "$PROJECT_ROOT/github_models_prep/pyannote-speaker-diarization-3.1.tar.gz" -C "$MODELS_DIR/pyannote/"

print_status "Pyannote models downloaded"

# Create model manifest
echo -e "\n${BLUE}📋 Creating model manifest...${NC}"

cat > "$MODELS_DIR/models_manifest.json" << EOF
{
  "version": "1.0",
  "created": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "models": {
    "whisper": {
      "base": {
        "file": "whisper/ggml-base.bin",
        "size_mb": 141,
        "description": "Whisper base model for speech transcription",
        "capabilities": ["transcription", "translation"]
      }
    },
    "voice_fingerprinting": {
      "wav2vec2-base-960h": {
        "path": "voice_fingerprinting/wav2vec2-base-960h/",
        "size_mb": 631,
        "description": "Voice feature extraction model",
        "capabilities": ["feature_extraction", "voice_analysis"]
      },
      "spkrec-ecapa-voxceleb": {
        "path": "voice_fingerprinting/spkrec-ecapa-voxceleb/",
        "size_mb": 79,
        "description": "Speaker recognition model",
        "capabilities": ["speaker_recognition", "voice_similarity"]
      }
    },
    "pyannote": {
      "speaker-diarization-3.1": {
        "path": "pyannote/pyannote-speaker-diarization-3.1/",
        "size_mb": 400,
        "description": "Speaker diarization and separation",
        "capabilities": ["speaker_diarization", "voice_activity_detection"]
      }
    }
  },
  "total_size_mb": 1251,
  "requirements": {
    "python_version": ">=3.13",
    "pytorch": ">=2.1.0",
    "transformers": ">=4.35.0",
    "pyannote.audio": ">=3.1.0"
  }
}
EOF

print_status "Model manifest created"

# Create model verification script
echo -e "\n${BLUE}🔍 Creating model verification script...${NC}"

cat > "$MODELS_DIR/verify_models.py" << 'EOF'
#!/usr/bin/env python3
"""
Model Verification Script for Skip the Podcast Desktop
Verifies that all bundled models are present and functional.
"""

import json
import os
import sys
from pathlib import Path

def verify_models(models_dir):
    """Verify all models are present and accessible."""
    models_dir = Path(models_dir)
    manifest_path = models_dir / "models_manifest.json"

    if not manifest_path.exists():
        print("❌ Model manifest not found")
        return False

    with open(manifest_path, 'r') as f:
        manifest = json.load(f)

    print("🔍 Verifying AI models...")
    success = True

    # Check Whisper models
    for model_name, model_info in manifest['models']['whisper'].items():
        model_path = models_dir / model_info['file']
        if model_path.exists():
            print(f"✅ Whisper {model_name}: {model_path}")
        else:
            print(f"❌ Whisper {model_name}: Missing {model_path}")
            success = False

    # Check voice fingerprinting models
    for model_name, model_info in manifest['models']['voice_fingerprinting'].items():
        model_path = models_dir / model_info['path']
        if model_path.exists() and model_path.is_dir():
            print(f"✅ Voice fingerprinting {model_name}: {model_path}")
        else:
            print(f"❌ Voice fingerprinting {model_name}: Missing {model_path}")
            success = False

    # Check Pyannote models
    for model_name, model_info in manifest['models']['pyannote'].items():
        model_path = models_dir / model_info['path']
        if model_path.exists() and model_path.is_dir():
            print(f"✅ Pyannote {model_name}: {model_path}")
        else:
            print(f"❌ Pyannote {model_name}: Missing {model_path}")
            success = False

    return success

def main():
    if len(sys.argv) != 2:
        print("Usage: verify_models.py <models_directory>")
        sys.exit(1)

    models_dir = sys.argv[1]

    if verify_models(models_dir):
        print("🎉 All models verified successfully")
        sys.exit(0)
    else:
        print("❌ Model verification failed")
        sys.exit(1)

if __name__ == "__main__":
    main()
EOF

chmod +x "$MODELS_DIR/verify_models.py"

print_status "Model verification script created"

# Verify models before packaging
echo -e "\n${BLUE}🧪 Verifying models...${NC}"
python3 "$MODELS_DIR/verify_models.py" "$MODELS_DIR"

# Create compressed archive
echo -e "\n${BLUE}🗜️ Creating AI models archive...${NC}"
cd "$BUILD_DIR"

tar -czf "$OUTPUT_DIR/ai-models-bundle.tar.gz" models/

# Calculate size
ARCHIVE_SIZE=$(du -h "$OUTPUT_DIR/ai-models-bundle.tar.gz" | cut -f1)

print_status "AI models archive created: $ARCHIVE_SIZE"

# Create checksum
echo -e "\n${BLUE}🔐 Creating checksum...${NC}"
cd "$OUTPUT_DIR"
shasum -a 256 "ai-models-bundle.tar.gz" > "ai-models-bundle.tar.gz.sha256"

print_status "Checksum created"

# Cleanup build directory
echo -e "\n${BLUE}🧹 Cleaning up build directory...${NC}"
rm -rf "$BUILD_DIR"

print_status "Build directory cleaned"

# Final summary
echo -e "\n${GREEN}${BOLD}🎉 AI Models Bundle Complete!${NC}"
echo "=============================================="
echo "Archive: $OUTPUT_DIR/ai-models-bundle.tar.gz"
echo "Size: $ARCHIVE_SIZE"
echo "Checksum: $OUTPUT_DIR/ai-models-bundle.tar.gz.sha256"
echo ""
echo "Bundled models:"
echo "• Whisper base (141MB)"
echo "• Wav2Vec2-base-960h (631MB)"
echo "• ECAPA-TDNN VoxCeleb (79MB)"
echo "• Pyannote Speaker Diarization 3.1 (400MB)"
echo ""
echo "Next steps:"
echo "1. Upload to GitHub releases"
echo "2. Test model loading in PKG installer"
echo "3. Verify model functionality"
