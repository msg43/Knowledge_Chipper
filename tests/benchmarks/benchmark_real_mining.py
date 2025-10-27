#!/usr/bin/env python3
"""
Benchmark unified mining with real episode data.
Tests different OLLAMA_NUM_PARALLEL values by processing actual segments.
"""
import subprocess
import sys
import time
from pathlib import Path

# Add project to path
sys.path.insert(0, "/Users/matthewgreer/Projects/Knowledge_Chipper/src")

from knowledge_system.processors.hce.types import EpisodeBundle, Segment
from knowledge_system.processors.hce.unified_miner import mine_episode_unified


def parse_transcript_to_segments(
    transcript_path: Path, max_segments: int = 50
) -> list[Segment]:
    """Parse markdown transcript into Segment objects."""
    segments = []

    with open(transcript_path) as f:
        lines = f.readlines()

    current_speaker = None
    current_time = None
    current_text = []

    for line in lines:
        line = line.strip()

        # Skip metadata and headers
        if (
            line.startswith("---")
            or line.startswith("#")
            or line.startswith("*")
            or line.startswith("!")
        ):
            continue

        # Detect speaker lines (bold text)
        if line.startswith("**") and line.endswith("**"):
            # Save previous segment if exists
            if current_speaker and current_text:
                text = " ".join(current_text).strip()
                if text:
                    segment = Segment(
                        segment_id=f"seg_{len(segments):04d}",
                        episode_id="vvj_J2tB2Ag",
                        speaker=current_speaker,
                        text=text,
                        transcript=text,
                        t0=current_time if current_time else len(segments) * 30.0,
                        t1=(current_time + 30.0)
                        if current_time
                        else (len(segments) + 1) * 30.0,
                        start_time=current_time
                        if current_time
                        else len(segments) * 30.0,
                        end_time=(current_time + 30.0)
                        if current_time
                        else (len(segments) + 1) * 30.0,
                    )
                    segments.append(segment)

                    if len(segments) >= max_segments:
                        return segments

            # Start new segment
            current_speaker = line.strip("*")
            current_text = []
            current_time = None

        # Detect timestamp
        elif line and ":" in line and len(line) < 10:
            try:
                parts = line.split(":")
                if len(parts) == 2:
                    mins = int(parts[0])
                    secs = int(parts[1])
                    current_time = mins * 60 + secs
            except:
                pass

        # Regular text
        elif line and not line.startswith("[") and current_speaker:
            current_text.append(line)

    # Save last segment
    if current_speaker and current_text:
        text = " ".join(current_text).strip()
        if text:
            segment = Segment(
                segment_id=f"seg_{len(segments):04d}",
                episode_id="vvj_J2tB2Ag",
                speaker=current_speaker,
                text=text,
                transcript=text,
                t0=current_time if current_time else len(segments) * 30.0,
                t1=(current_time + 30.0)
                if current_time
                else (len(segments) + 1) * 30.0,
                start_time=current_time if current_time else len(segments) * 30.0,
                end_time=(current_time + 30.0)
                if current_time
                else (len(segments) + 1) * 30.0,
            )
            segments.append(segment)

    return segments[:max_segments]


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
    subprocess.run(["killall", "Ollama"], capture_output=True)
    subprocess.run(["launchctl", "unload", str(plist_path)], capture_output=True)
    time.sleep(2)

    # Write new config
    plist_path.write_text(plist_content)

    # Start Ollama
    subprocess.run(["launchctl", "load", str(plist_path)], capture_output=True)
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
        episode_id="vvj_J2tB2Ag_benchmark",
        segments=segments,
        metadata={"title": "Bannon Digital Serfs Benchmark"},
    )

    # Run mining with timing
    model_uri = "ollama:qwen2.5:7b-instruct"

    print(f"Mining {len(segments)} segments with auto-calculated workers...")
    print(f"(Model: {model_uri})")

    start_time = time.time()
    completed_count = [0]  # Use list for mutable closure

    def progress_callback(msg: str):
        if "Processed segment" in msg:
            completed_count[0] += 1
            elapsed = time.time() - start_time
            rate = completed_count[0] / elapsed if elapsed > 0 else 0
            print(
                f"  [{completed_count[0]:3d}/{len(segments)}] {rate:.2f} seg/sec - {msg}"
            )

    try:
        results = mine_episode_unified(
            episode=episode,
            miner_model_uri=model_uri,
            max_workers=None,  # Auto-calculate (should be 7 for M2 Ultra)
            progress_callback=progress_callback,
        )

        elapsed = time.time() - start_time
        throughput = len(segments) / elapsed
        avg_per_segment = elapsed / len(segments)

        print(f"\n{'─'*70}")
        print(f"RESULTS:")
        print(f"  Total segments: {len(segments)}")
        print(f"  Total time: {elapsed:.2f}s")
        print(f"  Throughput: {throughput:.3f} segments/second")
        print(f"  Avg per segment: {avg_per_segment:.2f}s")
        print(f"{'─'*70}\n")

        return {
            "num_parallel": num_parallel,
            "segments": len(segments),
            "elapsed": elapsed,
            "throughput": throughput,
            "avg_per_segment": avg_per_segment,
            "success": True,
        }

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        return {"num_parallel": num_parallel, "success": False, "error": str(e)}


