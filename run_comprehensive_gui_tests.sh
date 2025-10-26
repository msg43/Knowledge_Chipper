#!/bin/bash
#
# Real GUI Test Runner
#
# Runs the full GUI test suite with REAL processing only.
# No fake mode - uses actual whisper.cpp and Ollama.
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

VERBOSE="${VERBOSE:-0}"

print_header() {
    echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ $1${NC}"
}

usage() {
    cat << EOF
Usage: $0 [OPTIONS]

Real GUI Test Runner - No Fake Mode

This script runs comprehensive GUI tests with REAL processing:
- Actual whisper.cpp transcription
- Actual Ollama summarization
- Real file I/O and database operations

Options:
  VERBOSE=1    Show detailed test output

Requirements:
  - whisper.cpp installed (whisper-cli command available)
  - Ollama running with at least one model
  - Python virtual environment with dependencies

Expected Duration: 60-90 minutes

Examples:
  $0                    # Run all real tests
  VERBOSE=1 $0          # Run with verbose output

EOF
    exit 1
}

check_whisper_cpp() {
    print_info "Checking whisper.cpp installation..."
    if command -v whisper-cli &> /dev/null; then
        print_success "whisper.cpp: whisper-cli found"
        return 0
    elif command -v whisper &> /dev/null; then
        print_success "whisper.cpp: whisper found"
        return 0
    else
        print_error "whisper.cpp not found"
        print_info "Install with: brew install whisper-cpp"
        return 1
    fi
}

check_ollama() {
    print_info "Checking Ollama installation..."
    if ! command -v ollama &> /dev/null; then
        print_error "Ollama not found"
        print_info "Install from: https://ollama.com"
        return 1
    fi
    print_success "Ollama: $(ollama --version 2>&1 | head -1)"

    # Check if Ollama is running
    print_info "Checking Ollama service..."
    if ! curl -s http://localhost:11434/api/version > /dev/null 2>&1; then
        print_error "Ollama service not running"
        print_info "Start with: ollama serve"
        return 1
    fi
    print_success "Ollama service: running"

    # Check for available models
    print_info "Checking Ollama models..."
    if ! ollama list | grep -q ":"; then
        print_warning "No Ollama models found"
        print_info "Pull a model with: ollama pull qwen2.5:7b-instruct"
        return 1
    fi
    print_success "Ollama models: $(ollama list | grep -c ':')"

    return 0
}

check_requirements() {
    print_header "Checking Requirements"

    # Check Python
    if ! command -v python3 &> /dev/null; then
        print_error "Python 3 not found"
        exit 1
    fi
    print_success "Python: $(python3 --version)"

    # Check venv
    if [ ! -d "venv" ]; then
        print_warning "Virtual environment not found. Creating..."
        python3 -m venv venv
    fi

    # Activate venv
    source venv/bin/activate

    # Check pytest
    if ! python -m pytest --version &> /dev/null; then
        print_warning "pytest not found. Installing..."
        pip install pytest pytest-timeout pytest-xdist
    fi
    print_success "pytest: $(python -m pytest --version | head -1)"

    # Check PyQt6
    if ! python -c "import PyQt6" 2>/dev/null; then
        print_error "PyQt6 not found. Install requirements: pip install -r requirements.txt"
        exit 1
    fi
    print_success "PyQt6 available"

    # Check whisper.cpp
    if ! check_whisper_cpp; then
        exit 1
    fi

    # Check Ollama
    if ! check_ollama; then
        exit 1
    fi

    print_success "All requirements met"
}

setup_environment() {
    print_header "Setting Up Test Environment"

    # Always set testing mode
    export KNOWLEDGE_CHIPPER_TESTING_MODE=1
    export QT_QPA_PLATFORM=offscreen

    print_success "Testing mode: ENABLED"
    print_success "Offscreen rendering: ENABLED"
    print_warning "Real processing mode: Tests will take 60-90 minutes"

    # Create test output directory
    mkdir -p tests/tmp
    mkdir -p test-results

    print_success "Environment configured"
}

run_real_tests() {
    print_header "Running Real GUI Tests"
    print_warning "This will take 60-90 minutes with real processing"

    local pytest_args=(
        "tests/gui_comprehensive/"
        "-v"
        "--timeout=300"
        "--tb=short"
        "--junit-xml=test-results/gui-tests-real.xml"
    )

    if [ "$VERBOSE" == "1" ]; then
        pytest_args+=("-s")
    fi

    if python -m pytest "${pytest_args[@]}"; then
        print_success "All tests passed"
        return 0
    else
        print_error "Some tests failed"
        return 1
    fi
}

main() {
    if [ "${1:-}" == "-h" ] || [ "${1:-}" == "--help" ]; then
        usage
    fi

    print_header "Real GUI Test Runner"
    print_warning "Tests use REAL processing - no fake mode"

    check_requirements
    setup_environment
    run_real_tests
}

main "$@"
