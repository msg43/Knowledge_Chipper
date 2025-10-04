#!/bin/bash
# post_install_setup.sh - Download essential models after installation
# This script is run automatically after DMG/PKG installation

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
LOG_FILE="$HOME/.knowledge_chipper/post_install.log"

# Create log directory
mkdir -p "$HOME/.knowledge_chipper"

# Logging function
log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "🚀 Skip the Podcast Post-Install Setup"
log "====================================="

# 1. Download Whisper Models
download_whisper_models() {
    log "📥 Setting up Whisper models..."
    
    # Create models directory
    WHISPER_CACHE="$HOME/.cache/whisper-cpp"
    mkdir -p "$WHISPER_CACHE"
    
    # Download base model (default for quality/speed balance)
    WHISPER_MODEL="ggml-base.bin"
    WHISPER_URL="https://huggingface.co/ggerganov/whisper.cpp/resolve/main/$WHISPER_MODEL"
    
    if [ -f "$WHISPER_CACHE/$WHISPER_MODEL" ]; then
        log "✅ Whisper base model already exists"
    else
        log "📥 Downloading Whisper base model (142MB)..."
        if curl -L "$WHISPER_URL" -o "$WHISPER_CACHE/$WHISPER_MODEL" --progress-bar; then
            log "✅ Whisper base model downloaded successfully"
        else
            log "⚠️  Failed to download Whisper model - will download on first use"
        fi
    fi
}

# 2. Setup Ollama and Default LLM Model  
setup_ollama_model() {
    log "🤖 Setting up Ollama models..."
    
    # Check if Ollama is installed
    if ! command -v ollama &> /dev/null; then
        log "⚠️  Ollama not installed - LLM features will require manual setup"
        return
    fi
    
    # Start Ollama service if not running
    if ! pgrep -x "ollama" > /dev/null; then
        log "Starting Ollama service..."
        ollama serve > /dev/null 2>&1 &
        sleep 5
    fi
    
    # Check for any installed Qwen models (our preferred series)
    INSTALLED_MODELS=$(ollama list 2>/dev/null | grep -E "^qwen" | awk '{print $1}' || true)
    
    if [ -n "$INSTALLED_MODELS" ]; then
        log "✅ Found existing Qwen models:"
        echo "$INSTALLED_MODELS" | while read -r model; do
            log "   - $model"
        done
        log "ℹ️  Skipping default model download - valid models already installed"
    else
        # No Qwen models found, download default
        DEFAULT_MODEL="qwen2.5:7b"
        log "📥 Downloading default LLM model: $DEFAULT_MODEL (~4.7GB)..."
        
        if ollama pull "$DEFAULT_MODEL" 2>&1 | tee -a "$LOG_FILE"; then
            log "✅ Default LLM model ready: $DEFAULT_MODEL"
        else
            log "⚠️  Failed to download default model - please run 'ollama pull $DEFAULT_MODEL' manually"
        fi
    fi
}

# 3. Setup Pyannote Configuration
setup_pyannote_config() {
    log "🎙️ Configuring speaker diarization..."
    
    PYANNOTE_DIR="$HOME/.cache/models/pyannote"
    mkdir -p "$PYANNOTE_DIR"
    
    # Create runtime configuration
    cat > "$PYANNOTE_DIR/runtime_download_config.json" << EOF
{
    "model": "pyannote/speaker-diarization-3.1",
    "download_on_first_use": true,
    "cache_location": "$PYANNOTE_DIR",
    "hf_token_required": true,
    "setup_complete": true
}
EOF
    
    log "✅ Pyannote configured for on-demand download"
    log "ℹ️  Note: HuggingFace token required for speaker diarization"
}

# 4. Create first-run completion marker
mark_setup_complete() {
    SETTINGS_DIR="$HOME/.knowledge_chipper/settings"
    mkdir -p "$SETTINGS_DIR"
    
    # Create a marker file to indicate post-install setup completed
    cat > "$SETTINGS_DIR/post_install_complete.json" << EOF
{
    "setup_completed": true,
    "timestamp": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
    "whisper_model": "base",
    "models_downloaded": true
}
EOF
    
    log "✅ Post-install setup marked as complete"
}

# Main execution
main() {
    log "Starting post-install setup..."
    
    # Run setup tasks
    download_whisper_models
    setup_ollama_model
    setup_pyannote_config
    mark_setup_complete
    
    log "✅ Post-install setup completed successfully!"
    log "📝 Log saved to: $LOG_FILE"
}

# Run main function
main

exit 0
