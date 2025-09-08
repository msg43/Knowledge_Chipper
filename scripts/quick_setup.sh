#!/bin/bash
# quick_setup.sh - Minimal setup with defaults (no prompts)
# For users who want the fastest possible setup for Knowledge_Chipper

set -e  # Exit on any error

echo "🚀 Knowledge_Chipper - Quick Setup (No Prompts)"
echo "==============================================="

# Check macOS
if [[ "$OSTYPE" != "darwin"* ]]; then
    echo "❌ This script requires macOS"
    exit 1
fi

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Please install Python 3.9+ first: brew install python@3.11"
    exit 1
fi

# Install Homebrew if needed
if ! command -v brew &> /dev/null; then
    echo "📦 Installing Homebrew..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    eval "$(/opt/homebrew/bin/brew shellenv)" 2>/dev/null || eval "$(/usr/local/bin/brew shellenv)" 2>/dev/null
fi

# Install FFmpeg
if ! command -v ffmpeg &> /dev/null; then
    echo "📦 Installing FFmpeg..."
    brew install ffmpeg
fi

# Setup Python environment
echo "🐍 Setting up Python environment..."
[ -d "venv" ] && rm -rf venv
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install -e .
pip install -e ".[gui]"

# Copy config files
echo "⚙️ Setting up configuration..."
[ ! -f "config/settings.yaml" ] && cp config/settings.example.yaml config/settings.yaml
[ ! -f "config/credentials.yaml" ] && cp config/credentials.example.yaml config/credentials.yaml

# Create directories
mkdir -p ~/Documents/KnowledgeSystem/{cache,transcripts,output,Reports/Logs}
mkdir -p ~/Documents/KnowledgeSystem/transcripts/Thumbnails

# Set permissions
chmod +x launch_gui.command 2>/dev/null || true

# Quick MVP AI Setup (no prompts)
echo "🤖 Setting up MVP AI System..."
if [ -f "scripts/setup_mvp_llm.sh" ]; then
    # Run MVP setup in quiet mode
    QUIET_MODE=1 bash scripts/setup_mvp_llm.sh || echo "⚠️  MVP AI setup failed, skipping..."
else
    # Fallback: quick Ollama + model install
    if command -v brew &> /dev/null && ! command -v ollama &> /dev/null; then
        echo "📦 Installing Ollama..."
        brew install ollama &> /dev/null || true
    fi
    if command -v ollama &> /dev/null; then
        echo "📥 Downloading AI model..."
        ollama serve &> /dev/null &
        sleep 3
        ollama pull llama3.2:3b &> /dev/null || true
        kill $! 2>/dev/null || true
    fi
fi

# Test
if python -m knowledge_system --help > /dev/null 2>&1; then
    echo "✅ Setup complete!"
    echo ""
    echo "Next steps:"
    echo "1. Add API keys to config/credentials.yaml"
    echo "2. Run: ./launch_gui.command"
    echo ""
    echo "🚀 Launch GUI now? (Ctrl+C to skip)"
    sleep 3
    python -m knowledge_system gui
else
    echo "❌ Setup failed - check errors above"
    exit 1
fi
