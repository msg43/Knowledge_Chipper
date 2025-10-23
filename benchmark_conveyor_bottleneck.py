#!/usr/bin/env python3
"""
Benchmark to identify conveyor belt bottlenecks.

Tests the actual throughput of each stage:
1. Download (simulated - assume instant for local files)
2. Transcription (Whisper base, local)
3. Mining (nested schema + structured outputs)

Goal: Determine which stage is the bottleneck for 7000 podcast pipeline.
"""

import json
import time
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from knowledge_system.processors.hce.types import Segment, EpisodeBundle
from knowledge_system.processors.hce.unified_miner import mine_episode_unified


def simulate_transcription_speed(audio_duration_seconds: float) -> float:
    """
    Simulate transcription time based on real Whisper Base performance.
    
    Real-world measurements:
    - Whisper Base on M2 Ultra: ~10x realtime
    - 1 hour (3600s) audio → 360s (6 min) transcription
    
    Args:
        audio_duration_seconds: Audio duration in seconds
        
    Returns:
        Estimated transcription time in seconds
    """
    # 10x realtime = divide by 10
    return audio_duration_seconds / 10.0


def benchmark_mining_with_nested_schema(segment_file: Path, num_segments: int = 14) -> tuple[float, int, int]:
    """
    Benchmark mining using nested schema + structured outputs.
    
    Returns:
        (segments_per_second, total_claims, total_people)
    """
    # Load segments
    with open(segment_file) as f:
        segment_data = json.load(f)
    
    segments = [Segment(**s) for s in segment_data[:num_segments]]
    episode = EpisodeBundle(episode_id="benchmark", segments=segments, metadata={})
    
    print(f"\n🔬 MINING BENCHMARK (Nested Schema + Structured Outputs)")
    print(f"Segments: {len(segments)}")
    print(f"Model: ollama:qwen2.5:7b-instruct")
    print(f"Schema: miner_output.v1.json (nested with timestamps)")
    
    start = time.time()
    results = mine_episode_unified(
        episode=episode,
        miner_model_uri="ollama:qwen2.5:7b-instruct",
        max_workers=None  # Auto-calculate optimal
    )
    elapsed = time.time() - start
    
    total_claims = sum(len(r.claims) for r in results)
    total_people = sum(len(r.people) for r in results)
    
    seg_per_sec = len(segments) / elapsed
    
    print(f"\n📊 Results:")
    print(f"  Time: {elapsed:.1f}s")
    print(f"  Throughput: {seg_per_sec:.3f} seg/sec")
    print(f"  Per segment: {elapsed/len(segments):.1f}s")
    print(f"  Entities: {total_claims} claims, {total_people} people")
    
    return seg_per_sec, total_claims, total_people


