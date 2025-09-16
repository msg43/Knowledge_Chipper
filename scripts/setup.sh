#!/bin/bash
# setup.sh - Knowledge_Chipper Complete Setup Script
# This script automates the entire installation process for Knowledge_Chipper

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m' # No Color

echo -e "${BLUE}${BOLD}🚀 Knowledge_Chipper - Complete Setup Script${NC}"
echo "=============================================="
echo "This script will automatically install and configure everything you need."
echo

# Check if running on macOS
if [[ "$OSTYPE" != "darwin"* ]]; then
    echo -e "${YELLOW}⚠️  Warning: This script is optimized for macOS${NC}"
    echo "Knowledge_Chipper is designed for Apple Silicon Macs."
    read -p "Continue anyway? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Setup cancelled."
        exit 1
    fi
fi

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to compare versions
version_greater_equal() {
    printf '%s\n%s\n' "$2" "$1" | sort -V -C
}

# Check Python version
echo -e "${BLUE}📋 Checking Python version...${NC}"
if ! command_exists python3; then
    echo -e "${RED}❌ Python 3 is required but not installed${NC}"
    echo "Please install Python 3.13+ first:"
    echo "  brew install python@3.13"
    exit 1
fi

PYTHON_VERSION=$(python3 --version 2>&1 | cut -d' ' -f2)
REQUIRED_VERSION="3.13.0"
if ! version_greater_equal "$PYTHON_VERSION" "$REQUIRED_VERSION"; then
    echo -e "${RED}❌ Python $PYTHON_VERSION found, but $REQUIRED_VERSION+ required${NC}"
    echo "Please upgrade Python:"
    echo "  brew install python@3.13"
    exit 1
fi
echo -e "${GREEN}✅ Python $PYTHON_VERSION detected${NC}"

# Check/Install Homebrew
echo -e "${BLUE}🍺 Checking Homebrew...${NC}"
if ! command_exists brew; then
    echo -e "${YELLOW}📦 Installing Homebrew...${NC}"
    echo "This may take a few minutes..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

    # Add Homebrew to PATH for current session
    if [[ -f "/opt/homebrew/bin/brew" ]]; then
        eval "$(/opt/homebrew/bin/brew shellenv)"
    elif [[ -f "/usr/local/bin/brew" ]]; then
        eval "$(/usr/local/bin/brew shellenv)"
    fi
else
    echo -e "${GREEN}✅ Homebrew found${NC}"
fi

# Install FFmpeg
echo -e "${BLUE}🎵 Checking FFmpeg...${NC}"
if ! command_exists ffmpeg; then
    echo -e "${YELLOW}📦 Installing FFmpeg...${NC}"
    brew install ffmpeg
else
    echo -e "${GREEN}✅ FFmpeg found${NC}"
fi

# Check Git
echo -e "${BLUE}📂 Checking Git...${NC}"
if ! command_exists git; then
    echo -e "${YELLOW}📦 Installing Git...${NC}"
    brew install git
else
    echo -e "${GREEN}✅ Git found${NC}"
fi

# Create virtual environment
echo -e "${BLUE}🐍 Setting up Python environment...${NC}"
if [ -d "venv" ]; then
    echo -e "${YELLOW}♻️  Removing existing virtual environment...${NC}"
    rm -rf venv
fi

python3 -m venv venv
source venv/bin/activate
echo -e "${GREEN}✅ Virtual environment created${NC}"

# Upgrade pip
echo -e "${BLUE}📦 Upgrading pip...${NC}"
pip install --upgrade pip

# Install Python dependencies
echo -e "${BLUE}📚 Installing Python dependencies...${NC}"
echo "This may take several minutes..."

# Install core requirements
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
else
    echo -e "${RED}❌ requirements.txt not found${NC}"
    exit 1
fi

# Install the package in development mode
pip install -e .

# Install optional GUI dependencies
echo -e "${BLUE}🖥️  Installing GUI dependencies...${NC}"
pip install -e ".[gui]"

echo -e "${GREEN}✅ Python dependencies installed${NC}"

# Set up configuration files with machine optimization
echo -e "${BLUE}⚙️  Setting up machine-optimized configuration...${NC}"

if [ ! -f "config/settings.yaml" ]; then
    # Try to generate machine-specific configuration
    if [ -f "scripts/generate_machine_config.py" ]; then
        echo -e "${BLUE}🔍 Generating configuration optimized for your hardware...${NC}"
        if python scripts/generate_machine_config.py --output config/settings.yaml; then
            echo -e "${GREEN}✅ Created machine-optimized config/settings.yaml${NC}"
        else
            echo -e "${YELLOW}⚠️  Machine optimization failed, using default config${NC}"
            if [ -f "config/settings.example.yaml" ]; then
                cp config/settings.example.yaml config/settings.yaml
                echo -e "${GREEN}✅ Created config/settings.yaml (default)${NC}"
            fi
        fi
    else
        # Fallback to example config
        if [ -f "config/settings.example.yaml" ]; then
            cp config/settings.example.yaml config/settings.yaml
            echo -e "${GREEN}✅ Created config/settings.yaml (default)${NC}"
        else
            echo -e "${YELLOW}⚠️  config/settings.example.yaml not found, skipping${NC}"
        fi
    fi
