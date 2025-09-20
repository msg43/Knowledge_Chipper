#!/bin/bash
# Auto-install Python 3.13 if missing for Skip the Podcast Desktop

APP_NAME="Skip the Podcast Desktop"
PYTHON_VERSION="3.13"

# Function to check if Python 3.13+ is available
check_python() {
    # Check common locations
    for py in "/opt/homebrew/bin/python3.13" \
              "/usr/local/bin/python3.13" \
              "/Library/Frameworks/Python.framework/Versions/3.13/bin/python3"; do
        if [ -x "$py" ]; then
            echo "$py"
            return 0
        fi
    done

    # Check PATH
    if command -v python3.13 &> /dev/null; then
        echo "$(command -v python3.13)"
        return 0
    fi

    return 1
}

# Check if Python is already installed
if PYTHON_BIN=$(check_python); then
    echo "$PYTHON_BIN"
    exit 0
fi

# Python not found - need to install
echo "Python $PYTHON_VERSION not found. Installing..." >&2

# Check if running in GUI context and if auto-installation is feasible
if [ -n "$DISPLAY" ] || [ -n "$SSH_CONNECTION" ] || [ -t 0 ]; then
    # Check for potential blockers first
    CAN_INSTALL=1
    INSTALL_ISSUES=""

    # Check network connectivity
    if ! curl -s --max-time 5 https://www.google.com > /dev/null 2>&1; then
        CAN_INSTALL=0
        INSTALL_ISSUES="• No internet connection detected\n"
    fi

    # Check if we can write to common install locations (indicates admin access)
    if [ ! -w "/opt/" ] && [ ! -w "/usr/local/" ] && [ ! -w "$HOME" ]; then
        CAN_INSTALL=0
        INSTALL_ISSUES="${INSTALL_ISSUES}• Admin privileges may be required\n"
    fi

    # Check if corporate firewall might block Homebrew
    if ! curl -s --max-time 5 https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh > /dev/null 2>&1; then
        CAN_INSTALL=0
        INSTALL_ISSUES="${INSTALL_ISSUES}• Corporate firewall may block installation\n"
    fi

    if [ "$CAN_INSTALL" -eq 0 ]; then
        # Show dialog explaining why auto-installation won't work
        osascript -e "display dialog \"Python $PYTHON_VERSION auto-installation not possible:

$INSTALL_ISSUES
Recommended solutions:
1. Download Python from python.org (most reliable)
2. Contact IT support for installation
3. Use company software center if available\" buttons {\"Open python.org\", \"OK\"} default button \"Open python.org\" with title \"Manual Installation Required\" with icon caution"

        if [ $? -eq 0 ]; then
            # User clicked "Open python.org"
            open "https://www.python.org/downloads/"
        fi
        exit 1
    fi

    # Show installation dialog with warnings
    RESULT=$(osascript -e "
    try
        set dialogResult to display dialog \"$APP_NAME requires Python $PYTHON_VERSION to run.

Auto-installation will:
1. Install Homebrew (if needed) - requires admin password
2. Install Python $PYTHON_VERSION via Homebrew
3. May take 5-10 minutes depending on connection

Note: This requires internet access and admin privileges.\" buttons {\"Cancel\", \"Manual Install\", \"Auto Install\"} default button \"Auto Install\" with title \"Python $PYTHON_VERSION Required\" with icon caution

        if button returned of dialogResult is \"Auto Install\" then
            return \"install\"
        else if button returned of dialogResult is \"Manual Install\" then
            return \"manual\"
        else
            return \"cancel\"
        end if
    on error
        return \"cancel\"
    end try
    ")

    if [ "$RESULT" = "manual" ]; then
        open "https://www.python.org/downloads/"
        echo "Manual installation requested - opened python.org" >&2
        exit 1
    elif [ "$RESULT" != "install" ]; then
        echo "Installation cancelled by user" >&2
        exit 1
    fi

    # Show progress notification
    osascript -e "display notification \"Installing Python $PYTHON_VERSION...\" with title \"$APP_NAME\" subtitle \"This may take several minutes\""
fi

# Create a temporary script for installation
INSTALL_SCRIPT="/tmp/install_python_for_skip_podcast.sh"
cat > "$INSTALL_SCRIPT" << 'EOF'
#!/bin/bash
set -e

echo "Installing Python 3.13..."

# Check if Homebrew is installed
if ! command -v brew &> /dev/null; then
    echo "Installing Homebrew..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

    # Add Homebrew to PATH for this session
    if [ -f "/opt/homebrew/bin/brew" ]; then
        eval "$(/opt/homebrew/bin/brew shellenv)"
    elif [ -f "/usr/local/bin/brew" ]; then
        eval "$(/usr/local/bin/brew shellenv)"
    fi
fi

# Install Python 3.13
echo "Installing Python 3.13..."
brew install python@3.13

# Verify installation
if command -v python3.13 &> /dev/null; then
    echo "✅ Python 3.13 installed successfully!"
    exit 0
else
    echo "❌ Python installation failed"
    exit 1
fi
EOF

chmod +x "$INSTALL_SCRIPT"

# Run installation in Terminal
if [ -n "$DISPLAY" ] || [ -n "$SSH_CONNECTION" ]; then
    # Open Terminal and run the installation
    osascript -e "
    tell application \"Terminal\"
        activate
        set newTab to do script \"bash $INSTALL_SCRIPT && echo 'Press any key to close this window' && read -n 1 && exit\"
        repeat
            delay 1
            if not busy of newTab then exit repeat
        end repeat
    end tell
    "

    # Wait a moment for Terminal to finish
    sleep 2

    # Check if installation succeeded
    if PYTHON_BIN=$(check_python); then
        osascript -e "display notification \"Python $PYTHON_VERSION installed successfully!\" with title \"$APP_NAME\" subtitle \"You can now use the app\""
        echo "$PYTHON_BIN"
        exit 0
    else
        osascript -e "display dialog \"Python installation failed. Please try installing manually:

1. Open Terminal
2. Run: brew install python@3.13\" buttons {\"OK\"} default button \"OK\" with title \"Installation Failed\" with icon stop"
        exit 1
    fi
else
    # Non-GUI context - just try to install
    bash "$INSTALL_SCRIPT"
    if PYTHON_BIN=$(check_python); then
        echo "$PYTHON_BIN"
        exit 0
    else
        exit 1
    fi
fi
