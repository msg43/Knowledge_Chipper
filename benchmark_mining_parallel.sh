#!/bin/bash

# Benchmark script for unified mining with different OLLAMA_NUM_PARALLEL settings
# Tests realistic mining workload with actual system load

PLIST_PATH="$HOME/Library/LaunchAgents/com.ollama.server.plist"
LOG_FILE="/Users/matthewgreer/Projects/Knowledge_Chipper/benchmark_mining_results.txt"

echo "════════════════════════════════════════════════════════════════"
echo "🧪 UNIFIED MINING BENCHMARK - OLLAMA PARALLEL SETTINGS"
echo "════════════════════════════════════════════════════════════════"
echo ""
echo "This benchmark will:"
echo "  • Test OLLAMA_NUM_PARALLEL values: 2, 4, 6, 7"
echo "  • Process 20 test segments with each setting"
echo "  • Measure actual segments/second throughput"
echo "  • Run with your current system load (realistic conditions)"
echo ""
echo "⚠️  This will take ~5-10 minutes total"
echo "⚠️  Keep your system as-is (don't close apps)"
echo ""
read -p "Press Enter to start benchmark..."

# Record initial system state
echo "" > "$LOG_FILE"
echo "UNIFIED MINING BENCHMARK RESULTS" >> "$LOG_FILE"
echo "Date: $(date)" >> "$LOG_FILE"
echo "System: $(sysctl -n machdep.cpu.brand_string)" >> "$LOG_FILE"
echo "Memory: $(sysctl -n hw.memsize | awk '{print $1/1024/1024/1024 " GB"}')" >> "$LOG_FILE"
echo "" >> "$LOG_FILE"
echo "System Load During Test:" >> "$LOG_FILE"
echo "  CPU Usage: $(top -l 1 | grep "CPU usage" | awk '{print $3, $5}')" >> "$LOG_FILE"
echo "  Memory Pressure: $(memory_pressure | grep "System-wide memory" | head -1)" >> "$LOG_FILE"
echo "" >> "$LOG_FILE"
echo "────────────────────────────────────────────────────────────────" >> "$LOG_FILE"
echo "" >> "$LOG_FILE"

# Test configurations
PARALLEL_VALUES=(2 4 6 7)
TEST_SEGMENTS=20  # Number of segments to process per test

for NUM_PARALLEL in "${PARALLEL_VALUES[@]}"; do
    echo ""
    echo "════════════════════════════════════════════════════════════════"
    echo "🔧 Testing OLLAMA_NUM_PARALLEL=$NUM_PARALLEL"
    echo "════════════════════════════════════════════════════════════════"
    
    # Update Ollama configuration
    echo "Step 1: Stopping Ollama..."
    killall Ollama 2>/dev/null || true
    launchctl unload "$PLIST_PATH" 2>/dev/null || true
    sleep 2
    
    echo "Step 2: Setting OLLAMA_NUM_PARALLEL=$NUM_PARALLEL..."
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
        <key>OLLAMA_NUM_PARALLEL</key>
        <string>$NUM_PARALLEL</string>
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
EOF
    
    echo "Step 3: Starting Ollama with new config..."
    launchctl load "$PLIST_PATH"
    sleep 3
    
    # Verify Ollama is running
    if ! curl -s http://localhost:11434/api/version > /dev/null 2>&1; then
        echo "❌ Error: Ollama failed to start"
        continue
    fi
    
    echo "Step 4: Warming up model (ensuring it's loaded)..."
    curl -s http://localhost:11434/api/generate -d '{
        "model": "qwen2.5:7b-instruct",
        "prompt": "test",
        "stream": false
    }' > /dev/null
    
    sleep 2
    
    echo "Step 5: Running mining test with $TEST_SEGMENTS segments..."
    echo ""
    
    # Create test Python script
    cat << 'PYTHON_EOF' > /tmp/test_mining_benchmark.py
import sys
import time
import asyncio
from pathlib import Path

# Add project to path
sys.path.insert(0, '/Users/matthewgreer/Projects/Knowledge_Chipper/src')

