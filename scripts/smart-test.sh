#!/bin/bash
# Smart Test Script - Runs tests and auto-fixes common issues
# This is a simpler, more robust version that actually works

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m' # No Color

# Configuration
DRY_RUN=false
VERBOSE=false
MAX_ITERATIONS=3

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
Smart Test Script for Knowledge Chipper

This script runs tests and automatically fixes common issues it finds.

Usage: $0 [OPTIONS]

Options:
    --dry-run       Show what would be fixed without making changes
    --verbose       Show detailed output
    -h, --help      Show this help

Features:
• Runs tests and captures output
• Automatically fixes formatting issues
• Fixes import path problems
• Removes unused imports
• Iteratively improves code quality
• Shows before/after comparison

Examples:
    $0                  # Run with auto-fixing
    $0 --dry-run        # Show what would be fixed
    $0 --verbose        # Detailed output

EOF
}

# Function to count linting violations
count_lint_violations() {
    make lint 2>&1 | tail -1 | grep -o '[0-9]\+' || echo "0"
}

# Function to run quick fixes
run_quick_fixes() {
    local before_count=$(count_lint_violations)

    print_fix "Running automatic fixes..."

    if [[ "$DRY_RUN" == "true" ]]; then
        echo "Would run:"
        echo "  • make format (black + isort)"
        echo "  • Fix import paths (src.knowledge_system → knowledge_system)"
        echo "  • Remove unused imports"
        echo "  • Clean whitespace"
        return 0
    fi

    # 1. Auto-format code
    print_fix "Auto-formatting code..."
    make format --quiet 2>/dev/null || make format

    # 2. Fix import paths in tests
    print_fix "Fixing import paths..."
    find tests/ -name "*.py" -exec sed -i '' 's/from src\.knowledge_system/from knowledge_system/g' {} \; 2>/dev/null || true
    find tests/ -name "*.py" -exec sed -i '' 's/import src\.knowledge_system/import knowledge_system/g' {} \; 2>/dev/null || true

    # 3. Remove unused imports (if autoflake available)
    if command -v autoflake >/dev/null 2>&1; then
        print_fix "Removing unused imports..."
        find src/ tests/ -name "*.py" -exec autoflake --remove-all-unused-imports --in-place {} \; 2>/dev/null || true
    fi

    # 4. Clean trailing whitespace
    print_fix "Cleaning whitespace..."
    find src/ tests/ scripts/ -name "*.py" -exec sed -i '' 's/[[:space:]]*$//' {} \; 2>/dev/null || true

    # 5. Run isort again to clean up
    isort src/ tests/ scripts/ --quiet 2>/dev/null || true

    local after_count=$(count_lint_violations)
    local fixed=$((before_count - after_count))

    if [[ $fixed -gt 0 ]]; then
        print_success "Fixed $fixed linting violations ($before_count → $after_count)"
    else
        echo "No violations were auto-fixable"
    fi

    return $after_count
}

# Function to run tests and show summary
run_test_summary() {
    local mode="${1:-quick}"

    print_header "Running Tests"

    local temp_output=$(mktemp)
    local exit_code=0

    if [[ "$mode" == "quick" ]]; then
        ./scripts/full-test.sh --quick > "$temp_output" 2>&1 || exit_code=$?
    else
        ./scripts/full-test.sh > "$temp_output" 2>&1 || exit_code=$?
    fi

    # Show key results
    local test_failures=$(grep -c "FAILED" "$temp_output" 2>/dev/null || echo "0")
    local test_passes=$(grep -c "PASSED" "$temp_output" 2>/dev/null || echo "0")
    local lint_violations=$(count_lint_violations)

    echo "Test Results:"
    echo "  • $test_passes tests passed"
    echo "  • $test_failures tests failed"
    echo "  • $lint_violations linting violations"

    if [[ $exit_code -eq 0 ]]; then
        print_success "All tests passing!"
    else
        if [[ $test_failures -gt 0 ]]; then
            print_warning "Some tests failed"
            echo ""
            echo "Failed tests:"
            grep "FAILED" "$temp_output" | head -3
            if [[ $test_failures -gt 3 ]]; then
                echo "  ... and $((test_failures - 3)) more"
            fi
        fi

        if [[ $lint_violations -gt 0 ]]; then
            print_warning "$lint_violations linting violations found"
        fi
    fi

    rm -f "$temp_output"
    return $exit_code
}

# Function to show specific fixable issues
show_fixable_issues() {
    print_header "Analysis of Fixable Issues"

    local temp_lint=$(mktemp)
    make lint > "$temp_lint" 2>&1 || true

    local e501_count=$(grep -c "E501.*line too long" "$temp_lint" 2>/dev/null || echo "0")
    local f401_count=$(grep -c "F401.*imported but unused" "$temp_lint" 2>/dev/null || echo "0")
    local w293_count=$(grep -c "W293.*blank line contains whitespace" "$temp_lint" 2>/dev/null || echo "0")
    local import_errors=$(find tests/ -name "*.py" -exec grep -l "from src\.knowledge_system" {} \; 2>/dev/null | wc -l | tr -d ' ')

    echo "Auto-fixable issues found:"
    echo "  • $e501_count line length violations (E501)"
    echo "  • $f401_count unused imports (F401)"
    echo "  • $w293_count whitespace issues (W293)"
    echo "  • $import_errors files with wrong import paths"

    local total_fixable=$((e501_count + f401_count + w293_count + import_errors))

    if [[ $total_fixable -gt 0 ]]; then
        echo ""
        print_fix "$total_fixable issues can be automatically fixed"
    else
        print_success "No auto-fixable issues found"
    fi

    rm -f "$temp_lint"
    return $total_fixable
}

# Main execution function
main() {
    print_header "Smart Test Script for Knowledge Chipper"

    if [[ "$DRY_RUN" == "true" ]]; then
        echo "🔍 DRY RUN MODE - No changes will be made"
    fi

    # Step 1: Initial assessment
    print_header "Step 1: Initial Assessment"

    local initial_violations=$(count_lint_violations)
    echo "Current linting violations: $initial_violations"

    # Step 2: Show what can be fixed
    show_fixable_issues
    local fixable_count=$?

    if [[ $fixable_count -eq 0 ]]; then
        print_success "No auto-fixable issues found. Running tests..."
        run_test_summary
        return $?
    fi

    # Step 3: Apply fixes
    print_header "Step 2: Applying Automatic Fixes"

    run_quick_fixes

    # Step 4: Re-test and show results
    print_header "Step 3: Validation"

    run_test_summary
    local final_exit_code=$?

    # Step 5: Summary
    print_header "Summary"

    local final_violations=$(count_lint_violations)
    local total_fixed=$((initial_violations - final_violations))

    if [[ $total_fixed -gt 0 ]]; then
        print_success "Automatically fixed $total_fixed issues"
        echo "  Before: $initial_violations violations"
        echo "  After:  $final_violations violations"
    fi

    if [[ $final_exit_code -eq 0 ]]; then
        echo ""
        print_success "🚀 All tests passing! Ready for release."
    else
        echo ""
        print_warning "Some issues require manual attention:"
        echo ""
        echo "Next steps:"
        echo "  1. Review failing tests: pytest tests/failing_test.py -v"
        echo "  2. Fix remaining violations: ./scripts/handle-test-failures.sh --all"
        echo "  3. Re-run: $0"
    fi

    return $final_exit_code
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --verbose)
            VERBOSE=true
            shift
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

# Run main function
main "$@"
