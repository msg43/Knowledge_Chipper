#!/bin/bash
# Extract Link Token from Download URL
# 
# This script is called by the PKG postinstall to extract the link_token
# parameter from the download URL and cache it for the daemon to use.
#
# The daemon will then auto-link the device on first run.

set -e

TOKEN_CACHE_DIR="$HOME/.skip_the_podcast"
TOKEN_CACHE_FILE="$TOKEN_CACHE_DIR/link_token_cache.json"
INSTALL_LOG="/tmp/skip_the_podcast_install.log"

echo "[Link Token] Checking for auto-link token..." | tee -a "$INSTALL_LOG"

# Try to extract token from various sources
LINK_TOKEN=""

# 1. Check if token was passed as argument to installer
if [ -n "$1" ]; then
    LINK_TOKEN="$1"
    echo "[Link Token] Token provided via argument" | tee -a "$INSTALL_LOG"
fi

# 2. Check environment variable (set by custom installer wrapper)
if [ -z "$LINK_TOKEN" ] && [ -n "$SKIP_LINK_TOKEN" ]; then
    LINK_TOKEN="$SKIP_LINK_TOKEN"
    echo "[Link Token] Token found in environment" | tee -a "$INSTALL_LOG"
fi

# 3. Check for token file left by download manager
TOKEN_FILE="/tmp/.skip_the_podcast_link_token"
if [ -z "$LINK_TOKEN" ] && [ -f "$TOKEN_FILE" ]; then
    LINK_TOKEN=$(cat "$TOKEN_FILE")
    rm -f "$TOKEN_FILE"  # Clean up
    echo "[Link Token] Token found in temp file" | tee -a "$INSTALL_LOG"
fi

# If we found a token, cache it
if [ -n "$LINK_TOKEN" ]; then
    echo "[Link Token] Caching token for daemon auto-link..." | tee -a "$INSTALL_LOG"
    
    # Create cache directory
    mkdir -p "$TOKEN_CACHE_DIR"
    
    # Write token to cache file (JSON format)
    cat > "$TOKEN_CACHE_FILE" << EOF
{
  "link_token": "$LINK_TOKEN",
  "cached_at": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
  "source": "installer"
}
EOF
    
    # Secure permissions
    chmod 600 "$TOKEN_CACHE_FILE"
    
    echo "[Link Token] ✅ Token cached successfully" | tee -a "$INSTALL_LOG"
    echo "[Link Token] Device will auto-link on daemon first run" | tee -a "$INSTALL_LOG"
else
    echo "[Link Token] No token found - manual device claiming will be required" | tee -a "$INSTALL_LOG"
fi

# Success
exit 0

