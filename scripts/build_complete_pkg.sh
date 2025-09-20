#!/bin/bash
# build_complete_pkg.sh - Master script to build complete PKG installer with all components
# This orchestrates the entire PKG migration process

set -e
set -o pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
VERSION=$(python3 -c "import tomllib; print(tomllib.load(open('$PROJECT_ROOT/pyproject.toml', 'rb'))['project']['version'])")

# Parse arguments
SKIP_FRAMEWORK=0
SKIP_MODELS=0
SKIP_FFMPEG=0
UPLOAD_RELEASE=0
BUILD_ONLY=0
FORCE_REBUILD=0

for arg in "$@"; do
    case "$arg" in
        --skip-framework)
            SKIP_FRAMEWORK=1
            ;;
        --skip-models)
            SKIP_MODELS=1
            ;;
        --skip-ffmpeg)
            SKIP_FFMPEG=1
            ;;
        --upload-release)
            UPLOAD_RELEASE=1
            ;;
        --build-only)
            BUILD_ONLY=1
            ;;
        --force)
            FORCE_REBUILD=1
            ;;
        --help|-h)
            echo "Usage: $0 [options]"
            echo ""
            echo "Options:"
            echo "  --skip-framework    Skip Python framework build (use existing)"
            echo "  --skip-models      Skip AI models bundle (use existing)"
            echo "  --skip-ffmpeg      Skip FFmpeg bundle (use existing)"
            echo "  --upload-release   Create and upload GitHub release"
            echo "  --build-only       Build PKG but don't upload"
            echo "  --force            Force rebuild existing files without prompting"
            echo "  --help, -h         Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0                              # Build everything"
            echo "  $0 --skip-models --build-only  # Quick PKG build"
            echo "  $0 --upload-release            # Full build + release"
            exit 0
            ;;
        *)
            echo "❌ Unknown option: $arg"
            echo "Use --help for usage information."
            exit 1
            ;;
    esac
done

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m' # No Color

echo -e "${BLUE}${BOLD}🚀 Complete PKG Installer Builder${NC}"
echo "=================================="
echo "Version: $VERSION"
echo "Building: Skip the Podcast Desktop PKG Installer"
echo ""

# Function to print status
print_status() {
    echo -e "${GREEN}✅${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠️${NC} $1"
}

print_error() {
    echo -e "${RED}❌${NC} $1"
}

print_section() {
    echo -e "\n${BLUE}${BOLD}$1${NC}"
    echo "$(printf '%.s─' $(seq 1 ${#1}))"
}

# Check prerequisites
print_section "📋 Checking Prerequisites"

# Check required tools
REQUIRED_TOOLS=("python3" "curl" "tar" "pkgbuild" "productbuild")
MISSING_TOOLS=()

for tool in "${REQUIRED_TOOLS[@]}"; do
    if command -v "$tool" &> /dev/null; then
        print_status "$tool found"
    else
        MISSING_TOOLS+=("$tool")
        print_error "$tool not found"
    fi
done

