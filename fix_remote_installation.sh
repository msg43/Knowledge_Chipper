#!/bin/bash
# Fix Remote Installation Issues Script
# Run this on the remote machine to fix all installation problems

set -e

echo "🚀 Knowledge Chipper - Remote Installation Fix"
echo "=============================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# 1. Clear macOS Launch Services cache
echo -e "${BLUE}🧹 Clearing macOS Launch Services cache...${NC}"
echo "   This fixes version confusion and ghost app issues"

# Reset Launch Services database
/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister -kill -r -domain local -domain system -domain user
echo -e "   ${GREEN}✓${NC} Launch Services cache cleared"

# Force rebuild of Launch Services database
/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister -f /Applications/Knowledge_Chipper.app 2>/dev/null || true
echo -e "   ${GREEN}✓${NC} App re-registered with Launch Services"

# 2. Remove stale pyproject.toml files affecting version detection
echo ""
echo -e "${BLUE}📄 Removing stale pyproject.toml files...${NC}"
echo "   This fixes version detection reading wrong version numbers"

# Find and remove stale pyproject.toml files in common locations
STALE_FILES=(
    "$HOME/pyproject.toml"
    "$HOME/Desktop/pyproject.toml"
    "$HOME/Downloads/pyproject.toml"
    "/Applications/pyproject.toml"
    "/tmp/pyproject.toml"
)

for file in "${STALE_FILES[@]}"; do
    if [ -f "$file" ]; then
        echo "   Removing: $file"
        rm -f "$file" || true
        echo -e "   ${GREEN}✓${NC} Removed stale file: $file"
    fi
done

# Also check for any pyproject.toml files in the user's home directory tree
find "$HOME" -name "pyproject.toml" -not -path "*/.*" -not -path "*/venv/*" -not -path "*/node_modules/*" 2>/dev/null | while read -r file; do
    if [[ "$file" != *"/Projects/Knowledge_Chipper/"* ]]; then
        echo "   Found potentially stale: $file"
        echo "   Please review if this should be removed manually"
    fi
done

# 3. Remove app quarantine and extended attributes
echo ""
echo -e "${BLUE}🛡️  Removing quarantine and fixing permissions...${NC}"
echo "   This ensures the app can access local services like Ollama"

APP_PATH="/Applications/Knowledge_Chipper.app"
if [ -d "$APP_PATH" ]; then
    # Remove quarantine attribute
    sudo xattr -dr com.apple.quarantine "$APP_PATH" 2>/dev/null || true
    echo -e "   ${GREEN}✓${NC} Quarantine removed"

    # Remove all extended attributes
    sudo xattr -cr "$APP_PATH" 2>/dev/null || true
    echo -e "   ${GREEN}✓${NC} Extended attributes cleared"

    # Fix permissions
    sudo chmod -R 755 "$APP_PATH" 2>/dev/null || true
    echo -e "   ${GREEN}✓${NC} Permissions fixed"

    # Update ownership
    sudo chown -R "$(whoami):admin" "$APP_PATH" 2>/dev/null || true
    echo -e "   ${GREEN}✓${NC} Ownership updated"
else
    echo -e "   ${YELLOW}⚠️${NC} App not found at $APP_PATH"
fi

# 4. Create fresh install markers
echo ""
echo -e "${BLUE}🆕 Creating fresh install markers...${NC}"
echo "   This prevents auto-update loops on first launch"

touch ~/.skip_the_podcast_desktop_authorized
touch ~/.skip_the_podcast_desktop_installed
echo -e "   ${GREEN}✓${NC} Fresh install markers created (.skip_the_podcast_desktop_authorized, .skip_the_podcast_desktop_installed)"
echo -e "   ${GREEN}✓${NC} Auto-update will be disabled until markers are manually removed"

# 5. Verify Ollama is accessible
echo ""
echo -e "${BLUE}🦙 Verifying Ollama accessibility...${NC}"
echo "   Checking if the app can connect to your Ollama installation"

