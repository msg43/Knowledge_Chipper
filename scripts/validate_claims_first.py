#!/usr/bin/env python3
"""
Validate Claims-First Pipeline

This script processes a set of test podcasts to validate the claims-first
pipeline implementation. It compares results against speaker-first when
available and generates a detailed validation report.

Usage:
    python scripts/validate_claims_first.py
    python scripts/validate_claims_first.py --count 5
    python scripts/validate_claims_first.py --output-dir ./validation_results
"""

import argparse
import json
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from knowledge_system.logger import get_logger
from knowledge_system.processors.claims_first import (
    ClaimsFirstConfig,
    ClaimsFirstPipeline,
)
from knowledge_system.processors.claims_first.transcript_fetcher import TranscriptSourceType

logger = get_logger(__name__)


# =============================================================================
# Test Podcast URLs
# =============================================================================

# Curated list of podcasts for testing
# Mix of interview styles, lengths, and topics
TEST_PODCASTS = [
    # Tech/AI podcasts
    {
        "url": "https://www.youtube.com/watch?v=5p248yoa3oE",
        "title": "AI Alignment Research",
        "expected_claims": "technical, AI safety",
        "duration_estimate": 60,
    },
    {
        "url": "https://www.youtube.com/watch?v=HZRDUZuIKg4",
        "title": "Machine Learning Interview",
        "expected_claims": "technical, ML concepts",
        "duration_estimate": 45,
    },
    # Business/Economics podcasts
    {
        "url": "https://www.youtube.com/watch?v=mBq_kzgR6yU",
        "title": "Economic Analysis",
        "expected_claims": "economics, markets",
        "duration_estimate": 50,
    },
    # Science podcasts
    {
        "url": "https://www.youtube.com/watch?v=XTsaZWzVJ4c",
        "title": "Science Discussion",
        "expected_claims": "scientific, research",
        "duration_estimate": 40,
    },
    # Philosophy/Ideas podcasts
    {
        "url": "https://www.youtube.com/watch?v=qVRNWvOo8MY",
        "title": "Philosophy Interview",
        "expected_claims": "philosophical, ethics",
        "duration_estimate": 55,
    },
]


# =============================================================================
# Validation Functions
# =============================================================================


def get_existing_podcasts_from_db(limit: int = 20) -> list[dict]:
    """
    Get podcasts that have already been processed from the database.
    
    This allows us to compare claims-first results against existing data.
    """
    db_paths = [
        Path(__file__).parent.parent / "data" / "knowledge_system.db",
        Path(__file__).parent.parent / "knowledge_system.db",
    ]
    
    db_path = None
    for path in db_paths:
        if path.exists():
            db_path = path
            break
    
    if not db_path:
        logger.warning("No database found, using test URLs only")
        return []
    
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        # Get podcasts that have been transcribed
        cursor.execute("""
            SELECT source_id, title, url, transcript_path
            FROM media_sources
            WHERE transcript_path IS NOT NULL
                AND type = 'podcast'
            ORDER BY created_at DESC
            LIMIT ?
        """, (limit,))
        
        rows = cursor.fetchall()
        conn.close()
        
        podcasts = []
        for row in rows:
            podcasts.append({
                "source_id": row[0],
                "title": row[1] or "Unknown",
                "url": row[2] or "",
                "transcript_path": row[3],
            })
        
        return podcasts
        
    except Exception as e:
        logger.warning(f"Could not query database: {e}")
        return []


