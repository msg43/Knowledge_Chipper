#!/usr/bin/env python3
"""
Matrix benchmark: Test combinations of OLLAMA_NUM_PARALLEL and worker counts
to find optimal configuration for small paragraph (segment) analysis.

Tests:
- OLLAMA_NUM_PARALLEL: [2, 3, 4, 5, 6, 7, 8]
- Workers: [2, 4, 6, 7, 8]
- Segments: 14 (from benchmark_segments.json)
"""

import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, "src")

from knowledge_system.processors.hce.types import EpisodeBundle, Segment
from knowledge_system.processors.hce.unified_miner import mine_episode_unified

# Configuration matrix
OLLAMA_PARALLEL_VALUES = [2, 3, 4, 5, 6, 7, 8]
WORKER_VALUES = [2, 4, 6, 7, 8]

COOLDOWN_TIME = 5  # seconds between tests
MODEL_URI = "ollama:qwen2.5:7b-instruct"
SEGMENT_FILE = Path("benchmark_segments.json")


def configure_ollama(num_parallel: int) -> bool:
    """Configure Ollama with specified NUM_PARALLEL value."""
    plist_path = Path.home() / "Library/LaunchAgents/com.ollama.server.plist"
    
    plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
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
        <string>{num_parallel}</string>
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
"""
    
    try:
        # Stop Ollama
        subprocess.run(["killall", "Ollama"], stderr=subprocess.DEVNULL, check=False)
        subprocess.run(["launchctl", "unload", str(plist_path)], stderr=subprocess.DEVNULL, check=False)
        time.sleep(1)
        
        # Write new config
        plist_path.write_text(plist_content)
        
        # Start Ollama
        subprocess.run(["launchctl", "load", str(plist_path)], check=True, capture_output=True)
        time.sleep(3)
        
        # Verify
        result = subprocess.run(
            ["curl", "-s", "http://localhost:11434/api/version"],
            capture_output=True,
            timeout=5
        )
        return result.returncode == 0
    except Exception as e:
        print(f"⚠️  Failed to configure Ollama: {e}")
        return False


def load_segments() -> list[Segment]:
    """Load segments from benchmark file."""
    if not SEGMENT_FILE.exists():
        raise FileNotFoundError(f"Segment file not found: {SEGMENT_FILE}")
    
    with open(SEGMENT_FILE) as f:
        data = json.load(f)
    
    # Handle both array and object formats
    segment_list = data if isinstance(data, list) else data.get("segments", [])
    
    segments = []
    for seg_data in segment_list:
        segment = Segment(
            episode_id=seg_data["episode_id"],
            segment_id=seg_data["segment_id"],
            speaker=seg_data["speaker"],
            t0=seg_data["t0"],
            t1=seg_data["t1"],
            text=seg_data["text"]
        )
        segments.append(segment)
    
    return segments


def run_mining_test(segments: list[Segment], workers: int) -> tuple[float, int, int]:
    """
    Run unified mining with specified worker count.
    
    Returns:
        (elapsed_time, success_count, total_count)
    """
    episode = EpisodeBundle(
        episode_id="benchmark",
        segments=segments,
        metadata={}
    )
    
    start_time = time.time()
    try:
        results = mine_episode_unified(
            episode=episode,
            miner_model_uri=MODEL_URI,
            max_workers=workers
        )
        elapsed = time.time() - start_time
        success_count = len([r for r in results if r.claims or r.jargon or r.people or r.mental_models])
        return elapsed, success_count, len(segments)
    except Exception as e:
        elapsed = time.time() - start_time
        print(f"      ❌ Test failed: {e}")
        return elapsed, 0, len(segments)


def print_header():
    """Print benchmark header."""
    print("=" * 80)
    print("OLLAMA PARALLEL × WORKERS MATRIX BENCHMARK")
    print("=" * 80)
    print()
    print(f"Test material: {SEGMENT_FILE}")
    print(f"Model: {MODEL_URI}")
    print()
    print(f"OLLAMA_NUM_PARALLEL values: {OLLAMA_PARALLEL_VALUES}")
    print(f"Worker counts: {WORKER_VALUES}")
    print(f"Total tests: {len(OLLAMA_PARALLEL_VALUES) * len(WORKER_VALUES)}")
    print(f"Estimated time: ~{len(OLLAMA_PARALLEL_VALUES) * len(WORKER_VALUES) * 2} minutes")
    print()
    print("=" * 80)
    print()


def print_results_table(results: dict):
    """Print results as a formatted table."""
    print()
    print("=" * 100)
    print("RESULTS MATRIX")
    print("=" * 100)
    print()
    
    # Header
    print(f"{'NUM_PARALLEL':<15}", end="")
    for workers in WORKER_VALUES:
        print(f"{f'{workers}W':<12}", end="")
    print("  │  Best")
    print("-" * 100)
    
    # Rows
    for num_parallel in OLLAMA_PARALLEL_VALUES:
        print(f"{num_parallel:<15}", end="")
        row_results = []
        for workers in WORKER_VALUES:
            key = (num_parallel, workers)
            if key in results:
                elapsed, success, total = results[key]
                throughput = success / elapsed if elapsed > 0 else 0
                row_results.append((throughput, key))
                print(f"{throughput:>6.3f} s/s  ", end="")
            else:
                print(f"{'---':<12}", end="")
        
        # Find best in row
        if row_results:
            best_throughput, best_key = max(row_results, key=lambda x: x[0])
            print(f"  │  {best_key[1]}W @ {best_throughput:.3f} s/s")
        else:
            print()
    
    print()
    
    # Overall best
    if results:
        best_key = max(results.items(), key=lambda x: x[1][1] / x[1][0] if x[1][0] > 0 else 0)
        (num_parallel, workers), (elapsed, success, total) = best_key
        throughput = success / elapsed
        print("=" * 100)
        print(f"🎯 OPTIMAL: NUM_PARALLEL={num_parallel}, Workers={workers}")
        print(f"   Throughput: {throughput:.3f} seg/sec")
        print(f"   Time: {elapsed:.1f}s for {total} segments")
        print("=" * 100)


def main():
    """Run matrix benchmark."""
    print_header()
    
    # Load segments once
    try:
        segments = load_segments()
        print(f"✓ Loaded {len(segments)} segments from {SEGMENT_FILE}")
        print()
    except Exception as e:
        print(f"❌ Failed to load segments: {e}")
        return 1
    
    results = {}
    test_num = 0
    total_tests = len(OLLAMA_PARALLEL_VALUES) * len(WORKER_VALUES)
    
    for num_parallel in OLLAMA_PARALLEL_VALUES:
        print("=" * 80)
        print(f"TESTING OLLAMA_NUM_PARALLEL={num_parallel}")
        print("=" * 80)
        
        # Configure Ollama
        print(f"Configuring Ollama (NUM_PARALLEL={num_parallel})...", end=" ", flush=True)
        if not configure_ollama(num_parallel):
            print("❌ FAILED")
            continue
        print("✓")
        
        for workers in WORKER_VALUES:
            test_num += 1
            print(f"\n[{test_num}/{total_tests}] Workers={workers}... ", end="", flush=True)
            
            elapsed, success, total = run_mining_test(segments, workers)
            results[(num_parallel, workers)] = (elapsed, success, total)
            
            throughput = success / elapsed if elapsed > 0 else 0
            print(f"✓ {throughput:.3f} seg/sec ({elapsed:.1f}s)")
            
            # Cooldown between tests
            if test_num < total_tests:
                print(f"   Cooling down ({COOLDOWN_TIME}s)...", end="", flush=True)
                time.sleep(COOLDOWN_TIME)
                print(" ✓")
    
    # Print final results
    print_results_table(results)
    
    # Save raw results
    output_file = Path("benchmark_matrix_results.json")
    output_data = {
        "results": {
            f"parallel_{np}_workers_{w}": {
                "num_parallel": np,
                "workers": w,
                "elapsed": elapsed,
                "success": success,
                "total": total,
                "throughput": success / elapsed if elapsed > 0 else 0
            }
            for (np, w), (elapsed, success, total) in results.items()
        },
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "model": MODEL_URI,
        "segment_count": len(segments)
    }
    
    with open(output_file, "w") as f:
        json.dump(output_data, f, indent=2)
    
    print()
    print(f"📊 Raw results saved to: {output_file}")
    print()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

