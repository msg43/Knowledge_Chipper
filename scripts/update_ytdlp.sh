#!/bin/bash
# Update yt-dlp to latest version
# YouTube frequently changes its API, requiring yt-dlp updates to keep working

set -e

echo "🔍 Checking yt-dlp version..."

# Get current and latest versions
CURRENT=$(pip show yt-dlp | grep Version | awk '{print $2}')
LATEST=$(pip index versions yt-dlp | grep "LATEST:" | awk '{print $2}')

echo "Current version: $CURRENT"
echo "Latest version:  $LATEST"

if [ "$CURRENT" != "$LATEST" ]; then
    echo ""
    echo "⚠️  yt-dlp is out of date!"
    echo "📦 Updating to version $LATEST..."
    pip install --upgrade yt-dlp
    echo "✅ Update complete!"
else
    echo "✅ yt-dlp is already up to date"
fi
