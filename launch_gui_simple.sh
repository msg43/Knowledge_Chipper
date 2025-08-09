#!/bin/bash

# Simple GUI launcher for Knowledge System
# Navigate to the script directory
cd "$(dirname "$0")"

# Activate virtual environment and launch
source venv/bin/activate
python -m knowledge_system gui
