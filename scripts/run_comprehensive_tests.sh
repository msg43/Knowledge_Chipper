#!/bin/bash

# Comprehensive Test Runner with Real-time Reporting
# Runs all three comprehensive test suites with detailed debugging

set -e

echo "🧪 Starting Comprehensive Test Suite"
echo "=================================="
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

print_status "Running comprehensive test suite with real-time reporting..."
echo ""

# Test 1: GUI Complete Tests
print_status "Test 1/3: GUI Complete Tests (Real GUI + Real Data + Real Outputs)"
echo "=================================================================="
pytest tests/comprehensive/test_real_gui_complete.py \
    -v \
    --tb=long \
    --capture=no \
    --log-cli-level=DEBUG \
    --log-cli-format="%(asctime)s [%(levelname)8s] %(name)s: %(message)s" \
    --log-cli-date-format="%H:%M:%S" \
    --durations=10 \
    --color=yes \
    --strict-markers

if [ $? -eq 0 ]; then
    print_success "GUI Complete Tests PASSED"
else
    print_warning "GUI Complete Tests FAILED - Continuing to find all issues..."
fi

echo ""
print_status "Test 2/3: Integration Complete Tests (Real Files + Real Processing + Real Database)"
echo "========================================================================================"
pytest tests/comprehensive/test_real_integration_complete.py \
    -v \
    --tb=long \
    --capture=no \
    --log-cli-level=DEBUG \
    --log-cli-format="%(asctime)s [%(levelname)8s] %(name)s: %(message)s" \
    --log-cli-date-format="%H:%M:%S" \
    --durations=10 \
    --color=yes \
    --strict-markers

if [ $? -eq 0 ]; then
    print_success "Integration Complete Tests PASSED"
else
    print_warning "Integration Complete Tests FAILED - Continuing to find all issues..."
fi

echo ""
print_status "Test 3/3: System2 Complete Tests (Real Orchestration + Real LLM + Real Checkpointing)"
echo "=========================================================================================="
pytest tests/comprehensive/test_real_system2_complete.py \
    -v \
    --tb=long \
    --capture=no \
    --log-cli-level=DEBUG \
    --log-cli-format="%(asctime)s [%(levelname)8s] %(name)s: %(message)s" \
    --log-cli-date-format="%H:%M:%S" \
    --durations=10 \
    --color=yes \
    --strict-markers

if [ $? -eq 0 ]; then
    print_success "System2 Complete Tests PASSED"
else
    print_warning "System2 Complete Tests FAILED - Continuing to find all issues..."
fi

echo ""
echo "=================================="
print_status "🔍 All tests completed - Check results above for any failures"
print_status "Test suite finished at $(date)"
echo "=================================="
