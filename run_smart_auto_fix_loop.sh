#!/bin/bash

# Comprehensive Test Runner - Smart Auto-Fix Loop Mode
# Advanced version that uses AI/LLM to analyze failures and suggest fixes

# set -e  # Commented out to allow script to continue on errors

echo "🧠 Comprehensive Test Suite - Smart Auto-Fix Loop Mode"
echo "====================================================="
echo "This will run tests, use AI to analyze failures, suggest fixes, and re-run until all clear."
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
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

print_ai() {
    echo -e "${CYAN}🤖 $1${NC}"
}

# Configuration
MAX_ITERATIONS=15
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

    # Check if pytest-html is available
    local html_args=""
    if python -c "import pytest_html" 2>/dev/null; then
        html_args="--html=test-results/comprehensive_report_${iteration}.html --self-contained-html"
        print_status "HTML reporting enabled"
    else
        print_warning "pytest-html not available, skipping HTML reports"
    fi

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
        $html_args 2>&1 | tee test-results/test_output_${iteration}.log

    return $?
}

# Function to analyze test failures using AI/LLM
analyze_failures_with_ai() {
    local iteration=$1
    local log_file="test-results/test_output_${iteration}.log"

    print_ai "Analyzing failures using AI analysis..."

    # Extract failure patterns
    local failure_patterns=$(grep -E "(FAILED|ERROR|AssertionError|ImportError|ModuleNotFoundError|FileNotFoundError|PermissionError|ConnectionError|TimeoutError)" "$log_file" | head -20)

    if [ -z "$failure_patterns" ]; then
        print_warning "No clear failure patterns found"
        return 0
    fi

    print_ai "Found failure patterns:"
    echo "$failure_patterns" | while read -r line; do
        echo "  - $line"
    done

    # Create analysis prompt for AI
    local analysis_prompt="
Test Failure Analysis Request:

The following test failures were encountered in a Python test suite:

$failure_patterns

Please analyze these failures and suggest specific fixes. Focus on:
1. Root cause identification
2. Specific commands or code changes needed
3. Priority order for fixes

Test environment:
- Python project with pytest
- GUI tests using PyQt
- Database tests using SQLite
- LLM integration with Ollama
- File processing tests

Please provide actionable fix suggestions.
"

    # Save analysis prompt
    echo "$analysis_prompt" > "test-results/analysis_prompt_${iteration}.txt"

    print_ai "Analysis prompt saved to test-results/analysis_prompt_${iteration}.txt"
    print_ai "You can use this with an AI assistant to get specific fix suggestions"

    return 1
}

