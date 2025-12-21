#!/usr/bin/env python3
"""
YouTube Auto-Transcript vs Whisper Quality Comparison Test

Tests whether YouTube's auto-generated transcripts are good enough for claim extraction
by comparing them against Whisper transcription on real podcast samples.

Measures:
1. Transcript accuracy (Word Error Rate)
2. Claim extraction quality (number and overlap of claims)
3. Speaker attribution accuracy (for claims)
4. Processing time and cost differences

Usage:
    python test_youtube_vs_whisper_quality.py <video_url> [--whisper-model medium]
    python test_youtube_vs_whisper_quality.py --batch urls.txt
"""

import argparse
import json
import sys
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from knowledge_system.logger import get_logger
from knowledge_system.processors.youtube_download import YouTubeDownloadProcessor
from knowledge_system.processors.whisper_cpp_transcribe import WhisperCppTranscribeProcessor
from knowledge_system.config import get_settings

logger = get_logger(__name__)

# YouTube transcript extraction
try:
    from youtube_transcript_api import YouTubeTranscriptApi
    YOUTUBE_TRANSCRIPT_AVAILABLE = True
except ImportError:
    logger.warning("youtube-transcript-api not installed. Install with: pip install youtube-transcript-api")
    YOUTUBE_TRANSCRIPT_AVAILABLE = False


@dataclass
class TranscriptQualityMetrics:
    """Metrics for comparing transcript quality."""
    source: str  # "youtube" or "whisper"
    video_id: str
    video_title: str

    # Transcript metrics
    transcript_length: int  # Number of words
    processing_time_seconds: float

    # Accuracy (only available when comparing to Whisper as ground truth)
    word_error_rate: float | None = None  # WER vs Whisper

    # Claim extraction results
    num_claims_total: int = 0
    num_claims_a_tier: int = 0  # importance >= 8
    num_claims_b_tier: int = 0  # importance 6-7
    num_claims_c_tier: int = 0  # importance < 6

    avg_claim_importance: float = 0.0
    avg_claim_confidence: float = 0.0

    # Sample claims
    sample_claims: list[dict] = None

    # Speaker attribution
    num_claims_with_speaker: int = 0
    speaker_attribution_confidence: float = 0.0

    # Timestamps
    timestamp_precision: str = "none"  # "word", "segment", "none"

    # Cost estimate
    estimated_cost_usd: float = 0.0

    def __post_init__(self):
        if self.sample_claims is None:
            self.sample_claims = []


def extract_video_id(url: str) -> str:
    """Extract YouTube video ID from URL."""
    from knowledge_system.utils.youtube_utils import extract_urls
    urls = extract_urls(url)
    if not urls:
        raise ValueError(f"No valid YouTube URL found: {url}")

    # Extract video ID from URL
    video_id = None
    for part in urls[0].split('/'):
        if 'watch?v=' in urls[0]:
            video_id = urls[0].split('watch?v=')[1].split('&')[0]
            break
        elif 'youtu.be/' in urls[0]:
            video_id = urls[0].split('youtu.be/')[1].split('?')[0]
            break

    if not video_id:
        raise ValueError(f"Could not extract video ID from URL: {url}")

    return video_id


def get_youtube_transcript(video_url: str) -> tuple[str, dict]:
    """
    Get YouTube auto-generated transcript.

    Returns:
        (transcript_text, metadata)
    """
    if not YOUTUBE_TRANSCRIPT_AVAILABLE:
        raise RuntimeError("youtube-transcript-api not installed")

    video_id = extract_video_id(video_url)

    logger.info(f"📺 Fetching YouTube auto-transcript for {video_id}...")
    start_time = time.time()

    try:
        # Get transcript (API v1.0+ uses instance.fetch() and returns objects)
        api = YouTubeTranscriptApi()
        transcript_list = api.fetch(video_id)

        # Format as continuous text with timestamps
        full_text = []
        segments = []

        for entry in transcript_list:
            full_text.append(entry.text)
            segments.append({
                'start': entry.start,
                'duration': entry.duration,
                'text': entry.text
            })

        transcript_text = ' '.join(full_text)

        processing_time = time.time() - start_time

        metadata = {
            'source': 'youtube',
            'video_id': video_id,
            'num_segments': len(segments),
            'processing_time': processing_time,
            'segments': segments
        }

        logger.info(f"✅ YouTube transcript fetched in {processing_time:.1f}s ({len(transcript_text.split())} words)")

        return transcript_text, metadata

    except Exception as e:
        logger.error(f"❌ Failed to get YouTube transcript: {e}")
        raise


