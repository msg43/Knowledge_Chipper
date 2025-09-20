#!/bin/bash
# intelligent_build_cache.sh - Smart build caching based on actual source changes
# Detects when you've manually added/updated files instead of using arbitrary time limits

# Configuration
CACHE_DIR="$(dirname "${BASH_SOURCE[0]}")/../dist/.build_cache"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Create cache directory
mkdir -p "$CACHE_DIR"

# Function to calculate hash of multiple files/directories
calculate_source_hash() {
    local source_type="$1"
    shift
    local sources=("$@")

    local temp_file="/tmp/source_hash_$$"

    case "$source_type" in
        "app_code")
            # Hash Python source files, configs, pyproject.toml
            find "$PROJECT_ROOT/src" -name "*.py" -type f 2>/dev/null | sort | xargs shasum -a 256 > "$temp_file" 2>/dev/null || true
            [ -f "$PROJECT_ROOT/pyproject.toml" ] && shasum -a 256 "$PROJECT_ROOT/pyproject.toml" >> "$temp_file"
            [ -f "$PROJECT_ROOT/requirements.txt" ] && shasum -a 256 "$PROJECT_ROOT/requirements.txt" >> "$temp_file"
            [ -d "$PROJECT_ROOT/config" ] && find "$PROJECT_ROOT/config" -name "*.yaml" -o -name "*.txt" | sort | xargs shasum -a 256 >> "$temp_file" 2>/dev/null || true
            ;;
        "python_framework")
            # Hash framework build script and any Python version changes
            [ -f "${sources[0]}" ] && shasum -a 256 "${sources[0]}" > "$temp_file"
            ;;
        "ai_models")
            # Hash model files in github_models_prep and bundle script
            if [ -d "$PROJECT_ROOT/github_models_prep" ]; then
                find "$PROJECT_ROOT/github_models_prep" -type f \( -name "*.bin" -o -name "*.tar.gz" -o -name "*.json" -o -name "*.ckpt" \) 2>/dev/null | sort | xargs shasum -a 256 > "$temp_file" 2>/dev/null || true
            fi
            [ -f "${sources[0]}" ] && shasum -a 256 "${sources[0]}" >> "$temp_file"
            ;;
        "ffmpeg")
            # Hash FFmpeg bundle script and any custom binaries
            [ -f "${sources[0]}" ] && shasum -a 256 "${sources[0]}" > "$temp_file"
            # Check for custom FFmpeg binaries
            if [ -d "$PROJECT_ROOT/binaries" ]; then
                find "$PROJECT_ROOT/binaries" -name "*ffmpeg*" -type f 2>/dev/null | sort | xargs shasum -a 256 >> "$temp_file" 2>/dev/null || true
            fi
            ;;
        "pkg_installer")
            # Hash PKG build script and app bundle template
            [ -f "${sources[0]}" ] && shasum -a 256 "${sources[0]}" > "$temp_file"
            [ -f "${sources[1]}" ] && shasum -a 256 "${sources[1]}" >> "$temp_file"
            ;;
    esac

    if [ -s "$temp_file" ]; then
        shasum -a 256 "$temp_file" | cut -d' ' -f1
    else
        echo "no_sources"
    fi

    rm -f "$temp_file"
}

# Function to check if component needs rebuild
needs_rebuild() {
    local component="$1"
    local current_hash="$2"
    local cache_file="$CACHE_DIR/${component}_hash"

    if [ ! -f "$cache_file" ]; then
        echo "true"  # No cache, need to build
        return
    fi

    local cached_hash=$(cat "$cache_file" 2>/dev/null || echo "")

    if [ "$current_hash" != "$cached_hash" ]; then
        echo "true"  # Hash changed, need to rebuild
    else
        echo "false" # Hash same, can skip
    fi
}

# Function to update cache after successful build
update_cache() {
    local component="$1"
    local hash="$2"
    local cache_file="$CACHE_DIR/${component}_hash"

    echo "$hash" > "$cache_file"
    echo "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$CACHE_DIR/${component}_last_built"
}

