#!/bin/bash
# optimize_for_machine.sh - Re-optimize configuration for current hardware
# Useful when moving installation to different machine or after hardware upgrades

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🔧 Knowledge Chipper - Machine Optimization${NC}"
echo "============================================="

# Get script directory and project root
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo -e "${RED}❌ Virtual environment not found${NC}"
    echo "Please run setup.sh first to create the environment"
    exit 1
fi

# Activate virtual environment
echo -e "${BLUE}🐍 Activating virtual environment...${NC}"
source venv/bin/activate

# Check if the generator exists
if [ ! -f "scripts/generate_machine_config.py" ]; then
    echo -e "${RED}❌ Machine config generator not found${NC}"
    echo "Please ensure scripts/generate_machine_config.py exists"
    exit 1
fi

# Backup existing config if it exists
if [ -f "config/settings.yaml" ]; then
    backup_file="config/settings.yaml.backup.$(date +%Y%m%d_%H%M%S)"
    echo -e "${YELLOW}📋 Backing up existing config to: ${backup_file}${NC}"
    cp "config/settings.yaml" "$backup_file"
fi

# Generate new optimized configuration
echo -e "${BLUE}🔍 Analyzing your hardware and generating optimized configuration...${NC}"
echo

if python scripts/generate_machine_config.py --output config/settings.yaml --force; then
    echo
    echo -e "${GREEN}🎉 Machine optimization complete!${NC}"
    echo -e "${GREEN}✅ Your configuration has been optimized for this hardware${NC}"
    echo
    echo -e "${BLUE}📊 What was optimized:${NC}"
    echo "   • CPU thread allocation based on your core count"
    echo "   • Memory limits adjusted for your RAM"
    echo "   • Concurrency settings tuned for your hardware"
    echo "   • Whisper model and batch sizes optimized"
    echo "   • Performance profile selected automatically"
    echo
    echo -e "${BLUE}💡 Next steps:${NC}"
    echo "   • Review the generated config/settings.yaml file"
    echo "   • Add your API keys to config/credentials.yaml if needed"
    echo "   • Launch the application to test the new settings"
    echo
    echo -e "${YELLOW}ℹ️  If you experience issues, restore from backup:${NC}"
    if [ -f "$backup_file" ]; then
        echo "   cp \"$backup_file\" config/settings.yaml"
    fi
else
    echo
    echo -e "${RED}❌ Optimization failed${NC}"
    if [ -f "$backup_file" ]; then
        echo -e "${YELLOW}Restoring backup configuration...${NC}"
        cp "$backup_file" config/settings.yaml
        echo -e "${GREEN}✅ Original configuration restored${NC}"
    fi
    exit 1
fi