def get_whisper_transcript(video_url: str, model: str = "medium") -> tuple[str, dict]:
    """
    Get Whisper transcription with word-level timestamps.

    Returns:
        (transcript_text, metadata)
    """
    logger.info(f"🎤 Transcribing with Whisper model '{model}'...")

    # Download audio
    downloader = YouTubeDownloadProcessor(
        output_format="best",  # Will be converted to WAV
        download_thumbnails=False
    )

    logger.info("⬇️ Downloading audio...")
    download_start = time.time()
    download_result = downloader.process(video_url)

    if not download_result.success:
        raise RuntimeError(f"Download failed: {download_result.errors}")

    audio_path = Path(download_result.data['output_file'])
    video_id = download_result.data['metadata'].get('id', 'unknown')
    video_title = download_result.data['metadata'].get('title', 'Unknown')
    download_time = time.time() - download_start

    logger.info(f"✅ Audio downloaded in {download_time:.1f}s")

    # Transcribe with Whisper
    transcriber = WhisperCppTranscribeProcessor(
        model=model,
        enable_word_timestamps=True  # Critical for word-level timestamps
    )

    logger.info("🎤 Transcribing (this may take 5-15 minutes)...")
    transcribe_start = time.time()
    transcribe_result = transcriber.process(audio_path)

    if not transcribe_result.success:
        raise RuntimeError(f"Transcription failed: {transcribe_result.errors}")

    transcribe_time = time.time() - transcribe_start
    total_time = download_time + transcribe_time

    # Extract transcript text and words
    transcript_data = transcribe_result.data.get('transcript', {})
    transcript_text = transcript_data.get('text', '')
    words = transcript_data.get('words', [])

    metadata = {
        'source': 'whisper',
        'model': model,
        'video_id': video_id,
        'video_title': video_title,
        'num_words': len(words),
        'download_time': download_time,
        'transcribe_time': transcribe_time,
        'total_time': total_time,
        'words': words,  # Word-level timestamps
        'audio_path': str(audio_path)
    }

    logger.info(f"✅ Whisper transcript completed in {transcribe_time:.1f}s ({len(transcript_text.split())} words)")
    logger.info(f"📊 Total processing time: {total_time:.1f}s")

    return transcript_text, metadata


def calculate_wer(reference: str, hypothesis: str) -> float:
    """
    Calculate Word Error Rate (WER) between two transcripts.

    WER = (Substitutions + Deletions + Insertions) / Total Words in Reference

    Simple implementation using Levenshtein distance on words.
    """
    ref_words = reference.lower().split()
    hyp_words = hypothesis.lower().split()

    # Levenshtein distance on word level
    m, n = len(ref_words), len(hyp_words)
    dp = [[0] * (n + 1) for _ in range(m + 1)]

    for i in range(m + 1):
        dp[i][0] = i
    for j in range(n + 1):
        dp[0][j] = j

    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if ref_words[i-1] == hyp_words[j-1]:
                dp[i][j] = dp[i-1][j-1]
            else:
                dp[i][j] = 1 + min(
                    dp[i-1][j],    # deletion
                    dp[i][j-1],    # insertion
                    dp[i-1][j-1]   # substitution
                )

    edit_distance = dp[m][n]
    wer = edit_distance / max(m, 1)  # Avoid division by zero

    return wer


