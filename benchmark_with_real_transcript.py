#!/usr/bin/env python3
"""
Benchmark with ACTUAL transcript from your app.
"""
import sys
import time
import subprocess
import glob
import re
from pathlib import Path

# Add project to path
sys.path.insert(0, '/Users/matthewgreer/Projects/Knowledge_Chipper/src')

from knowledge_system.processors.hce.types import Segment, EpisodeBundle
from knowledge_system.processors.hce.unified_miner import mine_episode_unified


def parse_your_transcript(max_segments: int = 50) -> list[Segment]:
    """Parse the actual transcript format from your transcription tab."""
    
    # Find the file
    files = glob.glob("output/transcripts/*Bannon*.md")
    if not files:
        raise FileNotFoundError("Bannon transcript not found")
    
    with open(files[0], 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Split by --- separators
    sections = content.split('\n---\n')
    
    segments = []
    for section in sections:
        lines = section.strip().split('\n')
        if len(lines) < 3:
            continue
        
        # Find speaker (bold text: **Name**)
        speaker = None
        timestamp = None
        text_lines = []
        
        for line in lines:
            # Speaker line
            if line.startswith('**') and line.endswith('**'):
                speaker = line.strip('*')
            # Timestamp line with [MM:SS] format
            elif '*[' in line and '](http' in line:
                # Extract timestamp like [01:30]
                match = re.search(r'\[(\d+:\d+)\]', line)
                if match:
                    timestamp = match.group(1)
            # Regular text
            elif line and not line.startswith('#') and not line.startswith('*'):
                text_lines.append(line)
        
        # Create segment if we have all required fields
        if speaker and timestamp and text_lines:
            text = ' '.join(text_lines).strip()
            if text:  # Skip empty segments
                segment = Segment(
                    episode_id="vvj_J2tB2Ag",
                    segment_id=f"seg_{len(segments):04d}",
                    speaker=speaker,
                    t0=timestamp,
                    t1=timestamp,  # We don't have end time, use start time
                    text=text
                )
                segments.append(segment)
                
                if len(segments) >= max_segments:
                    break
    
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
    
    print(f"  ✓ Ollama configured with NUM_PARALLEL={num_parallel}")


def benchmark_mining(segments: list[Segment], num_parallel: int) -> dict:
    """Run mining benchmark and return results."""
    print(f"\n{'='*70}")
    print(f"TESTING OLLAMA_NUM_PARALLEL={num_parallel}")
    print(f"{'='*70}")
    
    # Configure Ollama
    configure_ollama(num_parallel)
    
    # Create episode bundle
    episode = EpisodeBundle(
        episode_id="vvj_J2tB2Ag",
        segments=segments,
        metadata={"title": "Bannon Digital Serfs"}
    )
    
    model_uri = "ollama:qwen2.5:7b-instruct"
    
    print(f"Mining {len(segments)} segments from Bannon transcript...")
    print(f"Model: {model_uri}")
    print(f"Expected workers: 7 (auto-calculated for M2 Ultra)")
    print()
    
    # Run mining with timing
    start_time = time.time()
    completed_count = [0]
    
    def progress_callback(msg: str):
        if "Processed segment" in msg:
            completed_count[0] += 1
            elapsed = time.time() - start_time
            rate = completed_count[0] / elapsed if elapsed > 0 else 0
            print(f"  [{completed_count[0]:3d}/{len(segments)}] {rate:.2f} seg/sec")
    
    try:
        results = mine_episode_unified(
            episode=episode,
            miner_model_uri=model_uri,
            max_workers=None,  # Auto-calculate
            progress_callback=progress_callback
        )
        
        elapsed = time.time() - start_time
        throughput = len(segments) / elapsed
        avg_per_segment = elapsed / len(segments)
        
        print(f"\n{'─'*70}")
        print(f"RESULTS:")
        print(f"  Segments: {len(segments)}")
        print(f"  Time: {elapsed:.2f}s ({elapsed/60:.1f} min)")
        print(f"  Throughput: {throughput:.3f} segments/second")
        print(f"  Avg per segment: {avg_per_segment:.2f}s")
        print(f"{'─'*70}\n")
        
        return {
            'num_parallel': num_parallel,
            'segments': len(segments),
            'elapsed': elapsed,
            'throughput': throughput,
            'avg_per_segment': avg_per_segment,
            'success': True
        }
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return {
            'num_parallel': num_parallel,
            'success': False,
            'error': str(e)
        }


def main():
    print("="*70)
    print("REAL TRANSCRIPT MINING BENCHMARK")
    print("Testing OLLAMA_NUM_PARALLEL with actual Bannon transcript")
    print("="*70)
    print()
    
    # Parse your actual transcript
    print("Parsing Bannon transcript from transcription tab output...")
    try:
        segments = parse_your_transcript(max_segments=50)
        print(f"✓ Loaded {len(segments)} segments from transcript")
        print(f"  First segment: {segments[0].speaker} at {segments[0].t0}")
        print(f"  Last segment: {segments[-1].speaker} at {segments[-1].t0}\n")
    except Exception as e:
        print(f"❌ Failed to parse transcript: {e}")
        return 1
    
    # Test configurations
    test_configs = [2, 4, 6, 7]
    results = []
    
    print(f"Will test {len(test_configs)} configurations: {test_configs}")
    print(f"Estimated time: ~15-20 minutes\n")
    
    for num_parallel in test_configs:
        result = benchmark_mining(segments, num_parallel)
        results.append(result)
        print("Cooling down (5 seconds)...\n")
        time.sleep(5)
    
    # Summary
    print("\n" + "="*70)
    print("BENCHMARK SUMMARY")
    print("="*70)
    print()
    print(f"{'Configuration':<25} {'Throughput':<20} {'Total Time':<15}")
    print("─"*70)
    
    for result in results:
        if result['success']:
            config = f"OLLAMA_NUM_PARALLEL={result['num_parallel']}"
            throughput = f"{result['throughput']:.3f} seg/sec"
            total_time = f"{result['elapsed']:.1f}s"
            print(f"{config:<25} {throughput:<20} {total_time:<15}")
        else:
            config = f"OLLAMA_NUM_PARALLEL={result['num_parallel']}"
            print(f"{config:<25} {'FAILED':<20} {'N/A':<15}")
    
    print()
    
    # Find best config
    successful = [r for r in results if r['success']]
    if successful:
        best = max(successful, key=lambda x: x['throughput'])
        baseline = successful[0]  # NUM_PARALLEL=2
        improvement = ((best['throughput'] / baseline['throughput']) - 1) * 100
        
        print(f"🎯 OPTIMAL: OLLAMA_NUM_PARALLEL={best['num_parallel']}")
        print(f"   Throughput: {best['throughput']:.3f} seg/sec")
        print(f"   Improvement: {improvement:+.1f}% vs NUM_PARALLEL=2")
        print()
        print(f"To apply: Run ./configure_ollama_parallel.sh")
        print(f"   Then edit to set OLLAMA_NUM_PARALLEL={best['num_parallel']}")
    
    print()
    print("="*70)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

