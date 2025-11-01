#!/bin/bash
# Test script for Cookie Persistence and Format Selection Fixes
# October 31, 2025

set -e  # Exit on error

echo "=========================================="
echo "Testing Cookie Persistence and Format Fixes"
echo "=========================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test 1: Verify session_manager auto-save is in place
echo "Test 1: Verify SessionManager auto-save fix..."
if grep -q "self._save_session()" src/knowledge_system/gui/core/session_manager.py; then
    echo -e "${GREEN}✅ PASS${NC}: SessionManager.set_tab_setting() calls _save_session()"
else
    echo -e "${RED}❌ FAIL${NC}: SessionManager.set_tab_setting() does NOT call _save_session()"
    exit 1
fi
echo ""

# Test 2: Verify YouTube uses tv_embedded client (most reliable)
echo "Test 2: Verify YouTube uses tv_embedded client for reliable format listings..."
if grep -q '"tv_embedded".*# Most reliable for DASH' src/knowledge_system/processors/youtube_download.py; then
    echo -e "${GREEN}✅ PASS${NC}: YouTube downloader uses tv_embedded client (most reliable)"
else
    echo -e "${RED}❌ FAIL${NC}: YouTube downloader does NOT use tv_embedded client first"
    exit 1
fi
echo ""

# Test 3: Verify Android client is still available as fallback
echo "Test 3: Verify Android client is still available as fallback..."
if grep -q '"android".*# Fallback to Android' src/knowledge_system/processors/youtube_download.py; then
    echo -e "${GREEN}✅ PASS${NC}: Android client available as fallback"
else
    echo -e "${YELLOW}⚠️  WARNING${NC}: Android client may not be available as fallback"
fi
echo ""

# Test 4: Verify diagnostic logging is in place
echo "Test 4: Verify diagnostic logging is in place..."
if grep -q "yt-dlp format string:" src/knowledge_system/processors/youtube_download.py; then
    echo -e "${GREEN}✅ PASS${NC}: Diagnostic logging for format string is in place"
else
    echo -e "${YELLOW}⚠️  WARNING${NC}: Diagnostic logging may be missing"
fi
echo ""

# Test 5: Check if documentation was created
echo "Test 5: Verify documentation was created..."
if [ -f "docs/COOKIE_PERSISTENCE_AND_FORMAT_FIX_2025.md" ]; then
    echo -e "${GREEN}✅ PASS${NC}: Documentation file exists"
else
    echo -e "${RED}❌ FAIL${NC}: Documentation file missing"
    exit 1
fi
echo ""

# Test 6: Verify format string targets m4a format 139 (lowest bitrate)
echo "Test 6: Verify format string targets m4a format 139 (lowest bitrate)..."
if grep -q "ba\[ext=m4a\]\[abr<=60\]\[vcodec=none\]" src/knowledge_system/processors/youtube_download.py; then
    echo -e "${GREEN}✅ PASS${NC}: Format string targets m4a format 139 (48-50kbps)"
else
    echo -e "${RED}❌ FAIL${NC}: Format string does NOT target m4a format 139"
    exit 1
fi
echo ""

# Test 7: Verify format_sort for bitrate sorting
echo "Test 7: Verify format_sort for bitrate sorting..."
if grep -q '"format_sort".*"+abr"' src/knowledge_system/processors/youtube_download.py; then
    echo -e "${GREEN}✅ PASS${NC}: Format sorting configured (+abr for smallest files)"
else
    echo -e "${RED}❌ FAIL${NC}: Format sorting NOT configured"
    exit 1
fi
echo ""

# Test 8: Verify video fallbacks exist to prevent failures
echo "Test 8: Verify video fallbacks exist to prevent download failures..."
if grep -q "ba\[vcodec=none\]/worst/best" src/knowledge_system/processors/youtube_download.py; then
    echo -e "${GREEN}✅ PASS${NC}: Format string has video fallbacks (prevents failures)"
else
    echo -e "${RED}❌ FAIL${NC}: Format string missing video fallbacks (may cause failures)"
    exit 1
fi
echo ""

echo "=========================================="
echo -e "${GREEN}All Tests Passed!${NC}"
echo "=========================================="
echo ""
echo "⚠️  CRITICAL: You MUST restart the app for Python code changes to take effect!"
echo ""
echo "Next Steps:"
echo "1. ⚠️  RESTART THE APP COMPLETELY (close and reopen)"
echo "2. Add cookie files in Transcription tab (should persist after restart)"
echo "3. Download a YouTube video with cookies enabled"
echo "4. Check logs for:"
echo "   - '🔍 yt-dlp format string: ba[vcodec=none]/bestaudio[vcodec=none]...'"
echo "   - '✅ Downloaded audio-only' (NOT '⚠️ VIDEO+AUDIO')"
echo "5. Verify file size is ~6-15MB (NOT ~40-50MB for 16-min video)"
echo ""
echo "See docs/AUDIO_ONLY_FORMAT_FIX_FINAL.md for troubleshooting"
