#!/usr/bin/env python3
"""
Launch script for the new Layer Cake GUI.

Quick way to test the new interface.
"""

import sys
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

# Launch the layer cake GUI
from knowledge_system.gui.layer_cake_main_window import main

if __name__ == '__main__':
    main()

