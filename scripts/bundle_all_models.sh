#!/bin/bash
# Bundle ALL models into DMG for true offline experience
# This creates a ~4GB DMG with everything pre-installed

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
BUILD_APP_PATH="$1"

if [ -z "$BUILD_APP_PATH" ]; then
    echo "Usage: $0 <app-bundle-path>"
    exit 1
fi

MACOS_PATH="$BUILD_APP_PATH/Contents/MacOS"

echo "📦 Bundling ALL models for complete offline experience..."

# 1. Bundle Whisper model
echo "🎤 Bundling Whisper model..."
WHISPER_CACHE="$HOME/.cache/whisper/ggml-base.bin"
if [ -f "$WHISPER_CACHE" ]; then
    WHISPER_DIR="$MACOS_PATH/.cache/whisper"
    mkdir -p "$WHISPER_DIR"
    cp "$WHISPER_CACHE" "$WHISPER_DIR/"
    echo "✅ Whisper model bundled"
else
    echo "⚠️  Whisper model not found in cache - user must have run transcription once"
fi

# 2. Bundle Ollama binary and models
echo "🤖 Bundling Ollama and Llama model..."
OLLAMA_BIN="/usr/local/bin/ollama"
if [ -f "$OLLAMA_BIN" ]; then
    # Copy Ollama binary
    cp "$OLLAMA_BIN" "$MACOS_PATH/bin/ollama"
    chmod +x "$MACOS_PATH/bin/ollama"

    # Copy Llama model if it exists
    OLLAMA_MODELS="$HOME/.ollama/models"
    if [ -d "$OLLAMA_MODELS" ]; then
        echo "📥 Copying Ollama models (~2GB)..."
        BUNDLE_OLLAMA="$MACOS_PATH/.ollama/models"
        mkdir -p "$BUNDLE_OLLAMA"

        # Copy blobs (the actual model data)
        if [ -d "$OLLAMA_MODELS/blobs" ]; then
            cp -r "$OLLAMA_MODELS/blobs" "$BUNDLE_OLLAMA/"
        fi

        # Copy manifests
        if [ -d "$OLLAMA_MODELS/manifests" ]; then
            cp -r "$OLLAMA_MODELS/manifests" "$BUNDLE_OLLAMA/"
        fi

        echo "✅ Ollama and models bundled"
    else
        echo "⚠️  Ollama models not found - user must run 'ollama pull llama3.2:3b' first"
    fi
else
    echo "⚠️  Ollama not installed - skipping"
fi

# 3. Create environment setup script
cat > "$MACOS_PATH/setup_bundled_models.sh" << 'EOF'
#!/bin/bash
# Set up environment to use bundled models

APP_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Whisper cache
export WHISPER_CACHE_DIR="$APP_DIR/.cache/whisper"

# Ollama home
export OLLAMA_HOME="$APP_DIR/.ollama"
export PATH="$APP_DIR/bin:$PATH"

# Let the app know models are bundled
export MODELS_BUNDLED="true"
EOF
chmod +x "$MACOS_PATH/setup_bundled_models.sh"

echo
echo "📊 Bundle Summary:"
echo "  FFMPEG: ✅ (via silent_ffmpeg_installer.py)"
echo "  Pyannote: ✅ (via download_pyannote_direct.py)"
echo "  Whisper: $([ -f "$MACOS_PATH/.cache/whisper/ggml-base.bin" ] && echo "✅" || echo "❌ Not cached")"
echo "  Ollama: $([ -f "$MACOS_PATH/bin/ollama" ] && echo "✅" || echo "❌ Not installed")"
echo "  Llama 3.2:3b: $([ -d "$MACOS_PATH/.ollama/models/blobs" ] && echo "✅" || echo "❌ Not downloaded")"
echo
echo "DMG will be ~4GB with all models bundled"
