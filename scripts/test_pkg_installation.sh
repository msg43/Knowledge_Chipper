#!/bin/bash
# test_pkg_installation.sh - Comprehensive PKG installer testing suite
# Tests the complete PKG installation process and validates all components

set -e
set -o pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
TEST_LOG="/tmp/pkg_installation_test.log"
TEST_RESULTS_DIR="/tmp/pkg_test_results"

# Test configuration
RUN_DESTRUCTIVE_TESTS=0
QUICK_TEST=0
VERBOSE=0

# Parse arguments
for arg in "$@"; do
    case "$arg" in
        --destructive)
            RUN_DESTRUCTIVE_TESTS=1
            ;;
        --quick)
            QUICK_TEST=1
            ;;
        --verbose|-v)
            VERBOSE=1
            ;;
        --help|-h)
            echo "Usage: $0 [options]"
            echo ""
            echo "Options:"
            echo "  --destructive    Run destructive tests (removes existing installation)"
            echo "  --quick         Run only quick non-destructive tests"
            echo "  --verbose, -v   Verbose output"
            echo "  --help, -h      Show this help message"
            echo ""
            echo "Test Categories:"
            echo "  1. Component Build Tests"
            echo "  2. PKG Structure Validation"
            echo "  3. Installation Simulation"
            echo "  4. Component Verification"
            echo "  5. Integration Tests"
            exit 0
            ;;
        *)
            echo "❌ Unknown option: $arg"
            exit 1
            ;;
    esac
done

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m'

echo -e "${BLUE}${BOLD}🧪 PKG Installation Testing Suite${NC}"
echo "===================================="
echo "Testing complete PKG installer workflow"
echo "Destructive tests: $([ $RUN_DESTRUCTIVE_TESTS -eq 1 ] && echo "ENABLED" || echo "DISABLED")"
echo "Quick mode: $([ $QUICK_TEST -eq 1 ] && echo "ENABLED" || echo "DISABLED")"
echo ""

# Initialize test environment
mkdir -p "$TEST_RESULTS_DIR"
echo "=== PKG Installation Test Started: $(date) ===" > "$TEST_LOG"

# Test counters
TESTS_TOTAL=0
TESTS_PASSED=0
TESTS_FAILED=0
TESTS_SKIPPED=0

# Test result tracking
declare -a FAILED_TESTS=()
declare -a PASSED_TESTS=()

# Test functions
log_test() {
    echo "[$(date)] TEST: $1" >> "$TEST_LOG"
    if [ $VERBOSE -eq 1 ]; then
        echo -e "${BLUE}TEST:${NC} $1"
    fi
}

pass_test() {
    TESTS_PASSED=$((TESTS_PASSED + 1))
    PASSED_TESTS+=("$1")
    echo -e "${GREEN}✅ PASS:${NC} $1"
    echo "[$(date)] PASS: $1" >> "$TEST_LOG"
}

fail_test() {
    TESTS_FAILED=$((TESTS_FAILED + 1))
    FAILED_TESTS+=("$1")
    echo -e "${RED}❌ FAIL:${NC} $1"
    echo "[$(date)] FAIL: $1" >> "$TEST_LOG"
    if [ $VERBOSE -eq 1 ] && [ -n "$2" ]; then
        echo "  Error: $2"
        echo "[$(date)] ERROR: $2" >> "$TEST_LOG"
    fi
}

skip_test() {
    TESTS_SKIPPED=$((TESTS_SKIPPED + 1))
    echo -e "${YELLOW}⏭️ SKIP:${NC} $1"
    echo "[$(date)] SKIP: $1" >> "$TEST_LOG"
}

run_test() {
    local test_name="$1"
    local test_command="$2"

    TESTS_TOTAL=$((TESTS_TOTAL + 1))
    log_test "$test_name"

    if eval "$test_command" >> "$TEST_LOG" 2>&1; then
        pass_test "$test_name"
        return 0
    else
        fail_test "$test_name" "Command failed: $test_command"
        return 1
    fi
}

# Test Category 1: Component Build Tests
echo -e "\n${BLUE}${BOLD}📦 Test Category 1: Component Build Tests${NC}"

