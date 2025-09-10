#!/bin/bash
# Auto-Fixing Test Script for Knowledge Chipper
# This script runs tests, analyzes failures, and automatically fixes what it can

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m' # No Color

# Configuration
MAX_ITERATIONS=3
VERBOSE=false
DRY_RUN=false
AUTO_FIX=true

print_header() {
    echo -e "\n${BLUE}================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}================================${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_fix() {
    echo -e "${PURPLE}🔧 $1${NC}"
}

show_help() {
    cat << EOF
Auto-Fixing Test Script for Knowledge Chipper

This script runs tests, analyzes failures, and automatically fixes common issues.

Usage: $0 [OPTIONS]

Options:
    --dry-run       Show what would be fixed without making changes
    --no-auto-fix   Run tests but don't auto-fix issues
    --verbose       Show detailed output
    --max-iter N    Maximum fix iterations (default: 3)
    -h, --help      Show this help

The script will:
1. Run tests and capture output
2. Parse failures and violations
3. Automatically fix common issues
4. Re-run tests to verify fixes
5. Repeat until clean or max iterations reached

Examples:
    $0                  # Run with auto-fixing
    $0 --dry-run        # Show what would be fixed
    $0 --no-auto-fix    # Just run tests, no fixes

EOF
}

# Function to parse linting output and extract fixable issues
parse_linting_issues() {
    local lint_output="$1"
    local temp_file=$(mktemp)

    echo "$lint_output" > "$temp_file"

    # Extract different types of issues
    grep -E "E501.*line too long" "$temp_file" > "${temp_file}.e501" || true
    grep -E "F401.*imported but unused" "$temp_file" > "${temp_file}.f401" || true
    grep -E "W293.*blank line contains whitespace" "$temp_file" > "${temp_file}.w293" || true
    grep -E "E203.*whitespace before" "$temp_file" > "${temp_file}.e203" || true

    echo "$temp_file"
}

# Function to auto-fix E501 (line too long) issues
auto_fix_line_length() {
    local issues_file="$1"
    local fixed_count=0

    if [[ ! -f "${issues_file}.e501" ]] || [[ ! -s "${issues_file}.e501" ]]; then
        return 0
    fi

    print_fix "Fixing line length issues (E501)..."

    # Use black to auto-format files with line length issues
    while IFS= read -r line; do
        if [[ $line =~ ^([^:]+):([0-9]+):([0-9]+):.* ]]; then
            local file_path="${BASH_REMATCH[1]}"

            if [[ "$DRY_RUN" == "true" ]]; then
                echo "Would format: $file_path"
            else
                if [[ "$VERBOSE" == "true" ]]; then
                    echo "Formatting: $file_path"
                fi
                black "$file_path" --quiet 2>/dev/null || true
                ((fixed_count++))
            fi
        fi
    done < "${issues_file}.e501"

    if [[ $fixed_count -gt 0 ]]; then
        print_success "Fixed $fixed_count line length issues"
    fi

    return $fixed_count
}

# Function to auto-fix F401 (unused imports)
auto_fix_unused_imports() {
    local issues_file="$1"
    local fixed_count=0

    if [[ ! -f "${issues_file}.f401" ]] || [[ ! -s "${issues_file}.f401" ]]; then
        return 0
    fi

    print_fix "Fixing unused imports (F401)..."

    # Use autoflake to remove unused imports
    while IFS= read -r line; do
        if [[ $line =~ ^([^:]+):([0-9]+):([0-9]+):.* ]]; then
            local file_path="${BASH_REMATCH[1]}"

            if [[ "$DRY_RUN" == "true" ]]; then
                echo "Would remove unused imports from: $file_path"
            else
                if command -v autoflake >/dev/null 2>&1; then
                    autoflake --remove-all-unused-imports --in-place "$file_path" 2>/dev/null || true
                    ((fixed_count++))
                elif [[ "$VERBOSE" == "true" ]]; then
                    echo "autoflake not available, skipping unused import removal"
                fi
            fi
        fi
    done < "${issues_file}.f401"

    if [[ $fixed_count -gt 0 ]]; then
        print_success "Fixed $fixed_count unused import issues"
    fi

    return $fixed_count
}

