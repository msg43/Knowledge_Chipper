#!/usr/bin/env python3
"""
Compare YouTube AI summary vs Local LLM summary.
Works for any user with Playwright installed.
"""
import sys
import asyncio
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from knowledge_system.processors.dual_summary_processor import DualSummaryProcessor
from knowledge_system.logger import get_logger

logger = get_logger(__name__)


def print_comparison(result):
    """Print formatted comparison of both summaries."""
    print("\n" + "="*70)
    print(f"📹 Video: {result.data['url']}")
    print("="*70 + "\n")
    
    yt = result.data['youtube_summary']
    local = result.data['local_summary']
    comp = result.data['comparison']
    
    # YouTube summary
    print("🤖 YOUTUBE AI SUMMARY")
    print("-" * 70)
    if yt['success']:
        print(f"⏱️  Duration: {yt['duration']:.1f} seconds")
        print(f"📝 Length: {len(yt['summary'])} characters, {len(yt['summary'].split())} words")
        print()
        print(yt['summary'])
    else:
        print(f"❌ Failed: {yt['error']}")
    
    print("\n" + "-" * 70 + "\n")
    
    # Local summary
    print("🧠 LOCAL LLM SUMMARY")
    print("-" * 70)
    if local['success']:
        print(f"⏱️  Duration: {local['duration']:.1f} seconds")
        print(f"📝 Length: {len(local['summary'])} characters, {len(local['summary'].split())} words")
        print()
        print(local['summary'])
    else:
        print(f"❌ Failed: {local['error']}")
    
    print("\n" + "="*70)
    
    # Comparison
    if comp['both_succeeded']:
        print("📊 COMPARISON")
        print("-" * 70)
        print(f"Speed: YouTube was {comp['speed_ratio']:.1f}x faster")
        print(f"Length: Local was {comp['length_ratio']:.2f}x longer")
        print(f"YouTube: {comp['youtube_words']} words in {comp['youtube_duration']:.1f}s")
        print(f"Local:   {comp['local_words']} words in {comp['local_duration']:.1f}s")
    
    print("="*70 + "\n")


def main():
    if len(sys.argv) < 2:
        print("Usage: python compare_youtube_summaries.py <youtube_url>")
        print("\nExample:")
        print("  python compare_youtube_summaries.py https://www.youtube.com/watch?v=OIUNAYreyXY")
        sys.exit(1)
    
    url = sys.argv[1]
    
    print("\n🚀 Starting dual summary generation...")
    print(f"📺 URL: {url}\n")
    
    processor = DualSummaryProcessor()
    
    def progress(msg):
        print(f"  {msg}")
    
    result = processor.process(url, progress_callback=progress)
    
    if result.success:
        print_comparison(result)
    else:
        print(f"\n❌ Both methods failed")
        print(f"YouTube: {result.data['youtube_summary']['error']}")
        print(f"Local: {result.data['local_summary']['error']}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()

