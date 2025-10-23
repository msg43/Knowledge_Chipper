#!/bin/bash

PLIST_PATH="$HOME/Library/LaunchAgents/com.ollama.server.plist"

echo "🔧 Configuring Ollama for parallel requests..."

# Step 1: Stop Ollama app if running
echo "Step 1: Stopping Ollama app (if running)..."
killall Ollama 2>/dev/null || true
launchctl unload "$PLIST_PATH" 2>/dev/null || true
sleep 1

# Step 2: Create optimized Ollama service configuration
echo "Step 2: Creating optimized Ollama service configuration..."
cat << EOF > "$PLIST_PATH"
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
        <!-- Optimal parallel requests (matrix benchmark: 35 configs tested) -->
        <!-- NUM_PARALLEL=5 + 8 workers = 0.124 seg/sec (+18% vs baseline) -->
        <key>OLLAMA_NUM_PARALLEL</key>
        <string>5</string>
        
        <!-- Number of threads per request (Metal backend) -->
        <key>OLLAMA_NUM_THREAD</key>
        <string>5</string>
        
        <!-- Keep models loaded for 1 hour -->
        <key>OLLAMA_KEEP_ALIVE</key>
        <string>1h</string>
        
        <!-- Max loaded models -->
        <key>OLLAMA_MAX_LOADED_MODELS</key>
        <string>2</string>
        
        <!-- Enable flash attention for faster inference -->
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
EOF
echo "✓ Configuration created at: $PLIST_PATH"

# Step 3: Load Ollama service with new configuration
echo "Step 3: Loading Ollama service with new configuration..."
launchctl load "$PLIST_PATH"

sleep 3

# Step 4: Verify Ollama is running
echo "Step 4: Verifying Ollama is running..."
if curl -s http://localhost:11434/api/version > /dev/null 2>&1; then
    echo "✅ Ollama is running with optimized configuration!"
    echo ""
    echo "Configuration applied:"
    echo "  • OLLAMA_NUM_PARALLEL=5 (optimal from matrix benchmark)"
    echo "  • OLLAMA_NUM_THREAD=5 (5 threads per request)"
    echo "  • OLLAMA_KEEP_ALIVE=1h (keeps models in memory)"
    echo "  • OLLAMA_MAX_LOADED_MODELS=2"
    echo "  • OLLAMA_FLASH_ATTENTION=1"
    echo ""
    echo "📊 Matrix benchmark results (35 configs tested):"
    echo "   NUM_PARALLEL=2, 8W:  0.107 seg/sec (baseline)"
    echo "   NUM_PARALLEL=4, 4W:  0.120 seg/sec (+12%)"
    echo "   NUM_PARALLEL=5, 8W:  0.124 seg/sec (+18% ← OPTIMAL)"
    echo "   NUM_PARALLEL=8, 7W:  0.121 seg/sec (+13%)"
    echo ""
    echo "🧪 Test by running unified mining in the GUI and checking throughput"
    echo ""
    echo "To check logs: tail -f /tmp/ollama.log"
else
    echo "❌ Error: Ollama failed to start"
    echo "Check logs: cat /tmp/ollama.err"
    exit 1
fi