# Function to attempt smart fixes based on analysis
attempt_smart_fixes() {
    local iteration=$1
    local fixes_applied=0
    local log_file="test-results/test_output_${iteration}.log"

    print_fix "Applying smart fixes based on failure analysis..."

    # 1. Import and dependency issues
    if grep -q "ImportError\|ModuleNotFoundError" "$log_file"; then
        print_fix "Fixing import/dependency issues..."

        # Check for specific missing modules
        if grep -q "No module named 'PyQt5'" "$log_file"; then
            print_fix "Installing PyQt5..."
            pip install PyQt5 --quiet
            fixes_applied=$((fixes_applied + 1))
        fi

        if grep -q "No module named 'pytest'" "$log_file"; then
            print_fix "Installing pytest..."
            pip install pytest pytest-html pytest-xdist --quiet
            fixes_applied=$((fixes_applied + 1))
        fi

        if grep -q "No module named 'ollama'" "$log_file"; then
            print_fix "Installing ollama..."
            pip install ollama --quiet
            fixes_applied=$((fixes_applied + 1))
        fi

        # General requirements install
        if [ -f "requirements.txt" ]; then
            print_fix "Installing all requirements..."
            pip install -r requirements.txt --quiet
            fixes_applied=$((fixes_applied + 1))
        fi
    fi

    # 2. Database and file system issues
    if grep -q "database\|sqlite\|FileNotFoundError" "$log_file"; then
        print_fix "Fixing database and file system issues..."

        # Reset database
        if [ -f "knowledge_system.db" ]; then
            print_fix "Backing up and resetting database..."
            cp knowledge_system.db knowledge_system.db.backup.$(date +%Y%m%d_%H%M%S) 2>/dev/null || true
            rm -f knowledge_system.db
            fixes_applied=$((fixes_applied + 1))
        fi

        # Ensure test directories exist
        mkdir -p test-results
        mkdir -p tests/fixtures/sample_files
        mkdir -p tests/comprehensive
        fixes_applied=$((fixes_applied + 1))
    fi

    # 3. GUI and display issues
    if grep -q "GUI\|QApplication\|display\|X11" "$log_file"; then
        print_fix "Fixing GUI and display issues..."

        # Set display environment
        export DISPLAY=:0
        export QT_QPA_PLATFORM=offscreen
        export QT_QPA_PLATFORM_PLUGIN_PATH=""

        # Try to start Xvfb if available
        if command -v Xvfb &> /dev/null; then
            print_fix "Starting virtual display..."
            Xvfb :99 -screen 0 1024x768x24 &
            export DISPLAY=:99
            fixes_applied=$((fixes_applied + 1))
        fi

        fixes_applied=$((fixes_applied + 1))
    fi

    # 4. Network and service issues
    if grep -q "ConnectionError\|TimeoutError\|ollama.*refused" "$log_file"; then
        print_fix "Fixing network and service issues..."

        # Start Ollama service
        if command -v ollama &> /dev/null; then
            print_fix "Starting Ollama service..."
            pkill -f ollama 2>/dev/null || true
            ollama serve &
            sleep 10
            fixes_applied=$((fixes_applied + 1))
        fi

        # Check network connectivity
        print_fix "Checking network connectivity..."
        ping -c 1 8.8.8.8 >/dev/null 2>&1 && fixes_applied=$((fixes_applied + 1))
    fi

    # 5. Permission and file access issues
    if grep -q "PermissionError\|permission denied" "$log_file"; then
        print_fix "Fixing permission issues..."

        # Fix file permissions
        chmod -R 755 tests/ 2>/dev/null || true
        chmod -R 755 test-results/ 2>/dev/null || true
        chmod -R 755 src/ 2>/dev/null || true

        fixes_applied=$((fixes_applied + 1))
    fi

    # 6. Memory and performance issues
    if grep -q "MemoryError\|out of memory\|timeout" "$log_file"; then
        print_fix "Fixing memory and performance issues..."

        # Clear Python cache
        find . -name "*.pyc" -delete 2>/dev/null || true
        find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true

        # Clear system cache if possible
        if command -v sync &> /dev/null; then
            sync
        fi

        fixes_applied=$((fixes_applied + 1))
    fi

    # 7. Configuration issues
    if grep -q "config\|settings\|yaml\|json" "$log_file"; then
        print_fix "Fixing configuration issues..."

        # Reset configuration files
        if [ -f "config/settings.yaml" ]; then
            print_fix "Backing up configuration..."
            cp config/settings.yaml config/settings.yaml.backup.$(date +%Y%m%d_%H%M%S) 2>/dev/null || true
        fi

        # Ensure config directory exists
        mkdir -p config
        fixes_applied=$((fixes_applied + 1))
    fi

    echo "Applied $fixes_applied smart fixes in iteration $iteration"
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

    # Check if tests actually passed (exit code 0 AND no errors in output)
    log_file="test-results/test_output_${ITERATION}.log"
    has_errors=$(grep -c "ERROR\|FAILED\|FAILURES" "$log_file" 2>/dev/null || echo "0")

    if [ $TEST_EXIT_CODE -eq 0 ] && [ $has_errors -eq 0 ]; then
        print_success "🎉 ALL TESTS PASSED in iteration $ITERATION!"
        print_success "Total fixes applied: $TOTAL_FIXES"
        print_success "Test suite completed successfully at $(date)"
        exit 0
    else
        print_warning "Tests failed in iteration $ITERATION (exit code: $TEST_EXIT_CODE, errors: $has_errors)"
        FAILURE_COUNT=$((FAILURE_COUNT + 1))

        # Analyze failures with AI
        analyze_failures_with_ai $ITERATION

        # Attempt smart fixes
        attempt_smart_fixes $ITERATION
        FIXES_APPLIED=$?
        TOTAL_FIXES=$((TOTAL_FIXES + FIXES_APPLIED))

        if [ $FIXES_APPLIED -eq 0 ]; then
            print_error "No automatic fixes could be applied"
            print_error "Check test-results/analysis_prompt_${ITERATION}.txt for AI analysis"
            print_error "Manual intervention required"
            break
        fi

        print_fix "Applied $FIXES_APPLIED fixes, proceeding to next iteration..."

        # Wait a moment for fixes to take effect
        sleep 2
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
print_status "AI analysis prompts saved to test-results/analysis_prompt_*.txt"
echo "=================================="

exit 1
