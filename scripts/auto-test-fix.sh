#!/bin/bash
# Auto Test Fix - Simple script that runs tests and fixes what it can

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m' # No Color

print_header() {
    echo -e "\n${BLUE}=== $1 ===${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_fix() {
    echo -e "${PURPLE}🔧 $1${NC}"
}

# Function to count current issues
count_issues() {
    local lint_count=$(make lint 2>/dev/null | tail -1 | grep -o '[0-9]\+' || echo "0")
    local import_issues=$(find tests/ -name "*.py" -exec grep -l "from src\.knowledge_system" {} \; 2>/dev/null | wc -l | tr -d ' ')
    echo "$((lint_count + import_issues))"
}

print_header "Auto Test Fix for Knowledge Chipper"

# Check if this is a dry run
if [[ "$1" == "--dry-run" ]]; then
    echo "🔍 DRY RUN MODE - showing what would be fixed"
    echo ""

    current_issues=$(count_issues)
    echo "Current issues: $current_issues"

    echo ""
    echo "Would apply these fixes:"
    echo "  • Auto-format code (black + isort)"
    echo "  • Fix import paths (src.knowledge_system → knowledge_system)"
    echo "  • Remove unused imports"
    echo "  • Clean whitespace"
    echo ""
    echo "Run without --dry-run to apply fixes"
    exit 0
fi

# Step 1: Show current state
print_header "Current State"
before_issues=$(count_issues)
echo "Issues before fixes: $before_issues"

if [[ $before_issues -eq 0 ]]; then
    print_success "No issues found! Running quick test..."
    ./scripts/full-test.sh --quick
    exit $?
fi

# Step 2: Apply automatic fixes
print_header "Applying Automatic Fixes"

print_fix "Auto-formatting code..."
make format >/dev/null 2>&1

print_fix "Fixing import paths..."
find tests/ -name "*.py" -exec sed -i '' 's/from src\.knowledge_system/from knowledge_system/g' {} \; 2>/dev/null || true

print_fix "Removing unused imports..."
if command -v autoflake >/dev/null 2>&1; then
    find src/ tests/ -name "*.py" -exec autoflake --remove-all-unused-imports --in-place {} \; 2>/dev/null || true
fi

print_fix "Final cleanup..."
isort src/ tests/ scripts/ --quiet >/dev/null 2>&1 || true

# Step 3: Show results
print_header "Results"
after_issues=$(count_issues)
fixed_issues=$((before_issues - after_issues))

if [[ $fixed_issues -gt 0 ]]; then
    print_success "Fixed $fixed_issues issues ($before_issues → $after_issues)"
else
    echo "No issues were auto-fixable"
fi

# Step 4: Run tests
print_header "Running Tests"
./scripts/full-test.sh --quick

test_exit_code=$?

if [[ $test_exit_code -eq 0 ]]; then
    print_success "🚀 All tests passing! Ready for release."
else
    echo ""
    echo "Some issues require manual attention. Use:"
    echo "  ./scripts/handle-test-failures.sh --all"
fi

exit $test_exit_code
