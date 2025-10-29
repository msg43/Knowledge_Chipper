#!/bin/bash
# Monitor comprehensive GUI tests running in background

LOG_FILE="/tmp/gui_test_final.log"
CHECK_INTERVAL=120  # Check every 2 minutes

echo "=========================================="
echo "GUI Test Monitor Started"
echo "=========================================="
echo "Log file: $LOG_FILE"
echo "Check interval: ${CHECK_INTERVAL}s (2 minutes)"
echo "Press Ctrl+C to stop monitoring"
echo ""

# Function to display test status
show_status() {
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "📊 Test Status at $timestamp"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    # Check if process is still running
    if pgrep -f "pytest.*test_real_gui_complete.py" > /dev/null 2>&1; then
        local pid=$(pgrep -f "pytest.*test_real_gui_complete.py" | head -1)
        echo "✅ Tests are still running (PID: $pid)..."
    else
        echo "⚠️  Test process not found - tests may have completed or crashed"
    fi

    # Count test results
    if [ -f "$LOG_FILE" ]; then
        local passed=$(grep "PASSED" "$LOG_FILE" 2>/dev/null | wc -l | tr -d ' ')
        local failed=$(grep "FAILED" "$LOG_FILE" 2>/dev/null | wc -l | tr -d ' ')
        local errors=$(grep "ERROR" "$LOG_FILE" 2>/dev/null | wc -l | tr -d ' ')
        passed=${passed:-0}
        failed=${failed:-0}
        errors=${errors:-0}
        local total=$((passed + failed + errors))

        echo ""
        echo "Test Results So Far:"
        echo "  ✅ Passed: $passed"
        echo "  ❌ Failed: $failed"
        echo "  🔥 Errors: $errors"
        echo "  📈 Total:  $total / 18"

        # Show current test
        local current_test=$(grep -E "test_.*\[.*\]|test_.*PASSED|test_.*FAILED" "$LOG_FILE" | tail -1)
        if [ ! -z "$current_test" ]; then
            echo ""
            echo "Last activity:"
            echo "  $current_test"
        fi

        # Check for completion
        if grep -q "passed" "$LOG_FILE" && grep -q "warnings in" "$LOG_FILE"; then
            echo ""
            echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            echo "🎉 TESTS COMPLETED!"
            echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

            # Show final summary
            echo ""
            grep -A 10 "short test summary" "$LOG_FILE" 2>/dev/null || true
            grep "passed" "$LOG_FILE" | tail -1

            exit 0
        fi

        # Show recent errors if any
        if [ $errors -gt 0 ] || [ $failed -gt 0 ]; then
            echo ""
            echo "Recent Issues:"
            grep -E "FAILED|ERROR|AssertionError|NameError|AttributeError" "$LOG_FILE" | tail -5
        fi

        # Show file size to detect if still writing
        local filesize=$(ls -lh "$LOG_FILE" | awk '{print $5}')
        echo ""
        echo "Log file size: $filesize"

    else
        echo "⚠️  Log file not found yet: $LOG_FILE"
    fi

    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
}

# Initial status
show_status

# Monitor loop
while true; do
    sleep $CHECK_INTERVAL
    show_status

    # Check if process ended
    if ! ps aux | grep -q "[p]ython -m pytest tests/comprehensive/test_real_gui_complete.py"; then
        echo ""
        echo "⚠️  Test process ended. Showing final results..."
        sleep 2
        show_status
        echo ""
        echo "Full log available at: $LOG_FILE"
        echo "View with: cat $LOG_FILE"
        exit 0
    fi
done