def extract_claims_real(transcript_text: str, metadata: dict) -> list[dict]:
    """
    Real claim extraction using HCE pipeline.
    
    Uses UnifiedMiner for candidate extraction and FlagshipEvaluator for scoring.
    """
    try:
        from knowledge_system.processors.hce.unified_miner import UnifiedMiner
        from knowledge_system.processors.hce.flagship_evaluator import FlagshipEvaluator
        
        logger.info("🔍 Running real HCE claim extraction...")
        
        # Stage 1: Mine candidate claims from transcript
        miner = UnifiedMiner()
        
        # UnifiedMiner expects full text - use the mine() method for claims-first
        miner_output = miner.mine(transcript_text, metadata)
        
        if not miner_output or not miner_output.claims:
            logger.warning("⚠️ No claims extracted by UnifiedMiner")
            return []
        
        logger.info(f"  📋 Mined {len(miner_output.claims)} candidate claims")
        
        # Stage 2: Evaluate and score claims
        evaluator = FlagshipEvaluator()
        
        # Create content summary for evaluator
        content_summary = metadata.get('title', 'Podcast transcript')
        if metadata.get('description'):
            content_summary += f": {metadata['description'][:200]}"
        
        eval_output = evaluator.evaluate_claims(content_summary, [miner_output])
        
        if not eval_output or not eval_output.evaluated_claims:
            logger.warning("⚠️ No claims after evaluation")
            return []
        
        logger.info(f"  ✅ Evaluated {len(eval_output.evaluated_claims)} claims")
        
        # Convert to dict format for compatibility
        claims = []
        for claim in eval_output.evaluated_claims:
            claims.append({
                'canonical': getattr(claim, 'canonical', str(claim)),
                'evidence': getattr(claim, 'evidence', ''),
                'importance': getattr(claim, 'importance', 5),
                'confidence': getattr(claim, 'confidence', 0.7),
                'tier': getattr(claim, 'tier', 'C'),
                'speaker': getattr(claim, 'speaker', 'Unknown'),
            })
        
        return claims
        
    except Exception as e:
        logger.error(f"❌ HCE extraction failed: {e}")
        logger.warning("⚠️ Falling back to mock extraction")
        return extract_claims_fallback(transcript_text, metadata)