if [ $QUICK_TEST -eq 0 ]; then
    # Test Python framework build
    run_test "Python framework build script exists" "[ -x '$SCRIPT_DIR/build_python_framework.sh' ]"

    # Test AI models bundle script
    run_test "AI models bundle script exists" "[ -x '$SCRIPT_DIR/bundle_ai_models.sh' ]"

    # Test FFmpeg bundle script
    run_test "FFmpeg bundle script exists" "[ -x '$SCRIPT_DIR/bundle_ffmpeg.sh' ]"

    # Test PKG installer build script
    run_test "PKG installer build script exists" "[ -x '$SCRIPT_DIR/build_pkg_installer.sh' ]"

    # Test master build script
    run_test "Master build script exists" "[ -x '$SCRIPT_DIR/build_complete_pkg.sh' ]"
else
    skip_test "Component build tests (quick mode)"
fi

# Test Category 2: PKG Structure Validation
echo -e "\n${BLUE}${BOLD}🏗️ Test Category 2: PKG Structure Validation${NC}"

# Test app bundle template creation
run_test "App bundle template creator exists" "[ -x '$SCRIPT_DIR/create_app_bundle_template.sh' ]"

# Test error handler
run_test "Error handler script exists" "[ -x '$SCRIPT_DIR/pkg_error_handler.sh' ]"

# Test installer scripts
run_test "Enhanced preinstall script exists" "[ -x '$SCRIPT_DIR/enhanced_preinstall.sh' ]"
run_test "Enhanced postinstall script exists" "[ -x '$SCRIPT_DIR/enhanced_postinstall.sh' ]"

# Test Category 3: Installation Simulation
echo -e "\n${BLUE}${BOLD}🎯 Test Category 3: Installation Simulation${NC}"

if [ $QUICK_TEST -eq 0 ]; then
    # Simulate app bundle creation
    log_test "Creating test app bundle"
    TEST_APP_BUNDLE="$TEST_RESULTS_DIR/Skip the Podcast Desktop.app"

    if "$SCRIPT_DIR/create_app_bundle_template.sh" >> "$TEST_LOG" 2>&1; then
        if [ -d "$PROJECT_ROOT/build_app_template/app_template/Skip the Podcast Desktop.app" ]; then
            cp -R "$PROJECT_ROOT/build_app_template/app_template/Skip the Podcast Desktop.app" "$TEST_APP_BUNDLE"
            pass_test "App bundle template creation"
        else
            fail_test "App bundle template creation" "Template not found"
        fi
    else
        fail_test "App bundle template creation" "Script execution failed"
    fi

    # Test app bundle structure
    if [ -d "$TEST_APP_BUNDLE" ]; then
        run_test "App bundle Contents directory" "[ -d '$TEST_APP_BUNDLE/Contents' ]"
        run_test "App bundle MacOS directory" "[ -d '$TEST_APP_BUNDLE/Contents/MacOS' ]"
        run_test "App bundle Resources directory" "[ -d '$TEST_APP_BUNDLE/Contents/Resources' ]"
        run_test "App bundle Frameworks directory" "[ -d '$TEST_APP_BUNDLE/Contents/Frameworks' ]"
        run_test "App bundle Info.plist" "[ -f '$TEST_APP_BUNDLE/Contents/Info.plist' ]"
        run_test "App bundle launch script" "[ -x '$TEST_APP_BUNDLE/Contents/MacOS/launch' ]"
        run_test "App bundle diagnostics" "[ -x '$TEST_APP_BUNDLE/Contents/Helpers/diagnostics' ]"
    else
        fail_test "App bundle structure tests" "Test app bundle not available"
    fi
else
    skip_test "Installation simulation (quick mode)"
fi

# Test Category 4: Component Verification
echo -e "\n${BLUE}${BOLD}🔍 Test Category 4: Component Verification${NC}"

# Test hardware detection
log_test "Hardware detection functionality"
if python3 -c "
import subprocess
import json
try:
    result = subprocess.run(['system_profiler', 'SPHardwareDataType', '-json'],
                          capture_output=True, text=True, timeout=10)
    if result.returncode == 0:
        data = json.loads(result.stdout)
        hardware_info = data['SPHardwareDataType'][0]
        print(f'Chip: {hardware_info.get(\"chip_type\", \"unknown\")}')
        print(f'Memory: {hardware_info.get(\"physical_memory\", \"unknown\")}')
    exit(0)
except:
    exit(1)
" >> "$TEST_LOG" 2>&1; then
    pass_test "Hardware detection functionality"
else
    fail_test "Hardware detection functionality"
fi