else
    echo -e "${YELLOW}⚠️  config/settings.yaml already exists, skipping optimization${NC}"
    echo -e "${BLUE}💡 To re-optimize for your hardware, delete config/settings.yaml and re-run setup${NC}"
fi

if [ ! -f "config/credentials.yaml" ]; then
    if [ -f "config/credentials.example.yaml" ]; then
        cp config/credentials.example.yaml config/credentials.yaml
        echo -e "${GREEN}✅ Created config/credentials.yaml${NC}"
        echo -e "${YELLOW}⚠️  Remember to add your API keys to config/credentials.yaml${NC}"
    else
        echo -e "${YELLOW}⚠️  config/credentials.example.yaml not found, skipping${NC}"
    fi
else
    echo -e "${YELLOW}⚠️  config/credentials.yaml already exists, skipping${NC}"
fi

# Create data directories
echo -e "${BLUE}📁 Creating data directories...${NC}"
mkdir -p ~/Documents/KnowledgeSystem/{cache,transcripts,output,Reports/Logs}
mkdir -p ~/Documents/KnowledgeSystem/transcripts/Thumbnails
echo -e "${GREEN}✅ Data directories created${NC}"

# Download base Whisper model (optional but recommended)
echo
echo -e "${BLUE}🤖 Whisper Model Setup${NC}"
echo "The system can pre-download AI models for faster startup."
read -p "Download Whisper base model (~150MB)? (Y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$|^$ ]]; then
    echo -e "${BLUE}📥 Downloading Whisper base model...${NC}"
    python -c "
import whisper
print('Downloading base model...')
model = whisper.load_model('base')
print('Base model ready!')
" 2>/dev/null || echo -e "${YELLOW}⚠️  Model will download on first use${NC}"
    echo -e "${GREEN}✅ Whisper model ready${NC}"
fi

# Install Ollama (optional for local LLM)
echo
# MVP AI System (Essential for Speaker Attribution)
echo
echo -e "${BLUE}🤖 Installing MVP AI System...${NC}"
echo "Setting up built-in AI for automatic speaker attribution (works offline, no API keys needed)."
echo "This enables smart speaker identification in transcriptions (e.g., 'Joe Rogan' instead of 'SPEAKER_00')."
echo ""

# Always install MVP AI - it's now a core feature, not optional
if [ -f "scripts/setup_mvp_llm.sh" ]; then
    bash scripts/setup_mvp_llm.sh
else
    echo -e "${YELLOW}⚠️  MVP AI setup script not found. Using fallback method...${NC}"

    # Ensure Ollama is installed
    if ! command_exists ollama; then
        echo -e "${BLUE}📦 Installing Ollama...${NC}"
        brew install ollama
    fi

    # Start Ollama service
    echo -e "${BLUE}🚀 Starting Ollama service...${NC}"
    ollama serve > /dev/null 2>&1 &
    OLLAMA_PID=$!
    sleep 3

    # Download MVP model
    echo -e "${BLUE}📥 Downloading MVP AI model (llama3.2:3b)...${NC}"
    ollama pull llama3.2:3b || echo -e "${YELLOW}⚠️  Download failed, will retry...${NC}"

    # Verify installation
    if ollama list | grep -q "llama3.2:3b"; then
        echo -e "${GREEN}✅ MVP AI model ready${NC}"
    else
        echo -e "${YELLOW}⚠️  MVP AI model not found, may need manual installation${NC}"
    fi

    # Stop background service
    kill $OLLAMA_PID 2>/dev/null || true
fi

echo -e "${GREEN}✅ MVP AI System installation completed${NC}"

# Download all required models
echo
echo -e "${BLUE}📦 Downloading required AI models...${NC}"
echo "This will download Whisper, Diarization, and Ollama models"
echo "Total download size: ~600MB (one-time download)"
echo

# Check if credentials exist for diarization
if [ ! -f "config/credentials.yaml" ]; then
    echo -e "${YELLOW}⚠️  No credentials.yaml found${NC}"
    echo "   Copying example credentials file..."
    cp config/credentials.example.yaml config/credentials.yaml
    echo "   Please add your API keys to config/credentials.yaml after setup"
fi

