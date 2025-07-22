#!/bin/bash

# Install pywhispercpp with Core ML support
# For macOS Apple Silicon

echo "Installing pywhispercpp with Core ML support..."

# Check if running on macOS
if [[ "$OSTYPE" != "darwin"* ]]; then
    echo "Warning: This script is optimized for macOS. Continuing anyway..."
fi

# Check if we're on Apple Silicon
if [[ $(uname -m) == "arm64" ]]; then
    echo "Detected Apple Silicon Mac"
    COREML_SUPPORT=1
else
    echo "Detected Intel Mac or other platform"
    COREML_SUPPORT=0
fi

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    echo "Activating virtual environment..."
    source venv/bin/activate
elif [ -d "../venv" ]; then
    echo "Activating virtual environment from parent directory..."
    source ../venv/bin/activate
else
    echo "Warning: No virtual environment found. Installing globally..."
fi

# Uninstall existing whisper packages
echo "Removing any existing whisper packages..."
pip uninstall -y openai-whisper whisper pywhispercpp 2>/dev/null

# Install pywhispercpp with Core ML support
if [[ $COREML_SUPPORT -eq 1 ]]; then
    echo "Installing pywhispercpp with Core ML support..."
    WHISPER_COREML=1 pip install pywhispercpp
else
    echo "Installing pywhispercpp without Core ML support..."
    pip install pywhispercpp
fi

# Create models directory
echo "Creating models directory..."
mkdir -p models

# Download base model
echo "Downloading whisper.cpp base model..."
if command -v wget &> /dev/null; then
    wget -q --show-progress https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.bin -O models/ggml-base.bin
elif command -v curl &> /dev/null; then
    curl -L --progress-bar https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.bin -o models/ggml-base.bin
else
    echo "Error: Neither wget nor curl found. Please install one of them."
    exit 1
fi

echo "Installation complete!"
echo ""
echo "To use whisper.cpp in the Knowledge System:"
echo "1. Update your settings.yaml to include:"
echo "   transcription:"
echo "     use_whisper_cpp: true"
echo ""
echo "2. Or use the CLI flag:"
echo "   knowledge-system transcribe input.mp3 --use-whisper-cpp"
echo ""
echo "3. The GUI will automatically use whisper.cpp if configured in settings" 