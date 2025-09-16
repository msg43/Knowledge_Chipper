#!/bin/bash
# Create a universal Python launcher for the app

cat > "$1" << 'EOF'
#!/bin/bash
# Universal Python Launcher for Skip the Podcast Desktop
# This finds and uses the best available Python 3.13+

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
APP_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"

# Function to check Python version
check_python_version() {
    local py_bin="$1"
    if [ -x "$py_bin" ]; then
        version=$("$py_bin" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null)
        if [[ "$version" == "3.13" ]] || [[ "$version" == "3.14" ]]; then
            echo "$py_bin"
            return 0
        fi
    fi
    return 1
}

# Try to find Python 3.13+
PYTHON_BIN=""

# Check common locations
for py in "/opt/homebrew/bin/python3.13" \
          "/usr/local/bin/python3.13" \
          "/Library/Frameworks/Python.framework/Versions/3.13/bin/python3" \
          "/opt/homebrew/bin/python3" \
          "/usr/local/bin/python3" \
          "/usr/bin/python3"; do
    if result=$(check_python_version "$py"); then
        PYTHON_BIN="$result"
        break
    fi
done

# If not found, try PATH
if [ -z "$PYTHON_BIN" ]; then
    if command -v python3.13 &> /dev/null; then
        PYTHON_BIN=$(command -v python3.13)
    elif command -v python3 &> /dev/null; then
        if result=$(check_python_version "$(command -v python3)"); then
            PYTHON_BIN="$result"
        fi
    fi
fi

# If still not found, try auto-installation
if [ -z "$PYTHON_BIN" ]; then
    # Get the auto-installer path
    AUTO_INSTALLER="$APP_DIR/bin/python_auto_installer.sh"

    if [ -f "$AUTO_INSTALLER" ]; then
        # Run auto-installer with verbose logging for debugging
        echo "Attempting Python auto-installation..." >&2
        if PYTHON_BIN=$("$AUTO_INSTALLER" 2>&1); then
            # Installation succeeded
            echo "Python installed: $PYTHON_BIN" >&2
        else
            # Installation failed - show detailed error
            echo "Python auto-installation failed" >&2
            osascript -e 'display dialog "Python 3.13 installation failed.\n\nPossible causes:\n• Network restrictions\n• Admin privileges required\n• Corporate firewall blocking downloads\n\nPlease contact IT support or install manually:\n1. Download Python 3.13 from python.org\n2. Or use: brew install python@3.13" buttons {"OK"} default button 1 with title "Python Installation Failed" with icon stop'
            exit 1
        fi
    else
        # Fallback to enhanced error dialog with more options
        osascript -e 'display dialog "Skip the Podcast Desktop requires Python 3.13 or later.\n\nInstallation Options:\n\nOption 1 (Recommended):\n  Download from python.org/downloads\n\nOption 2 (Advanced):\n  1. Install Homebrew: brew.sh\n  2. Run: brew install python@3.13\n\nOption 3 (Corporate):\n  Contact IT support for Python installation" buttons {"Open python.org", "OK"} default button 1 with title "Python 3.13 Required" with icon caution'
        if [ $? -eq 0 ]; then
            # User clicked "Open python.org"
            open "https://www.python.org/downloads/"
        fi
        exit 1
    fi
fi

# Set up environment
export PYTHONPATH="$APP_DIR/src:$APP_DIR/venv/lib/python3.13/site-packages:$PYTHONPATH"
export PYTHONHOME=""
export VIRTUAL_ENV="$APP_DIR/venv"
export PATH="$APP_DIR/venv/bin:$PATH"

# Execute with all arguments
exec "$PYTHON_BIN" "$@"
EOF

chmod +x "$1"
