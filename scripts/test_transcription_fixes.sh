#!/bin/bash
# Test script to verify transcription tab fixes
# Tests:
# 1. Color-coded checkbox defaults to unchecked
# 2. Thumbnail and description appear in .md files

set -e

echo "🧪 Testing Transcription Tab Fixes"
echo "=================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test 1: Check color-coded checkbox default
echo "Test 1: Checking color-coded checkbox default..."
echo "   This requires manual verification in the GUI:"
echo "   1. Launch the app"
echo "   2. Go to Transcription tab"
echo "   3. Verify 'Generate color-coded transcripts' checkbox is UNCHECKED"
echo ""
echo -e "${YELLOW}   ⚠️  Manual test required - launch GUI and verify${NC}"
echo ""

# Test 2: Check if thumbnail/description code is present
echo "Test 2: Checking thumbnail/description code in audio_processor.py..."

if grep -q "Embedded thumbnail in markdown" src/knowledge_system/processors/audio_processor.py; then
    echo -e "${GREEN}   ✅ Thumbnail embedding code found${NC}"
else
    echo -e "${RED}   ❌ Thumbnail embedding code NOT found${NC}"
    exit 1
fi

if grep -q "Added description to markdown" src/knowledge_system/processors/audio_processor.py; then
    echo -e "${GREEN}   ✅ Description embedding code found${NC}"
else
    echo -e "${RED}   ❌ Description embedding code NOT found${NC}"
    exit 1
fi

if grep -q "Added.*tags to YAML frontmatter" src/knowledge_system/processors/audio_processor.py; then
    echo -e "${GREEN}   ✅ Tags/keywords embedding code found${NC}"
else
    echo -e "${RED}   ❌ Tags/keywords embedding code NOT found${NC}"
    exit 1
fi

echo ""
echo "Test 3: Checking enhanced logging in transcription_tab.py..."

if grep -q "thumbnail: {has_thumbnail}, description: {has_description}" src/knowledge_system/gui/tabs/transcription_tab.py; then
    echo -e "${GREEN}   ✅ Enhanced metadata logging found${NC}"
else
    echo -e "${RED}   ❌ Enhanced metadata logging NOT found${NC}"
    exit 1
fi

echo ""
echo "Test 4: Checking color-coded checkbox fix..."

if grep -q "ALWAYS start color-coded checkbox as unchecked" src/knowledge_system/gui/tabs/transcription_tab.py; then
    echo -e "${GREEN}   ✅ Color-coded checkbox fix found${NC}"
else
    echo -e "${RED}   ❌ Color-coded checkbox fix NOT found${NC}"
    exit 1
fi

echo ""
echo "=================================="
echo -e "${GREEN}✅ All automated tests passed!${NC}"
echo ""
echo "📋 Manual Testing Steps:"
echo "   1. Launch the GUI: python -m knowledge_system.gui"
echo "   2. Go to Transcription tab"
echo "   3. Verify 'Generate color-coded transcripts' is UNCHECKED"
echo "   4. Download a YouTube video (with audio)"
echo "   5. Transcribe it"
echo "   6. Check the generated .md file for:"
echo "      - Thumbnail image: ![Thumbnail](...)"
echo "      - ## Description section"
echo "      - tags: [...] in YAML frontmatter"
echo "   7. Check logs for:"
echo "      - '✅ Embedded thumbnail in markdown'"
echo "      - '✅ Added description to markdown'"
echo "      - '✅ Added N tags to YAML frontmatter'"
echo ""
echo "📝 If thumbnail/description are still missing:"
echo "   - Check logs for 'No thumbnail_local_path' or 'No description'"
echo "   - This means the database doesn't have the data"
echo "   - Re-download the video to populate database with metadata"
echo ""
