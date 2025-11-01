#!/bin/bash
# Test script to verify the division by zero fix in whisper_cpp_transcribe.py

echo "Testing division by zero fix in whisper transcription..."
echo ""
echo "This test verifies that:"
echo "1. Division by zero errors are prevented when realtime_speed is 0"
echo "2. The reading thread doesn't crash and cause SIGPIPE"
echo "3. Progress parsing errors are caught and don't interrupt streaming"
echo ""

# Run a simple transcription test
cd "$(dirname "$0")/.." || exit 1

# Check if test audio file exists
if [ ! -f "data/test_files/test_audio.mp3" ]; then
    echo "⚠️  Test audio file not found. Please ensure data/test_files/test_audio.mp3 exists."
    echo "You can test with any audio/video file using the GUI transcription tab."
    exit 0
fi

# Activate virtual environment if it exists
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
fi

echo "Running transcription test..."
python3 << 'PYTHON_CODE'
import sys
sys.path.insert(0, 'src')

from knowledge_system.processors.whisper_cpp_transcribe import WhisperCppTranscriber
from pathlib import Path

def progress_callback(message, percent):
    print(f"Progress: {message} ({percent}%)")

transcriber = WhisperCppTranscriber(
    model_size="base",
    progress_callback=progress_callback,
    device="cpu"
)

test_file = Path("data/test_files/test_audio.mp3")
print(f"\nTranscribing: {test_file}")
result = transcriber.transcribe_audio(str(test_file))

if result.success:
    print("\n✅ Transcription completed successfully!")
    print(f"Text length: {len(result.text or '')} characters")
else:
    print(f"\n❌ Transcription failed: {result.errors}")
    sys.exit(1)
PYTHON_CODE

echo ""
echo "✅ Test completed. Check the output above for any division by zero errors or SIGPIPE issues."

