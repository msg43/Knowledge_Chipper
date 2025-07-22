#!/bin/bash

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

echo "Knowledge System GUI Launcher"
echo "============================="
echo "Project directory: $SCRIPT_DIR"

# Change to the project directory
cd "$SCRIPT_DIR"

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "❌ Error: Virtual environment not found at $SCRIPT_DIR/venv"
    echo ""
    echo "Please create a virtual environment first:"
    echo "  python3 -m venv venv"
    echo "  source venv/bin/activate"
    echo "  pip install -r requirements.txt"
    echo ""
    read -p "Press any key to exit..."
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
    read -p "Press any key to exit..."
    exit 1
fi

echo "✅ PyQt6 is available"

# Check if knowledge_system module is available
if ! ./venv/bin/python -c "import knowledge_system" 2>/dev/null; then
    echo "❌ Error: knowledge_system module is not installed"
    echo ""
    echo "Please install the module in development mode:"
    echo "  source venv/bin/activate"
    echo "  pip install -e ."
    echo ""
    read -p "Press any key to exit..."
    exit 1
fi

echo "✅ Knowledge System module is available"
echo ""
echo "🚀 Launching GUI..."

# Activate virtual environment and launch GUI
source venv/bin/activate
python -m knowledge_system gui 