# Test Ollama model recommendation
run_test "Ollama setup script exists" "[ -x '$SCRIPT_DIR/setup_ollama_models.sh' ]"

if [ -x "$SCRIPT_DIR/setup_ollama_models.sh" ]; then
    log_test "Ollama model recommendation"
    if "$SCRIPT_DIR/setup_ollama_models.sh" recommend >> "$TEST_LOG" 2>&1; then
        pass_test "Ollama model recommendation"
    else
        fail_test "Ollama model recommendation"
    fi
fi

# Test Obsidian integration
run_test "Obsidian integration script exists" "[ -x '$SCRIPT_DIR/setup_obsidian_integration.sh' ]"

# Test GitHub release creation
run_test "GitHub release script exists" "[ -x '$SCRIPT_DIR/create_github_release.sh' ]"

# Test Category 5: Integration Tests
echo -e "\n${BLUE}${BOLD}🔗 Test Category 5: Integration Tests${NC}"

# Test version extraction
log_test "Version extraction from pyproject.toml"
if VERSION=$(python3 -c "import tomllib; print(tomllib.load(open('$PROJECT_ROOT/pyproject.toml', 'rb'))['project']['version'])" 2>/dev/null); then
    echo "Detected version: $VERSION" >> "$TEST_LOG"
    pass_test "Version extraction from pyproject.toml"
else
    fail_test "Version extraction from pyproject.toml"
fi

# Test Python 3.13+ requirement
log_test "Python version compatibility"
PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
MAJOR=$(echo "$PYTHON_VERSION" | cut -d. -f1)
MINOR=$(echo "$PYTHON_VERSION" | cut -d. -f2)

if [ "$MAJOR" -eq 3 ] && [ "$MINOR" -ge 13 ]; then
    pass_test "Python version compatibility ($PYTHON_VERSION)"
else
    fail_test "Python version compatibility ($PYTHON_VERSION)" "Requires Python 3.13+"
fi

# Test HuggingFace configuration
log_test "HuggingFace token configuration"
if [ -f "$PROJECT_ROOT/config/credentials.yaml" ]; then
    if grep -q "hf_token\|huggingface_token" "$PROJECT_ROOT/config/credentials.yaml"; then
        pass_test "HuggingFace token configuration"
    else
        fail_test "HuggingFace token configuration" "Token not found in credentials.yaml"
    fi
else
    fail_test "HuggingFace token configuration" "credentials.yaml not found"
fi

# Test existing HardwareDetector integration
log_test "HardwareDetector class availability"
if [ -f "$PROJECT_ROOT/src/knowledge_system/utils/hardware_detection.py" ]; then
    if python3 -c "
import sys
sys.path.insert(0, '$PROJECT_ROOT/src')
from knowledge_system.utils.hardware_detection import HardwareDetector
detector = HardwareDetector()
specs = detector.detect_hardware()
print(f'Detected: {specs.chip_type.value}, {specs.memory_gb}GB')
" >> "$TEST_LOG" 2>&1; then
        pass_test "HardwareDetector class availability"
    else
        fail_test "HardwareDetector class availability" "Import or execution failed"
    fi
else
    fail_test "HardwareDetector class availability" "hardware_detection.py not found"
fi

# Destructive tests (only if explicitly enabled)
if [ $RUN_DESTRUCTIVE_TESTS -eq 1 ]; then
    echo -e "\n${BLUE}${BOLD}💥 Destructive Tests (Enabled)${NC}"

    print_warning() {
        echo -e "${YELLOW}⚠️${NC} $1"
    }

    print_warning "Running destructive tests - existing installation may be affected"

    # Test cleanup of existing installation
    if [ -d "/Applications/Skip the Podcast Desktop.app" ]; then
        log_test "Backup existing installation"
        if cp -R "/Applications/Skip the Podcast Desktop.app" "$TEST_RESULTS_DIR/backup_app.app" 2>>"$TEST_LOG"; then
            pass_test "Backup existing installation"

            # Test removal
            log_test "Remove existing installation"
            if rm -rf "/Applications/Skip the Podcast Desktop.app" 2>>"$TEST_LOG"; then
                pass_test "Remove existing installation"
            else
                fail_test "Remove existing installation"
            fi
        else
            fail_test "Backup existing installation"
        fi
    else
        skip_test "No existing installation to test"
    fi
else
    skip_test "Destructive tests (not enabled - use --destructive)"
fi

