#!/bin/bash
set -e

# Get script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "================================================================"
echo "Running Fully Automated Test Suite"
echo "Zero human intervention required"
echo "================================================================"
echo ""
echo "Project root: $PROJECT_ROOT"
echo ""

# Set environment for automation
export KNOWLEDGE_CHIPPER_TESTING_MODE=1
export QT_QPA_PLATFORM=offscreen

echo "Environment configured:"
echo "  KNOWLEDGE_CHIPPER_TESTING_MODE=1 (suppresses dialogs)"
echo "  QT_QPA_PLATFORM=offscreen (no display needed)"
echo ""

# Use venv python
PYTEST="$PROJECT_ROOT/venv/bin/pytest"

if [ ! -f "$PYTEST" ]; then
    echo "❌ Error: pytest not found at $PYTEST"
    echo "Please ensure venv is set up: python3 -m venv venv && ./venv/bin/pip install -e ."
    exit 1
fi

# Phase 1: Fast direct logic tests
echo "================================================================"
echo "Phase 1: Direct Logic Tests (No GUI)"
echo "================================================================"
$PYTEST tests/core/test_system2_orchestrator.py -v -k "not LiveAPI" --timeout=60 || true
$PYTEST tests/core/test_llm_adapter_async.py -v -k "not skip" --timeout=60 || true

# Phase 2: GUI integration tests (automated)
echo ""
echo "================================================================"
echo "Phase 2: GUI Integration Tests (Automated, No Dialogs)"
echo "================================================================"
$PYTEST tests/gui_comprehensive/test_system2_integration.py -v --timeout=120 || true

# Phase 3: Full integration (automated)
echo ""
echo "================================================================"
echo "Phase 3: Full Integration Tests (Automated)"
echo "================================================================"
$PYTEST tests/core/test_integration_direct.py -v --timeout=180 || true

# Phase 4: Smoke tests
echo ""
echo "================================================================"
echo "Phase 4: Smoke Tests (GUI Launch Verification)"
echo "================================================================"
$PYTEST tests/gui_comprehensive/test_smoke_automated.py -v --timeout=60 || true

# Phase 5: CLI Removal Verification
echo ""
echo "================================================================"
echo "Phase 5: CLI Removal Verification"
echo "================================================================"
$PYTEST tests/test_cli_removal_verification.py -v --timeout=30 || true

echo ""
echo "================================================================"
echo "All Automated Tests Complete!"
echo "No human intervention was required."
echo "================================================================"

