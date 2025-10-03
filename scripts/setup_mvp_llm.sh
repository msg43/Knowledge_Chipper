#!/bin/bash
# setup_mvp_llm.sh - MVP LLM Setup for DMG Installation
# Installs Ollama + Llama 3.2:3b for out-of-the-box speaker attribution

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# Check if running in quiet mode
if [ "$QUIET_MODE" = "1" ]; then
    echo "🤖 Setting up MVP AI System (quiet mode)..."
else
    echo -e "${BLUE}${BOLD}🤖 Setting up MVP AI System${NC}"
    echo "=============================="
    echo "Installing built-in AI for speaker attribution (works offline, no API keys needed)"
    echo "This is now a core feature that enables professional speaker identification."
    echo ""
fi

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check if running on macOS
if [[ "$OSTYPE" != "darwin"* ]]; then
    echo -e "${YELLOW}⚠️  MVP AI System requires macOS. Skipping...${NC}"
    exit 0
fi

# Check disk space (need ~3GB total)
AVAILABLE_SPACE=$(df -BG . | awk 'NR==2 {print $4}' | sed 's/G//')
if [ "$AVAILABLE_SPACE" -lt 3 ]; then
    if [ "$QUIET_MODE" != "1" ]; then
        echo -e "${YELLOW}⚠️  Insufficient disk space (~3GB needed). Skipping MVP AI setup...${NC}"
        echo "You can install it later from Settings → MVP AI System → Refresh Status"
    fi
    exit 0
fi

if [ "$QUIET_MODE" != "1" ]; then
    echo -e "${BLUE}💾 Available disk space: ${AVAILABLE_SPACE}GB (3GB needed)${NC}"
fi

# Install Ollama if not present
echo -e "${BLUE}📦 Checking Ollama installation...${NC}"
if ! command_exists ollama; then
    echo -e "${YELLOW}Installing Ollama...${NC}"

    # Download and install Ollama
    if command_exists brew; then
        # Use Homebrew if available (cleaner)
        brew install ollama
    else
        # Direct download method
        curl -fsSL https://ollama.ai/install.sh | sh
    fi

    if command_exists ollama; then
        echo -e "${GREEN}✅ Ollama installed successfully${NC}"
    else
        echo -e "${RED}❌ Ollama installation failed${NC}"
        echo "You can install it later from Settings → MVP AI System"
        exit 1
    fi
else
    echo -e "${GREEN}✅ Ollama already installed${NC}"
fi

# Start Ollama service
echo -e "${BLUE}🚀 Starting Ollama service...${NC}"
ollama serve > /dev/null 2>&1 &
OLLAMA_PID=$!

# Wait for service to be ready
echo -e "${BLUE}⏳ Waiting for Ollama service...${NC}"
for i in {1..10}; do
    if curl -s http://localhost:11434 > /dev/null 2>&1; then
        echo -e "${GREEN}✅ Ollama service ready${NC}"
        break
    fi
    if [ $i -eq 10 ]; then
        echo -e "${RED}❌ Ollama service failed to start${NC}"
        kill $OLLAMA_PID 2>/dev/null || true
        exit 1
    fi
    sleep 2
done

# Download MVP model (Llama 3.2:3b) if not already present
if [ "$QUIET_MODE" != "1" ]; then
    echo -e "${BLUE}📥 Checking AI model for speaker attribution...${NC}"
fi

# Check if model already exists
if ollama list | grep -q "qwen2.5:7b"; then
    if [ "$QUIET_MODE" != "1" ]; then
        echo -e "${GREEN}✅ AI model (Qwen 2.5:7b) already available${NC}"
    fi
else
    if [ "$QUIET_MODE" != "1" ]; then
        echo -e "${BLUE}📥 Downloading AI model (Qwen 2.5:7b)...${NC}"
        echo "Model: ~4GB download for automatic speaker identification"
        echo ""
    fi

    # Download with progress (silent in quiet mode)
    if [ "$QUIET_MODE" = "1" ]; then
        ollama pull qwen2.5:7b > /dev/null 2>&1
    else
        ollama pull qwen2.5:7b
    fi

    # Verify download
    if ollama list | grep -q "qwen2.5:7b"; then
        if [ "$QUIET_MODE" != "1" ]; then
            echo -e "${GREEN}✅ MVP AI model downloaded successfully${NC}"
        fi
    else
        if [ "$QUIET_MODE" != "1" ]; then
            echo -e "${RED}❌ Model download failed${NC}"
            echo "You can download it later with: ollama pull qwen2.5:7b"
        fi
        kill $OLLAMA_PID 2>/dev/null || true
        exit 1
    fi
fi

# Test the model
echo -e "${BLUE}🧪 Testing AI model...${NC}"
TEST_RESPONSE=$(ollama run qwen2.5:7b "Say 'MVP AI ready' and nothing else." --timeout 30s 2>/dev/null || echo "")

if [[ "$TEST_RESPONSE" == *"MVP AI ready"* ]]; then
    echo -e "${GREEN}✅ AI model test successful${NC}"
else
    echo -e "${YELLOW}⚠️  AI model test failed, but installation completed${NC}"
    echo "The model will be tested when first used in the application"
fi

# Stop background Ollama service (app will start it as needed)
kill $OLLAMA_PID 2>/dev/null || true

echo ""
echo -e "${GREEN}${BOLD}🎉 MVP AI System setup complete!${NC}"
echo ""
echo -e "${BLUE}Benefits:${NC}"
echo "• Works completely offline (no internet needed after setup)"
echo "• No API keys or subscriptions required"
echo "• Automatically identifies speakers in conversations"
echo "• Provides intelligent names instead of generic 'SPEAKER_00' labels"
echo ""
echo -e "${BLUE}Next steps:${NC}"
echo "• The AI system will activate automatically when you use speaker diarization"
echo "• Check status anytime in Settings → MVP AI System"
echo ""
