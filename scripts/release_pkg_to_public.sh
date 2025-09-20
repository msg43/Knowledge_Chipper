#!/bin/bash
# release_pkg_to_public.sh - Build and release PKG installer (replaces DMG workflow)
# Migrated from release_dmg_to_public.sh for PKG installer approach

set -e
set -o pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Parse arguments (same as original)
BUMP_VERSION=0
BUMP_PART="patch"

while [[ $# -gt 0 ]]; do
    case $1 in
        --bump-version)
            BUMP_VERSION=1
            shift
            ;;
        --bump-part)
            BUMP_PART="$2"
            if [[ ! "$BUMP_PART" =~ ^(patch|minor|major)$ ]]; then
                echo "❌ Invalid bump part: $BUMP_PART. Must be patch, minor, or major."
                exit 1
            fi
            shift 2
            ;;
        --help|-h)
            echo "Usage: $0 [options]"
            echo ""
            echo "Options:"
            echo "  --bump-version        Automatically increment version before release"
            echo "  --bump-part PART      Which version part to bump (patch|minor|major, default: patch)"
            echo "  --help, -h           Show this help message"
            exit 0
            ;;
        *)
            echo "❌ Unknown option: $1"
            exit 1
            ;;
    esac
done

echo "🚀 Building and releasing PKG installer..."

# Bump version if requested
if [ $BUMP_VERSION -eq 1 ]; then
    echo "🔢 Bumping version ($BUMP_PART)..."
    if ! python3 "$SCRIPT_DIR/bump_version.py" --part "$BUMP_PART"; then
        echo "❌ Version bump failed"
        exit 1
    fi
fi

# Build complete PKG
echo "📦 Building complete PKG installer..."
"$SCRIPT_DIR/build_complete_pkg.sh" --upload-release

echo "🎉 PKG release completed successfully!"
