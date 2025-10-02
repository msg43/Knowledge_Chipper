#!/bin/bash

# Activate Cursor Auto-Wrap for this project
# Source this script in your terminal: source ./activate_cursor_wrap.sh

export CURSOR_AUTO_WRAP=1
export CURSOR_PROJECT_ROOT="/Users/matthewgreer/Projects/Knowledge_Chipper"

# Source the terminal initialization
if [[ -f "/Users/matthewgreer/Projects/Knowledge_Chipper/scripts/cursor_terminal_init.sh" ]]; then
    source "/Users/matthewgreer/Projects/Knowledge_Chipper/scripts/cursor_terminal_init.sh"
    echo -e "\033[0;32m[CURSOR]\033[0m Auto-wrap activated for this terminal session"
    echo "Use 'cursor_status' to see configuration"
else
    echo -e "\033[0;31m[ERROR]\033[0m Cursor scripts not found"
fi