def run_claims_first_validation(
    podcast: dict,
    config: ClaimsFirstConfig,
) -> dict[str, Any]:
    """
    Run claims-first validation on a single podcast.
    
    Returns dict with validation results and metrics.
    """
    start_time = time.time()
    
    result = {
        "url": podcast.get("url", ""),
        "title": podcast.get("title", "Unknown"),
        "success": False,
        "error": None,
        "processing_time_seconds": 0,
        "transcript_source": None,
        "transcript_quality": None,
        "total_claims": 0,
        "a_tier_claims": 0,
        "b_tier_claims": 0,
        "claims_attributed": 0,
        "attribution_rate": 0,
        "sample_claims": [],
    }
    
    try:
        pipeline = ClaimsFirstPipeline(config=config)
        
        # Get audio path if available
        audio_path = None
        if "transcript_path" in podcast and podcast["transcript_path"]:
            # Try to find corresponding audio file
            transcript_path = Path(podcast["transcript_path"])
            possible_audio = transcript_path.with_suffix(".mp3")
            if possible_audio.exists():
                audio_path = possible_audio
        
        # Run pipeline
        pipeline_result = pipeline.process(
            source_url=podcast.get("url", ""),
            audio_path=audio_path,
            metadata={
                "title": podcast.get("title", ""),
                "source_id": podcast.get("source_id", ""),
            },
        )
        
        # Populate results
        result["success"] = True
        result["processing_time_seconds"] = time.time() - start_time
        result["transcript_source"] = pipeline_result.transcript.source_type.value
        result["transcript_quality"] = pipeline_result.transcript.quality_score
        result["total_claims"] = pipeline_result.total_claims
        result["a_tier_claims"] = len(pipeline_result.a_tier_claims)
        result["b_tier_claims"] = len(pipeline_result.b_tier_claims)
        result["claims_attributed"] = len(pipeline_result.attributed_claims)
        
        if pipeline_result.total_claims > 0:
            result["attribution_rate"] = (
                len(pipeline_result.attributed_claims) / pipeline_result.total_claims
            )
        
        # Get sample claims for review
        for claim in pipeline_result.claims[:5]:
            result["sample_claims"].append({
                "canonical": claim.canonical,
                "importance": claim.importance,
                "tier": claim.tier,
                "speaker": claim.speaker.speaker_name if claim.speaker else None,
                "timestamp": claim.timestamp.timestamp_start if claim.timestamp else None,
            })
        
    except Exception as e:
        result["error"] = str(e)
        result["processing_time_seconds"] = time.time() - start_time
        logger.error(f"Validation failed for {podcast.get('title', 'Unknown')}: {e}")
    
    return result


def generate_validation_report(results: list[dict], output_path: Path) -> dict:
    """
    Generate a comprehensive validation report.
    
    Returns summary statistics.
    """
    summary = {
        "timestamp": datetime.now().isoformat(),
        "total_podcasts": len(results),
        "successful": 0,
        "failed": 0,
        "total_claims": 0,
        "total_a_tier": 0,
        "total_b_tier": 0,
        "total_attributed": 0,
        "avg_processing_time": 0,
        "youtube_transcripts": 0,
        "whisper_transcripts": 0,
        "avg_transcript_quality": 0,
    }
    
    processing_times = []
    quality_scores = []
    
    for result in results:
        if result["success"]:
            summary["successful"] += 1
            summary["total_claims"] += result["total_claims"]
            summary["total_a_tier"] += result["a_tier_claims"]
            summary["total_b_tier"] += result["b_tier_claims"]
            summary["total_attributed"] += result["claims_attributed"]
            processing_times.append(result["processing_time_seconds"])
            
            if result["transcript_source"] == "youtube":
                summary["youtube_transcripts"] += 1
            else:
                summary["whisper_transcripts"] += 1
            
            if result["transcript_quality"]:
                quality_scores.append(result["transcript_quality"])
        else:
            summary["failed"] += 1
    
    if processing_times:
        summary["avg_processing_time"] = sum(processing_times) / len(processing_times)
    
    if quality_scores:
        summary["avg_transcript_quality"] = sum(quality_scores) / len(quality_scores)
    
    # Write detailed report
    report = {
        "summary": summary,
        "results": results,
    }
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, "w") as f:
        json.dump(report, f, indent=2)
    
    # Also write a human-readable summary
    summary_path = output_path.with_suffix(".txt")
    with open(summary_path, "w") as f:
        f.write("=" * 60 + "\n")
        f.write("CLAIMS-FIRST PIPELINE VALIDATION REPORT\n")
        f.write("=" * 60 + "\n\n")
        f.write(f"Timestamp: {summary['timestamp']}\n")
        f.write(f"Total podcasts: {summary['total_podcasts']}\n")
        f.write(f"Successful: {summary['successful']}\n")
        f.write(f"Failed: {summary['failed']}\n\n")
        f.write("-" * 40 + "\n")
        f.write("CLAIM EXTRACTION\n")
        f.write("-" * 40 + "\n")
        f.write(f"Total claims extracted: {summary['total_claims']}\n")
        f.write(f"A-tier claims: {summary['total_a_tier']}\n")
        f.write(f"B-tier claims: {summary['total_b_tier']}\n")
        f.write(f"Claims with speaker attribution: {summary['total_attributed']}\n\n")
        f.write("-" * 40 + "\n")
        f.write("TRANSCRIPT SOURCES\n")
        f.write("-" * 40 + "\n")
        f.write(f"YouTube transcripts: {summary['youtube_transcripts']}\n")
        f.write(f"Whisper transcripts: {summary['whisper_transcripts']}\n")
        f.write(f"Average quality score: {summary['avg_transcript_quality']:.2f}\n\n")
        f.write("-" * 40 + "\n")
        f.write("PERFORMANCE\n")
        f.write("-" * 40 + "\n")
        f.write(f"Average processing time: {summary['avg_processing_time']:.1f} seconds\n\n")
        
        f.write("=" * 60 + "\n")
        f.write("SAMPLE CLAIMS\n")
        f.write("=" * 60 + "\n\n")
        
        for result in results:
            if result["success"] and result["sample_claims"]:
                f.write(f"\n{result['title']}\n")
                f.write("-" * 40 + "\n")
                for claim in result["sample_claims"][:3]:
                    f.write(f"  [{claim['tier']}] {claim['canonical'][:80]}...\n")
                    if claim["speaker"]:
                        f.write(f"      Speaker: {claim['speaker']}\n")
    
    logger.info(f"Validation report written to: {output_path}")
    logger.info(f"Summary written to: {summary_path}")
    
    return summary


