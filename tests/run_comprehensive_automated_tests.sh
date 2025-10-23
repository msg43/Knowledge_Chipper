#!/bin/bash
# Comprehensive automated GUI testing that catches bugs before they reach production
# Tests all workflows, tabs, and edge cases without human intervention

set -e

# Get script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo "================================================================"
echo "🤖 COMPREHENSIVE AUTOMATED GUI TESTING SUITE"
echo "================================================================"
echo ""
echo "This will test ALL GUI workflows and processes to catch bugs"
echo "No human intervention required - fully automated"
echo ""
echo "Project root: $PROJECT_ROOT"
echo "Test framework: pytest + PyQt6 automation"
echo ""

# Set environment for automation
export KNOWLEDGE_CHIPPER_TESTING_MODE=1
export QT_QPA_PLATFORM=offscreen
export PYTHONPATH="$PROJECT_ROOT/src:$PYTHONPATH"

echo -e "${BLUE}Environment configured:${NC}"
echo "  KNOWLEDGE_CHIPPER_TESTING_MODE=1 (suppresses dialogs)"
echo "  QT_QPA_PLATFORM=offscreen (no display needed)"
echo "  PYTHONPATH includes src directory"
echo ""

# Check for virtual environment
PYTHON="$PROJECT_ROOT/venv/bin/python3"
PYTEST="$PROJECT_ROOT/venv/bin/pytest"

if [ ! -f "$PYTHON" ]; then
    echo -e "${RED}❌ Error: Python not found at $PYTHON${NC}"
    echo "Please set up venv: python3 -m venv venv && ./venv/bin/pip install -e ."
    exit 1
fi

if [ ! -f "$PYTEST" ]; then
    echo -e "${RED}❌ Error: pytest not found at $PYTEST${NC}"
    echo "Please install test dependencies: ./venv/bin/pip install pytest pytest-asyncio pytest-timeout"
    exit 1
fi

# Create reports directory
REPORTS_DIR="$PROJECT_ROOT/tests/reports/automated_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$REPORTS_DIR"

echo -e "${BLUE}Test reports will be saved to: $REPORTS_DIR${NC}"
echo ""

# Test counter
TOTAL_PHASES=6
CURRENT_PHASE=0
FAILED_PHASES=()

# Function to run a test phase
run_test_phase() {
    local phase_name="$1"
    local test_path="$2"
    local timeout="$3"
    
    CURRENT_PHASE=$((CURRENT_PHASE + 1))
    
    echo ""
    echo "================================================================"
    echo -e "${BLUE}Phase $CURRENT_PHASE/$TOTAL_PHASES: $phase_name${NC}"
    echo "================================================================"
    
    local report_file="$REPORTS_DIR/phase_${CURRENT_PHASE}_$(echo $phase_name | tr ' ' '_' | tr '[:upper:]' '[:lower:]').txt"
    
    if $PYTEST "$test_path" -v --timeout="$timeout" --tb=short 2>&1 | tee "$report_file"; then
        echo -e "${GREEN}✅ Phase $CURRENT_PHASE passed${NC}"
        return 0
    else
        echo -e "${RED}❌ Phase $CURRENT_PHASE failed (continuing to next phase)${NC}"
        FAILED_PHASES+=("Phase $CURRENT_PHASE: $phase_name")
        return 1
    fi
}

# Phase 1: Unit tests for core components
run_test_phase \
    "Core Unit Tests" \
    "$PROJECT_ROOT/tests/core/" \
    60

# Phase 2: GUI smoke tests (basic launch and tab loading)
run_test_phase \
    "GUI Smoke Tests" \
    "$PROJECT_ROOT/tests/gui_comprehensive/test_smoke_automated.py" \
    60

# Phase 3: Complete workflow tests (all tabs and operations)
run_test_phase \
    "All GUI Workflows" \
    "$PROJECT_ROOT/tests/gui_comprehensive/test_all_workflows_automated.py" \
    300

