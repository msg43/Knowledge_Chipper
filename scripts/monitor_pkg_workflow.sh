#!/bin/bash
# Monitor PKG workflow health and performance

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")") && pwd)"

echo "📊 PKG Workflow Health Check"
echo "============================="

# Check script availability
echo "Scripts Status:"
for script in build_complete_pkg.sh build_pkg_installer.sh; do
    if [ -x "$SCRIPT_DIR/$script" ]; then
        echo "  ✅ $script"
    else
        echo "  ❌ $script"
    fi
done

# Check build artifacts
echo ""
echo "Build Artifacts:"
DIST_DIR="$(dirname "$SCRIPT_DIR")/dist"
if [ -d "$DIST_DIR" ]; then
    echo "  📁 $DIST_DIR"
    ls -lh "$DIST_DIR"/*.{pkg,tar.gz} 2>/dev/null | awk '{print "    " $9 " (" $5 ")"}' || echo "    No artifacts found"
else
    echo "  📁 $DIST_DIR (not found)"
fi

# Check system requirements
echo ""
echo "System Requirements:"
echo "  Python: $(python3 --version)"
echo "  PKG Tools: $(command -v pkgbuild >/dev/null && echo "✅ Available" || echo "❌ Missing")"
echo "  Git: $(git --version | head -1)"

# Performance check
echo ""
echo "Performance Check:"
start_time=$(date +%s)
timeout 10 "$SCRIPT_DIR/build_complete_pkg.sh" --help >/dev/null 2>&1 || true
end_time=$(date +%s)
duration=$((end_time - start_time))
echo "  Build script response: ${duration}s"

echo ""
echo "Health check completed: $(date)"
