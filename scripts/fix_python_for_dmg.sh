#!/bin/bash
# Fix Python dependency issue for Skip the Podcast Desktop
# This script installs Python 3.13 if missing

echo "🐍 Skip the Podcast Desktop - Python Fix"
echo "======================================="
echo ""

APP_PATH="/Applications/Skip the Podcast Desktop.app"

# Check if Python 3.13 is installed
if command -v python3.13 &> /dev/null; then
    echo "✅ Python 3.13 is already installed"
    python3.13 --version
else
    echo "❌ Python 3.13 is not installed"
    echo ""
    echo "Skip the Podcast Desktop requires Python 3.13 to run."
    echo ""

    # Check if Homebrew is installed
    if command -v brew &> /dev/null; then
        echo "🍺 Homebrew detected. Installing Python 3.13..."
        echo ""
        echo "This will run: brew install python@3.13"
        echo ""
        read -p "Continue? (y/N): " -n 1 -r
        echo

        if [[ $REPLY =~ ^[Yy]$ ]]; then
            brew install python@3.13
            echo ""
            echo "✅ Python 3.13 installed!"
        else
            echo "❌ Installation cancelled"
            exit 1
        fi
    else
        echo "📦 Please install Python 3.13 using one of these methods:"
        echo ""
        echo "Option 1: Install Homebrew first, then run this script again"
        echo "   /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
        echo ""
        echo "Option 2: Download Python 3.13 from python.org"
        echo "   https://www.python.org/downloads/"
        echo ""
        exit 1
    fi
fi

# Now fix the app
echo ""
echo "🔧 Fixing Skip the Podcast Desktop..."

# Remove quarantine
sudo xattr -dr com.apple.quarantine "$APP_PATH" 2>/dev/null || true

# Test the app
echo ""
echo "🧪 Testing app launch..."
cd "$APP_PATH/Contents/MacOS"
if ./launch 2>&1 | head -5 | grep -q "Launching GUI"; then
    echo "✅ App is working!"
    echo ""
    echo "🚀 You can now launch Skip the Podcast Desktop!"
else
    echo "❌ App still not working. Please check:"
    echo "   ~/Library/Logs/Skip the Podcast Desktop/knowledge_system.log"
fi