if [ ${#MISSING_TOOLS[@]} -ne 0 ]; then
    print_error "Missing required tools. Please install:"
    for tool in "${MISSING_TOOLS[@]}"; do
        echo "  - $tool"
    done
    exit 1
fi

# Check Python modules
echo -e "\n${BLUE}Checking Python modules...${NC}"
python3 -c "import tomllib, yaml, json" || {
    print_error "Required Python modules missing. Install with:"
    echo "  pip install pyyaml"
    exit 1
}

print_status "All prerequisites satisfied"

# Start build process
print_section "🏗️ Starting Build Process"

# Create dist directory
mkdir -p "$PROJECT_ROOT/dist"

# Build Python Framework (check if source changed)
if [ $SKIP_FRAMEWORK -eq 0 ]; then
    print_section "🐍 Building Python Framework"

    # Check if we need to rebuild based on source changes
    FRAMEWORK_CACHE_FILE="$PROJECT_ROOT/dist/.python_framework_hash"
    NEEDS_REBUILD=1

    if [ -f "$PROJECT_ROOT/dist/python-framework-3.13-macos.tar.gz" ] && [ -f "$FRAMEWORK_CACHE_FILE" ]; then
        # Calculate hash of framework build script
        CURRENT_HASH=$(shasum -a 256 "$SCRIPT_DIR/build_simple_python_framework.sh" | cut -d' ' -f1)
        CACHED_HASH=$(cat "$FRAMEWORK_CACHE_FILE" 2>/dev/null || echo "")

        if [ "$CURRENT_HASH" = "$CACHED_HASH" ]; then
            print_status "Python framework up-to-date (build script unchanged)"
            NEEDS_REBUILD=0
        else
            print_warning "Python framework build script changed - rebuilding"
        fi
    else
        print_warning "No existing framework or cache found"
    fi

    if [ $NEEDS_REBUILD -eq 1 ]; then
        "$SCRIPT_DIR/build_simple_python_framework.sh"
        # Cache the hash after successful build
        shasum -a 256 "$SCRIPT_DIR/build_simple_python_framework.sh" | cut -d' ' -f1 > "$FRAMEWORK_CACHE_FILE"
    fi

    print_status "Python framework ready"
else
    print_warning "Skipping Python framework build"
    if [ ! -f "$PROJECT_ROOT/dist/python-framework-3.13-macos.tar.gz" ]; then
        print_error "Python framework not found and build skipped"
        exit 1
    fi
fi

# Build AI Models Bundle (check if model sources changed)
if [ $SKIP_MODELS -eq 0 ]; then
    print_section "🧠 Building AI Models Bundle"

    # Check if we need to rebuild based on source changes
    MODELS_CACHE_FILE="$PROJECT_ROOT/dist/.ai_models_hash"
    NEEDS_REBUILD=1

    if [ -f "$PROJECT_ROOT/dist/ai-models-bundle.tar.gz" ] && [ -f "$MODELS_CACHE_FILE" ]; then
        # Calculate hash of model sources and build script
        MODEL_SOURCES=""

        # Check github_models_prep directory for manually added models
        if [ -d "$PROJECT_ROOT/github_models_prep" ]; then
            MODEL_SOURCES=$(find "$PROJECT_ROOT/github_models_prep" -type f \( -name "*.bin" -o -name "*.tar.gz" -o -name "*.json" \) 2>/dev/null | sort)
        fi

        # Include the bundle script itself
        MODEL_SOURCES="$MODEL_SOURCES $SCRIPT_DIR/bundle_simple_ai_models.sh"

        # Calculate combined hash
        CURRENT_HASH=""
        if [ -n "$MODEL_SOURCES" ]; then
            CURRENT_HASH=$(echo "$MODEL_SOURCES" | xargs shasum -a 256 2>/dev/null | shasum -a 256 | cut -d' ' -f1)
        else
            CURRENT_HASH=$(shasum -a 256 "$SCRIPT_DIR/bundle_simple_ai_models.sh" | cut -d' ' -f1)
        fi

        CACHED_HASH=$(cat "$MODELS_CACHE_FILE" 2>/dev/null || echo "")

        if [ "$CURRENT_HASH" = "$CACHED_HASH" ]; then
            print_status "AI models bundle up-to-date (no source changes detected)"
            NEEDS_REBUILD=0
        else
            print_warning "AI model sources or build script changed - rebuilding"
        fi
    else
        print_warning "No existing models bundle or cache found"
    fi

    if [ $NEEDS_REBUILD -eq 1 ]; then
        "$SCRIPT_DIR/bundle_simple_ai_models.sh"
        # Cache the hash after successful build
        MODEL_SOURCES=""
        if [ -d "$PROJECT_ROOT/github_models_prep" ]; then
            MODEL_SOURCES=$(find "$PROJECT_ROOT/github_models_prep" -type f \( -name "*.bin" -o -name "*.tar.gz" -o -name "*.json" \) 2>/dev/null | sort)
        fi
        MODEL_SOURCES="$MODEL_SOURCES $SCRIPT_DIR/bundle_simple_ai_models.sh"

        if [ -n "$MODEL_SOURCES" ]; then
            echo "$MODEL_SOURCES" | xargs shasum -a 256 2>/dev/null | shasum -a 256 | cut -d' ' -f1 > "$MODELS_CACHE_FILE"
        else
            shasum -a 256 "$SCRIPT_DIR/bundle_simple_ai_models.sh" | cut -d' ' -f1 > "$MODELS_CACHE_FILE"
        fi
    fi

    print_status "AI models bundle ready"
else
    print_warning "Skipping AI models bundle build"
    if [ ! -f "$PROJECT_ROOT/dist/ai-models-bundle.tar.gz" ]; then
        print_error "AI models bundle not found and build skipped"
        exit 1
    fi
fi

# Build FFmpeg Bundle
if [ $SKIP_FFMPEG -eq 0 ]; then
    print_section "🎬 Building FFmpeg Bundle"

    if [ -f "$PROJECT_ROOT/dist/ffmpeg-macos-universal.tar.gz" ]; then
        print_warning "FFmpeg bundle already exists"
        read -p "Rebuild? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            rm -f "$PROJECT_ROOT/dist/ffmpeg-macos-universal.tar.gz"*
            "$SCRIPT_DIR/bundle_ffmpeg.sh"
        fi
    else
        "$SCRIPT_DIR/bundle_ffmpeg.sh"
    fi

    print_status "FFmpeg bundle ready"
else
    print_warning "Skipping FFmpeg bundle build"
    if [ ! -f "$PROJECT_ROOT/dist/ffmpeg-macos-universal.tar.gz" ]; then
        print_error "FFmpeg bundle not found and build skipped"
        exit 1
    fi
fi

# Build PKG Installer
print_section "📦 Building PKG Installer"

if [ -f "$PROJECT_ROOT/dist/Skip_the_Podcast_Desktop-${VERSION}.pkg" ]; then
    if [ $FORCE_REBUILD -eq 1 ]; then
        print_warning "PKG installer already exists - force rebuilding"
        rm -f "$PROJECT_ROOT/dist/Skip_the_Podcast_Desktop-${VERSION}.pkg"*
        "$SCRIPT_DIR/build_pkg_installer.sh"
    else
        print_warning "PKG installer already exists"
        read -p "Rebuild? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            rm -f "$PROJECT_ROOT/dist/Skip_the_Podcast_Desktop-${VERSION}.pkg"*
            "$SCRIPT_DIR/build_pkg_installer.sh"
        fi
    fi
else
    "$SCRIPT_DIR/build_pkg_installer.sh"
fi

print_status "PKG installer ready"

# Calculate build statistics
print_section "📊 Build Statistics"

cd "$PROJECT_ROOT/dist"

COMPONENTS=(
    "Skip_the_Podcast_Desktop-${VERSION}.pkg"
    "python-framework-3.13-macos.tar.gz"
    "ai-models-bundle.tar.gz"
    "ffmpeg-macos-universal.tar.gz"
)

echo -e "${BLUE}Component Sizes:${NC}"
TOTAL_SIZE=0

for component in "${COMPONENTS[@]}"; do
    if [ -f "$component" ]; then
        SIZE_BYTES=$(stat -f%z "$component")
        SIZE_HUMAN=$(du -h "$component" | cut -f1)
        TOTAL_SIZE=$((TOTAL_SIZE + SIZE_BYTES))

        printf "  %-45s %8s\n" "$component" "$SIZE_HUMAN"
    else
        printf "  %-45s %8s\n" "$component" "MISSING"
    fi
done

# Convert bytes to human readable format (macOS compatible)
if [ $TOTAL_SIZE -gt 1073741824 ]; then
    TOTAL_SIZE_HUMAN=$(echo "scale=1; $TOTAL_SIZE / 1073741824" | bc -l 2>/dev/null || echo "$((TOTAL_SIZE / 1073741824))")GB
elif [ $TOTAL_SIZE -gt 1048576 ]; then
    TOTAL_SIZE_HUMAN=$(echo "scale=1; $TOTAL_SIZE / 1048576" | bc -l 2>/dev/null || echo "$((TOTAL_SIZE / 1048576))")MB
elif [ $TOTAL_SIZE -gt 1024 ]; then
    TOTAL_SIZE_HUMAN=$(echo "scale=1; $TOTAL_SIZE / 1024" | bc -l 2>/dev/null || echo "$((TOTAL_SIZE / 1024))")KB
else
    TOTAL_SIZE_HUMAN="${TOTAL_SIZE}B"
fi
echo -e "\n${BOLD}Total Size: $TOTAL_SIZE_HUMAN${NC}"

# PKG vs DMG comparison
PKG_SIZE_BYTES=$(stat -f%z "Skip_the_Podcast_Desktop-${VERSION}.pkg" 2>/dev/null || echo "0")
# Convert PKG size to human readable format
if [ $PKG_SIZE_BYTES -gt 1073741824 ]; then
    PKG_SIZE_HUMAN=$(echo "scale=1; $PKG_SIZE_BYTES / 1073741824" | bc -l 2>/dev/null || echo "$((PKG_SIZE_BYTES / 1073741824))")GB
elif [ $PKG_SIZE_BYTES -gt 1048576 ]; then
    PKG_SIZE_HUMAN=$(echo "scale=1; $PKG_SIZE_BYTES / 1048576" | bc -l 2>/dev/null || echo "$((PKG_SIZE_BYTES / 1048576))")MB
elif [ $PKG_SIZE_BYTES -gt 1024 ]; then
    PKG_SIZE_HUMAN=$(echo "scale=1; $PKG_SIZE_BYTES / 1024" | bc -l 2>/dev/null || echo "$((PKG_SIZE_BYTES / 1024))")KB
else
    PKG_SIZE_HUMAN="${PKG_SIZE_BYTES}B"
fi

# Estimated DMG size (603MB)
DMG_SIZE_BYTES=632107622  # 603MB
# Convert DMG size to human readable format
if [ $DMG_SIZE_BYTES -gt 1073741824 ]; then
    DMG_SIZE_HUMAN=$(echo "scale=1; $DMG_SIZE_BYTES / 1073741824" | bc -l 2>/dev/null || echo "$((DMG_SIZE_BYTES / 1073741824))")GB
elif [ $DMG_SIZE_BYTES -gt 1048576 ]; then
    DMG_SIZE_HUMAN=$(echo "scale=1; $DMG_SIZE_BYTES / 1048576" | bc -l 2>/dev/null || echo "$((DMG_SIZE_BYTES / 1048576))")MB
elif [ $DMG_SIZE_BYTES -gt 1024 ]; then
    DMG_SIZE_HUMAN=$(echo "scale=1; $DMG_SIZE_BYTES / 1024" | bc -l 2>/dev/null || echo "$((DMG_SIZE_BYTES / 1024))")KB
else
    DMG_SIZE_HUMAN="${DMG_SIZE_BYTES}B"
fi

REDUCTION_PERCENT=$(( (DMG_SIZE_BYTES - PKG_SIZE_BYTES) * 100 / DMG_SIZE_BYTES ))

echo -e "\n${BLUE}Size Comparison:${NC}"
printf "  %-20s %10s\n" "Previous DMG:" "$DMG_SIZE_HUMAN"
printf "  %-20s %10s\n" "New PKG:" "$PKG_SIZE_HUMAN"
printf "  %-20s %10s%%\n" "Reduction:" "$REDUCTION_PERCENT"

print_status "Build statistics calculated"

cd "$PROJECT_ROOT"

# Upload release if requested
if [ $UPLOAD_RELEASE -eq 1 ] && [ $BUILD_ONLY -eq 0 ]; then
    print_section "🚀 Creating GitHub Release"

    echo -e "${YELLOW}This will create a public GitHub release.${NC}"
    echo "Components will be uploaded to: https://github.com/msg43/Knowledge_Chipper/releases"
    echo ""
    read -p "Continue with release creation? (y/N): " -n 1 -r
    echo

    if [[ $REPLY =~ ^[Yy]$ ]]; then
        "$SCRIPT_DIR/create_github_release.sh"
        print_status "GitHub release created"
    else
        print_warning "Release creation cancelled"
    fi
fi

# Test PKG integrity
print_section "🧪 Testing PKG Integrity"

PKG_FILE="$PROJECT_ROOT/dist/Skip_the_Podcast_Desktop-${VERSION}.pkg"

if pkgutil --check-signature "$PKG_FILE" &> /dev/null; then
    print_status "PKG signature valid"
else
    print_warning "PKG not signed (expected for development)"
fi

if pkgutil --expand "$PKG_FILE" "/tmp/pkg_test_$$" &> /dev/null; then
    print_status "PKG structure valid"
    rm -rf "/tmp/pkg_test_$$"
else
    print_error "PKG structure invalid"
    exit 1
fi

# Final summary
print_section "🎉 Build Complete"

echo -e "${GREEN}${BOLD}✅ PKG Installer Build Successful!${NC}"
echo ""
echo -e "${BLUE}Build Results:${NC}"
echo "  Version: $VERSION"
echo "  PKG Installer: Skip_the_Podcast_Desktop-${VERSION}.pkg ($PKG_SIZE_HUMAN)"
echo "  Total Components: $TOTAL_SIZE_HUMAN"
echo "  Size Reduction: ${REDUCTION_PERCENT}% vs DMG"
echo ""

if [ $UPLOAD_RELEASE -eq 1 ] && [[ $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${BLUE}Release Information:${NC}"
    echo "  GitHub Release: https://github.com/msg43/Knowledge_Chipper/releases/tag/v$VERSION"
    echo "  Download URL: https://github.com/msg43/Knowledge_Chipper/releases/download/v$VERSION/Skip_the_Podcast_Desktop-${VERSION}.pkg"
    echo ""
fi

echo -e "${BLUE}Next Steps:${NC}"
echo "1. Test PKG installation on clean macOS system"
echo "2. Verify all components download and install correctly"
echo "3. Test application functionality after PKG installation"
echo "4. Update documentation with new installation process"

if [ $BUILD_ONLY -eq 1 ]; then
    echo "5. Upload release with: $SCRIPT_DIR/create_github_release.sh"
fi

echo ""
echo -e "${GREEN}The PKG installer is ready for distribution! 🚀${NC}"
