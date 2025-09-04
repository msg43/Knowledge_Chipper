#!/usr/bin/env bash
set -euo pipefail

# GUI Comprehensive Testing Runner
# This script demonstrates how to run GUI tests with different configurations

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo "GUI Comprehensive Testing Runner"
echo "================================"
echo "Project root: $PROJECT_ROOT"
echo "Script directory: $SCRIPT_DIR"
echo ""

# Change to project root for proper Python path resolution
cd "$PROJECT_ROOT"

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "❌ Error: Virtual environment not found at $PROJECT_ROOT/venv"
    echo "Please create and set up a virtual environment first"
    exit 1
fi

echo "✅ Virtual environment found"

# Check if test data exists
if [ ! -d "tests/fixtures/sample_files/audio" ]; then
    echo "⚠️  Test data not found. Setting up test data first..."
    cd "$SCRIPT_DIR"
    python3 main_test_runner.py setup
    cd "$PROJECT_ROOT"
    echo "✅ Test data setup complete"
else
    echo "✅ Test data found"
fi

echo ""
echo "Available test modes:"
echo ""
echo "1. Smoke tests (5-10 minutes) - Quick validation"
echo "2. Comprehensive tests (1-2 hours) - Full coverage"
echo "3. Stress tests (2+ hours) - Large file testing"
echo "4. Custom mode"
echo ""

# Get user choice
read -p "Select test mode (1-4): " choice

case $choice in
    1)
        echo "Running smoke tests..."
        MODE="smoke"
        ;;
    2)
        echo "Running comprehensive tests..."
        MODE="comprehensive"
        ;;
    3)
        echo "Running stress tests..."
        MODE="stress"
        ;;
    4)
        read -p "Enter custom mode (smoke/basic/comprehensive/stress/all): " MODE
        ;;
    *)
        echo "Invalid choice. Using smoke tests."
        MODE="smoke"
        ;;
esac

echo ""
echo "GUI Launch Options:"
echo "1. Auto-launch GUI (recommended)"
echo "2. Use existing GUI (assume GUI is already running)"
echo ""

read -p "Select GUI option (1-2): " gui_choice

GUI_ARGS=""
case $gui_choice in
    2)
        echo "Will use existing GUI instance"
        GUI_ARGS="--no-gui-launch"
        ;;
    *)
        echo "Will auto-launch GUI"
        ;;
esac

echo ""
echo "🚀 Starting GUI comprehensive tests..."
echo "Mode: $MODE"
echo "GUI Args: $GUI_ARGS"
echo ""

# Activate virtual environment and run tests
source venv/bin/activate

# Set Python path to include src directory
export PYTHONPATH="$PROJECT_ROOT/src:${PYTHONPATH:-}"

# Run the tests using venv Python directly (bypasses pyenv issues)
cd "$SCRIPT_DIR"
"$PROJECT_ROOT/venv/bin/python3" main_test_runner.py $MODE $GUI_ARGS --verbose

echo ""
echo "🎉 Testing completed!"
echo "Check the output directory for detailed results: tests/reports/"
