#!/bin/bash
# push_to_github.sh - Auto-increment version and push Knowledge_Chipper to GitHub
# Automatically increments patch version and pushes to current branch

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

# Auto-increment version in pyproject.toml
echo "📈 Auto-incrementing version..."
if [ -f "pyproject.toml" ]; then
    CURRENT_VERSION=$(grep '^version\s*=\s*"' pyproject.toml | sed -E 's/.*"([^"]+)".*/\1/')
    echo "📋 Current version: $CURRENT_VERSION"
    
    # Parse version components (assuming semantic versioning: major.minor.patch)
    IFS='.' read -r major minor patch <<< "$CURRENT_VERSION"
    
    # Increment patch version
    new_patch=$((patch + 1))
    NEW_VERSION="${major}.${minor}.${new_patch}"
    
    echo "📈 Incrementing version: $CURRENT_VERSION → $NEW_VERSION"
    
    # Update version in pyproject.toml
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        sed -i '' "s/^version\s*=\s*\"[^\"]*\"/version = \"$NEW_VERSION\"/" pyproject.toml
    else
        # Linux
        sed -i "s/^version\s*=\s*\"[^\"]*\"/version = \"$NEW_VERSION\"/" pyproject.toml
    fi
    
    echo "✅ Version updated to $NEW_VERSION in pyproject.toml"
else
    echo "⚠️  Warning: pyproject.toml not found, skipping version increment"
    NEW_VERSION="unknown"
fi

# Stage all changes
echo "📦 Staging all files..."
git add .

# Check if there are changes to commit
if git diff --staged --quiet; then
    echo "ℹ️  No changes to commit"
else
    # Commit with version increment message
    if [ "$NEW_VERSION" != "unknown" ]; then
        git commit -m "Version bump to $NEW_VERSION

- Incremented version from $CURRENT_VERSION to $NEW_VERSION
- Latest code changes and improvements"
    else
        git commit -m "Code updates and improvements

- Latest development changes
- Bug fixes and enhancements"
    fi
    echo "✅ Committed changes with version increment"
fi

# Push to GitHub
echo "🚀 Pushing to GitHub..."
echo "This will push to: https://github.com/msg43/Knowledge_Chipper.git"
echo "Branch: $CURRENT_BRANCH"
if [ "$NEW_VERSION" != "unknown" ]; then
    echo "New version: $NEW_VERSION"
fi
read -p "Continue? (y/N): " -n 1 -r
echo

if [[ $REPLY =~ ^[Yy]$ ]]; then
    # Push to current branch (not forcing main)
    git push -u origin "$CURRENT_BRANCH"

    echo "🎉 Successfully pushed to GitHub!"
    echo ""
    echo "📍 Repository: https://github.com/msg43/Knowledge_Chipper"
    echo "🌿 Branch: $CURRENT_BRANCH"
    if [ "$NEW_VERSION" != "unknown" ]; then
        echo "📈 Version: $NEW_VERSION"
    fi
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
if [ "$NEW_VERSION" != "unknown" ]; then
    echo "Version: $NEW_VERSION"
fi
echo ""
echo "✅ Push complete!"
