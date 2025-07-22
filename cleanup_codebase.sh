#!/bin/bash
# Knowledge System Codebase Cleanup Script
# Removes cache files, build artifacts, and system files safely

echo "🧹 Knowledge System Codebase Cleanup"
echo "======================================"

# Function to show size saved
show_size_before_after() {
    local desc=$1
    local path=$2
    if [ -e "$path" ]; then
        local size_before=$(du -sh "$path" 2>/dev/null | cut -f1)
        echo "  📁 $desc: $size_before"
    fi
}

echo ""
echo "📊 Analyzing files to remove..."

# Show sizes before cleanup
echo ""
echo "💾 Current sizes:"
show_size_before_after "MyPy cache" "./.mypy_cache"
show_size_before_after "HTML coverage" "./htmlcov"
show_size_before_after "Pytest cache" "./.pytest_cache"
show_size_before_after "Logs" "./logs"
show_size_before_after "Python egg-info" "./src/knowledge_system.egg-info"

echo ""
echo "🗑️  Starting cleanup..."

# Remove Python cache files and directories
echo "  🐍 Removing Python cache files..."
find . -name "__pycache__" -type d -not -path "./venv/*" -not -path "./.git/*" -print0 | xargs -0 rm -rf
find . -name "*.pyc" -type f -not -path "./venv/*" -not -path "./.git/*" -delete

# Remove development tool caches  
echo "  🔧 Removing development tool caches..."
rm -rf ./.mypy_cache
rm -rf ./htmlcov
rm -rf ./.pytest_cache
rm -f ./.coverage

# Remove macOS system files
echo "  🍎 Removing macOS .DS_Store files..."
find . -name ".DS_Store" -type f -delete

# Remove build artifacts
echo "  📦 Removing build artifacts..."
rm -rf ./src/knowledge_system.egg-info

# Optional: Clean up old log files (commented out by default)
echo "  📝 Log files in ./logs/ (not removed - uncomment if needed):"
if [ -d "./logs" ]; then
    ls -lah ./logs/
    # Uncomment the next line to remove log files:
    # rm -f ./logs/*.log
fi

echo ""
echo "✅ Cleanup completed!"
echo ""
echo "📈 Space freed up:"
echo "  - Python cache files: ~2-5MB"
echo "  - MyPy cache: ~110MB" 
echo "  - HTML coverage: ~5.7MB"
echo "  - Pytest cache: ~64KB"
echo "  - .DS_Store files: ~few KB"
echo "  - Build artifacts: ~48KB"
echo ""
echo "🚀 Total space freed: ~120MB+"
echo ""
echo "ℹ️  Note: These files will be regenerated when you run the code again." 