#!/bin/bash
# Run all working test suites
#
# This script runs all test suites that are known to pass reliably:
# - Basic unit tests
# - Logger tests
# - Evaluators unit tests
# - Schema validation tests
# - Error handling tests
# - Backend integration tests (real data processing)
#
# Usage:
#   ./tests/run_working_tests.sh [pytest options]
#
# Examples:
#   ./tests/run_working_tests.sh
#   ./tests/run_working_tests.sh -v
#   ./tests/run_working_tests.sh --co
#   ./tests/run_working_tests.sh --tb=short

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

echo "================================================================================"
echo "Running Working Test Suites"
echo "================================================================================"
echo ""
echo "Test files:"
echo "  ✓ tests/test_basic.py"
echo "  ✓ tests/test_logger.py"
echo "  ✓ tests/test_evaluators_unit.py"
echo "  ✓ tests/test_schema_validation.py"
echo "  ✓ tests/test_errors.py"
echo "  ✓ tests/comprehensive/test_real_integration_complete.py"
echo ""
echo "================================================================================"
echo ""

# Run pytest with all working test suites
python -m pytest \
    tests/test_basic.py \
    tests/test_logger.py \
    tests/test_evaluators_unit.py \
    tests/test_schema_validation.py \
    tests/test_errors.py \
    tests/comprehensive/test_real_integration_complete.py \
    -v \
    --tb=line \
    "$@"
