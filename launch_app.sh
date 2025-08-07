#!/bin/bash

# Get the directory where this script is located
APP_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

# Activate virtual environment
source "$APP_DIR/venv/bin/activate"

# Set PYTHONPATH to include src directory
export PYTHONPATH="$APP_DIR/src:$PYTHONPATH"

# Launch the GUI
python3 -m knowledge_system.gui.__main__
