#!/bin/bash
echo "=== Detailed HCE Monitor ==="
echo "Time: $(date)"

echo -e "\n=== Process Status ==="
if ps aux | grep "knowledge-system process" | grep -v grep > /dev/null; then
    echo "🔄 HCE process is running"
    ps aux | grep "knowledge-system process" | grep -v grep | awk '{print "  PID:", $2, "CPU:", $3"%", "Memory:", $4"%", "Time:", $10}'
else
    echo "✅ HCE process completed or not running"
fi

echo -e "\n=== File Timestamps ==="
ls -la output/ | grep -E "(What's happening|gold)" | while read line; do
    echo "  $line"
done

echo -e "\n=== Database Check ==="
if [ -f "/Users/matthewgreer/Library/Application Support/Knowledge Chipper/knowledge_system.db" ]; then
    echo "📊 Database exists"
    echo "  Size: $(ls -lh "/Users/matthewgreer/Library/Application Support/Knowledge Chipper/knowledge_system.db" | awk '{print $5}')"
    echo "  Modified: $(ls -l "/Users/matthewgreer/Library/Application Support/Knowledge Chipper/knowledge_system.db" | awk '{print $6, $7, $8}')"
else
    echo "❌ Database not found"
fi

echo -e "\n=== Recent Logs ==="
if [ -d "logs" ]; then
    echo "📝 Checking recent log entries..."
    find logs -name "*.log" -type f -exec tail -3 {} \; 2>/dev/null | tail -10
else
    echo "No logs directory found"
fi

echo -e "\n=== System Resources ==="
echo "💾 Memory usage: $(ps aux | grep ollama | grep -v grep | awk '{sum+=$4} END {print sum"%"}' || echo "0%") (Ollama)"
echo "🖥️  CPU load: $(uptime | awk -F'load averages:' '{print $2}')"