from knowledge_system.models.segment import Segment
from knowledge_system.processors.hce.unified_miner import UnifiedMiner
from knowledge_system.core.config import get_settings

def create_test_segments(count: int) -> list[Segment]:
    """Create realistic test segments."""
    test_content = """
    Machine learning models require careful optimization of hyperparameters 
    to achieve optimal performance. The learning rate, batch size, and 
    regularization parameters all interact in complex ways. Dr. Sarah Chen 
    from Stanford found that adaptive learning rates can reduce training 
    time by 40%. The concept of gradient descent forms the foundation of 
    modern deep learning architectures.
    """
    
    segments = []
    for i in range(count):
        segment = Segment(
            segment_id=f"test_seg_{i}",
            transcript=test_content,
            start_time=i * 30.0,
            end_time=(i + 1) * 30.0,
            episode_id="benchmark_test"
        )
        segments.append(segment)
    return segments

def main():
    num_segments = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    
    # Get settings for model URI
    settings = get_settings()
    model_uri = f"{settings.llm.provider}:{settings.llm.local_model}"
    
    print(f"Creating {num_segments} test segments...")
    segments = create_test_segments(num_segments)
    
    print(f"Initializing miner with model: {model_uri}")
    miner = UnifiedMiner(model_uri=model_uri)
    
    print(f"Starting parallel mining of {num_segments} segments...")
    start_time = time.time()
    
    # Create fake episode bundle
    class FakeEpisode:
        def __init__(self, segments):
            self.segments = segments
            self.episode_id = "benchmark_test"
    
    episode = FakeEpisode(segments)
    
    # Mine with auto-calculated workers (should be 7 for M2 Ultra)
    results = miner.mine_episode(
        episode=episode,
        max_workers=None,  # Auto-calculate
        progress_callback=lambda msg: print(f"  {msg}")
    )
    
    elapsed = time.time() - start_time
    segments_per_sec = num_segments / elapsed
    
    print(f"\n{'='*60}")
    print(f"RESULTS:")
    print(f"  Total segments: {num_segments}")
    print(f"  Total time: {elapsed:.2f}s")
    print(f"  Throughput: {segments_per_sec:.2f} segments/second")
    print(f"  Avg time per segment: {elapsed/num_segments:.2f}s")
    print(f"{'='*60}\n")
    
    return segments_per_sec

if __name__ == "__main__":
    throughput = main()
    # Output just the number for parsing
    print(f"THROUGHPUT:{throughput:.3f}")
PYTHON_EOF
    
    # Run the benchmark and capture throughput
    THROUGHPUT=$(cd /Users/matthewgreer/Projects/Knowledge_Chipper && \
                 source .venv/bin/activate 2>/dev/null && \
                 python /tmp/test_mining_benchmark.py $TEST_SEGMENTS 2>&1 | \
                 tee /dev/tty | \
                 grep "THROUGHPUT:" | \
                 cut -d: -f2)
    
    # Record results
    echo "" >> "$LOG_FILE"
    echo "OLLAMA_NUM_PARALLEL=$NUM_PARALLEL" >> "$LOG_FILE"
    echo "  Segments processed: $TEST_SEGMENTS" >> "$LOG_FILE"
    echo "  Throughput: $THROUGHPUT segments/second" >> "$LOG_FILE"
    echo "  CPU during test: $(top -l 1 | grep "CPU usage" | awk '{print $3}')" >> "$LOG_FILE"
    echo "" >> "$LOG_FILE"
    
    echo ""
    echo "✅ Test complete: $THROUGHPUT segments/second"
    echo ""
    echo "Cooling down (5 seconds)..."
    sleep 5
done

echo ""
echo "════════════════════════════════════════════════════════════════"
echo "✅ BENCHMARK COMPLETE"
echo "════════════════════════════════════════════════════════════════"
echo ""
echo "Results saved to: $LOG_FILE"
echo ""
cat "$LOG_FILE"
echo ""
echo "════════════════════════════════════════════════════════════════"
echo ""
echo "📊 To apply the optimal setting, edit configure_ollama_parallel.sh"
echo "   and set OLLAMA_NUM_PARALLEL to the value with highest throughput"
echo ""

