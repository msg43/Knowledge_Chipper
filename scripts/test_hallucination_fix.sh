#!/bin/bash

# Test script to verify hallucination prevention fix
# Tests the video that previously had 86 seconds of hallucinations

echo "=================================================="
echo "Hallucination Prevention Fix - Test Script"
echo "=================================================="
echo ""
echo "Testing video: kxKk7sBpcYA (Why Trump's Stance on Canada Makes Sense)"
echo "Previous result: 42 repetitions removed (172s-258s = 86 seconds lost)"
echo "Expected result: Clean transcription with no or minimal cleanup"
echo ""

# Check if we're in the project root
if [ ! -f "pyproject.toml" ]; then
    echo "❌ Error: Must be run from project root"
    exit 1
fi

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    echo "📦 Activating virtual environment..."
    source venv/bin/activate
fi

# Create test output directory
TEST_OUTPUT_DIR="output/hallucination_test_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$TEST_OUTPUT_DIR"

echo "📁 Test output directory: $TEST_OUTPUT_DIR"
echo ""

# Test URL
TEST_URL="https://www.youtube.com/watch?v=kxKk7sBpcYA"

echo "🎬 Starting transcription..."
echo "   URL: $TEST_URL"
echo "   Output: $TEST_OUTPUT_DIR"
echo ""

# Run transcription (you'll need to adapt this to your actual CLI command)
# This is a placeholder - replace with your actual transcription command
echo "⚠️  Note: This is a template script"
echo "    Please update with your actual CLI transcription command"
echo ""
echo "Expected command:"
echo "  python -m knowledge_system.cli transcribe \\"
echo "    --url '$TEST_URL' \\"
echo "    --output '$TEST_OUTPUT_DIR' \\"
echo "    --model large"
echo ""

# After transcription completes, check the logs
echo "=================================================="
echo "After transcription completes, check the logs for:"
echo "=================================================="
echo ""
echo "✅ Expected log entries:"
echo "   🛡️ Hallucination prevention: entropy=2.8, logprob=-0.8, max_len=200, temp=0.0"
echo "   🎯 Using aggressive hallucination prevention for large model"
echo ""
echo "✅ Success indicators:"
echo "   - No or minimal '⚠️ Heavy hallucination detected' warnings"
echo "   - No large blocks of repetitions removed"
echo "   - Full ~4.3 minute video transcribed"
echo ""
echo "❌ Failure indicators:"
echo "   - '⚠️ Heavy hallucination detected: 42 repetitions...' (same as before)"
echo "   - Large time ranges removed (e.g., 172.0s to 258.0s)"
echo ""

echo "=================================================="
echo "Manual Verification Steps"
echo "=================================================="
echo ""
echo "1. Look at the transcript markdown file in: $TEST_OUTPUT_DIR"
echo "2. Check if the video ends properly (should discuss Canada/demographics)"
echo "3. Verify the last ~86 seconds aren't missing"
echo "4. Compare word count with original (should be ~550-650 words)"
echo ""
echo "Original transcript length (with hallucinations cleaned): ~3120 characters"
echo "Expected with prevention: ~4500-5000 characters (no missing content)"
echo ""
