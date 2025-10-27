#!/bin/bash

# Comprehensive Test Runner - Alternative Single Command
# Runs all three comprehensive test suites in one go with detailed reporting

set -e

echo "🧪 Running All Comprehensive Tests with Real-time Reporting"
echo "=========================================================="
echo ""

# Run all three comprehensive test files in sequence with detailed reporting
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

echo ""
echo "=================================="
echo "🎉 Comprehensive Test Suite Complete!"
echo "Results saved to test-results/"
echo "=================================="