# Function to auto-fix W293 (blank line whitespace)
auto_fix_blank_line_whitespace() {
    local issues_file="$1"
    local fixed_count=0

    if [[ ! -f "${issues_file}.w293" ]] || [[ ! -s "${issues_file}.w293" ]]; then
        return 0
    fi

    print_fix "Fixing blank line whitespace (W293)..."

    while IFS= read -r line; do
        if [[ $line =~ ^([^:]+):([0-9]+):([0-9]+):.* ]]; then
            local file_path="${BASH_REMATCH[1]}"

            if [[ "$DRY_RUN" == "true" ]]; then
                echo "Would fix whitespace in: $file_path"
            else
                # Remove trailing whitespace from blank lines
                sed -i '' 's/^[[:space:]]*$//' "$file_path" 2>/dev/null || true
                ((fixed_count++))
            fi
        fi
    done < "${issues_file}.w293"

    if [[ $fixed_count -gt 0 ]]; then
        print_success "Fixed $fixed_count blank line whitespace issues"
    fi

    return $fixed_count
}

# Function to parse test failures and extract fixable issues
parse_test_failures() {
    local test_output="$1"
    local temp_file=$(mktemp)

    echo "$test_output" > "$temp_file"

    # Extract import errors
    grep -B2 -A2 "ModuleNotFoundError.*No module named 'src'" "$temp_file" > "${temp_file}.import_errors" || true

    echo "$temp_file"
}

# Function to auto-fix import path issues
auto_fix_import_paths() {
    local issues_file="$1"
    local fixed_count=0

    if [[ ! -f "${issues_file}.import_errors" ]] || [[ ! -s "${issues_file}.import_errors" ]]; then
        return 0
    fi

    print_fix "Fixing import path issues..."

    # Find all files with src.knowledge_system imports
    local files_to_fix=$(find tests/ -name "*.py" -exec grep -l "from src\.knowledge_system" {} \; 2>/dev/null || true)

    for file_path in $files_to_fix; do
        if [[ "$DRY_RUN" == "true" ]]; then
            echo "Would fix imports in: $file_path"
        else
            if [[ "$VERBOSE" == "true" ]]; then
                echo "Fixing imports in: $file_path"
            fi
            # Fix the import paths
            sed -i '' 's/from src\.knowledge_system/from knowledge_system/g' "$file_path"
            ((fixed_count++))
        fi
    done

    if [[ $fixed_count -gt 0 ]]; then
        print_success "Fixed import paths in $fixed_count files"
    fi

    return $fixed_count
}

# Function to run tests and capture output
run_tests_with_capture() {
    local mode="${1:-quick}"
    local output_file=$(mktemp)
    local exit_code=0

    print_header "Running Tests ($mode mode)"

    # Run the test script and capture output
    if [[ "$mode" == "quick" ]]; then
        ./scripts/full-test.sh --quick > "$output_file" 2>&1 || exit_code=$?
    elif [[ "$mode" == "lint-only" ]]; then
        make lint > "$output_file" 2>&1 || exit_code=$?
    else
        ./scripts/full-test.sh > "$output_file" 2>&1 || exit_code=$?
    fi

    if [[ "$VERBOSE" == "true" ]]; then
        echo "Test output captured to: $output_file"
    fi

    echo "$output_file:$exit_code"
}

# Function to analyze issues and determine if they're fixable
analyze_issues() {
    local output_file="$1"
    local total_issues=0
    local fixable_issues=0

    # Count linting issues
    local lint_violations=$(grep -E "(E501|F401|W293|E203)" "$output_file" | wc -l | tr -d ' ')
    local import_errors=$(grep -c "ModuleNotFoundError.*No module named 'src'" "$output_file" || echo "0")

    total_issues=$((lint_violations + import_errors))

    # Estimate fixable issues (we can auto-fix most common ones)
    fixable_issues=$((lint_violations + import_errors))

    echo "Found $total_issues total issues, $fixable_issues potentially auto-fixable"

    echo "$total_issues:$fixable_issues"
}

