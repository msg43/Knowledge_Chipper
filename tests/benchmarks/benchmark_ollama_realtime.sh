#!/bin/bash

# Real-time benchmark: measure ACTUAL Ollama processing time with stream=false
# This ensures we wait for full response before measuring completion

PLIST_PATH="$HOME/Library/LaunchAgents/com.ollama.server.plist"
RESULTS_FILE="/Users/matthewgreer/Projects/Knowledge_Chipper/benchmark_results.txt"

echo "════════════════════════════════════════════════════════════════"
echo "🧪 REAL OLLAMA THROUGHPUT BENCHMARK"
echo "════════════════════════════════════════════════════════════════"
echo ""

# Test prompt (similar to mining content)
TEST_PROMPT='Extract all claims, jargon terms, people, and mental models from this text: "Machine learning models require careful optimization of hyperparameters to achieve optimal performance. The learning rate, batch size, and regularization parameters all interact in complex ways. Dr. Sarah Chen from Stanford found that adaptive learning rates can reduce training time by 40 percent. The concept of gradient descent forms the foundation of modern deep learning architectures."'

echo "" > "$RESULTS_FILE"
echo "OLLAMA BENCHMARK RESULTS" >> "$RESULTS_FILE"
echo "Date: $(date)" >> "$RESULTS_FILE"
echo "System: $(sysctl -n machdep.cpu.brand_string)" >> "$RESULTS_FILE"
echo "" >> "$RESULTS_FILE"

test_parallel_requests() {
    local num_parallel=$1
    local num_requests=$2

    echo "────────────────────────────────────────────────────────────────"
    echo "Testing OLLAMA_NUM_PARALLEL=$num_parallel"
    echo "────────────────────────────────────────────────────────────────"

    # Configure Ollama
    echo "  Reconfiguring Ollama..."
    killall Ollama 2>/dev/null || true
    launchctl unload "$PLIST_PATH" 2>/dev/null || true
    sleep 2

    cat << PLIST_EOF > "$PLIST_PATH"
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.ollama.server</string>
    <key>ProgramArguments</key>
    <array>
        <string>/Applications/Ollama.app/Contents/Resources/ollama</string>
        <string>serve</string>
    </array>
    <key>EnvironmentVariables</key>
    <dict>
        <key>OLLAMA_NUM_PARALLEL</key>
        <string>$num_parallel</string>
        <key>OLLAMA_NUM_THREAD</key>
        <string>5</string>
        <key>OLLAMA_KEEP_ALIVE</key>
        <string>1h</string>
        <key>OLLAMA_MAX_LOADED_MODELS</key>
        <string>2</string>
        <key>OLLAMA_FLASH_ATTENTION</key>
        <string>1</string>
    </dict>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/tmp/ollama.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/ollama.err</string>
</dict>
</plist>
PLIST_EOF

    launchctl load "$PLIST_PATH"
    sleep 3

    # Verify Ollama is running
    if ! curl -s http://localhost:11434/api/version > /dev/null 2>&1; then
        echo "  ❌ Ollama failed to start"
        return 1
    fi

    # Warm up - ensure model is loaded
    echo "  Warming up model..."
    curl -s http://localhost:11434/api/generate -d "{
        \"model\": \"qwen2.5:7b-instruct\",
        \"prompt\": \"test\",
        \"stream\": false
    }" > /dev/null

    sleep 2

    # Run benchmark with stream=false to ensure we wait for full response
    echo "  Sending $num_requests requests (waiting for full completion)..."
    start_time=$(date +%s.%N)

    # Create temporary directory for responses
    TEMP_DIR=$(mktemp -d)

    # Launch requests in background, each waits for full response
    for i in $(seq 1 $num_requests); do
        (
            curl -s http://localhost:11434/api/generate -d "{
                \"model\": \"qwen2.5:7b-instruct\",
                \"prompt\": \"$TEST_PROMPT\",
                \"stream\": false,
                \"options\": {\"temperature\": 0.7, \"num_ctx\": 2048}
            }" > "$TEMP_DIR/response_$i.json"
        ) &
    done

    # Wait for all requests to actually complete
    wait

    end_time=$(date +%s.%N)
    elapsed=$(echo "$end_time - $start_time" | bc)
    throughput=$(echo "scale=3; $num_requests / $elapsed" | bc)
    avg_per_request=$(echo "scale=2; $elapsed / $num_requests" | bc)

    # Verify responses were actually received
    response_count=$(ls "$TEMP_DIR"/*.json 2>/dev/null | wc -l | tr -d ' ')

    echo "  ✅ Completed $response_count requests in ${elapsed}s"
    echo "  📊 Throughput: ${throughput} requests/second"
    echo "  ⏱️  Avg time per request: ${avg_per_request}s"
    echo ""

    # Log results
    echo "OLLAMA_NUM_PARALLEL=$num_parallel:" >> "$RESULTS_FILE"
    echo "  Requests: $response_count/$num_requests" >> "$RESULTS_FILE"
    echo "  Total time: ${elapsed}s" >> "$RESULTS_FILE"
    echo "  Throughput: ${throughput} req/sec" >> "$RESULTS_FILE"
    echo "  Avg per request: ${avg_per_request}s" >> "$RESULTS_FILE"
    echo "" >> "$RESULTS_FILE"

    # Cleanup
    rm -rf "$TEMP_DIR"

    sleep 3
}

# Test with 10 concurrent requests for each config
echo "Testing with 10 concurrent requests per configuration..."
echo ""

test_parallel_requests 2 10
test_parallel_requests 4 10
test_parallel_requests 6 10
test_parallel_requests 7 10

echo "════════════════════════════════════════════════════════════════"
echo "✅ BENCHMARK COMPLETE"
echo "════════════════════════════════════════════════════════════════"
echo ""
echo "Results saved to: $RESULTS_FILE"
echo ""
cat "$RESULTS_FILE"
echo ""
echo "════════════════════════════════════════════════════════════════"
echo "🎯 RECOMMENDATION:"
echo "Use the OLLAMA_NUM_PARALLEL value with highest throughput (req/sec)"
echo "════════════════════════════════════════════════════════════════"
