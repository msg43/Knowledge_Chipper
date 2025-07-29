#!/bin/bash

# This script will recreate the venv using Python 3.13 and reinstall all dependencies
# Usage: bash reset_venv_py313.sh

set -e

# Check for python3.13
if ! command -v python3.13 &> /dev/null; then
    echo "Python 3.13 is not installed. Please install it first (e.g., brew install python@3.13)"
    exit 1
fi

# Remove old venv if it exists
if [ -d "venv" ]; then
    echo "Removing existing venv..."
    rm -rf venv
fi

# Create new venv with Python 3.13
python3.13 -m venv venv

# Activate venv
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install project dependencies (including dev)
pip install -e ".[dev]"

# Show Python version and pip list
python --version
pip list

echo "\n✅ venv reset complete. You are now using Python 3.13 with all dependencies installed." 