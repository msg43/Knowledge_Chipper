#!/bin/bash

# Get the directory where this script is located
APP_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

# Change to the project directory
cd "$APP_DIR"

# Ensure local src/ is importable without requiring editable install
export PYTHONPATH="$APP_DIR/src:${PYTHONPATH}"

# Activate virtual environment
source "$APP_DIR/venv/bin/activate"

# Launch the GUI via the direct entrypoint to avoid CLI side-effects
python -m knowledge_system.gui