def extract_claims_fallback(transcript_text: str, metadata: dict) -> list[dict]:
    """
    Fallback mock claim extraction when HCE is unavailable.
    """
    logger.warning("⚠️ Using FALLBACK claim extraction (HCE unavailable)")

    # Generate basic claims based on transcript length
    num_words = len(transcript_text.split())
    num_claims = max(5, num_words // 500)  # Roughly 1 claim per 500 words

    claims = []
    for i in range(num_claims):
        claims.append({
            'canonical': f'Fallback claim {i+1} extracted from transcript',
            'evidence': transcript_text[:100],
            'importance': 5 + (i % 5),  # 5-9
            'confidence': 0.7 + (i % 3) * 0.1,  # 0.7-0.9
            'speaker': 'Unknown',
        })

    return claims


def analyze_claims(claims: list[dict]) -> dict:
    """Analyze extracted claims and return statistics."""
    if not claims:
        return {
            'total': 0,
            'a_tier': 0,
            'b_tier': 0,
            'c_tier': 0,
            'avg_importance': 0.0,
            'avg_confidence': 0.0,
            'with_speaker': 0,
        }

    a_tier = [c for c in claims if c.get('importance', 0) >= 8]
    b_tier = [c for c in claims if 6 <= c.get('importance', 0) < 8]
    c_tier = [c for c in claims if c.get('importance', 0) < 6]

    with_speaker = [c for c in claims if c.get('speaker') and c['speaker'] != 'Unknown']

    importances = [c.get('importance', 0) for c in claims]
    confidences = [c.get('confidence', 0) for c in claims]

    return {
        'total': len(claims),
        'a_tier': len(a_tier),
        'b_tier': len(b_tier),
        'c_tier': len(c_tier),
        'avg_importance': sum(importances) / len(importances) if importances else 0.0,
        'avg_confidence': sum(confidences) / len(confidences) if confidences else 0.0,
        'with_speaker': len(with_speaker),
    }


def compare_transcripts(video_url: str, whisper_model: str = "medium") -> dict:
    """
    Compare YouTube auto-transcript vs Whisper transcription.

    Returns comparison results with metrics for both.
    """
    logger.info(f"🔬 Starting YouTube vs Whisper comparison")
    logger.info(f"📹 Video: {video_url}")
    logger.info(f"🎤 Whisper model: {whisper_model}")
    logger.info("=" * 80)

    # Get both transcripts
    yt_text, yt_meta = get_youtube_transcript(video_url)
    whisper_text, whisper_meta = get_whisper_transcript(video_url, whisper_model)

    # Calculate WER (using Whisper as ground truth)
    wer = calculate_wer(whisper_text, yt_text)
    accuracy_percent = (1 - wer) * 100

    logger.info(f"📊 Transcript Accuracy: YouTube is {accuracy_percent:.1f}% accurate vs Whisper")
    logger.info(f"   Word Error Rate: {wer:.3f}")

    # Extract claims from both
    logger.info("\n🔍 Extracting claims from YouTube transcript...")
    yt_claims = extract_claims_real(yt_text, yt_meta)
    yt_stats = analyze_claims(yt_claims)

    logger.info(f"✅ YouTube claims: {yt_stats['total']} total ({yt_stats['a_tier']} A-tier, {yt_stats['b_tier']} B-tier)")

    logger.info("\n🔍 Extracting claims from Whisper transcript...")
    whisper_claims = extract_claims_real(whisper_text, whisper_meta)
    whisper_stats = analyze_claims(whisper_claims)

    logger.info(f"✅ Whisper claims: {whisper_stats['total']} total ({whisper_stats['a_tier']} A-tier, {whisper_stats['b_tier']} B-tier)")

    # Build metrics
    yt_metrics = TranscriptQualityMetrics(
        source="youtube",
        video_id=yt_meta['video_id'],
        video_title=whisper_meta.get('video_title', 'Unknown'),
        transcript_length=len(yt_text.split()),
        processing_time_seconds=yt_meta['processing_time'],
        word_error_rate=wer,
        num_claims_total=yt_stats['total'],
        num_claims_a_tier=yt_stats['a_tier'],
        num_claims_b_tier=yt_stats['b_tier'],
        num_claims_c_tier=yt_stats['c_tier'],
        avg_claim_importance=yt_stats['avg_importance'],
        avg_claim_confidence=yt_stats['avg_confidence'],
        num_claims_with_speaker=yt_stats['with_speaker'],
        timestamp_precision="segment",
        estimated_cost_usd=0.01,  # Rough estimate for LLM claim extraction
        sample_claims=yt_claims[:3]
    )

    whisper_metrics = TranscriptQualityMetrics(
        source="whisper",
        video_id=whisper_meta['video_id'],
        video_title=whisper_meta['video_title'],
        transcript_length=len(whisper_text.split()),
        processing_time_seconds=whisper_meta['total_time'],
        word_error_rate=None,  # Whisper is ground truth
        num_claims_total=whisper_stats['total'],
        num_claims_a_tier=whisper_stats['a_tier'],
        num_claims_b_tier=whisper_stats['b_tier'],
        num_claims_c_tier=whisper_stats['c_tier'],
        avg_claim_importance=whisper_stats['avg_importance'],
        avg_claim_confidence=whisper_stats['avg_confidence'],
        num_claims_with_speaker=whisper_stats['with_speaker'],
        timestamp_precision="word",
        estimated_cost_usd=0.30,  # Rough estimate
        sample_claims=whisper_claims[:3]
    )

    return {
        'video_url': video_url,
        'whisper_model': whisper_model,
        'youtube': asdict(yt_metrics),
        'whisper': asdict(whisper_metrics),
        'comparison': {
            'youtube_accuracy_percent': accuracy_percent,
            'word_error_rate': wer,
            'claim_count_ratio': yt_stats['total'] / max(whisper_stats['total'], 1),
            'time_speedup': whisper_meta['total_time'] / max(yt_meta['processing_time'], 0.1),
            'cost_savings': whisper_metrics.estimated_cost_usd - yt_metrics.estimated_cost_usd,
        }
    }


def print_summary(results: dict):
    """Print human-readable summary of comparison results."""
    print("\n" + "=" * 80)
    print("📊 COMPARISON SUMMARY")
    print("=" * 80)

    yt = results['youtube']
    wh = results['whisper']
    comp = results['comparison']

    print(f"\n🎬 Video: {yt['video_title']}")
    print(f"🆔 Video ID: {yt['video_id']}")
    print(f"🎤 Whisper Model: {results['whisper_model']}")

    print(f"\n📊 TRANSCRIPT ACCURACY:")
    print(f"   YouTube Accuracy: {comp['youtube_accuracy_percent']:.1f}%")
    print(f"   Word Error Rate: {comp['word_error_rate']:.3f}")

    print(f"\n⏱️ PROCESSING TIME:")
    print(f"   YouTube: {yt['processing_time_seconds']:.1f}s")
    print(f"   Whisper: {wh['processing_time_seconds']:.1f}s")
    print(f"   Speedup: {comp['time_speedup']:.1f}x faster with YouTube")

    print(f"\n💵 COST ESTIMATE:")
    print(f"   YouTube: ${yt['estimated_cost_usd']:.3f}")
    print(f"   Whisper: ${wh['estimated_cost_usd']:.3f}")
    print(f"   Savings: ${comp['cost_savings']:.3f}")

    print(f"\n📝 CLAIM EXTRACTION:")
    print(f"   YouTube: {yt['num_claims_total']} claims ({yt['num_claims_a_tier']} A-tier)")
    print(f"   Whisper: {wh['num_claims_total']} claims ({wh['num_claims_a_tier']} A-tier)")
    print(f"   Ratio: {comp['claim_count_ratio']:.2f}")

    print(f"\n🎯 QUALITY METRICS:")
    print(f"   YouTube avg importance: {yt['avg_claim_importance']:.1f}")
    print(f"   Whisper avg importance: {wh['avg_claim_importance']:.1f}")

    print(f"\n⏰ TIMESTAMP PRECISION:")
    print(f"   YouTube: {yt['timestamp_precision']}")
    print(f"   Whisper: {wh['timestamp_precision']}")

    print("\n" + "=" * 80)

    # Recommendation
    if comp['youtube_accuracy_percent'] >= 85 and comp['claim_count_ratio'] >= 0.85:
        print("✅ RECOMMENDATION: YouTube transcripts appear good enough for your use case")
        print(f"   - {comp['youtube_accuracy_percent']:.0f}% accuracy is acceptable")
        print(f"   - Claims extracted are {comp['claim_count_ratio']*100:.0f}% as many as Whisper")
        print(f"   - {comp['time_speedup']:.0f}x faster processing")
    elif comp['youtube_accuracy_percent'] >= 75:
        print("⚠️ RECOMMENDATION: YouTube transcripts are marginal")
        print(f"   - {comp['youtube_accuracy_percent']:.0f}% accuracy may miss some claims")
        print("   - Consider hybrid approach: YouTube first, Whisper for high-value episodes")
    else:
        print("❌ RECOMMENDATION: Stick with Whisper")
        print(f"   - {comp['youtube_accuracy_percent']:.0f}% accuracy is too low")
        print("   - YouTube transcripts will significantly reduce claim quality")

    print("=" * 80)


def main():
    parser = argparse.ArgumentParser(
        description="Compare YouTube auto-transcripts vs Whisper for claim extraction quality"
    )
    parser.add_argument(
        'video_url',
        nargs='?',
        help='YouTube video URL to test'
    )
    parser.add_argument(
        '--batch',
        type=str,
        help='Path to file with multiple video URLs (one per line)'
    )
    parser.add_argument(
        '--whisper-model',
        type=str,
        default='medium',
        choices=['tiny', 'base', 'small', 'medium', 'large', 'large-v3'],
        help='Whisper model size (default: medium)'
    )
    parser.add_argument(
        '--output',
        type=str,
        help='Output file for JSON results'
    )

    args = parser.parse_args()

    if not args.video_url and not args.batch:
        parser.print_help()
        sys.exit(1)

    # Collect URLs
    urls = []
    if args.batch:
        with open(args.batch) as f:
            urls = [line.strip() for line in f if line.strip() and not line.startswith('#')]
    else:
        urls = [args.video_url]

    # Run comparisons
    results_list = []
    for i, url in enumerate(urls, 1):
        print(f"\n{'='*80}")
        print(f"Testing {i}/{len(urls)}: {url}")
        print(f"{'='*80}\n")

        try:
            results = compare_transcripts(url, args.whisper_model)
            results_list.append(results)

            print_summary(results)

        except Exception as e:
            logger.error(f"❌ Failed to compare {url}: {e}", exc_info=True)
            continue

    # Save results
    if args.output:
        output_path = Path(args.output)
        with open(output_path, 'w') as f:
            json.dump(results_list, f, indent=2)
        logger.info(f"💾 Results saved to {output_path}")

    # Print aggregate summary
    if len(results_list) > 1:
        avg_accuracy = sum(r['comparison']['youtube_accuracy_percent'] for r in results_list) / len(results_list)
        avg_speedup = sum(r['comparison']['time_speedup'] for r in results_list) / len(results_list)
        avg_claim_ratio = sum(r['comparison']['claim_count_ratio'] for r in results_list) / len(results_list)

        print(f"\n{'='*80}")
        print(f"📊 AGGREGATE RESULTS ({len(results_list)} videos)")
        print(f"{'='*80}")
        print(f"Average YouTube accuracy: {avg_accuracy:.1f}%")
        print(f"Average speedup: {avg_speedup:.1f}x")
        print(f"Average claim ratio: {avg_claim_ratio:.2f}")
        print(f"{'='*80}\n")


if __name__ == "__main__":
    main()
