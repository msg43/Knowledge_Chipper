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

# Extract version and branch from version.py
VERSION_FILE="src/knowledge_system/version.py"
if [ -f "$VERSION_FILE" ]; then
    CURRENT_VERSION=$(grep 'VERSION = ' "$VERSION_FILE" | sed 's/VERSION = "\(.*\)"/\1/')
    CURRENT_BRANCH=$(grep 'BRANCH = ' "$VERSION_FILE" | sed 's/BRANCH = "\(.*\)"/\1/')
    echo "📋 Found version: $CURRENT_VERSION, branch: $CURRENT_BRANCH"
else
    echo "❌ Error: $VERSION_FILE not found"
    exit 1
fi

# Update version.py
if [ -f "$VERSION_FILE" ]; then
    # Use sed to replace the BUILD_DATE line
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        sed -i '' "s/BUILD_DATE = \"[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]\"/BUILD_DATE = \"$BUILD_DATE\"/" "$VERSION_FILE"
    else
        # Linux
        sed -i "s/BUILD_DATE = \"[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]\"/BUILD_DATE = \"$BUILD_DATE\"/" "$VERSION_FILE"
    fi
    echo "✅ Updated $VERSION_FILE"
else
    echo "⚠️  Warning: $VERSION_FILE not found"
fi

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