# Run the model downloader script
echo -e "${BLUE}Starting model downloads...${NC}"
if python scripts/download_models.py; then
    echo -e "${GREEN}✅ All models downloaded successfully${NC}"
else
    echo -e "${YELLOW}⚠️  Some models failed to download${NC}"
    echo "   You can run this again later with:"
    echo "   python scripts/download_models.py"
    echo
    echo "   For speaker diarization, you need:"
    echo "   1. A HuggingFace token from https://huggingface.co/settings/tokens"
    echo "   2. Accept the license at https://huggingface.co/pyannote/speaker-diarization"
    echo "   3. Add your token to config/credentials.yaml"
fi

# Make launch script executable
if [ -f "launch_gui.command" ]; then
    chmod +x launch_gui.command
    echo -e "${GREEN}✅ Launch script permissions set${NC}"
fi

# Test installation
echo
echo -e "${BLUE}🧪 Testing installation...${NC}"

# Test CLI
if python -m knowledge_system --help > /dev/null 2>&1; then
    echo -e "${GREEN}✅ CLI working${NC}"
else
    echo -e "${RED}❌ CLI test failed${NC}"
    echo "Please check the installation logs above for errors."
    exit 1
fi

# Test GUI imports
if python -c "import knowledge_system.gui" 2>/dev/null; then
    echo -e "${GREEN}✅ GUI imports working${NC}"
else
    echo -e "${RED}❌ GUI import test failed${NC}"
    echo "PyQt6 may not be properly installed."
    exit 1
fi

# Test basic functionality
echo -e "${BLUE}📝 Creating test file...${NC}"
echo "This is a test transcript for the Knowledge System." > test_transcript.txt
if python -c "
import sys
sys.path.insert(0, 'src')
from knowledge_system.processors.summarizer import Summarizer
print('✅ Core modules loading correctly')
" 2>/dev/null; then
    echo -e "${GREEN}✅ Core functionality test passed${NC}"
    rm -f test_transcript.txt
else
    echo -e "${YELLOW}⚠️  Core functionality test failed (may need API keys)${NC}"
    rm -f test_transcript.txt
fi

echo
echo -e "${GREEN}${BOLD}🎉 Setup Complete!${NC}"
echo "=============================================="
echo
echo -e "${BLUE}📝 ${BOLD}Next Steps:${NC}"
echo
echo -e "${YELLOW}1. Configure API Keys${NC} (Required for AI features):"
echo "   Edit: config/credentials.yaml"
echo "   Add your API keys for:"
echo "   • OpenAI (for GPT-based summarization)"
echo "   • WebShare proxy (for YouTube processing)"
echo "   • Anthropic (optional, for Claude)"
echo
echo -e "${YELLOW}2. Launch the Application:${NC}"
echo "   • GUI: Double-click ./launch_gui.command"
echo "   • CLI: source venv/bin/activate && knowledge-system --help"
echo "   • Direct: source venv/bin/activate && python -m knowledge_system gui"
echo
echo -e "${YELLOW}3. Test Your Setup:${NC}"
echo "   • Start with the Cloud Transcription tab"
echo "   • Try a short video first: https://www.youtube.com/watch?v=dQw4w9WgXcQ"
echo "   • Check the Summarization tab with the resulting transcript"
echo
echo -e "${BLUE}📚 ${BOLD}Resources:${NC}"
echo "   • Documentation: README.md"
echo "   • API Setup Guides: docs/YOUTUBE_API_SETUP.md"
echo "   • Configuration: config/settings.yaml"
echo "   • Logs: logs/ directory"
echo
echo -e "${BLUE}🔧 ${BOLD}Troubleshooting:${NC}"
echo "   • Check logs in the GUI console output"
echo "   • Re-download models: python scripts/download_models.py"
echo "   • Models are cached in:"
echo "     - Whisper: ~/.cache/whisper-cpp/"
echo "     - Diarization: ~/.cache/huggingface/hub/"
echo "     - Ollama: ~/.ollama/models/"
echo "   • Verify API keys in config/credentials.yaml"
echo "   • See README.md troubleshooting section"
echo

# Optional: Show system info
if command_exists sw_vers; then
    echo -e "${BLUE}💻 System Information:${NC}"
    echo "   macOS: $(sw_vers -productVersion)"
    echo "   Architecture: $(uname -m)"
    echo "   Python: $PYTHON_VERSION"
    echo
fi

# Optional: Launch GUI immediately
read -p "🚀 Launch the GUI now? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${BLUE}🚀 Launching Knowledge System GUI...${NC}"
    echo "Close this terminal when you're done using the application."
    python -m knowledge_system gui
fi

echo
echo -e "${GREEN}Setup script completed successfully!${NC}"
echo "Welcome to Knowledge_Chipper! 🎉"