# Function to get cache info
get_cache_info() {
    local component="$1"
    local cache_file="$CACHE_DIR/${component}_hash"
    local time_file="$CACHE_DIR/${component}_last_built"

    if [ -f "$cache_file" ] && [ -f "$time_file" ]; then
        local last_built=$(cat "$time_file" 2>/dev/null || echo "unknown")
        local hash=$(cat "$cache_file" 2>/dev/null || echo "unknown")
        echo "Last built: $last_built (hash: ${hash:0:12}...)"
    else
        echo "Never built"
    fi
}

# Function to show what files are being tracked for each component
show_tracked_files() {
    local component="$1"

    case "$component" in
        "app_code")
            echo "Tracking:"
            echo "  • Python files in src/"
            echo "  • pyproject.toml"
            echo "  • requirements.txt"
            echo "  • Config files in config/"
            ;;
        "python_framework")
            echo "Tracking:"
            echo "  • scripts/build_python_framework.sh"
            ;;
        "ai_models")
            echo "Tracking:"
            echo "  • Model files in github_models_prep/"
            echo "  • scripts/bundle_ai_models.sh"
            ;;
        "ffmpeg")
            echo "Tracking:"
            echo "  • scripts/bundle_ffmpeg.sh"
            echo "  • Custom FFmpeg binaries in binaries/"
            ;;
        "pkg_installer")
            echo "Tracking:"
            echo "  • scripts/build_pkg_installer.sh"
            echo "  • scripts/create_app_bundle_template.sh"
            ;;
    esac
}

# Main function for checking if rebuild needed
check_rebuild_needed() {
    local component="$1"
    shift
    local sources=("$@")

    local current_hash=$(calculate_source_hash "$component" "${sources[@]}")
    local rebuild_needed=$(needs_rebuild "$component" "$current_hash")

    if [ "$rebuild_needed" = "true" ]; then
        if [ "$current_hash" = "no_sources" ]; then
            echo "REBUILD_NEEDED:No source files found for $component"
        else
            echo "REBUILD_NEEDED:Source files changed for $component"
        fi
        echo "CURRENT_HASH:$current_hash"
    else
        echo "UP_TO_DATE:$component is up-to-date"
        echo "CURRENT_HASH:$current_hash"
    fi
}

# Main function for updating cache after build
update_build_cache() {
    local component="$1"
    shift
    local sources=("$@")

    local current_hash=$(calculate_source_hash "$component" "${sources[@]}")
    update_cache "$component" "$current_hash"
    echo "Cache updated for $component (hash: ${current_hash:0:12}...)"
}

# Command line interface
case "${1:-help}" in
    "check")
        check_rebuild_needed "$2" "${@:3}"
        ;;
    "update")
        update_build_cache "$2" "${@:3}"
        ;;
    "info")
        get_cache_info "$2"
        ;;
    "tracked")
        show_tracked_files "$2"
        ;;
    "clear")
        if [ -n "$2" ]; then
            rm -f "$CACHE_DIR/${2}_hash" "$CACHE_DIR/${2}_last_built"
            echo "Cache cleared for $2"
        else
            rm -rf "$CACHE_DIR"
            mkdir -p "$CACHE_DIR"
            echo "All caches cleared"
        fi
        ;;
    "status")
        echo "Build Cache Status:"
        echo "=================="
        for component in app_code python_framework ai_models ffmpeg pkg_installer; do
            echo "$component: $(get_cache_info "$component")"
        done
        ;;
    *)
        echo "Intelligent Build Cache - Smart rebuild detection based on source changes"
        echo ""
        echo "Usage: $0 <command> [component] [sources...]"
        echo ""
        echo "Commands:"
        echo "  check <component> [sources...]   Check if component needs rebuild"
        echo "  update <component> [sources...]  Update cache after successful build"
        echo "  info <component>                 Show cache info for component"
        echo "  tracked <component>              Show what files are tracked"
        echo "  clear [component]                Clear cache (all or specific component)"
        echo "  status                           Show status of all caches"
        echo ""
        echo "Components:"
        echo "  app_code         Your Python application code"
        echo "  python_framework Python framework build"
        echo "  ai_models        AI models bundle"
        echo "  ffmpeg           FFmpeg bundle"
        echo "  pkg_installer    PKG installer"
        echo ""
        echo "Examples:"
        echo "  $0 check app_code"
        echo "  $0 update ai_models /path/to/bundle_script.sh"
        echo "  $0 status"
        echo "  $0 clear python_framework"
        ;;
esac