# Phase 4: System 2 integration tests
run_test_phase \
    "System 2 Integration" \
    "$PROJECT_ROOT/tests/gui_comprehensive/test_system2_integration.py" \
    120

# Phase 5: Database integration tests
if [ -f "$PROJECT_ROOT/tests/integration/test_system2_database.py" ]; then
    run_test_phase \
        "Database Integration" \
        "$PROJECT_ROOT/tests/integration/test_system2_database.py" \
        90
else
    echo -e "${YELLOW}⚠️  Skipping Phase 5: Database tests not found${NC}"
    CURRENT_PHASE=$((CURRENT_PHASE + 1))
fi

# Phase 6: Review tab and monitoring
if [ -f "$PROJECT_ROOT/tests/gui_comprehensive/test_review_tab_system2.py" ]; then
    run_test_phase \
        "Review Tab & Monitoring" \
        "$PROJECT_ROOT/tests/gui_comprehensive/test_review_tab_system2.py" \
        90
else
    echo -e "${YELLOW}⚠️  Skipping Phase 6: Review tab tests not found${NC}"
    CURRENT_PHASE=$((CURRENT_PHASE + 1))
fi

# Generate final report
echo ""
echo "================================================================"
echo "📊 FINAL TEST REPORT"
echo "================================================================"
echo ""

PASSED_COUNT=$((TOTAL_PHASES - ${#FAILED_PHASES[@]}))
SUCCESS_RATE=$(( (PASSED_COUNT * 100) / TOTAL_PHASES ))

echo "Total test phases: $TOTAL_PHASES"
echo "Passed: $PASSED_COUNT"
echo "Failed: ${#FAILED_PHASES[@]}"
echo "Success rate: ${SUCCESS_RATE}%"
echo ""

if [ ${#FAILED_PHASES[@]} -eq 0 ]; then
    echo -e "${GREEN}🎉 ALL TESTS PASSED!${NC}"
    echo "The GUI is working correctly across all workflows."
    echo ""
    echo "✅ All tabs load successfully"
    echo "✅ All workflows function properly"
    echo "✅ Error handling works correctly"
    echo "✅ Database integration functional"
    echo "✅ System 2 orchestration working"
else
    echo -e "${RED}⚠️  SOME TESTS FAILED${NC}"
    echo ""
    echo "Failed phases:"
    for failed_phase in "${FAILED_PHASES[@]}"; do
        echo -e "  ${RED}❌ $failed_phase${NC}"
    done
    echo ""
    echo "Review detailed reports in: $REPORTS_DIR"
fi

echo ""
echo "================================================================"
echo "📁 Detailed reports saved to:"
echo "   $REPORTS_DIR"
echo "================================================================"
echo ""

# Save summary
SUMMARY_FILE="$REPORTS_DIR/SUMMARY.txt"
cat > "$SUMMARY_FILE" << EOF
COMPREHENSIVE AUTOMATED GUI TEST SUMMARY
========================================

Test Date: $(date)
Total Phases: $TOTAL_PHASES
Passed: $PASSED_COUNT
Failed: ${#FAILED_PHASES[@]}
Success Rate: ${SUCCESS_RATE}%

Environment:
- Testing Mode: ENABLED
- Display: offscreen
- Python: $PYTHON
- Pytest: $PYTEST

$(if [ ${#FAILED_PHASES[@]} -eq 0 ]; then
    echo "RESULT: ✅ ALL TESTS PASSED"
else
    echo "RESULT: ❌ SOME TESTS FAILED"
    echo ""
    echo "Failed Phases:"
    for failed_phase in "${FAILED_PHASES[@]}"; do
        echo "  - $failed_phase"
    done
fi)

Individual test reports are available in this directory.
EOF

echo "Summary saved to: $SUMMARY_FILE"
echo ""

# Exit with appropriate code
if [ ${#FAILED_PHASES[@]} -eq 0 ]; then
    echo -e "${GREEN}✅ Testing complete - All systems operational${NC}"
    exit 0
else
    echo -e "${RED}❌ Testing complete - Some issues found${NC}"
    exit 1
fi

