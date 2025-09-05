#!/bin/bash
# push_to_github.sh - Push Knowledge_Chipper to GitHub
# Pushes current changes to GitHub without auto-incrementing version

set -e

echo "🚀 Pushing Knowledge_Chipper to GitHub"
echo "======================================"
echo "Repository: https://github.com/msg43/Knowledge_Chipper"
echo

# Check if we're in a git repository
if [ ! -d ".git" ]; then
    echo "❌ Not a git repository. Please run this from the Knowledge_Chipper directory."
    exit 1
fi

# Get current branch
CURRENT_BRANCH=$(git branch --show-current 2>/dev/null || echo "main")
echo "📋 Current branch: $CURRENT_BRANCH"

# Ensure correct remote is configured
echo "🔧 Checking Git remote..."
if ! git remote get-url origin >/dev/null 2>&1; then
    echo "📝 Adding GitHub remote..."
    git remote add origin https://github.com/msg43/Knowledge_Chipper.git
elif [ "$(git remote get-url origin)" != "https://github.com/msg43/Knowledge_Chipper.git" ]; then
    echo "📝 Updating GitHub remote URL..."
    git remote set-url origin https://github.com/msg43/Knowledge_Chipper.git
else
    echo "✅ GitHub remote already configured correctly"
fi

# Get current version for display (no auto-increment)
if [ -f "pyproject.toml" ]; then
    CURRENT_VERSION=$(grep '^version\s*=\s*"' pyproject.toml | sed -E 's/.*"([^"]+)".*/\1/')
    echo "📋 Current version: $CURRENT_VERSION"
else
    CURRENT_VERSION="unknown"
fi

# Stage all changes
echo "📦 Staging all files..."
git add .

# Check if there are changes to commit
if git diff --staged --quiet; then
    echo "ℹ️  No changes to commit"
else
    # Commit with descriptive message
    git commit -m "Code updates and improvements

- Latest development changes
- Bug fixes and enhancements"
    echo "✅ Committed changes"
fi

# Push to GitHub
echo "🚀 Pushing to GitHub..."
echo "This will push to: https://github.com/msg43/Knowledge_Chipper.git"
echo "Branch: $CURRENT_BRANCH"
echo "Current version: $CURRENT_VERSION"
read -p "Continue? (y/N): " -n 1 -r
echo

if [[ $REPLY =~ ^[Yy]$ ]]; then
    # Push to current branch (not forcing main)
    git push -u origin "$CURRENT_BRANCH"

    echo "🎉 Successfully pushed to GitHub!"
    echo ""
    echo "📍 Repository: https://github.com/msg43/Knowledge_Chipper"
    echo "🌿 Branch: $CURRENT_BRANCH"
    echo "📋 Version: $CURRENT_VERSION"
    echo ""
    echo "✨ Changes are now live on GitHub!"
    echo ""
else
    echo "❌ Push cancelled"
    exit 1
fi

# Verify the push
echo "🔍 Verifying push status..."
echo "Remote: $(git remote get-url origin)"
echo "Branch: $(git branch --show-current) ($(git log --oneline -1 | cut -d' ' -f1))"
echo "Version: $CURRENT_VERSION"
echo ""
echo "✅ Push complete!"
