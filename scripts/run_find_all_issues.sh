#!/bin/bash

# Comprehensive Test Runner - Find ALL Issues Mode
# Runs all three comprehensive test suites and reports ALL failures for parallel fixing

set -e

echo "🔍 Comprehensive Test Suite - Find ALL Issues Mode"
echo "================================================="
echo "This will run ALL tests and report ALL failures so you can fix them in parallel."
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[$(date '+%H:%M:%S')]${NC} $1"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

# Check if pytest is available
if ! command -v pytest &> /dev/null; then
    print_error "pytest is not installed or not in PATH"
    exit 1
fi

# Check if we're in the right directory
if [ ! -f "pyproject.toml" ]; then
    print_error "Not in project root directory"
    exit 1
fi

# Check if comprehensive tests exist
if [ ! -d "tests/comprehensive" ]; then
    print_error "Comprehensive test directory not found"
    exit 1
fi

print_status "Running comprehensive test suite to find ALL issues..."
echo ""

# Run all three comprehensive test files with detailed reporting
# NO early exit - let all tests run to find all issues
pytest tests/comprehensive/test_real_gui_complete.py tests/comprehensive/test_real_integration_complete.py tests/comprehensive/test_real_system2_complete.py \
    -v \
    --tb=long \
    --capture=no \
    --log-cli-level=DEBUG \
    --log-cli-format="%(asctime)s [%(levelname)8s] %(name)s: %(message)s" \
    --log-cli-date-format="%H:%M:%S" \
    --durations=10 \
    --color=yes \
    --strict-markers \
    --junitxml=test-results/comprehensive_results.xml \
    --html=test-results/comprehensive_report.html \
    --self-contained-html

# Capture exit code
EXIT_CODE=$?

echo ""
echo "=================================="
if [ $EXIT_CODE -eq 0 ]; then
    print_success "🎉 ALL COMPREHENSIVE TESTS PASSED!"
else
    print_warning "🔍 Test suite completed with failures - Check results above"
    print_status "All issues have been identified for parallel fixing"
fi
print_status "Test suite finished at $(date)"
print_status "Results saved to test-results/"
echo "=================================="

# Exit with the pytest exit code so CI/CD systems know if tests passed
exit $EXIT_CODE