def main():
    print("=" * 70)
    print("REAL-WORLD UNIFIED MINING BENCHMARK")
    print("=" * 70)
    print()

    # Load transcript (use glob to handle special characters in filename)
    transcript_dir = Path(
        "/Users/matthewgreer/Projects/Knowledge_Chipper/output/transcripts"
    )
    transcript_files = list(transcript_dir.glob("*Bannon*Digital Serfs*.md"))

    if not transcript_files:
        print(f"❌ Transcript not found in: {transcript_dir}")
        return 1

    transcript_path = transcript_files[0]

    print(f"Loading transcript: {transcript_path.name}")
    segments = parse_transcript_to_segments(transcript_path, max_segments=50)
    print(f"✓ Loaded {len(segments)} segments\n")

    if len(segments) < 10:
        print(
            f"⚠️  Warning: Only {len(segments)} segments found. Results may not be reliable."
        )

    # Test configurations
    test_configs = [2, 4, 6, 7]
    results = []

    for num_parallel in test_configs:
        result = benchmark_mining(segments, num_parallel)
        results.append(result)
        time.sleep(3)  # Cooldown between tests

    # Summary
    print("\n" + "=" * 70)
    print("BENCHMARK SUMMARY")
    print("=" * 70)
    print()
    print(f"{'Config':<20} {'Throughput':<20} {'Avg Time':<15} {'Status'}")
    print("─" * 70)

    for result in results:
        if result["success"]:
            config = f"NUM_PARALLEL={result['num_parallel']}"
            throughput = f"{result['throughput']:.3f} seg/sec"
            avg_time = f"{result['avg_per_segment']:.2f}s"
            status = "✓"
        else:
            config = f"NUM_PARALLEL={result['num_parallel']}"
            throughput = "N/A"
            avg_time = "N/A"
            status = f"✗ {result.get('error', 'Failed')[:20]}"

        print(f"{config:<20} {throughput:<20} {avg_time:<15} {status}")

    print()

    # Find best config
    successful = [r for r in results if r["success"]]
    if successful:
        best = max(successful, key=lambda x: x["throughput"])
        print(f"🎯 OPTIMAL CONFIGURATION: OLLAMA_NUM_PARALLEL={best['num_parallel']}")
        print(f"   Throughput: {best['throughput']:.3f} segments/second")
        print(
            f"   {((best['throughput'] / successful[0]['throughput']) - 1) * 100:.1f}% faster than NUM_PARALLEL=2"
        )

    print()
    print("=" * 70)

    return 0


if __name__ == "__main__":
    sys.exit(main())
