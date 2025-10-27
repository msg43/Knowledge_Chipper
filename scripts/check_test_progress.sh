#!/bin/bash
# Monitor GUI test progress

LOG_FILE="test_run_results.log"

echo "=== GUI Test Progress Monitor ==="
echo ""

if [ ! -f "$LOG_FILE" ]; then
    echo "❌ Test log file not found yet..."
    exit 1
fi

echo "📊 Current Status:"
echo ""

# Count completed tests
PASSED=$(grep -c "PASSED" "$LOG_FILE" 2>/dev/null || echo "0")
FAILED=$(grep -c "FAILED" "$LOG_FILE" 2>/dev/null || echo "0")
SKIPPED=$(grep -c "SKIPPED" "$LOG_FILE" 2>/dev/null || echo "0")

echo "✅ Passed:  $PASSED"
echo "❌ Failed:  $FAILED"
echo "⏭️  Skipped: $SKIPPED"
echo ""

# Show currently running test
CURRENT=$(tail -20 "$LOG_FILE" | grep -E "test_.*PASSED|test_.*FAILED|test_.*::" | tail -1)
if [ -n "$CURRENT" ]; then
    echo "🔄 Latest activity:"
    echo "   $CURRENT"
fi

echo ""
echo "📝 Last 10 lines of log:"
tail -10 "$LOG_FILE"

echo ""
echo "---"
echo "To view full log: tail -f test_run_results.log"
