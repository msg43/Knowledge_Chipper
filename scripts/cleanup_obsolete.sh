#!/bin/bash
# Safe cleanup of obsolete folders and files
# Date: 2025-10-27
# See: docs/OBSOLETE_FOLDERS_ANALYSIS.md for details

set -e  # Exit on error

cd "$(dirname "$0")/.." || exit 1

echo "🧹 Knowledge Chipper - Obsolete Folder Cleanup"
echo "=============================================="
echo ""

# Calculate sizes before cleanup
TOTAL_SIZE=0

calculate_size() {
    if [ -e "$1" ]; then
        SIZE=$(du -sk "$1" 2>/dev/null | awk '{print $1}')
        TOTAL_SIZE=$((TOTAL_SIZE + SIZE))
    fi
}

echo "📊 Calculating space to be freed..."
calculate_size "_to_delete"
calculate_size "_quarantine"
calculate_size ".git_backup_20250807_185718"
calculate_size "build_framework"
calculate_size "github_models_prep"
calculate_size "build_ffmpeg"
calculate_size "build_pkg"
calculate_size "build_app_template"
calculate_size "build_packages"
calculate_size "htmlcov"
calculate_size "test-results"
calculate_size "Reports"

TOTAL_MB=$((TOTAL_SIZE / 1024))
echo "Total space to be freed: ~${TOTAL_MB} MB"
echo ""

# Confirm before deletion
read -p "Continue with cleanup? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "❌ Cleanup cancelled."
    exit 1
fi

echo ""
echo "🗑️  Removing obsolete folders..."

# Explicitly marked for deletion
if [ -d "_to_delete" ]; then
    echo "  ✓ Removing _to_delete/..."
    rm -rf _to_delete/
fi

if [ -d "_quarantine" ]; then
    echo "  ✓ Removing _quarantine/..."
    rm -rf _quarantine/
fi

if [ -d ".git_backup_20250807_185718" ]; then
    echo "  ✓ Removing .git_backup_20250807_185718/..."
    rm -rf .git_backup_20250807_185718/
fi

# Build artifacts
echo ""
echo "🔨 Removing build artifacts (can be rebuilt)..."

if [ -d "build_framework" ]; then
    echo "  ✓ Removing build_framework/ (706 MB)..."
    rm -rf build_framework/
fi

if [ -d "github_models_prep" ]; then
    echo "  ✓ Removing github_models_prep/ (502 MB)..."
    rm -rf github_models_prep/
fi

if [ -d "build_ffmpeg" ]; then
    echo "  ✓ Removing build_ffmpeg/ (101 MB)..."
    rm -rf build_ffmpeg/
fi

if [ -d "build_pkg" ]; then
    echo "  ✓ Removing build_pkg/..."
    rm -rf build_pkg/
fi

if [ -d "build_app_template" ]; then
    echo "  ✓ Removing build_app_template/..."
    rm -rf build_app_template/
fi

if [ -d "build_packages" ]; then
    echo "  ✓ Removing build_packages/..."
    rm -rf build_packages/
fi

# Test artifacts
echo ""
echo "🧪 Removing test artifacts (regenerate with pytest)..."

if [ -d "htmlcov" ]; then
    echo "  ✓ Removing htmlcov/..."
    rm -rf htmlcov/
fi

if [ -d "test-results" ]; then
    echo "  ✓ Removing test-results/..."
    rm -rf test-results/
fi

if [ -d "Reports" ]; then
    echo "  ✓ Removing Reports/..."
    rm -rf Reports/
fi

# Old backups
echo ""
echo "💾 Cleaning up old backups..."

if ls knowledge_system.db.pre_unification.* 1> /dev/null 2>&1; then
    echo "  ✓ Removing old pre_unification database backups..."
    rm -f knowledge_system.db.pre_unification.*
fi

if ls *.backup 1> /dev/null 2>&1; then
    echo "  ✓ Removing config backup files..."
    rm -f *.backup
fi

if ls state/*.backup 1> /dev/null 2>&1; then
    echo "  ✓ Cleaning state folder backups..."
    rm -f state/*.backup
fi

echo ""
echo "✅ Cleanup complete!"
echo ""
echo "📁 Kept (still needed):"
echo "  - _deprecated/ (grace period until Dec 2025)"
echo "  - data/ (test files)"
echo "  - output/ (user-generated content)"
echo "  - knowledge_system.db.backup.20251024_195602 (recent backup)"
echo ""
echo "💡 To rebuild deleted artifacts:"
echo "  - Python framework: ./scripts/build_python_framework.sh"
echo "  - Complete PKG: ./scripts/build_complete_pkg.sh"
echo "  - Coverage reports: pytest --cov=src --cov-report=html"
echo ""
echo "Space freed: ~${TOTAL_MB} MB"

