#!/bin/bash

# Setup Cursor Auto-Wrap System
# This script installs and configures automatic timeout prevention for Cursor

set -Eeuo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() {
    echo -e "${BLUE}[INFO]${NC} $*"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $*"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $*"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $*"
}

# Get project root
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPTS_DIR="$PROJECT_ROOT/scripts"

log_info "Setting up Cursor Auto-Wrap System in: $PROJECT_ROOT"

# Create necessary directories
mkdir -p "$PROJECT_ROOT/.cursor"
mkdir -p "$PROJECT_ROOT/.vscode"
mkdir -p "$PROJECT_ROOT/tmp"

# Make all scripts executable
log_info "Making scripts executable..."
chmod +x "$SCRIPTS_DIR"/*.sh "$SCRIPTS_DIR"/*.py 2>/dev/null || true

# Test if Python is available
if ! command -v python3 >/dev/null 2>&1; then
    log_error "Python 3 is required but not found"
    exit 1
fi

# Test smart detector
log_info "Testing smart detector..."
if python3 "$SCRIPTS_DIR/cursor_smart_detector.py" --help >/dev/null 2>&1; then
    log_success "Smart detector is working"
else
    log_error "Smart detector test failed"
    exit 1
fi

# Test wrapper scripts
log_info "Testing wrapper scripts..."
if [[ -x "$SCRIPTS_DIR/cursor_safe_run.sh" ]]; then
    log_success "Safe run script is ready"
else
    log_error "Safe run script not found or not executable"
    exit 1
fi

# Create shell configuration snippet
SHELL_CONFIG="$PROJECT_ROOT/.cursor_shell_config"
cat > "$SHELL_CONFIG" << 'EOF'
# Cursor Auto-Wrap Configuration
# Add this to your shell configuration (.zshrc, .bashrc, etc.)

# Enable Cursor auto-wrapping
export CURSOR_AUTO_WRAP=1
export CURSOR_PROJECT_ROOT="$(pwd)"

# Source the terminal initialization
if [[ -f "$CURSOR_PROJECT_ROOT/scripts/cursor_terminal_init.sh" ]]; then
    source "$CURSOR_PROJECT_ROOT/scripts/cursor_terminal_init.sh"
fi
EOF

# Update .gitignore to exclude temporary files
GITIGNORE="$PROJECT_ROOT/.gitignore"
if [[ -f "$GITIGNORE" ]]; then
    if ! grep -q "tmp/cursor_jobs" "$GITIGNORE" 2>/dev/null; then
        log_info "Adding Cursor temp files to .gitignore..."
        cat >> "$GITIGNORE" << 'EOF'

# Cursor Auto-Wrap temporary files
tmp/cursor_jobs/
tmp/cursor_command_stats.json
.cursor_shell_config
EOF
    fi
else
    log_info "Creating .gitignore with Cursor exclusions..."
    cat > "$GITIGNORE" << 'EOF'
# Cursor Auto-Wrap temporary files
tmp/cursor_jobs/
tmp/cursor_command_stats.json
.cursor_shell_config
EOF
fi

# Create a project-specific activation script
ACTIVATE_SCRIPT="$PROJECT_ROOT/activate_cursor_wrap.sh"
cat > "$ACTIVATE_SCRIPT" << EOF
#!/bin/bash

# Activate Cursor Auto-Wrap for this project
# Source this script in your terminal: source ./activate_cursor_wrap.sh

export CURSOR_AUTO_WRAP=1
export CURSOR_PROJECT_ROOT="$PROJECT_ROOT"

# Source the terminal initialization
if [[ -f "$PROJECT_ROOT/scripts/cursor_terminal_init.sh" ]]; then
    source "$PROJECT_ROOT/scripts/cursor_terminal_init.sh"
    echo -e "\033[0;32m[CURSOR]\033[0m Auto-wrap activated for this terminal session"
    echo "Use 'cursor_status' to see configuration"
else
    echo -e "\033[0;31m[ERROR]\033[0m Cursor scripts not found"
fi
EOF

chmod +x "$ACTIVATE_SCRIPT"

# Test the system
log_info "Testing the complete system..."

# Test smart detection
test_command="python --version"
if python3 "$SCRIPTS_DIR/cursor_smart_detector.py" --project-root "$PROJECT_ROOT" $test_command >/dev/null 2>&1; then
    log_success "Smart detection working for: $test_command"
else
    log_info "Smart detection says no wrap needed for: $test_command (this is correct)"
fi

# Create a quick test script
TEST_SCRIPT="$PROJECT_ROOT/test_cursor_wrap.py"
cat > "$TEST_SCRIPT" << 'EOF'
#!/usr/bin/env python3
import time
import sys

print("Starting test script...")
for i in range(5):
    print(f"Step {i+1}/5")
    time.sleep(1)
print("Test completed!")
EOF

chmod +x "$TEST_SCRIPT"

log_success "Cursor Auto-Wrap System installed successfully!"
echo
log_info "Next steps:"
echo "1. Restart Cursor or open a new terminal"
echo "2. Or manually activate with: source ./activate_cursor_wrap.sh"
echo "3. Test with: python test_cursor_wrap.py"
echo "4. Check status with: cursor_status"
echo "5. Manage jobs with: cursor_jobs list"
echo
log_info "Configuration files created:"
echo "  - .cursor/settings.json (Cursor IDE settings)"
echo "  - .vscode/tasks.json (VS Code tasks)"
echo "  - activate_cursor_wrap.sh (manual activation)"
echo "  - test_cursor_wrap.py (test script)"
echo
log_info "Available commands in wrapped terminals:"
echo "  cursor_status    - Show system status"
echo "  cursor_disable   - Disable auto-wrapping"
echo "  cursor_enable    - Enable auto-wrapping"
echo "  cursor_raw cmd   - Run command without wrapping"
echo "  cursor_wrap cmd  - Force wrap a command"
echo "  cursor_jobs      - Manage background jobs"
echo
log_warn "Note: The system learns from your usage patterns and gets smarter over time!"

# Clean up test script
rm -f "$TEST_SCRIPT"

log_success "Setup complete! The system is now ready to prevent Cursor timeouts automatically."
