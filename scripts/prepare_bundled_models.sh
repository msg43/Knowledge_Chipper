#!/bin/bash
# Prepare bundled models for DMG distribution
# This script downloads and stores models in the repo for consistent builds

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"
MODELS_DIR="$PROJECT_ROOT/bundled_models"

echo "🎯 Preparing bundled models for internal company distribution"
echo "============================================================"

# Create models directory
mkdir -p "$MODELS_DIR/pyannote"

# Check if we have a HuggingFace token
HF_TOKEN="${HF_TOKEN:-}"
if [ -z "$HF_TOKEN" ]; then
    # Try to read from credentials
    if [ -f "$PROJECT_ROOT/config/credentials.yaml" ]; then
        HF_TOKEN=$(grep "huggingface_token:" "$PROJECT_ROOT/config/credentials.yaml" | sed 's/.*: //' | tr -d '"' | tr -d "'")
    fi
fi

if [ -z "$HF_TOKEN" ] || [ "$HF_TOKEN" = "your_huggingface_token_here" ]; then
    echo "❌ No HuggingFace token found!"
    echo "   Set HF_TOKEN environment variable or add to config/credentials.yaml"
    exit 1
fi

echo "✅ HuggingFace token found"

# Function to download model files
download_model() {
    local model_name="$1"
    local output_dir="$2"

    echo "📥 Downloading $model_name model files..."

    # Create Python script to download the model
    cat > /tmp/download_pyannote.py << 'EOF'
import os
import sys
import shutil
from pathlib import Path
from huggingface_hub import snapshot_download

model_id = sys.argv[1]
output_dir = Path(sys.argv[2])
token = os.environ.get("HF_TOKEN")

print(f"Downloading {model_id} to {output_dir}")

# Download the model
cache_dir = snapshot_download(
    repo_id=model_id,
    token=token,
    cache_dir="/tmp/hf_cache",
    local_dir=output_dir,
    local_dir_use_symlinks=False,
    ignore_patterns=["*.md", "*.txt", ".git*"]
)

print(f"✅ Model downloaded to: {output_dir}")

# Clean up cache
shutil.rmtree("/tmp/hf_cache", ignore_errors=True)
EOF

    # Run the download script
    HF_TOKEN="$HF_TOKEN" python /tmp/download_pyannote.py "$model_name" "$output_dir"

    # Clean up
    rm -f /tmp/download_pyannote.py
}

# Download pyannote model
echo
echo "🎙️ Downloading pyannote speaker-diarization model..."
download_model "pyannote/speaker-diarization-3.1" "$MODELS_DIR/pyannote/speaker-diarization-3.1"

# Create info file
cat > "$MODELS_DIR/README.md" << EOF
# Bundled Models

This directory contains pre-downloaded models for internal company use.
These models are bundled with the DMG to provide a zero-setup experience.

## Models Included:

- **pyannote/speaker-diarization-3.1**: Speaker diarization model (~400MB)
  - Terms accepted by company administrator
  - For internal use only

## Updating Models:

Run \`scripts/prepare_bundled_models.sh\` to update these models.
EOF

# Create .gitignore to exclude large model files
cat > "$MODELS_DIR/.gitignore" << EOF
# Ignore model binaries but keep structure
*.bin
*.pth
*.pt
*.onnx
*.safetensors

# Keep these files
!README.md
!model_info.json
!config.yaml
!preprocessor_config.json
!.gitkeep
EOF

# Add .gitkeep files to maintain structure
find "$MODELS_DIR" -type d -exec touch {}/.gitkeep \;

echo
echo "✅ Models prepared successfully!"
echo "   Location: $MODELS_DIR"
echo
echo "📝 Next steps:"
echo "   1. The model files are stored locally in bundled_models/"
echo "   2. Large binary files are gitignored"
echo "   3. The build script will copy from this location"
echo
echo "⚠️  Note: This is for internal company use only where terms are pre-accepted"
