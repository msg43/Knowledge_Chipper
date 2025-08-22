#!/bin/bash

# Get the directory where this script is located
APP_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

# Change to the project directory
cd "$APP_DIR"

# Activate virtual environment
source "$APP_DIR/venv/bin/activate"

# Launch the GUI with the correct command
python -m knowledge_system gui