def main():
    parser = argparse.ArgumentParser(
        description="Validate claims-first pipeline on test podcasts"
    )
    parser.add_argument(
        "--count", "-n",
        type=int,
        default=20,
        help="Number of podcasts to validate (default: 20)"
    )
    parser.add_argument(
        "--output-dir", "-o",
        type=Path,
        default=Path("./output/validation"),
        help="Output directory for validation reports"
    )
    parser.add_argument(
        "--use-db",
        action="store_true",
        help="Use podcasts from database instead of test URLs"
    )
    parser.add_argument(
        "--youtube-only",
        action="store_true",
        help="Only use YouTube transcripts (skip Whisper)"
    )
    
    args = parser.parse_args()
    
    # Get podcasts to validate
    if args.use_db:
        podcasts = get_existing_podcasts_from_db(limit=args.count)
        if not podcasts:
            logger.warning("No podcasts found in database, using test URLs")
            podcasts = TEST_PODCASTS[:args.count]
    else:
        podcasts = TEST_PODCASTS[:args.count]
    
    logger.info(f"Validating claims-first pipeline on {len(podcasts)} podcasts")
    
    # Configure pipeline
    config = ClaimsFirstConfig(
        enabled=True,
        transcript_source="youtube" if args.youtube_only else "auto",
        youtube_quality_threshold=0.7,
        evaluator_model="configurable",
        lazy_attribution_min_importance=7,
        store_candidates=True,
    )
    
    # Run validation
    results = []
    for i, podcast in enumerate(podcasts, 1):
        logger.info(f"Processing {i}/{len(podcasts)}: {podcast.get('title', 'Unknown')}")
        result = run_claims_first_validation(podcast, config)
        results.append(result)
        
        # Log progress
        if result["success"]:
            logger.info(
                f"  ✅ Success: {result['total_claims']} claims, "
                f"{result['claims_attributed']} attributed, "
                f"{result['processing_time_seconds']:.1f}s"
            )
        else:
            logger.error(f"  ❌ Failed: {result['error']}")
    
    # Generate report
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = args.output_dir / f"validation_report_{timestamp}.json"
    
    summary = generate_validation_report(results, output_path)
    
    # Print summary
    print("\n" + "=" * 60)
    print("VALIDATION COMPLETE")
    print("=" * 60)
    print(f"Total: {summary['total_podcasts']} podcasts")
    print(f"Success: {summary['successful']} ({100*summary['successful']/max(1, summary['total_podcasts']):.0f}%)")
    print(f"Total claims: {summary['total_claims']}")
    print(f"A-tier claims: {summary['total_a_tier']}")
    print(f"Claims attributed: {summary['total_attributed']}")
    print(f"Average time: {summary['avg_processing_time']:.1f}s")
    print("=" * 60)
    
    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