def analyze_conveyor_belt(
    podcast_duration_minutes: int = 60,
    segments_per_hour: int = 120,
    mining_seg_per_sec: float = 0.1
):
    """
    Analyze conveyor belt throughput for the full pipeline.
    
    Args:
        podcast_duration_minutes: Podcast duration
        segments_per_hour: Number of segments per hour (typical: 120)
        mining_seg_per_sec: Mining throughput from benchmark
    """
    print(f"\n\n📊 CONVEYOR BELT ANALYSIS")
    print(f"=" * 60)
    
    podcast_duration_sec = podcast_duration_minutes * 60
    num_segments = int(segments_per_hour * (podcast_duration_minutes / 60))
    
    # Stage 1: Download (assume instant for local, or fast for remote)
    download_time = 30  # seconds (conservative estimate)
    
    # Stage 2: Transcription (10x realtime)
    transcription_time = simulate_transcription_speed(podcast_duration_sec)
    
    # Stage 3: Mining
    mining_time = num_segments / mining_seg_per_sec
    
    print(f"\n🎙️  Podcast: {podcast_duration_minutes} minutes ({podcast_duration_sec}s audio)")
    print(f"📝 Segments: {num_segments}")
    print(f"\n⏱️  STAGE TIMINGS (Sequential):")
    print(f"  1. Download:      {download_time:>7.1f}s  (  0.5 min)")
    print(f"  2. Transcription: {transcription_time:>7.1f}s  ({transcription_time/60:>5.1f} min)")
    print(f"  3. Mining:        {mining_time:>7.1f}s  ({mining_time/60:>5.1f} min)")
    print(f"  ----------------------------------------")
    print(f"  TOTAL:           {download_time + transcription_time + mining_time:>7.1f}s  ({(download_time + transcription_time + mining_time)/60:>5.1f} min)")
    
    # Identify bottleneck
    bottleneck = max(
        ("Download", download_time),
        ("Transcription", transcription_time),
        ("Mining", mining_time),
        key=lambda x: x[1]
    )
    
    print(f"\n🚨 BOTTLENECK: {bottleneck[0]} ({bottleneck[1]:.1f}s)")
    
    # Parallel conveyor belt (stages overlap)
    # Throughput is limited by the slowest stage
    parallel_time = max(download_time, transcription_time, mining_time)
    
    print(f"\n🔄 PARALLEL CONVEYOR BELT:")
    print(f"  Throughput limited by: {bottleneck[0]}")
    print(f"  Time per podcast: {parallel_time:.1f}s ({parallel_time/60:.1f} min)")
    
    # 7000 podcast projection
    print(f"\n📈 7000 PODCAST PROJECTION:")
    sequential_total = (download_time + transcription_time + mining_time) * 7000
    parallel_total = parallel_time * 7000
    
    print(f"  Sequential: {sequential_total/3600:.1f} hours ({sequential_total/3600/24:.1f} days)")
    print(f"  Parallel:   {parallel_total/3600:.1f} hours ({parallel_total/3600/24:.1f} days)")
    print(f"  Speedup:    {sequential_total/parallel_total:.1f}x")
    
    # Mining optimization impact
    if bottleneck[0] == "Mining":
        print(f"\n⚠️  Mining is the bottleneck! Optimization is CRITICAL.")
        print(f"  If we 2x mining speed: {(parallel_time/2)/60:.1f} min/podcast")
    elif mining_time < transcription_time:
        print(f"\n✅ Mining is NOT the bottleneck (faster than transcription).")
        print(f"  Mining takes: {(mining_time/transcription_time)*100:.0f}% of transcription time")
        print(f"  Optimizing mining beyond this point has diminishing returns.")
    else:
        print(f"\n⚠️  Mining is slower than transcription!")
        print(f"  Need to speed up mining to at least {transcription_time:.1f}s")
    
    return {
        "download_time": download_time,
        "transcription_time": transcription_time,
        "mining_time": mining_time,
        "bottleneck": bottleneck[0],
        "parallel_time": parallel_time,
        "sequential_total": sequential_total,
        "parallel_total": parallel_total
    }


def main():
    """Run the conveyor belt bottleneck benchmark."""
    segment_file = Path(__file__).parent / "benchmark_segments.json"
    
    if not segment_file.exists():
        print(f"❌ Segment file not found: {segment_file}")
        print("Please create benchmark_segments.json with test segments.")
        return 1
    
    print("=" * 60)
    print("CONVEYOR BELT BOTTLENECK BENCHMARK")
    print("=" * 60)
    
    # Benchmark mining with nested schema
    try:
        seg_per_sec, claims, people = benchmark_mining_with_nested_schema(segment_file, num_segments=14)
    except Exception as e:
        print(f"❌ Mining benchmark failed: {e}")
        import traceback
        traceback.print_exc()
        # Use fallback estimate
        print(f"\n⚠️  Using fallback estimate: 0.10 seg/sec")
        seg_per_sec = 0.10
    
    # Analyze conveyor belt
    results = analyze_conveyor_belt(
        podcast_duration_minutes=60,
        segments_per_hour=120,
        mining_seg_per_sec=seg_per_sec
    )
    
    # Summary
    print(f"\n\n{'=' * 60}")
    print("SUMMARY")
    print(f"{'=' * 60}")
    print(f"Mining throughput: {seg_per_sec:.3f} seg/sec")
    print(f"Bottleneck: {results['bottleneck']}")
    print(f"Optimal strategy: {'Optimize transcription' if results['bottleneck'] == 'Transcription' else 'Current mining speed is adequate' if results['bottleneck'] != 'Mining' else 'Optimize mining'}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

