#!/usr/bin/env python3
"""
Fix launch_gui.command for zsh compatibility.
Replace BASH_SOURCE with zsh-compatible variable.
Replace read -p with zsh-compatible read.
"""

from pathlib import Path

launch_script = Path("launch_gui.command")
content = launch_script.read_text()

# Fix 1: Replace BASH_SOURCE with zsh equivalent
content = content.replace(
    'SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"',
    'SCRIPT_DIR="$( cd "$( dirname "${(%):-%x}" )" &> /dev/null && pwd )"',
)

# Fix 2: Replace read -p with zsh-compatible version
content = content.replace(
    'read -p "Press any key to exit..."', 'read "?Press any key to exit..."'
)

launch_script.write_text(content)

print("✅ Fixed launch_gui.command for zsh compatibility")
print("   - Replaced BASH_SOURCE with ${(%):-%x}")
print("   - Replaced read -p with read ?")