# Main auto-fixing function
run_auto_fix_cycle() {
    local iteration=1
    local previous_issues=-1
    local current_issues=0

    print_header "Auto-Fix Test Cycle"

    while [[ $iteration -le $MAX_ITERATIONS ]]; do
        echo -e "\n${YELLOW}--- Iteration $iteration/$MAX_ITERATIONS ---${NC}"

        # Run tests and capture output
        local test_result=$(run_tests_with_capture "lint-only")
        local output_file="${test_result%:*}"
        local exit_code="${test_result#*:}"

        # Analyze current state
        local analysis=$(analyze_issues "$output_file")
        current_issues="${analysis%:*}"
        local fixable_issues="${analysis#*:}"

        echo "Current issues: $current_issues"

        # Check if we're making progress
        if [[ $current_issues -eq 0 ]]; then
            print_success "All auto-fixable issues resolved!"
            break
        fi

        if [[ $current_issues -eq $previous_issues ]]; then
            print_warning "No progress made in this iteration, stopping"
            break
        fi

        if [[ "$AUTO_FIX" == "false" ]]; then
            echo "Auto-fixing disabled, stopping after analysis"
            break
        fi

        # Parse and fix issues
        local temp_files=""

        # Fix linting issues
        if grep -q -E "(E501|F401|W293|E203)" "$output_file"; then
            print_fix "Applying automatic fixes..."

            local lint_issues=$(parse_linting_issues "$(cat "$output_file")")
            temp_files="$temp_files $lint_issues"

            auto_fix_line_length "$lint_issues"
            auto_fix_unused_imports "$lint_issues"
            auto_fix_blank_line_whitespace "$lint_issues"
        fi

        # Fix test failures
        if grep -q "ModuleNotFoundError.*No module named 'src'" "$output_file"; then
            local test_issues=$(parse_test_failures "$(cat "$output_file")")
            temp_files="$temp_files $test_issues"

            auto_fix_import_paths "$test_issues"
        fi

        # Clean up temp files
        for temp_file in $temp_files; do
            rm -f "$temp_file"* 2>/dev/null || true
        done

        previous_issues=$current_issues
        ((iteration++))

        # Run isort after fixes to clean up imports
        if [[ "$DRY_RUN" == "false" ]]; then
            isort src/ tests/ scripts/ --quiet 2>/dev/null || true
        fi
    done

    return $current_issues
}

# Function to run final validation
run_final_validation() {
    print_header "Final Validation"

    local test_result=$(run_tests_with_capture "quick")
    local output_file="${test_result%:*}"
    local exit_code="${test_result#*:}"

    if [[ $exit_code -eq 0 ]]; then
        print_success "All tests passing! 🎉"
        echo "Your code is ready for release."
    else
        print_warning "Some issues remain that require manual attention"
        echo ""
        echo "Remaining issues summary:"

        # Show summary of remaining issues
        local analysis=$(analyze_issues "$output_file")
        local remaining_issues="${analysis%:*}"

        if [[ $remaining_issues -gt 0 ]]; then
            echo "• $remaining_issues issues need manual review"
            echo ""
            echo "Use these commands for manual fixing:"
            echo "  ./scripts/handle-test-failures.sh --all"
            echo "  pytest tests/failing_test.py::specific_test -v -s"
        fi

        # Show first few issues for context
        echo ""
        echo "First few remaining issues:"
        head -10 "$output_file" | grep -E "(FAILED|ERROR|E[0-9]|F[0-9]|W[0-9])" || echo "See full output for details"
    fi

    # Cleanup
    rm -f "$output_file" 2>/dev/null || true

    return $exit_code
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --no-auto-fix)
            AUTO_FIX=false
            shift
            ;;
        --verbose)
            VERBOSE=true
            shift
            ;;
        --max-iter)
            MAX_ITERATIONS="$2"
            shift 2
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

# Main execution
main() {
    print_header "Auto-Fixing Test Script for Knowledge Chipper"

    if [[ "$DRY_RUN" == "true" ]]; then
        echo "🔍 DRY RUN MODE - No changes will be made"
    fi

    if [[ "$AUTO_FIX" == "false" ]]; then
        echo "📋 ANALYSIS ONLY - No automatic fixes will be applied"
    fi

    echo "Max iterations: $MAX_ITERATIONS"
    echo ""

    # Check prerequisites
    if [[ ! -f "./scripts/full-test.sh" ]]; then
        print_error "full-test.sh not found. Run from project root."
        exit 1
    fi

    # Install autoflake if not available (for unused import removal)
    if [[ "$AUTO_FIX" == "true" ]] && [[ "$DRY_RUN" == "false" ]]; then
        if ! command -v autoflake >/dev/null 2>&1; then
            print_fix "Installing autoflake for unused import removal..."
            pip install autoflake --quiet || print_warning "Could not install autoflake"
        fi
    fi

    # Run the auto-fix cycle
    run_auto_fix_cycle
    local remaining_issues=$?

    echo ""

    # Run final validation
    run_final_validation
    local final_exit_code=$?

    if [[ $final_exit_code -eq 0 ]]; then
        echo ""
        print_success "🚀 Auto-fixing completed successfully!"
        echo "Ready to commit and release."
    else
        echo ""
        print_warning "Auto-fixing completed with some issues remaining"
        echo "Manual review recommended before release."
    fi

    return $final_exit_code
}

# Run main function
main "$@"
