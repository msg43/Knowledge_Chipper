#!/bin/zsh

# Set terminal window size to larger dimensions (1400x900)
# Silently ignore errors if Terminal window doesn't exist or is not accessible
osascript -e 'tell application "Terminal" to set bounds of front window to {0, 0, 1400, 900}' 2>/dev/null || true
osascript -e 'tell application "Terminal" to set number of columns of front window to 240' 2>/dev/null || true
osascript -e 'tell application "Terminal" to set number of rows of front window to 50' 2>/dev/null || true

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${(%):-%x}" )" &> /dev/null && pwd )"

echo "Skip the Podcast GUI Launcher"
echo "=============================="
echo "Project directory: $SCRIPT_DIR"

# Change to the project directory
cd "$SCRIPT_DIR"

# Ensure local src/ is importable without requiring editable install
export PYTHONPATH="$SCRIPT_DIR/src:${PYTHONPATH}"

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "❌ Error: Virtual environment not found at $SCRIPT_DIR/venv"
    echo ""
    echo "Please create a virtual environment first:"
    echo "  python3 -m venv venv"
    echo "  source venv/bin/activate"
    echo "  pip install -r requirements.txt"
    echo ""
    read "?Press any key to exit..."
    exit 1
fi

echo "✅ Virtual environment found"

# Check if PyQt6 is installed
if ! ./venv/bin/python -c "import PyQt6" 2>/dev/null; then
    echo "❌ Error: PyQt6 is not installed in the virtual environment"
    echo ""
    echo "Please install it:"
    echo "  source venv/bin/activate"
    echo "  pip install PyQt6"
    echo ""
    read "?Press any key to exit..."
    exit 1
fi

echo "✅ PyQt6 is available"

# Check if knowledge_system module is available (with local src path)
if ! ./venv/bin/python -c "import sys; sys.path.insert(0, 'src'); import knowledge_system" 2>/dev/null; then
    echo "❌ Error: knowledge_system module is not installed"
    echo ""
    echo "Please install the module in development mode:"
    echo "  source venv/bin/activate"
    echo "  pip install -e ."
    echo ""
    read "?Press any key to exit..."
    exit 1
fi

echo "✅ Skip the Podcast module is available"
echo ""
echo "🚀 Launching GUI..."

# Activate virtual environment and launch GUI via the direct GUI entrypoint
source venv/bin/activate
python -m knowledge_system.gui
