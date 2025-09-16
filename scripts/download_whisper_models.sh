#!/bin/bash

# Download whisper.cpp models
# Usage: ./download_whisper_models.sh [model_name]
# If no model specified, shows available models

MODEL=$1

# Model URLs
declare -A MODEL_URLS=(
    ["tiny"]="https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-tiny.bin"
    ["base"]="https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.bin"
    ["small"]="https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-small.bin"
    ["medium"]="https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-medium.en.bin"
    ["large"]="https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3.bin"
)

# Create models directory if it doesn't exist
mkdir -p models

if [ -z "$MODEL" ]; then
    echo "Available whisper.cpp models:"
    echo ""
    echo "  tiny    - Fastest, least accurate (39M parameters, ~75 MB)"
    echo "  base    - Good balance (74M parameters, ~142 MB)"
    echo "  small   - Better accuracy (244M parameters, ~466 MB)"
    echo "  medium  - English-only, faster (769M parameters, ~769 MB)"
    echo "  large   - Best accuracy, latest v3 (1550M parameters, ~3.1 GB)"
    echo ""
    echo "Usage: $0 <model_name>"
    echo "Example: $0 small"
    echo ""
    echo "Models already downloaded:"
    for model in "${!MODEL_URLS[@]}"; do
        filename="ggml-${model}.bin"
        if [ -f "models/$filename" ]; then
            size=$(ls -lh "models/$filename" | awk '{print $5}')
            echo "  ✓ $model ($size)"
        fi
    done
    exit 0
fi

# Check if model exists
if [ -z "${MODEL_URLS[$MODEL]}" ]; then
    echo "Error: Unknown model '$MODEL'"
    echo "Available models: tiny, base, small, medium, large"
    exit 1
fi

# Construct filename based on model mappings
case "$MODEL" in
    "medium")
        FILENAME="ggml-medium.en.bin"
        ;;
    "large")
        FILENAME="ggml-large-v3.bin"
        ;;
    *)
        FILENAME="ggml-${MODEL}.bin"
        ;;
esac

# Check if already downloaded
if [ -f "models/$FILENAME" ]; then
    echo "Model '$MODEL' already exists at models/$FILENAME"
    read -p "Do you want to re-download it? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 0
    fi
fi

# Download the model
echo "Downloading whisper.cpp $MODEL model..."
echo "This may take a while depending on your internet connection..."

if command -v wget &> /dev/null; then
    wget -q --show-progress "${MODEL_URLS[$MODEL]}" -O "models/$FILENAME"
elif command -v curl &> /dev/null; then
    curl -L --progress-bar "${MODEL_URLS[$MODEL]}" -o "models/$FILENAME"
else
    echo "Error: Neither wget nor curl found. Please install one of them."
    exit 1
fi

if [ $? -eq 0 ]; then
    echo "✓ Successfully downloaded $MODEL model to models/$FILENAME"
    size=$(ls -lh "models/$FILENAME" | awk '{print $5}')
    echo "  File size: $size"
else
    echo "✗ Failed to download model"
    exit 1
fi
