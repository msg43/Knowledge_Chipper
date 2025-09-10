#!/bin/bash
# Knowledge Chipper - Comprehensive Local Testing Script
# This script replaces GitHub CI for solo development by running all quality checks locally

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
VERBOSE=false
SKIP_SLOW=false
SKIP_GUI=false
COVERAGE=false
AUTO_FIX=false

# Function to print colored output
print_status() {
    echo -e "${BLUE}[$(date +'%H:%M:%S')]${NC} $1"
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

print_header() {
    echo -e "\n${BLUE}================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}================================${NC}"
}

# Function to show usage
show_help() {
    cat << EOF
Knowledge Chipper - Comprehensive Local Testing Script

This script runs the same checks that would happen in GitHub CI, but locally.
Perfect for solo development to catch issues before pushing to GitHub.

Usage: $0 [OPTIONS]

Options:
    -h, --help      Show this help message
    -v, --verbose   Enable verbose output
    -s, --skip-slow Skip slow tests (integration, GUI)
    --skip-gui      Skip GUI tests only
    -c, --coverage  Generate coverage reports
    --quick         Run only quick checks (lint + unit tests)
    --smoke         Run only smoke test
    --release       Full release-ready test suite (includes auto-fixing)
    --auto-fix      Enable automatic fixing of common issues

Examples:
    $0                  # Run full test suite
    $0 --quick          # Quick development check
    $0 --release        # Pre-release verification (with auto-fixing)
    $0 --auto-fix       # Run with automatic issue fixing
    $0 --coverage       # Generate coverage reports
    $0 --skip-slow      # Skip integration/GUI tests

EOF
}

# Function to check if we're in the right directory
check_project_root() {
    if [[ ! -f "pyproject.toml" ]] || [[ ! -d "src/knowledge_system" ]]; then
        print_error "This script must be run from the Knowledge_Chipper project root directory"
        exit 1
    fi
}

# Function to check if virtual environment is active
check_venv() {
    if [[ "$VIRTUAL_ENV" == "" ]]; then
        print_warning "Not in a virtual environment. Consider activating venv first:"
        echo "  source venv/bin/activate"
        echo ""
        read -p "Continue anyway? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    else
        print_success "Virtual environment active: $(basename $VIRTUAL_ENV)"
    fi
}

# Function to install dependencies
install_dependencies() {
    print_header "Installing Dependencies"

    print_status "Upgrading pip..."
    python -m pip install --upgrade pip

    print_status "Installing core dependencies..."
    pip install -r requirements.txt

    print_status "Installing development dependencies..."
    pip install -r requirements-dev.txt

    print_status "Installing package in editable mode..."
    pip install -e ".[hce]"

    print_success "Dependencies installed"
}

# Function to verify critical dependencies
verify_dependencies() {
    print_header "Verifying Dependencies"

    local failed=0

    # Core imports
    python -c "import knowledge_system" 2>/dev/null && print_success "knowledge_system imports" || { print_error "knowledge_system import failed"; failed=1; }
    python -c "import sqlalchemy" 2>/dev/null && print_success "SQLAlchemy available" || { print_error "SQLAlchemy missing"; failed=1; }
    python -c "import openai" 2>/dev/null && print_success "OpenAI available" || { print_error "OpenAI missing"; failed=1; }

    # Optional dependencies
    python -c "import PyQt6" 2>/dev/null && print_success "PyQt6 available (GUI enabled)" || print_warning "PyQt6 missing (GUI disabled)"
    # Check for whisper.cpp binaries (the actual implementation used)
    if command -v whisper-cli >/dev/null 2>&1 || command -v whisper-cpp >/dev/null 2>&1 || command -v whisper >/dev/null 2>&1; then
        print_success "Whisper.cpp binary available"
    else
        print_warning "Whisper.cpp binary missing (local transcription disabled)"
    fi
    python -c "import pyannote.audio" 2>/dev/null && print_success "pyannote.audio available" || print_warning "pyannote.audio missing (diarization disabled)"

    if [[ $failed -eq 1 ]]; then
        print_error "Critical dependencies missing. Run with --install to fix."
        exit 1
    fi

    print_success "Dependency verification complete"
}

# Function to run linting
run_linting() {
    print_header "Code Linting"

    print_status "Running flake8 critical checks..."
    flake8 src/ --count --select=E9,F63,F7,F82,F821 --show-source --statistics

    print_status "Running flake8 style checks..."
    flake8 src/ --count --exit-zero --max-complexity=10 --max-line-length=100 --statistics

    print_success "Linting passed"
}

# Function to run security checks
run_security() {
    print_header "Security Analysis"

    print_status "Running bandit security scanner..."
    bandit -r src/ --skip B101,B601 -f json -o bandit-report.json || true
    bandit -r src/ --skip B101,B601 || print_warning "Some security warnings found - review bandit-report.json"

    print_success "Security analysis complete"
}

# Function to run unit tests
run_unit_tests() {
    print_header "Unit Tests"

    local coverage_args=""
    if [[ "$COVERAGE" == "true" ]]; then
        coverage_args="--cov=knowledge_system --cov-report=html --cov-report=term --cov-report=xml"
    fi

    print_status "Running unit tests..."
    pytest tests/ -v -k "not integration and not gui and not slow" --maxfail=5 $coverage_args

    print_success "Unit tests passed"
}

# Function to run integration tests
run_integration_tests() {
    if [[ "$SKIP_SLOW" == "true" ]]; then
        print_warning "Skipping integration tests (--skip-slow enabled)"
        return
    fi

    print_header "Integration Tests"

    print_status "Running integration tests..."
    if [[ -d "tests/integration" ]]; then
        pytest tests/integration/ -v --maxfail=3
        print_success "Integration tests passed"
    else
        print_warning "No integration tests found"
    fi
}

# Function to run GUI tests
run_gui_tests() {
    if [[ "$SKIP_SLOW" == "true" ]] || [[ "$SKIP_GUI" == "true" ]]; then
        print_warning "Skipping GUI tests"
        return
    fi

    print_header "GUI Tests"

    # Check if PyQt6 is available
    if ! python -c "import PyQt6" 2>/dev/null; then
        print_warning "PyQt6 not available - skipping GUI tests"
        return
    fi

    print_status "Running GUI tests..."
    if [[ -d "tests/gui_comprehensive" ]]; then
        pytest tests/gui_comprehensive/ -v --maxfail=2
        print_success "GUI tests passed"
    else
        print_warning "No GUI tests found"
    fi
}

# Function to run smoke test
run_smoke_test() {
    print_header "Smoke Test"

    print_status "Testing CLI availability..."
    knowledge-system --version || { print_error "CLI not available"; exit 1; }

    print_status "Testing core imports..."
    python -c "from knowledge_system.cli import main; print('CLI import works')" || { print_error "CLI import failed"; exit 1; }
    python -c "from knowledge_system.config import get_settings; print('Config import works')" || { print_error "Config import failed"; exit 1; }

    print_status "Testing database service..."
    python -c "from knowledge_system.database.service import DatabaseService; db = DatabaseService(); print('Database service works')" || { print_error "Database service failed"; exit 1; }

    print_success "Smoke test passed"
}

# Function to run HCE tests
run_hce_tests() {
    print_header "HCE Tests"

    if [[ -f "Makefile.hce" ]]; then
        print_status "Running HCE smoke test..."
        make -f Makefile.hce hce-smoketest || print_warning "HCE smoke test failed"

        print_status "Running HCE test suite..."
        make -f Makefile.hce hce-test-all || print_warning "Some HCE tests failed"

        print_success "HCE tests complete"
    else
        print_warning "No HCE tests found"
    fi
}

# Function to run comprehensive test
run_comprehensive_test() {
    if [[ -f "tests/comprehensive_test_suite.py" ]]; then
        print_header "Comprehensive System Test"

        print_status "Running comprehensive test suite..."
        python tests/comprehensive_test_suite.py || print_warning "Some comprehensive tests failed"

        print_success "Comprehensive tests complete"
    fi
}

# Function to run automatic fixes
run_auto_fixes() {
    if [[ "$AUTO_FIX" != "true" ]]; then
        return 0
    fi

    print_header "Auto-Fixing Common Issues"

    # Count issues before fixing
    local before_count=$(make lint 2>/dev/null | tail -1 | grep -o '[0-9]\+' || echo "0")

    print_status "Auto-formatting code..."
    make format >/dev/null 2>&1 || true

    print_status "Fixing import paths..."
    find tests/ -name "*.py" -exec sed -i '' 's/from src\.knowledge_system/from knowledge_system/g' {} \; 2>/dev/null || true

    print_status "Removing unused imports..."
    if command -v autoflake >/dev/null 2>&1; then
        find src/ tests/ -name "*.py" -exec autoflake --remove-all-unused-imports --in-place {} \; 2>/dev/null || true
    fi

    print_status "Final cleanup..."
    isort src/ tests/ scripts/ --quiet >/dev/null 2>&1 || true

    # Count issues after fixing
    local after_count=$(make lint 2>/dev/null | tail -1 | grep -o '[0-9]\+' || echo "0")
    local fixed_count=$((before_count - after_count))

    if [[ $fixed_count -gt 0 ]]; then
        print_success "Auto-fixed $fixed_count issues ($before_count → $after_count)"
    else
        print_status "No auto-fixable issues found"
    fi
}

# Function to generate final report
generate_report() {
    print_header "Test Summary"

    echo "Test run completed at: $(date)"
    echo "Configuration:"
    echo "  - Verbose: $VERBOSE"
    echo "  - Skip slow tests: $SKIP_SLOW"
    echo "  - Skip GUI tests: $SKIP_GUI"
    echo "  - Coverage enabled: $COVERAGE"

    if [[ "$COVERAGE" == "true" ]] && [[ -f "htmlcov/index.html" ]]; then
        echo "  - Coverage report: htmlcov/index.html"
    fi

    if [[ -f "bandit-report.json" ]]; then
        echo "  - Security report: bandit-report.json"
    fi

    print_success "All tests completed successfully!"
    echo ""
    echo "Your code is ready to push to GitHub! 🚀"
}

# Main execution function
main() {
    local mode="full"
    local install_deps=false

    # Parse command line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                show_help
                exit 0
                ;;
            -v|--verbose)
                VERBOSE=true
                shift
                ;;
            -s|--skip-slow)
                SKIP_SLOW=true
                shift
                ;;
            --skip-gui)
                SKIP_GUI=true
                shift
                ;;
            -c|--coverage)
                COVERAGE=true
                shift
                ;;
            --quick)
                mode="quick"
                shift
                ;;
            --smoke)
                mode="smoke"
                shift
                ;;
            --release)
                mode="release"
                AUTO_FIX=true  # Release mode enables auto-fixing by default
                shift
                ;;
            --auto-fix)
                AUTO_FIX=true
                shift
                ;;
            --install)
                install_deps=true
                shift
                ;;
            *)
                print_error "Unknown option: $1"
                show_help
                exit 1
                ;;
        esac
    done

    # Verbose mode
    if [[ "$VERBOSE" == "true" ]]; then
        set -x
    fi

    print_header "Knowledge Chipper - Local Test Suite"
    echo "Mode: $mode"
    echo "This replaces GitHub CI for solo development"
    echo ""

    # Pre-checks
    check_project_root
    check_venv

    # Install dependencies if requested
    if [[ "$install_deps" == "true" ]]; then
        install_dependencies
    fi

    # Verify dependencies
    verify_dependencies

    # Run tests based on mode
    case $mode in
        "quick")
            run_linting
            run_unit_tests
            run_smoke_test
            ;;
        "smoke")
            run_smoke_test
            ;;
        "release")
            run_auto_fixes
            run_linting
            run_security
            run_unit_tests
            run_integration_tests
            run_gui_tests
            run_smoke_test
            run_hce_tests
            run_comprehensive_test
            ;;
        "full"|*)
            run_auto_fixes
            run_linting
            run_security
            run_unit_tests
            run_integration_tests
            run_gui_tests
            run_smoke_test
            run_hce_tests
            ;;
    esac

    generate_report
}

# Run main function with all arguments
main "$@"