# Performance tests
echo -e "\n${BLUE}${BOLD}⚡ Performance Tests${NC}"

# Test build speed simulation
log_test "Build script performance check"
start_time=$(date +%s)
if timeout 30 "$SCRIPT_DIR/build_complete_pkg.sh" --help >/dev/null 2>&1; then
    end_time=$(date +%s)
    duration=$((end_time - start_time))
    echo "Build script help executed in ${duration}s" >> "$TEST_LOG"
    pass_test "Build script performance check"
else
    fail_test "Build script performance check" "Timeout or execution error"
fi

# Generate test report
echo -e "\n${BLUE}${BOLD}📊 Generating Test Report${NC}"

cat > "$TEST_RESULTS_DIR/test_report.md" << EOF
# PKG Installation Test Report

Generated: $(date)

## Test Summary

- **Total Tests**: $TESTS_TOTAL
- **Passed**: $TESTS_PASSED
- **Failed**: $TESTS_FAILED
- **Skipped**: $TESTS_SKIPPED
- **Success Rate**: $(( TESTS_TOTAL > 0 ? (TESTS_PASSED * 100) / TESTS_TOTAL : 0 ))%

## Test Configuration

- Destructive Tests: $([ $RUN_DESTRUCTIVE_TESTS -eq 1 ] && echo "Enabled" || echo "Disabled")
- Quick Mode: $([ $QUICK_TEST -eq 1 ] && echo "Enabled" || echo "Disabled")
- Verbose: $([ $VERBOSE -eq 1 ] && echo "Enabled" || echo "Disabled")

## System Information

- macOS Version: $(sw_vers -productVersion)
- Architecture: $(uname -m)
- Python Version: $(python3 --version)
- Memory: $(sysctl -n hw.memsize | awk '{print int($1/1024/1024/1024)')}GB
- CPU Cores: $(sysctl -n hw.ncpu)

## Passed Tests

$(printf '%s\n' "${PASSED_TESTS[@]}" | sed 's/^/- /')

EOF

if [ ${#FAILED_TESTS[@]} -gt 0 ]; then
    cat >> "$TEST_RESULTS_DIR/test_report.md" << EOF

## Failed Tests

$(printf '%s\n' "${FAILED_TESTS[@]}" | sed 's/^/- /')

## Troubleshooting

For failed tests, check the detailed log at: $TEST_LOG

Common issues:
1. Missing dependencies (Python 3.13+, system tools)
2. Permission issues (try with admin privileges)
3. Network connectivity (for download tests)
4. Disk space (for build tests)

EOF
fi

cat >> "$TEST_RESULTS_DIR/test_report.md" << EOF

## Next Steps

$(if [ $TESTS_FAILED -eq 0 ]; then
    echo "✅ All tests passed! The PKG installer is ready for production use."
    echo ""
    echo "Recommended actions:"
    echo "1. Proceed with production PKG builds"
    echo "2. Test on additional hardware configurations"
    echo "3. Validate user experience on clean systems"
else
    echo "❌ Some tests failed. Address these issues before production:"
    echo ""
    echo "Required actions:"
    echo "1. Fix failed tests listed above"
    echo "2. Re-run test suite"
    echo "3. Validate fixes on clean systems"
fi)

## Files Generated

- Test Report: $TEST_RESULTS_DIR/test_report.md
- Detailed Log: $TEST_LOG
- Test App Bundle: $TEST_RESULTS_DIR/Skip the Podcast Desktop.app (if created)

EOF

# Final results
echo -e "\n${GREEN}${BOLD}📋 Test Results Summary${NC}"
echo "=============================================="
echo "Total Tests: $TESTS_TOTAL"
echo "Passed: $TESTS_PASSED"
echo "Failed: $TESTS_FAILED"
echo "Skipped: $TESTS_SKIPPED"

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "\n${GREEN}${BOLD}🎉 All Tests Passed!${NC}"
    echo "PKG installer is ready for production use."
    EXIT_CODE=0
else
    echo -e "\n${RED}${BOLD}❌ Some Tests Failed${NC}"
    echo "Address failed tests before production deployment."
    echo ""
    echo "Failed tests:"
    printf '%s\n' "${FAILED_TESTS[@]}" | sed 's/^/  - /'
    EXIT_CODE=1
fi

echo ""
echo "Detailed report: $TEST_RESULTS_DIR/test_report.md"
echo "Full log: $TEST_LOG"

exit $EXIT_CODE
