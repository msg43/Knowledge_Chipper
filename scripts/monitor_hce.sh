#!/bin/bash
echo "=== HCE Processing Monitor ==="
echo "Checking process status..."
ps aux | grep "knowledge-system" | grep -v grep | head -3

echo -e "\n=== Recent Output Files ==="
ls -la output/ | grep -E "(What's happening|gold)" | tail -5

echo -e "\n=== Checking for Claims in Summary ==="
if [ -f "output/What's happening with GOLD right now will make you crazy_summary.md" ]; then
    echo "Summary file exists. Checking claims..."
    grep -A 5 -B 5 "claims" "output/What's happening with GOLD right now will make you crazy_summary.md" || echo "No claims section found"
    echo -e "\nLast few lines of summary:"
    tail -10 "output/What's happening with GOLD right now will make you crazy_summary.md"
else
    echo "Summary file not found yet"
fi

echo -e "\n=== Process Complete Check ==="
if ! ps aux | grep "knowledge-system" | grep -v grep > /dev/null; then
    echo "✅ HCE process appears to be complete!"
else
    echo "🔄 HCE process still running..."
fi
