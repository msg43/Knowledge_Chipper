#!/bin/bash
# cleanup_build.sh - Clean up build directories that may have root-owned files

echo "🧹 Cleaning up build directories..."

# List of directories that might need cleaning
DIRS_TO_CLEAN=(
    "build_pkg"
    "build_installer_app"
    "test_auth_build"
    "test_root_build"
    "test_system_build"
    "build_packages"
)

PROJECT_ROOT="$(dirname "$(dirname "${BASH_SOURCE[0]}")")"

for dir in "${DIRS_TO_CLEAN[@]}"; do
    if [ -d "$PROJECT_ROOT/$dir" ]; then
        echo "Found: $dir"
        rm -rf "$PROJECT_ROOT/$dir" 2>/dev/null || {
            echo "  ⚠️  Needs sudo to remove $dir"
            sudo rm -rf "$PROJECT_ROOT/$dir"
        }
    fi
done

echo "✅ Cleanup complete!"
