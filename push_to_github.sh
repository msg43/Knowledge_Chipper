#!/bin/bash
# push_to_github.sh - Setup and push Knowledge_Chipper to GitHub
# Simple script for msg43's Knowledge_Chipper repository

set -e

echo "🚀 Setting up Knowledge_Chipper on GitHub"
echo "==========================================="
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

# Remove old origin if it exists
echo "🔧 Configuring Git remote..."
git remote remove origin 2>/dev/null || true

# Add new origin
git remote add origin https://github.com/msg43/Knowledge_Chipper.git

echo "✅ Git remote configured"

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
        git commit -m "Version bump to $NEW_VERSION and repository updates

- Incremented version from $CURRENT_VERSION to $NEW_VERSION
- Updated all repository references to Knowledge_Chipper
- Updated URLs in README, CONTRIBUTING, pyproject.toml
- Prepared for GitHub push"
    else
        git commit -m "Update repository URLs for GitHub migration

- Updated all repository references to Knowledge_Chipper
- Updated URLs in README, CONTRIBUTING, pyproject.toml
- Prepared for GitHub push"
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
    echo "📍 Your repository is now available at:"
    echo "   https://github.com/msg43/Knowledge_Chipper"
    echo ""
    echo "🔐 Repository is private as requested"
    echo ""
    if [ "$NEW_VERSION" != "unknown" ]; then
        echo "📈 Version successfully incremented to: $NEW_VERSION"
        echo ""
    fi
    echo "📋 Next steps:"
    echo "1. Visit your repository on GitHub to verify everything looks correct"
    echo "2. Update any team members or collaborators in GitHub settings"
    echo "3. Consider setting up branch protection rules in Settings → Branches"
    echo ""
else
    echo "❌ Push cancelled"
    exit 1
fi

# Verify the setup
echo "🧪 Verifying Git configuration..."
echo "Current remote:"
git remote -v
echo ""
echo "Current branch and version:"
git branch -v
if [ "$NEW_VERSION" != "unknown" ]; then
    echo "App version: $NEW_VERSION"
fi
echo ""
echo "✅ Setup complete!"
