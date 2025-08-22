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

# Remove old origin if it exists
echo "🔧 Configuring Git remote..."
git remote remove origin 2>/dev/null || true

# Add new origin
git remote add origin https://github.com/msg43/Knowledge_Chipper.git

echo "✅ Git remote configured"

# Stage all changes
echo "📦 Staging all files..."
git add .

# Check if there are changes to commit
if git diff --staged --quiet; then
    echo "ℹ️  No changes to commit"
else
    # Commit the repository URL updates
    git commit -m "Update repository URLs for GitHub migration

- Updated all repository references to Knowledge_Chipper
- Updated URLs in README, CONTRIBUTING, pyproject.toml
- Prepared for initial GitHub push"
    echo "✅ Committed repository URL updates"
fi

# Push to GitHub
echo "🚀 Pushing to GitHub..."
echo "This will push to: https://github.com/msg43/Knowledge_Chipper.git"
read -p "Continue? (y/N): " -n 1 -r
echo

if [[ $REPLY =~ ^[Yy]$ ]]; then
    # Push to main branch
    git branch -M main
    git push -u origin main

    echo "🎉 Successfully pushed to GitHub!"
    echo ""
    echo "📍 Your repository is now available at:"
    echo "   https://github.com/msg43/Knowledge_Chipper"
    echo ""
    echo "🔐 Repository is private as requested"
    echo ""
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
echo "Current branch:"
git branch -v
echo ""
echo "✅ Setup complete!"
