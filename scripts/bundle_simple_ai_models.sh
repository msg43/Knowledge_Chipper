#!/bin/bash
# bundle_simple_ai_models.sh - Create simple AI models package for PKG installer
# Uses existing models from github_models_prep directory

set -e
set -o pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
BUILD_DIR="$PROJECT_ROOT/build_ai_models"
OUTPUT_DIR="$PROJECT_ROOT/dist"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m' # No Color

echo -e "${BLUE}${BOLD}🧠 Simple AI Models Bundle Creator${NC}"
echo "=================================="
echo "Bundling existing AI models for PKG installer"
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

MODELS_DIR="$BUILD_DIR/ai_models"
mkdir -p "$MODELS_DIR"

print_status "Build directories created"

# Check what models are available and copy them
echo -e "\n${BLUE}🔍 Checking available models...${NC}"

MODELS_FOUND=0

# Check for Whisper models
if [ -d "$PROJECT_ROOT/github_models_prep/whisper-base" ]; then
    echo "Found Whisper base model"
    cp -R "$PROJECT_ROOT/github_models_prep/whisper-base" "$MODELS_DIR/"
    MODELS_FOUND=$((MODELS_FOUND + 1))
fi

# Check for Voice Fingerprinting models
if [ -d "$PROJECT_ROOT/github_models_prep/wav2vec2-base-960h" ]; then
    echo "Found Wav2Vec2 model"
    cp -R "$PROJECT_ROOT/github_models_prep/wav2vec2-base-960h" "$MODELS_DIR/"
    MODELS_FOUND=$((MODELS_FOUND + 1))
fi

if [ -d "$PROJECT_ROOT/github_models_prep/spkrec-ecapa-voxceleb" ]; then
    echo "Found ECAPA-TDNN model"
    cp -R "$PROJECT_ROOT/github_models_prep/spkrec-ecapa-voxceleb" "$MODELS_DIR/"
    MODELS_FOUND=$((MODELS_FOUND + 1))
fi

# Check for Pyannote models
if [ -d "$PROJECT_ROOT/github_models_prep/pyannote-speaker-diarization-3.1" ]; then
    echo "Found Pyannote diarization model"
    cp -R "$PROJECT_ROOT/github_models_prep/pyannote-speaker-diarization-3.1" "$MODELS_DIR/"
    MODELS_FOUND=$((MODELS_FOUND + 1))
fi

if [ $MODELS_FOUND -eq 0 ]; then
    print_warning "No AI models found in github_models_prep directory"
    print_warning "Creating minimal placeholder structure"

    # Create minimal structure for PKG installer
    mkdir -p "$MODELS_DIR/whisper-base"
    mkdir -p "$MODELS_DIR/voice_fingerprinting"
    mkdir -p "$MODELS_DIR/pyannote"

    # Create placeholder files
    echo "# Whisper base model placeholder" > "$MODELS_DIR/whisper-base/placeholder.txt"
    echo "# Voice fingerprinting models placeholder" > "$MODELS_DIR/voice_fingerprinting/placeholder.txt"
    echo "# Pyannote models placeholder" > "$MODELS_DIR/pyannote/placeholder.txt"
else
    print_status "Found $MODELS_FOUND model directories"
fi

# Create model manifest
echo -e "\n${BLUE}📋 Creating model manifest...${NC}"

cat > "$MODELS_DIR/models_manifest.json" << EOF
{
  "ai_models_bundle": {
    "version": "1.0.0",
    "build_date": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
    "models_found": $MODELS_FOUND,
    "models": {
      "whisper": {
        "base": "$([ -d "$MODELS_DIR/whisper-base" ] && echo "available" || echo "placeholder")"
      },
      "voice_fingerprinting": {
        "wav2vec2": "$([ -d "$MODELS_DIR/wav2vec2-base-960h" ] && echo "available" || echo "missing")",
        "ecapa_tdnn": "$([ -d "$MODELS_DIR/spkrec-ecapa-voxceleb" ] && echo "available" || echo "missing")"
      },
      "pyannote": {
        "speaker_diarization": "$([ -d "$MODELS_DIR/pyannote-speaker-diarization-3.1" ] && echo "available" || echo "missing")"
      }
    }
  }
}
EOF

print_status "Model manifest created"

# Create installation script
echo -e "\n${BLUE}📜 Creating installation script...${NC}"

cat > "$MODELS_DIR/install_models.sh" << 'EOF'
#!/bin/bash
# AI Models installer for PKG

APP_BUNDLE="$1"
if [ -z "$APP_BUNDLE" ]; then
    echo "Usage: $0 <path-to-app-bundle>"
    exit 1
fi

echo "Installing AI models to: $APP_BUNDLE"

# Create models directory in app bundle
MODELS_TARGET="$APP_BUNDLE/Contents/Resources/ai_models"
mkdir -p "$MODELS_TARGET"

# Copy all model directories
for model_dir in */; do
    if [ -d "$model_dir" ] && [ "$model_dir" != "." ] && [ "$model_dir" != ".." ]; then
        echo "Installing model: $model_dir"
        cp -R "$model_dir" "$MODELS_TARGET/"
    fi
done

# Copy manifest
cp models_manifest.json "$MODELS_TARGET/"

echo "AI models installed successfully"
EOF

chmod +x "$MODELS_DIR/install_models.sh"

print_status "Installation script created"

# Create the tarball
echo -e "\n${BLUE}📦 Creating AI models archive...${NC}"
cd "$BUILD_DIR"
tar -czf "$OUTPUT_DIR/ai-models-bundle.tar.gz" "ai_models"
ARCHIVE_SIZE=$(du -h "$OUTPUT_DIR/ai-models-bundle.tar.gz" | cut -f1)

print_status "AI models archive created: ai-models-bundle.tar.gz ($ARCHIVE_SIZE)"

# Create checksums
cd "$OUTPUT_DIR"
shasum -a 256 "ai-models-bundle.tar.gz" > "ai-models-bundle.tar.gz.sha256"

print_status "Checksums created"

# Cleanup
rm -rf "$BUILD_DIR"

echo ""
echo -e "${GREEN}${BOLD}✅ AI Models Bundle Ready!${NC}"
echo "=========================="
echo "Archive: $OUTPUT_DIR/ai-models-bundle.tar.gz"
echo "Size: $ARCHIVE_SIZE"
echo "Models included: $MODELS_FOUND directories"
echo ""
