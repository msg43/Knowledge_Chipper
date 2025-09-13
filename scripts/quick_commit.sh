#!/bin/bash
# Quick commit with auto-fix - simplified version
# Usage: ./scripts/quick_commit.sh "commit message"

set -e

# Get commit message
if [ $# -eq 0 ]; then
    echo "💬 Enter commit message:"
    read -r MSG
else
    MSG="$*"
fi

echo "🔧 Auto-fixing and committing..."

# Stage all changes
git add .

# Try to commit - if it fails due to auto-fixes, stage and try again
if ! git commit -m "$MSG"; then
    echo "🔄 Auto-fixes applied, re-committing..."
    git add .
    git commit -m "$MSG"
fi

echo "✅ Commit successful!"

# Ask about push
echo -n "🚀 Push to GitHub? (y/N): "
read -r -n 1 REPLY
echo

if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "📤 Pushing..."
    git push origin main
    echo "✅ Pushed!"
fi
