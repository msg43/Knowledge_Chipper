#!/bin/bash
# setup_dev_models.sh - Pre-download all models for development use
# This ensures launch_gui.command doesn't need to download models

set -e

echo "🚀 Skip the Podcast Development Model Setup"
echo "=========================================="
echo "This will download all models for development use"
echo

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

# 1. Ensure Whisper model is cached
echo "🎤 Checking Whisper model..."
if [ -f "$HOME/.cache/whisper/ggml-base.bin" ]; then
    echo "✅ Whisper model already cached"
else
    echo "📥 Downloading Whisper model..."
    # Create a test file to trigger download
    echo "Test audio for model download" > /tmp/test_audio.txt

    # Run a quick transcription to trigger download
    if source venv/bin/activate && python -c "
import sys
sys.path.insert(0, 'src')
from knowledge_system.processors.whisper_cpp_transcribe import WhisperCppTranscribeProcessor
processor = WhisperCppTranscribeProcessor()
# This will trigger model download
model_path = processor._download_model('base')
print('✅ Whisper model downloaded')
" 2>/dev/null; then
        echo "✅ Whisper model ready"
    else
        echo "⚠️  Whisper download failed - will download on first use"
    fi
fi

# 2. Ensure Ollama is installed and model is downloaded
echo
echo "🤖 Checking Ollama..."
if command -v ollama &> /dev/null; then
    echo "✅ Ollama installed"

    # Start Ollama service if not running
    if ! pgrep -x "ollama" > /dev/null; then
        echo "Starting Ollama service..."
        ollama serve > /dev/null 2>&1 &
        sleep 3
    fi

    # Check/download Llama model
    if ollama list | grep -q "llama3.2:3b"; then
        echo "✅ Llama 3.2:3b already downloaded"
    else
        echo "📥 Downloading Llama 3.2:3b (~2GB)..."
        ollama pull llama3.2:3b
    fi
else
    echo "❌ Ollama not installed"
    echo "   Run: brew install ollama"
fi

# 3. Download Pyannote model (requires HF token)
echo
echo "🎙️ Checking Pyannote diarization model..."

# Check for HF token
HF_TOKEN=""
if [ -f "config/credentials.yaml" ]; then
    HF_TOKEN=$(grep -E "hf_token:|huggingface_token:" config/credentials.yaml | head -1 | sed 's/.*: //' | tr -d '"' | tr -d "'")
fi

# Check if already cached
PYANNOTE_CACHE="$HOME/.cache/torch/pyannote"
if [ -d "$PYANNOTE_CACHE/models--pyannote--speaker-diarization-3.1" ]; then
    echo "✅ Pyannote model already cached"
else
    if [ ! -z "$HF_TOKEN" ] && [ "$HF_TOKEN" != "your_huggingface_token_here" ]; then
        echo "📥 Downloading Pyannote model (~400MB)..."
        echo "   This may take a few minutes..."

        # Use the model_downloader script
        if HF_TOKEN="$HF_TOKEN" python scripts/download_models.py --skip-whisper --skip-ollama; then
            echo "✅ Pyannote model downloaded successfully"
        else
            echo "⚠️  Pyannote download failed - will download on first use"
            echo "   Make sure you've accepted the license at:"
            echo "   https://huggingface.co/pyannote/speaker-diarization"
        fi
    else
        echo "⚠️  No HuggingFace token found - Pyannote will download on first use"
        echo "   To download now:"
        echo "   1. Get a token from https://huggingface.co/settings/tokens"
        echo "   2. Accept license at https://huggingface.co/pyannote/speaker-diarization"
        echo "   3. Add token to config/credentials.yaml"
        echo "   4. Run this script again"
    fi
fi

echo
echo "✅ Development model setup complete!"
echo "   You can now run ./launch_gui.command without download delays"
