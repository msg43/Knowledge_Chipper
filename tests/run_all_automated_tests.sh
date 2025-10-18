#!/bin/bash
set -e

echo "================================================================"
echo "Running Fully Automated Test Suite"
echo "Zero human intervention required"
echo "================================================================"
echo ""

# Set environment for automation
export KNOWLEDGE_CHIPPER_TESTING_MODE=1
export QT_QPA_PLATFORM=offscreen

echo "Environment configured:"
echo "  KNOWLEDGE_CHIPPER_TESTING_MODE=1 (suppresses dialogs)"
echo "  QT_QPA_PLATFORM=offscreen (no display needed)"
echo ""

# Phase 1: Fast direct logic tests
echo "================================================================"
echo "Phase 1: Direct Logic Tests (No GUI)"
echo "================================================================"
pytest tests/core/ -v -m "not slow" --timeout=60 || true

# Phase 2: GUI integration tests (automated)
echo ""
echo "================================================================"
echo "Phase 2: GUI Integration Tests (Automated, No Dialogs)"
echo "================================================================"
pytest tests/gui_comprehensive/test_system2_integration.py -v --timeout=120 || true

# Phase 3: Full integration (automated)
echo ""
echo "================================================================"
echo "Phase 3: Full Integration Tests (Automated)"
echo "================================================================"
pytest tests/core/test_integration_direct.py -v --timeout=180 || true

# Phase 4: Smoke tests
echo ""
echo "================================================================"
echo "Phase 4: Smoke Tests (GUI Launch Verification)"
echo "================================================================"
pytest tests/gui_comprehensive/test_smoke_automated.py -v --timeout=60 || true

# Phase 5: All tests together
echo ""
echo "================================================================"
echo "Phase 5: Complete Test Suite"
echo "================================================================"
pytest tests/ -v --timeout=300 -x  # Stop on first failure

echo ""
echo "================================================================"
echo "All Automated Tests Complete!"
echo "No human intervention was required."
echo "================================================================"

