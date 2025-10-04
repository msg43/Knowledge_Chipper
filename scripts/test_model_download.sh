#!/bin/bash
# Test model download notifications

set -e

echo "🧪 Model Download Test Script"
echo "============================"
echo
echo "This script helps test the model download notifications by:"
echo "1. Temporarily hiding existing models"
echo "2. Launching the app to trigger downloads"
echo "3. Restoring models after testing"
echo

# Check current models
echo "📦 Current Whisper models:"
ls -la ~/.cache/whisper-cpp/*.bin 2>/dev/null || echo "   No models found"
echo

echo "🤖 Current Ollama models:"
ollama list 2>/dev/null || echo "   Ollama not running or no models"
echo

# Prompt for action
echo "Choose an action:"
echo "  h - Hide models (to test downloads)"
echo "  r - Restore hidden models"
echo "  t - Test with missing tiny model"
echo "  q - Quit"
echo
read -p "Action: " action

case $action in
    h)
        echo "📦 Hiding existing models..."
        # Backup Whisper models
        if [ -d ~/.cache/whisper-cpp ]; then
            mv ~/.cache/whisper-cpp ~/.cache/whisper-cpp-backup
            mkdir -p ~/.cache/whisper-cpp
            echo "✅ Whisper models hidden"
        fi

        echo
        echo "🚀 Models hidden! Now:"
        echo "1. Run: ./launch_gui.command"
        echo "2. Watch for download notifications at the top of the window"
        echo "3. Or try to transcribe a file to trigger the notification"
        echo
        echo "⚠️  Run '$0 r' to restore models after testing"
        ;;

    r)
        echo "📦 Restoring hidden models..."
        # Restore Whisper models
        if [ -d ~/.cache/whisper-cpp-backup ]; then
            rm -rf ~/.cache/whisper-cpp
            mv ~/.cache/whisper-cpp-backup ~/.cache/whisper-cpp
            echo "✅ Whisper models restored"
        else
            echo "⚠️  No backup found"
        fi
        ;;

    t)
        echo "📦 Removing only tiny model to test partial downloads..."
        rm -f ~/.cache/whisper-cpp/ggml-tiny.bin
        echo "✅ Tiny model removed"
        echo
        echo "The app will still work with base/small/medium models"
        echo "But you can test downloading tiny if you select it"
        ;;

    q)
        echo "👋 Exiting..."
        exit 0
        ;;

    *)
        echo "❌ Invalid option"
        exit 1
        ;;
esac
