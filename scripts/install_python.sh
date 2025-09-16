#!/bin/bash
# Install Python 3.13 for Skip the Podcast Desktop

echo "================================"
echo "Installing Python 3.13"
echo "================================"
echo ""

# Check if Homebrew is installed
if ! command -v brew &> /dev/null; then
    echo "📦 Installing Homebrew first..."
    echo "This is the package manager for macOS."
    echo ""
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

    # Add Homebrew to PATH
    if [ -f "/opt/homebrew/bin/brew" ]; then
        eval "$(/opt/homebrew/bin/brew shellenv)"
    fi
fi

echo ""
echo "🐍 Installing Python 3.13..."
brew install python@3.13

echo ""
echo "✅ Installation complete!"
echo ""
echo "Press any key to close this window..."
read -n 1
