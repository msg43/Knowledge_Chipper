#!/bin/bash
# Script to manually update build dates and sync version info across all relevant files
# Usage: bash scripts/update_build_date.sh [date]
# If no date provided, uses current date
# Note: Since version.py was eliminated, this script now only updates README.md

# Get date (use provided date or current date)
if [ -n "$1" ]; then
    BUILD_DATE="$1"
    echo "🕐 Using provided date: $BUILD_DATE"
else
    BUILD_DATE=$(date +"%Y-%m-%d")
    echo "🕐 Using current date: $BUILD_DATE"
fi

# Validate date format (YYYY-MM-DD)
if [[ ! $BUILD_DATE =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]]; then
    echo "❌ Error: Date must be in YYYY-MM-DD format"
    exit 1
fi

# Files to update
README_FILE="README.md"

echo "📝 Updating build dates to $BUILD_DATE..."

# Get version from pyproject.toml (source of truth)
if [ -f "pyproject.toml" ]; then
    CURRENT_VERSION=$(grep '^version\s*=\s*"' pyproject.toml | sed -E 's/.*"([^"]+)".*/\1/')
    echo "📋 Using version from pyproject.toml: $CURRENT_VERSION"
else
    echo "❌ Error: pyproject.toml not found"
    exit 1
fi

# Use current git branch
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "main")
echo "📋 Using current git branch: $CURRENT_BRANCH"

echo "✅ Version info: $CURRENT_VERSION on $CURRENT_BRANCH (no version.py needed)"

# Update README.md with version, build date, and branch
if [ -f "$README_FILE" ]; then
    # Update the entire version header line in README.md
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        sed -i '' "s/\*\*Version:\*\* [^|]* | \*\*Build Date:\*\* [0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9] | \*\*Branch:\*\* .*/\*\*Version:\*\* $CURRENT_VERSION | \*\*Build Date:\*\* $BUILD_DATE | \*\*Branch:\*\* $CURRENT_BRANCH/" "$README_FILE"
    else
        # Linux
        sed -i "s/\*\*Version:\*\* [^|]* | \*\*Build Date:\*\* [0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9] | \*\*Branch:\*\* .*/\*\*Version:\*\* $CURRENT_VERSION | \*\*Build Date:\*\* $BUILD_DATE | \*\*Branch:\*\* $CURRENT_BRANCH/" "$README_FILE"
    fi
    echo "✅ Updated $README_FILE (version: $CURRENT_VERSION, date: $BUILD_DATE, branch: $CURRENT_BRANCH)"
else
    echo "⚠️  Warning: $README_FILE not found"
fi

echo "🎉 Build date update complete!"

# Show git status if we're in a git repo
if [ -d ".git" ]; then
    echo ""
    echo "📊 Git status:"
    git status --porcelain "$README_FILE"
fi
