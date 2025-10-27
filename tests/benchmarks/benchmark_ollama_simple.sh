#!/bin/bash

# Simple benchmark: measure Ollama throughput with concurrent requests
# This bypasses Python and tests Ollama directly

PLIST_PATH="$HOME/Library/LaunchAgents/com.ollama.server.plist"

echo "════════════════════════════════════════════════════════════════"
echo "🧪 SIMPLE OLLAMA BENCHMARK"
echo "════════════════════════════════════════════════════════════════"
echo ""

# Test prompt (similar to mining content)
TEST_PROMPT='Extract claims and entities from: "Machine learning models require optimization of hyperparameters. Dr. Sarah Chen from Stanford found adaptive learning rates reduce training by 40%. Gradient descent is fundamental to neural networks."'

test_parallel_requests() {
    local num_parallel=$1
    local num_requests=$2

    echo "Testing OLLAMA_NUM_PARALLEL=$num_parallel with $num_requests requests..."

    # Configure Ollama
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
        echo "❌ Ollama failed to start"
        return 1
    fi

    # Warm up
    curl -s http://localhost:11434/api/generate -d "{
        \"model\": \"qwen2.5:7b-instruct\",
        \"prompt\": \"test\",
        \"stream\": false
    }" > /dev/null

    sleep 1

    # Run benchmark
    echo "  Sending $num_requests requests in parallel..."
    start_time=$(date +%s.%N)

    # Launch requests in background
    for i in $(seq 1 $num_requests); do
        (
            curl -s http://localhost:11434/api/generate -d "{
                \"model\": \"qwen2.5:7b-instruct\",
                \"prompt\": \"$TEST_PROMPT\",
                \"stream\": false,
                \"options\": {\"temperature\": 0.7}
            }" > /dev/null
        ) &
    done

    # Wait for all requests to complete
    wait

    end_time=$(date +%s.%N)
    elapsed=$(echo "$end_time - $start_time" | bc)
    throughput=$(echo "scale=2; $num_requests / $elapsed" | bc)

    echo "  ✅ Completed in ${elapsed}s"
    echo "  📊 Throughput: ${throughput} requests/second"
    echo ""

    sleep 3
}

# Test with different OLLAMA_NUM_PARALLEL values
echo "Testing 10 concurrent requests with different OLLAMA_NUM_PARALLEL..."
echo ""

test_parallel_requests 2 10
test_parallel_requests 4 10
test_parallel_requests 6 10
test_parallel_requests 7 10

echo "════════════════════════════════════════════════════════════════"
echo "✅ BENCHMARK COMPLETE"
echo "════════════════════════════════════════════════════════════════"