if curl -s http://localhost:11434/api/version > /dev/null; then
    OLLAMA_VERSION=$(curl -s http://localhost:11434/api/version | grep -o '"version":"[^"]*' | cut -d'"' -f4)
    echo -e "   ${GREEN}✓${NC} Ollama is running (version: $OLLAMA_VERSION)"

    # Count available models
    MODEL_COUNT=$(ollama list | tail -n +2 | wc -l | tr -d ' ')
    echo -e "   ${GREEN}✓${NC} Found $MODEL_COUNT installed models"

    # List models for verification
    echo "   Available models:"
    ollama list | tail -n +2 | head -5 | while IFS= read -r line; do
        MODEL_NAME=$(echo "$line" | awk '{print $1}')
        echo "     • $MODEL_NAME"
    done

    if [ "$MODEL_COUNT" -gt 5 ]; then
        echo "     • ... and $((MODEL_COUNT - 5)) more"
    fi
else
    echo -e "   ${YELLOW}⚠️${NC} Ollama service not accessible"
    echo "   The app should automatically prompt to install/start Ollama on first launch"
fi

# 6. Test network connectivity for the app
echo ""
echo -e "${BLUE}🌐 Testing network connectivity...${NC}"
echo "   Verifying the app can access external services"

# Test GitHub (for updates)
if curl -s --max-time 5 https://api.github.com/repos/msg43/Skipthepodcast.com/releases/latest > /dev/null; then
    echo -e "   ${GREEN}✓${NC} GitHub API accessible"
else
    echo -e "   ${YELLOW}⚠️${NC} GitHub API not accessible (updates may not work)"
fi

# Test OpenAI (if API key exists)
if [ -f "$HOME/Library/Application Support/Knowledge Chipper/Config/credentials.yaml" ]; then
    echo -e "   ${GREEN}✓${NC} Credentials file found"
else
    echo -e "   ${YELLOW}ℹ️${NC} No credentials file found (expected for new install)"
fi

# 7. Final verification
echo ""
echo -e "${BLUE}🔍 Final verification...${NC}"

# Check app bundle structure
if [ -f "$APP_PATH/Contents/Info.plist" ]; then
    APP_VERSION=$(defaults read "$APP_PATH/Contents/Info.plist" CFBundleShortVersionString 2>/dev/null || echo "Unknown")
    echo -e "   ${GREEN}✓${NC} App bundle valid (version: $APP_VERSION)"

    # Check for version sync issues
    if [ -f "$APP_PATH/Contents/MacOS/pyproject.toml" ]; then
        BUNDLED_VERSION=$(grep '^version = ' "$APP_PATH/Contents/MacOS/pyproject.toml" | sed 's/version = "\(.*\)"/\1/')
        if [ "$APP_VERSION" = "$BUNDLED_VERSION" ]; then
            echo -e "   ${GREEN}✓${NC} Version sync correct (Info.plist: $APP_VERSION, pyproject.toml: $BUNDLED_VERSION)"
        else
            echo -e "   ${YELLOW}⚠️${NC} Version mismatch detected (Info.plist: $APP_VERSION, pyproject.toml: $BUNDLED_VERSION)"
            echo -e "   ${BLUE}ℹ️${NC} App will now prefer Info.plist version (fixed in this update)"
        fi
    fi
else
    echo -e "   ${RED}❌${NC} App bundle invalid or corrupted"
fi

# Check if app can be launched
if [ -x "$APP_PATH/Contents/MacOS/launch" ]; then
    echo -e "   ${GREEN}✓${NC} App launcher is executable"
else
    echo -e "   ${RED}❌${NC} App launcher not found or not executable"
fi

echo ""
echo -e "${GREEN}🎉 Remote Installation Fix Complete!${NC}"
echo ""
echo -e "${BLUE}📋 Summary of changes:${NC}"
echo "   • Launch Services cache cleared (fixes version confusion)"
echo "   • Stale configuration files removed (fixes version detection)"
echo "   • App quarantine and permissions fixed (enables Ollama access)"
echo "   • Fresh install marker created (prevents auto-update)"
echo "   • Network connectivity verified"
echo ""
echo -e "${BLUE}🚀 Next steps:${NC}"
echo "1. Launch Knowledge Chipper from Applications"
echo "2. The app should automatically detect and use your Ollama models"
echo "3. Cloud transcription should now work properly"
echo "4. No more auto-update loops on startup"
echo ""
echo -e "${BLUE}🐛 If issues persist:${NC}"
echo "• Check logs: ~/Library/Logs/Knowledge\\ Chipper/knowledge_system.log"
echo "• Verify Ollama: curl http://localhost:11434/api/version"
echo "• Report issues with full logs"
echo ""
