#!/bin/bash
# cleanup_old_install.sh - Complete cleanup of old Skip the Podcast installations
# Run this before testing the new PKG installer to ensure a clean environment

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m' # No Color

echo -e "${BLUE}${BOLD}🧹 Skip the Podcast Cleanup Utility${NC}"
echo "======================================"
echo "This will completely remove all old installations"
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

# Function to safely remove directory
safe_remove() {
    local path="$1"
    local description="$2"

    if [ -e "$path" ]; then
        echo -e "${BLUE}Removing:${NC} $description"
        echo "  Path: $path"

        # Get size before removal
        if [ -d "$path" ]; then
            SIZE=$(du -sh "$path" 2>/dev/null | cut -f1 || echo "unknown")
            echo "  Size: $SIZE"
        fi

        # Remove with confirmation for important paths
        if [[ "$path" == *"/Applications/"* ]] || [[ "$path" == *"/Library/"* ]]; then
            read -p "  Remove this directory? (y/N): " -n 1 -r
            echo
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                sudo rm -rf "$path"
                print_status "Removed: $description"
            else
                print_warning "Skipped: $description"
            fi
        else
            rm -rf "$path"
            print_status "Removed: $description"
        fi
    else
        print_status "Not found: $description"
    fi
}

echo -e "${BLUE}🔍 Scanning for old installations...${NC}"
echo ""

# 1. Application Bundle
echo -e "${BLUE}📱 Application Bundle:${NC}"
safe_remove "/Applications/Skip the Podcast Desktop.app" "Main application bundle"
safe_remove "/Applications/Skip the Podcast.app" "Alternative app name"

# 2. User Application Support
echo -e "\n${BLUE}👤 User Application Support:${NC}"
safe_remove "$HOME/Library/Application Support/Skip the Podcast Desktop" "User app support data"
safe_remove "$HOME/Library/Application Support/Skip the Podcast" "Alternative user data"

# 3. User Preferences
echo -e "\n${BLUE}⚙️ User Preferences:${NC}"
safe_remove "$HOME/Library/Preferences/com.knowledgechipper.skipthepodcast.plist" "User preferences"
safe_remove "$HOME/Library/Preferences/com.knowledgechipper.skipthepodcastdesktop.plist" "Alternative preferences"

# 4. User Caches
echo -e "\n${BLUE}🗄️ User Caches:${NC}"
safe_remove "$HOME/Library/Caches/com.knowledgechipper.skipthepodcast" "User caches"
safe_remove "$HOME/Library/Caches/Skip the Podcast Desktop" "Alternative cache location"

# 5. Component Cache (our new system)
echo -e "\n${BLUE}📦 Component Cache:${NC}"
safe_remove "$HOME/.skip_the_podcast" "New component cache directory"

# 6. System-wide LaunchDaemons
echo -e "\n${BLUE}🚀 System LaunchDaemons:${NC}"
safe_remove "/Library/LaunchDaemons/com.knowledgechipper.skipthepodcast.plist" "System launch daemon"

# 7. System Application Support
echo -e "\n${BLUE}🏢 System Application Support:${NC}"
safe_remove "/Library/Application Support/Skip the Podcast Desktop" "System app support"

# 8. Ollama Models (if you want to start fresh)
echo -e "\n${BLUE}🤖 Ollama Models:${NC}"
if [ -d "$HOME/.ollama/models" ]; then
    echo "Found Ollama models directory: $HOME/.ollama/models"
    echo "Models found:"
    find "$HOME/.ollama/models" -name "*.bin" -o -name "*.safetensors" 2>/dev/null | head -5 || echo "  (checking for model files...)"

    read -p "Remove all Ollama models? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        sudo rm -rf "$HOME/.ollama/models"
        print_status "Removed all Ollama models"
    else
        print_warning "Kept existing Ollama models"
    fi
else
    print_status "No Ollama models directory found"
fi

# 9. Python Virtual Environments
echo -e "\n${BLUE}🐍 Python Environments:${NC}"
safe_remove "$HOME/.skip_the_podcast_venv" "Old Python virtual environment"
safe_remove "$HOME/venv" "Alternative venv location"

# 10. Database Files
echo -e "\n${BLUE}🗃️ Database Files:${NC}"
safe_remove "$HOME/knowledge_system.db" "Old database file"
safe_remove "$HOME/.knowledge_system.db" "Alternative database location"

# 11. Configuration Files
echo -e "\n${BLUE}📋 Configuration Files:${NC}"
safe_remove "$HOME/.skip_the_podcast_config" "Old config directory"
safe_remove "$HOME/.knowledge_chipper" "Alternative config location"

# 12. Log Files
echo -e "\n${BLUE}📝 Log Files:${NC}"
safe_remove "$HOME/Library/Logs/Skip the Podcast Desktop" "Application logs"
safe_remove "/tmp/skip_the_podcast_install.log" "Installation log"

# 13. Check for running processes
echo -e "\n${BLUE}🔄 Running Processes:${NC}"
RUNNING_PROCESSES=$(pgrep -f -i "skip.*podcast\|knowledge.*system" 2>/dev/null || true)

if [ -n "$RUNNING_PROCESSES" ]; then
    echo "Found running processes:"
    echo "$RUNNING_PROCESSES"
    echo ""
    read -p "Kill these processes? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "$RUNNING_PROCESSES" | xargs kill -9 2>/dev/null || true
        print_status "Killed running processes"
    else
        print_warning "Left processes running"
    fi
else
    print_status "No running processes found"
fi

# 14. Final verification
echo -e "\n${BLUE}🔍 Final Verification:${NC}"

REMAINING_FILES=()
if [ -e "/Applications/Skip the Podcast Desktop.app" ]; then
    REMAINING_FILES+=("/Applications/Skip the Podcast Desktop.app")
fi
if [ -e "$HOME/Library/Application Support/Skip the Podcast Desktop" ]; then
    REMAINING_FILES+=("$HOME/Library/Application Support/Skip the Podcast Desktop")
fi
if [ -e "$HOME/.skip_the_podcast" ]; then
    REMAINING_FILES+=("$HOME/.skip_the_podcast")
fi

if [ ${#REMAINING_FILES[@]} -eq 0 ]; then
    print_status "Cleanup complete! System is ready for fresh installation."
else
    echo -e "${YELLOW}⚠️ Some files may still remain:${NC}"
    for file in "${REMAINING_FILES[@]}"; do
        echo "  - $file"
    done
    echo ""
    echo "You may need to remove these manually or run the script again."
fi

echo ""
echo -e "${GREEN}${BOLD}🎉 Cleanup Summary${NC}"
echo "=================="
echo "Your system is now ready for a clean installation of the new PKG."
echo ""
echo -e "${BLUE}Next steps:${NC}"
echo "1. Download the new PKG from: https://github.com/msg43/Knowledge_Chipper/releases/latest"
echo "2. Double-click the PKG to install"
echo "3. The installer will automatically:"
echo "   - Download optimal Qwen model for your Mac"
echo "   - Set up all components with intelligent caching"
echo "   - Configure everything automatically"
echo ""
echo -e "${YELLOW}💡 Tip:${NC} Keep 'Check for updates on startup' enabled for fast future updates!"
