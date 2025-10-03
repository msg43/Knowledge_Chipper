#!/bin/bash
# bundle_ollama_models.sh - Create Ollama models package for PKG installer
# Downloads and bundles the qwen2.5:7b-instruct model for offline installation

set -e
set -o pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
BUILD_DIR="$PROJECT_ROOT/build_ollama_models"
OUTPUT_DIR="$PROJECT_ROOT/dist"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m' # No Color

echo -e "${BLUE}${BOLD}🤖 Ollama Models Bundle Creator for PKG Installer${NC}"
echo "=================================================="
echo "Creating Ollama models package for offline installation"
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

print_status "Build directories created"

# Check if Ollama is installed
echo -e "\n${BLUE}🔍 Checking Ollama installation...${NC}"
if ! command -v ollama &> /dev/null; then
    print_error "Ollama is not installed"
    echo "Please install Ollama first:"
    echo "  brew install ollama"
    exit 1
fi

print_status "Ollama is installed"

# Start Ollama service if not running
echo -e "\n${BLUE}🚀 Starting Ollama service...${NC}"
if ! pgrep -x "ollama" > /dev/null; then
    echo "Starting Ollama service..."
    ollama serve > /dev/null 2>&1 &
    sleep 5
    print_status "Ollama service started"
else
    print_status "Ollama service already running"
fi

# Download the model
echo -e "\n${BLUE}📥 Downloading qwen2.5:7b-instruct model...${NC}"
echo "This is a ~4GB download and may take several minutes..."

if ollama list | grep -q "qwen2.5:7b-instruct"; then
    print_status "qwen2.5:7b-instruct model already downloaded"
else
    echo "Downloading qwen2.5:7b-instruct model..."
    if ollama pull qwen2.5:7b-instruct; then
        print_status "qwen2.5:7b-instruct model downloaded successfully"
    else
        print_error "Failed to download qwen2.5:7b-instruct model"
        exit 1
    fi
fi

# Find the model directory
echo -e "\n${BLUE}📂 Locating model files...${NC}"
OLLAMA_MODELS_DIR="$HOME/.ollama/models"

if [ ! -d "$OLLAMA_MODELS_DIR" ]; then
    print_error "Ollama models directory not found: $OLLAMA_MODELS_DIR"
    exit 1
fi

MODEL_DIR="$OLLAMA_MODELS_DIR/qwen2.5/7b-instruct"
if [ ! -d "$MODEL_DIR" ]; then
    print_error "qwen2.5:7b-instruct model directory not found: $MODEL_DIR"
    exit 1
fi

print_status "Model files located at: $MODEL_DIR"

# Copy model to build directory
echo -e "\n${BLUE}📋 Copying model files...${NC}"
BUILD_MODEL_DIR="$BUILD_DIR/qwen2.5/7b-instruct"
mkdir -p "$BUILD_MODEL_DIR"

cp -r "$MODEL_DIR"/* "$BUILD_MODEL_DIR/"

# Verify files were copied
MODEL_FILES=$(find "$BUILD_MODEL_DIR" -type f | wc -l)
echo "Copied $MODEL_FILES model files"

if [ $MODEL_FILES -eq 0 ]; then
    print_error "No model files were copied"
    exit 1
fi

print_status "Model files copied successfully"

# Create the bundle
echo -e "\n${BLUE}📦 Creating Ollama models bundle...${NC}"
OUTPUT_FILE="$OUTPUT_DIR/ollama-models-bundle.tar.gz"

cd "$BUILD_DIR"
tar -czf "$OUTPUT_FILE" .

# Verify the bundle
if [ -f "$OUTPUT_FILE" ]; then
    BUNDLE_SIZE=$(du -h "$OUTPUT_FILE" | cut -f1)
    print_status "Ollama models bundle created: $OUTPUT_FILE ($BUNDLE_SIZE)"
else
    print_error "Failed to create Ollama models bundle"
    exit 1
fi

# Cleanup
echo -e "\n${BLUE}🧹 Cleaning up...${NC}"
rm -rf "$BUILD_DIR"
print_status "Build directory cleaned up"

echo -e "\n${GREEN}${BOLD}🎉 Ollama Models Bundle Creation Complete!${NC}"
echo "========================================"
echo "Output file: $OUTPUT_FILE"
echo "Size: $BUNDLE_SIZE"
echo ""
echo "This bundle will be included in the PKG installer and downloaded"
echo "during installation, eliminating the surprise 4GB download."
