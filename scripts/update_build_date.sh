#!/bin/bash
# Script to manually update build dates and sync version info across all relevant files
# Usage: bash scripts/update_build_date.sh [date]
# If no date provided, uses current date

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
VERSION_FILE="src/knowledge_system/version.py"
README_FILE="README.md"

echo "📝 Updating build dates to $BUILD_DATE..."

# Extract version from pyproject.toml (source of truth) and branch from version.py
VERSION_FILE="src/knowledge_system/version.py"

# Get version from pyproject.toml (source of truth)
if [ -f "pyproject.toml" ]; then
    CURRENT_VERSION=$(grep '^version\s*=\s*"' pyproject.toml | sed -E 's/.*"([^"]+)".*/\1/')
    echo "📋 Using version from pyproject.toml: $CURRENT_VERSION"
else
    echo "❌ Error: pyproject.toml not found"
    exit 1
fi

# Get branch from version.py or default to main
if [ -f "$VERSION_FILE" ]; then
    CURRENT_BRANCH=$(grep 'BRANCH = ' "$VERSION_FILE" | sed 's/BRANCH = "\(.*\)"/\1/')
    echo "📋 Found branch: $CURRENT_BRANCH"
else
    CURRENT_BRANCH="main"
    echo "📋 Using default branch: $CURRENT_BRANCH"
fi

# Update version.py to match pyproject.toml
cat > "$VERSION_FILE" << EOF
# Auto-generated version info
VERSION = "$CURRENT_VERSION"
BRANCH = "$CURRENT_BRANCH"
BUILD_DATE = "$BUILD_DATE"
EOF

echo "✅ Updated $VERSION_FILE (synced with pyproject.toml)"

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
    git status --porcelain "$VERSION_FILE" "$README_FILE"
fi
