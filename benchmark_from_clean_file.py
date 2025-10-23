#!/usr/bin/env python3
"""
Benchmark using pre-extracted clean segment file.
Fast, repeatable, consistent.
"""
import sys
import time
import subprocess
import json
from pathlib import Path

# Add project to path
sys.path.insert(0, '/Users/matthewgreer/Projects/Knowledge_Chipper/src')

from knowledge_system.processors.hce.types import Segment, EpisodeBundle
from knowledge_system.processors.hce.unified_miner import mine_episode_unified


def load_segments(json_path: str = 'benchmark_segments.json') -> list[Segment]:
    """Load segments from clean JSON file."""
    with open(json_path, 'r') as f:
        data = json.load(f)
    
    segments = []
    for seg_data in data:
        segment = Segment(**seg_data)
        segments.append(segment)
    
    return segments


def configure_ollama(num_parallel: int):
    """Configure Ollama with specified NUM_PARALLEL."""
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
    
    # Stop Ollama
    subprocess.run(['killall', 'Ollama'], capture_output=True)
    subprocess.run(['launchctl', 'unload', str(plist_path)], capture_output=True)
    time.sleep(2)
    
    # Write new config
    plist_path.write_text(plist_content)
    
    # Start Ollama
    subprocess.run(['launchctl', 'load', str(plist_path)], capture_output=True)
    time.sleep(3)


def benchmark_mining(segments: list[Segment], num_parallel: int) -> dict:
    """Run mining benchmark and return results."""
    print(f"\n{'='*70}")
    print(f"TESTING OLLAMA_NUM_PARALLEL={num_parallel}")
    print(f"{'='*70}")
    
    configure_ollama(num_parallel)
    print(f"✓ Ollama configured, model loading...")
    
    episode = EpisodeBundle(
        episode_id="vvj_J2tB2Ag",
        segments=segments,
        metadata={"title": "Bannon Benchmark"}
    )
    
    model_uri = "ollama:qwen2.5:7b-instruct"
    print(f"Mining {len(segments)} segments (workers: auto-calc)")
    
    start_time = time.time()
    completed_count = [0]
    
    def progress_callback(msg: str):
        if "Processed segment" in msg:
            completed_count[0] += 1
            elapsed = time.time() - start_time
            rate = completed_count[0] / elapsed if elapsed > 0 else 0
            print(f"  [{completed_count[0]:2d}/{len(segments)}] {rate:.2f} seg/sec")
    
    try:
        results = mine_episode_unified(
            episode=episode,
            miner_model_uri=model_uri,
            max_workers=None,
            progress_callback=progress_callback
        )
        
        elapsed = time.time() - start_time
        throughput = len(segments) / elapsed
        
        print(f"\n✅ RESULTS:")
        print(f"   Time: {elapsed:.1f}s ({elapsed/60:.1f} min)")
        print(f"   Throughput: {throughput:.3f} seg/sec")
        print(f"   Avg/segment: {elapsed/len(segments):.2f}s\n")
        
        return {
            'num_parallel': num_parallel,
            'elapsed': elapsed,
            'throughput': throughput,
            'success': True
        }
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        return {'num_parallel': num_parallel, 'success': False, 'error': str(e)}


def main():
    print("="*70)
    print("OLLAMA PARALLEL BENCHMARK - Clean Segment File")
    print("="*70)
    print()
    
    # Load segments
    try:
        segments = load_segments('benchmark_segments.json')
        print(f"✓ Loaded {len(segments)} segments from benchmark_segments.json\n")
    except FileNotFoundError:
        print("❌ benchmark_segments.json not found. Run extraction first.")
        return 1
    
    # Test configurations
    test_configs = [2, 4, 6, 7]
    results = []
    
    print(f"Testing configs: {test_configs}")
    print(f"Estimated time: ~10-12 minutes\n")
    
    for num_parallel in test_configs:
        result = benchmark_mining(segments, num_parallel)
        results.append(result)
        if num_parallel < test_configs[-1]:  # Don't wait after last one
            print("Cooling down (5s)...\n")
            time.sleep(5)
    
    # Summary
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    print(f"\n{'Config':<20} {'Throughput':<20} {'Time':<15}")
    print("─"*70)
    
    for r in results:
        if r['success']:
            print(f"NUM_PARALLEL={r['num_parallel']:<8} {r['throughput']:.3f} seg/sec{'':<7} {r['elapsed']:.1f}s")
    
    # Find best
    successful = [r for r in results if r['success']]
    if successful:
        best = max(successful, key=lambda x: x['throughput'])
        baseline = successful[0]
        improvement = ((best['throughput'] / baseline['throughput']) - 1) * 100
        
        print(f"\n🎯 OPTIMAL: NUM_PARALLEL={best['num_parallel']}")
        print(f"   {best['throughput']:.3f} seg/sec ({improvement:+.1f}% vs baseline)")
    
    print("\n" + "="*70 + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())

