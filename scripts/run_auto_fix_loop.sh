#!/bin/bash

# Comprehensive Test Runner - Auto-Fix Loop Mode
# Runs tests, attempts to fix issues automatically, then re-runs until all clear

set -e

echo "🤖 Comprehensive Test Suite - Auto-Fix Loop Mode"
echo "==============================================="
echo "This will run tests, attempt to fix issues automatically, then re-run until all clear."
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
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

print_fix() {
    echo -e "${PURPLE}🔧 $1${NC}"
}

# Configuration
MAX_ITERATIONS=10
ITERATION=1
FAILURE_COUNT=0
TOTAL_FIXES=0

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

# Function to run tests and capture results
run_tests() {
    local iteration=$1
    print_status "Iteration $iteration: Running comprehensive test suite..."

    # Run tests and capture output
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
        --junitxml=test-results/comprehensive_results_${iteration}.xml \
        --html=test-results/comprehensive_report_${iteration}.html \
        --self-contained-html 2>&1 | tee test-results/test_output_${iteration}.log

    return $?
}

# Function to analyze test failures and attempt fixes
attempt_fixes() {
    local iteration=$1
    local fixes_applied=0

    print_fix "Analyzing failures from iteration $iteration..."

    # Check for common issues and attempt fixes

    # 1. Import errors
    if grep -q "ImportError\|ModuleNotFoundError" test-results/test_output_${iteration}.log; then
        print_fix "Found import errors - attempting to fix..."
        # Try to install missing dependencies
        if grep -q "No module named" test-results/test_output_${iteration}.log; then
            print_fix "Installing missing Python packages..."
            pip install -r requirements.txt --quiet
            fixes_applied=$((fixes_applied + 1))
        fi
    fi

    # 2. Database connection issues
    if grep -q "database\|sqlite\|connection" test-results/test_output_${iteration}.log; then
        print_fix "Found database issues - attempting to fix..."
        # Try to reset database
        if [ -f "knowledge_system.db" ]; then
            print_fix "Backing up and resetting database..."
            cp knowledge_system.db knowledge_system.db.backup.$(date +%Y%m%d_%H%M%S)
            rm -f knowledge_system.db
            fixes_applied=$((fixes_applied + 1))
        fi
    fi

    # 3. File permission issues
    if grep -q "PermissionError\|permission denied" test-results/test_output_${iteration}.log; then
        print_fix "Found permission issues - attempting to fix..."
        # Fix file permissions
        chmod -R 755 tests/
        chmod -R 755 test-results/
        fixes_applied=$((fixes_applied + 1))
    fi

    # 4. Missing test files
    if grep -q "FileNotFoundError\|No such file" test-results/test_output_${iteration}.log; then
        print_fix "Found missing file issues - attempting to fix..."
        # Ensure test directories exist
        mkdir -p test-results
        mkdir -p tests/fixtures/sample_files
        fixes_applied=$((fixes_applied + 1))
    fi

    # 5. Ollama connection issues
    if grep -q "ollama\|connection.*refused\|timeout" test-results/test_output_${iteration}.log; then
        print_fix "Found Ollama connection issues - attempting to fix..."
        # Try to start Ollama service
        if command -v ollama &> /dev/null; then
            print_fix "Starting Ollama service..."
            ollama serve &
            sleep 5
            fixes_applied=$((fixes_applied + 1))
        fi
    fi

    # 6. GUI test issues
    if grep -q "GUI\|QApplication\|display" test-results/test_output_${iteration}.log; then
        print_fix "Found GUI issues - attempting to fix..."
        # Set display for GUI tests
        export DISPLAY=:0
        export QT_QPA_PLATFORM=offscreen
        fixes_applied=$((fixes_applied + 1))
    fi

    # 7. Memory issues
    if grep -q "MemoryError\|out of memory" test-results/test_output_${iteration}.log; then
        print_fix "Found memory issues - attempting to fix..."
        # Clear Python cache
        find . -name "*.pyc" -delete
        find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
        fixes_applied=$((fixes_applied + 1))
    fi

    # 8. Configuration issues
    if grep -q "config\|settings\|yaml" test-results/test_output_${iteration}.log; then
        print_fix "Found configuration issues - attempting to fix..."
        # Reset configuration
        if [ -f "config/settings.yaml" ]; then
            print_fix "Backing up and resetting configuration..."
            cp config/settings.yaml config/settings.yaml.backup.$(date +%Y%m%d_%H%M%S)
            # Could add logic to reset to defaults here
            fixes_applied=$((fixes_applied + 1))
        fi
    fi

    echo "Applied $fixes_applied fixes in iteration $iteration"
    return $fixes_applied
}

# Main loop
while [ $ITERATION -le $MAX_ITERATIONS ]; do
    echo ""
    print_status "🔄 Starting iteration $ITERATION of $MAX_ITERATIONS"
    echo "=================================================="

    # Run tests
    run_tests $ITERATION
    TEST_EXIT_CODE=$?

    if [ $TEST_EXIT_CODE -eq 0 ]; then
        print_success "🎉 ALL TESTS PASSED in iteration $ITERATION!"
        print_success "Total fixes applied: $TOTAL_FIXES"
        print_success "Test suite completed successfully at $(date)"
        exit 0
    else
        print_warning "Tests failed in iteration $ITERATION"
        FAILURE_COUNT=$((FAILURE_COUNT + 1))

        # Attempt to fix issues
        attempt_fixes $ITERATION
        FIXES_APPLIED=$?
        TOTAL_FIXES=$((TOTAL_FIXES + FIXES_APPLIED))

        if [ $FIXES_APPLIED -eq 0 ]; then
            print_error "No automatic fixes could be applied"
            print_error "Manual intervention required"
            break
        fi

        print_fix "Applied $FIXES_APPLIED fixes, proceeding to next iteration..."
    fi

    ITERATION=$((ITERATION + 1))
done

echo ""
echo "=================================="
if [ $ITERATION -gt $MAX_ITERATIONS ]; then
    print_error "❌ Maximum iterations ($MAX_ITERATIONS) reached"
    print_error "Some issues may require manual intervention"
else
    print_error "❌ Auto-fix loop stopped - manual intervention required"
fi
print_status "Total iterations: $((ITERATION - 1))"
print_status "Total fixes applied: $TOTAL_FIXES"
print_status "Final test results saved to test-results/"
echo "=================================="

exit 1
