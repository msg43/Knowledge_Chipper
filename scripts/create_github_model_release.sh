#!/bin/bash
set -e

echo "🚀 Creating GitHub Release for AI Models"
echo "========================================"

# Configuration
RELEASE_TAG="models-v1.0"
RELEASE_NAME="Skip the Podcast Desktop - AI Models v1.0"
RELEASE_DESCRIPTION="Pre-bundled AI models for Skip the Podcast Desktop

This release contains optimized AI models for offline use:

🎤 **Whisper Base Model** (141MB) - Speech transcription
🎙️ **Pyannote Speaker Diarization** (~400MB) - Speaker separation
🗣️ **Wav2Vec2 Base** (631MB) - Voice feature extraction
🎯 **ECAPA-TDNN** (79MB) - Speaker recognition

**Benefits:**
- ✅ Fast downloads from GitHub CDN
- ✅ Guaranteed availability
- ✅ No external dependencies
- ✅ Integrity verification with SHA256 checksums

**Total Size:** ~1.2GB for complete offline functionality

The main app automatically downloads these models on first use."

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
MODELS_DIR="$PROJECT_ROOT/github_models_prep"

# Check if models are prepared
if [ ! -d "$MODELS_DIR" ]; then
    echo "❌ Models not prepared. Run scripts/prepare_models_for_github.py first"
    exit 1
fi

echo "📁 Models directory: $MODELS_DIR"
echo "📦 Files to upload:"
ls -lh "$MODELS_DIR"

# Check if gh CLI is available
if ! command -v gh >/dev/null 2>&1; then
    echo "❌ GitHub CLI (gh) not found. Install with: brew install gh"
    echo "   Then authenticate with: gh auth login"
    exit 1
fi

# Check if authenticated
if ! gh auth status >/dev/null 2>&1; then
    echo "❌ Not authenticated with GitHub. Run: gh auth login"
    exit 1
fi

echo ""
echo "🏷️  Release Information:"
echo "   Tag: $RELEASE_TAG"
echo "   Name: $RELEASE_NAME"
echo ""

# Confirm before proceeding
read -p "Create this release? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "❌ Release creation cancelled"
    exit 1
fi

echo ""
echo "🚀 Creating GitHub release..."

# Create release with all assets
gh release create "$RELEASE_TAG" \
    --title "$RELEASE_NAME" \
    --notes "$RELEASE_DESCRIPTION" \
    --draft \
    "$MODELS_DIR"/*

echo ""
echo "✅ GitHub release created successfully!"
echo ""
echo "📋 Next Steps:"
echo "1. Review the draft release at: https://github.com/$(gh repo view --json owner,name -q '.owner.login + \"/\" + .name')/releases"
echo "2. If everything looks good, publish the release"
echo "3. Update scripts/download_models_from_github.py with the correct repo/tag"
echo "4. Test the new download system"
echo ""
echo "🔗 Release URL: https://github.com/$(gh repo view --json owner,name -q '.owner.login + \"/\" + .name')/releases/tag/$RELEASE_TAG"
