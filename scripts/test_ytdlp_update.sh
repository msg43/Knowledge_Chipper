#!/bin/bash
# Test yt-dlp updates before promoting to production
# This ensures new versions work before pinning them for users

set -e

echo "🧪 yt-dlp Update Testing Workflow"
echo "=================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check current version
CURRENT=$(pip show yt-dlp | grep Version | awk '{print $2}')
echo "📌 Current pinned version: $CURRENT"

# Check latest version
echo "🔍 Checking for updates..."
LATEST=$(pip index versions yt-dlp 2>/dev/null | grep "LATEST:" | awk '{print $2}')

if [ -z "$LATEST" ]; then
    echo -e "${RED}❌ Could not fetch latest version${NC}"
    exit 1
fi

echo "🆕 Latest available version: $LATEST"
echo ""

if [ "$CURRENT" = "$LATEST" ]; then
    echo -e "${GREEN}✅ Already on latest version${NC}"
    exit 0
fi

echo -e "${YELLOW}⚠️  Update available: $CURRENT → $LATEST${NC}"
echo ""
echo "This will:"
echo "  1. Install the latest yt-dlp"
echo "  2. Run automated tests"
echo "  3. Prompt you to test manually"
echo "  4. Update production pins if all tests pass"
echo ""
read -p "Continue? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Cancelled."
    exit 0
fi

echo ""
echo "📦 Installing yt-dlp $LATEST..."
pip install "yt-dlp==$LATEST"

echo ""
echo "🧪 Running automated tests..."
echo ""

# Test 1: Import test
echo "Test 1: Import test..."
if python -c "import yt_dlp; print('✅ Import successful')" 2>/dev/null; then
    echo -e "${GREEN}✅ PASS${NC}"
else
    echo -e "${RED}❌ FAIL: Cannot import yt_dlp${NC}"
    exit 1
fi

# Test 2: Version check
echo "Test 2: Version check..."
if python -c "import yt_dlp; assert yt_dlp.version.__version__ == '$LATEST'" 2>/dev/null; then
    echo -e "${GREEN}✅ PASS${NC}"
else
    echo -e "${RED}❌ FAIL: Version mismatch${NC}"
    exit 1
fi

# Test 3: Basic YouTube video info extraction (no download)
echo "Test 3: YouTube info extraction..."
TEST_URL="https://www.youtube.com/watch?v=dQw4w9WgXcQ"  # Rick Astley - Never Gonna Give You Up
if yt-dlp --skip-download --print title "$TEST_URL" > /dev/null 2>&1; then
    echo -e "${GREEN}✅ PASS${NC}"
else
    echo -e "${RED}❌ FAIL: Could not extract video info${NC}"
    echo "This likely means YouTube has blocked the request or the version is broken."
    exit 1
fi

# Test 4: Run integration tests if available
echo "Test 4: Integration tests..."
if [ -f "tests/test_youtube_download.py" ]; then
    if pytest tests/test_youtube_download.py -v; then
        echo -e "${GREEN}✅ PASS${NC}"
    else
        echo -e "${RED}❌ FAIL: Integration tests failed${NC}"
        exit 1
    fi
else
    echo -e "${YELLOW}⚠️  SKIP: No integration tests found${NC}"
fi

echo ""
echo -e "${GREEN}🎉 All automated tests passed!${NC}"
echo ""
echo "📝 Manual Testing Required:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Please test the following scenarios manually:"
echo ""
echo "1. Single video download:"
echo "   knowledge-system youtube https://www.youtube.com/watch?v=dQw4w9WgXcQ"
echo ""
echo "2. Playlist download:"
echo "   knowledge-system youtube https://www.youtube.com/playlist?list=PLrAXtmErZgOeiKm4sgNOknGvNjby9efdf"
echo ""
echo "3. Long video (>1 hour):"
echo "   knowledge-system youtube https://www.youtube.com/watch?v=VIDEO_ID"
echo ""
echo "4. Live stream recording:"
echo "   knowledge-system youtube https://www.youtube.com/watch?v=LIVESTREAM_ID"
echo ""
echo "5. Age-restricted video:"
echo "   Test with an age-restricted video URL"
echo ""

read -p "Did all manual tests pass? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo ""
    echo -e "${YELLOW}⚠️  Tests failed. Keeping development version but NOT updating production pins.${NC}"
    echo "To rollback: pip install yt-dlp==$CURRENT"
    exit 1
fi

echo ""
echo "🎯 Promoting version $LATEST to production..."
echo ""

# Update requirements.txt
echo "Updating requirements.txt..."
TODAY=$(date +%Y-%m-%d)
sed -i.bak "s/yt-dlp==.*/yt-dlp==$LATEST  # Last tested: $TODAY - format selection and signature extraction working/" requirements.txt

# Update pyproject.toml
echo "Updating pyproject.toml..."
sed -i.bak "s/yt-dlp==.*/yt-dlp==$LATEST\",  # Last tested: $TODAY - See docs\/DEPENDENCY_UPDATE_STRATEGY.md/" pyproject.toml

# Clean up backup files
rm -f requirements.txt.bak pyproject.toml.bak

echo ""
echo -e "${GREEN}✅ Production pins updated!${NC}"
echo ""
echo "📋 Next steps:"
echo "  1. Review the changes:"
echo "     git diff requirements.txt pyproject.toml"
echo ""
echo "  2. Commit the update:"
echo "     git add requirements.txt pyproject.toml"
echo "     git commit -m \"Update yt-dlp to $LATEST (tested)\""
echo ""
echo "  3. Build and test the DMG:"
echo "     make build"
echo ""
echo "  4. Release when ready:"
echo "     git push"
echo ""
echo -e "${GREEN}🎉 Update complete!${NC}"
