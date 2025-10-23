#!/usr/bin/env python3
"""
Simple benchmark: Test different OLLAMA_NUM_PARALLEL values with synthetic segments.
"""
import sys
import time
import subprocess
from pathlib import Path

# Add project to path
sys.path.insert(0, '/Users/matthewgreer/Projects/Knowledge_Chipper/src')

from knowledge_system.processors.hce.types import Segment, EpisodeBundle
from knowledge_system.processors.hce.unified_miner import mine_episode_unified


def create_realistic_segments(count: int = 50) -> list[Segment]:
    """Create realistic segments based on Bannon transcript."""
    
    # Sample realistic political/tech discussion text
    segment_texts = [
        "Silicon Valley is basically trying to bring in as much foreign labor as possible to keep costs down. This is not just about H1B visas, but about a broader vision of technofutilism.",
        "Obama made a Faustian bargain with the sociopathic overlords on Wall Street to bail us out of the 2008 crisis. At the same time, the established order went to Silicon Valley and made a deal with them.",
        "We will allow you to become the wealthiest people in the history of the world. We will let you create an apartheid state. We will let you become monopolies with no antitrust enforcement.",
        "The Chinese Communist Party and the PLA created TikTok, which is far more powerful than all the social media platforms these guys put together. We now know they face planted on AI.",
        "In technofutilism, you're just a digital serf. Your value as a human being built in the image and likeness of God is not considered. Everything's digital to them. They are transhumanist at the end of the day.",
        "Transhumanists see homo sapien here and homo sapien plus on the other side of what they call the singularity. They're rushing toward artificial intelligence, regenerative robotics, quantum computing, advanced chip design, CRISPR biotech.",
        "The oligarchs are going to lead that revolution because they want eternal life. They're complete atheistic eleven year old boys that are kind of science fiction dungeon and dragons guys.",
        "Elon got the first awakening because as an engineer he could see the math. He fully supported our plan to go to the low information voters who had flipped during the pandemic.",
        "The rest of them, even Andreessen, they're all super progressive liberals. They're all technofutilists. They don't give a flying fuck about the human being.",
        "If we don't stop it now, it's going to destroy not just this country but the world. We have no controls over artificial intelligence. We've allowed these monopolies to exist.",
    ]
    
    speakers = ["Steve Bannon", "Ross Douthat"]
    segments = []
    
    for i in range(count):
        # Cycle through segment texts
        text = segment_texts[i % len(segment_texts)]
        speaker = speakers[i % 2]  # Alternate speakers
        
        # Create timestamps (30 second segments)
        start_sec = i * 30
        end_sec = start_sec + 30
        t0 = f"{start_sec // 60:02d}:{start_sec % 60:02d}"
        t1 = f"{end_sec // 60:02d}:{end_sec % 60:02d}"
        
        segment = Segment(
            episode_id="benchmark_test",
            segment_id=f"seg_{i:04d}",
            speaker=speaker,
            t0=t0,
            t1=t1,
            text=text
        )
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
        episode_id="benchmark_test",
        segments=segments,
        metadata={"title": "Bannon Digital Serfs Benchmark"}
    )
    
    model_uri = "ollama:qwen2.5:7b-instruct"
    
    print(f"Mining {len(segments)} segments...")
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
        print(f"  Time: {elapsed:.2f}s")
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
    print("UNIFIED MINING BENCHMARK - OLLAMA PARALLEL OPTIMIZATION")
    print("="*70)
    print()
    
    # Create synthetic segments
    print("Creating 50 realistic test segments...")
    segments = create_realistic_segments(50)
    print(f"✓ Created {len(segments)} segments\n")
    
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
        print(f"To apply: Edit configure_ollama_parallel.sh")
        print(f"   Set OLLAMA_NUM_PARALLEL={best['num_parallel']}")
    
    print()
    print("="*70)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

