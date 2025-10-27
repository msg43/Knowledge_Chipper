#!/bin/bash
# Quick launcher for automated GUI testing
# Run this script to test ALL GUI workflows and catch bugs automatically

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo ""
echo -e "${BLUE}╔════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║    🤖 AUTOMATED GUI TESTING - Quick Start            ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════╝${NC}"
echo ""

# Check if we're in the right directory
if [ ! -f "$SCRIPT_DIR/pyproject.toml" ]; then
    echo "❌ Error: Must be run from project root"
    exit 1
fi

# Show menu
echo "Select test mode:"
echo ""
echo "  1) 🚀 Quick Smoke Tests (5-10 minutes)"
echo "     - Verify GUI launches and all tabs load"
echo "     - Fast sanity check before committing"
echo ""
echo "  2) 📋 Full Workflow Tests (30 minutes)"
echo "     - Test all GUI workflows and operations"
echo "     - Recommended before merging PRs"
echo ""
echo "  3) 🔍 Comprehensive + Bug Detection (40 minutes)"
echo "     - Full workflow tests"
echo "     - Automated bug detection and reporting"
echo "     - Coverage analysis"
echo ""
echo "  4) 📊 Coverage Analysis Only (2 minutes)"
echo "     - Analyze which code is tested"
echo "     - Generate coverage report"
echo ""
echo "  5) 🐛 Bug Detection Only (analyze existing reports)"
echo "     - Scan recent test reports for bugs"
echo ""
echo "  6) ⚙️  Custom (advanced users)"
echo ""
read -p "Enter choice [1-6]: " choice
echo ""

case $choice in
    1)
        echo -e "${GREEN}Running smoke tests...${NC}"
        cd "$SCRIPT_DIR/tests/gui_comprehensive"
        ../../venv/bin/python3 main_test_runner.py smoke
        ;;

    2)
        echo -e "${GREEN}Running comprehensive workflow tests...${NC}"
        "$SCRIPT_DIR/tests/run_comprehensive_automated_tests.sh"
        ;;

    3)
        echo -e "${GREEN}Running full test suite with analysis...${NC}"

        # Run tests
        "$SCRIPT_DIR/tests/run_comprehensive_automated_tests.sh"

        # Find most recent report directory
        REPORTS_DIR=$(ls -td "$SCRIPT_DIR/tests/reports/automated_"* 2>/dev/null | head -1)

        if [ -n "$REPORTS_DIR" ]; then
            echo ""
            echo -e "${BLUE}Running bug detection...${NC}"
            "$SCRIPT_DIR/venv/bin/python3" "$SCRIPT_DIR/tests/tools/bug_detector.py" "$REPORTS_DIR"

            # Show bug report location
            BUG_REPORT=$(ls -t "$REPORTS_DIR/bug_reports/"*.md 2>/dev/null | head -1)
            if [ -n "$BUG_REPORT" ]; then
                echo ""
                echo -e "${GREEN}✅ Bug report generated:${NC}"
                echo "   $BUG_REPORT"
                echo ""

                read -p "Open bug report? [y/N]: " open_report
                if [[ $open_report =~ ^[Yy]$ ]]; then
                    open "$BUG_REPORT" || cat "$BUG_REPORT"
                fi
            fi
        fi

        # Run coverage analysis
        echo ""
        echo -e "${BLUE}Running coverage analysis...${NC}"
        "$SCRIPT_DIR/venv/bin/python3" "$SCRIPT_DIR/tests/tools/coverage_analyzer.py"

        COVERAGE_REPORT="$SCRIPT_DIR/tests/reports/coverage_analysis.md"
        if [ -f "$COVERAGE_REPORT" ]; then
            echo ""
            echo -e "${GREEN}✅ Coverage report generated:${NC}"
            echo "   $COVERAGE_REPORT"
            echo ""

            read -p "Open coverage report? [y/N]: " open_coverage
            if [[ $open_coverage =~ ^[Yy]$ ]]; then
                open "$COVERAGE_REPORT" || cat "$COVERAGE_REPORT"
            fi
        fi
        ;;

    4)
        echo -e "${GREEN}Running coverage analysis...${NC}"
        "$SCRIPT_DIR/venv/bin/python3" "$SCRIPT_DIR/tests/tools/coverage_analyzer.py"

        COVERAGE_REPORT="$SCRIPT_DIR/tests/reports/coverage_analysis.md"
        echo ""
        echo -e "${GREEN}✅ Coverage report generated:${NC}"
        echo "   $COVERAGE_REPORT"

        if [ -f "$COVERAGE_REPORT" ]; then
            echo ""
            # Show summary
            echo -e "${BLUE}Coverage Summary:${NC}"
            grep -A 5 "^## Summary" "$COVERAGE_REPORT" || true
        fi
        ;;

    5)
        echo -e "${GREEN}Analyzing existing test reports for bugs...${NC}"

        # Find most recent report directory
        REPORTS_DIR=$(ls -td "$SCRIPT_DIR/tests/reports/automated_"* 2>/dev/null | head -1)

        if [ -z "$REPORTS_DIR" ]; then
            echo -e "${YELLOW}⚠️  No test reports found. Run tests first.${NC}"
            exit 1
        fi

        echo "Analyzing: $REPORTS_DIR"
        "$SCRIPT_DIR/venv/bin/python3" "$SCRIPT_DIR/tests/tools/bug_detector.py" "$REPORTS_DIR"

        # Show bug report location
        BUG_REPORT=$(ls -t "$REPORTS_DIR/bug_reports/"*.md 2>/dev/null | head -1)
        if [ -n "$BUG_REPORT" ]; then
            echo ""
            echo -e "${GREEN}✅ Bug report generated:${NC}"
            echo "   $BUG_REPORT"
            echo ""

            # Show summary
            echo -e "${BLUE}Bug Summary:${NC}"
            head -20 "$BUG_REPORT"
            echo ""

            read -p "Open full report? [y/N]: " open_report
            if [[ $open_report =~ ^[Yy]$ ]]; then
                open "$BUG_REPORT" || cat "$BUG_REPORT"
            fi
        else
            echo -e "${GREEN}✅ No bugs detected!${NC}"
        fi
        ;;

    6)
        echo "Custom testing options:"
        echo ""
        echo "Available commands:"
        echo "  ./tests/run_comprehensive_automated_tests.sh"
        echo "  ./tests/gui_comprehensive/main_test_runner.py [mode]"
        echo "  python tests/tools/bug_detector.py [reports_dir]"
        echo "  python tests/tools/coverage_analyzer.py"
        echo ""
        echo "Test modes: smoke, basic, comprehensive, stress, all"
        echo ""
        ;;

    *)
        echo "Invalid choice"
        exit 1
        ;;
esac

echo ""
echo -e "${BLUE}════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}Testing complete!${NC}"
echo ""
echo "For more information, see:"
echo "  📖 docs/AUTOMATED_TESTING_GUIDE.md"
echo "  📖 tests/README.md"
echo "  📖 tests/gui_comprehensive/README.md"
echo ""
echo -e "${BLUE}════════════════════════════════════════════════════════${NC}"
echo ""
