#!/usr/bin/env python3
"""
LLM Extraction Benchmark Script

Tests claim extraction quality across three LLMs:
1. Local Qwen 2.5 (via Ollama)
2. GPT-4o-mini (OpenAI)
3. Claude 3.5 Sonnet (Anthropic)

Outputs a single markdown file comparing:
- Processing time
- Summary quality
- Claims, people, jargon, and mental models extracted

Usage:
    # From file:
    python scripts/benchmark_llm_extraction.py output/transcripts/my_podcast.md
    
    # From database by source_id:
    python scripts/benchmark_llm_extraction.py --source-id vvj_J2tB2Ag
    
    # List available source_ids in database:
    python scripts/benchmark_llm_extraction.py --list-sources
    
Example:
    python scripts/benchmark_llm_extraction.py output/transcripts/my_podcast.md
    python scripts/benchmark_llm_extraction.py --source-id abc123xyz -n 5 --models gpt_mini
"""

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from knowledge_system.config import get_settings
from knowledge_system.database.service import DatabaseService
from knowledge_system.processors.hce.types import Segment
from knowledge_system.processors.hce.unified_miner import UnifiedMiner
from knowledge_system.processors.hce.models.llm_system2 import System2LLM
from knowledge_system.processors.hce.model_uri_parser import parse_model_uri


# LLM configurations to benchmark
# Adjust the local model to match what you have installed via `ollama list`
BENCHMARK_MODELS = {
    "qwen_local": {
        "name": "Qwen 2.5 7B (Local)",
        "uri": "local://qwen2.5:7b-instruct",  # Adjust to your installed model
        "provider": "ollama",
    },
    "gpt_mini": {
        "name": "GPT-4o-mini (OpenAI)",
        "uri": "openai:gpt-4o-mini-2024-07-18",
        "provider": "openai",
    },
    "claude_sonnet": {
        "name": "Claude Sonnet 4 (Anthropic)",
        "uri": "anthropic:claude-sonnet-4-20250514",
        "provider": "anthropic",
    },
}


def list_available_sources() -> list[dict]:
    """List all available sources in the database with transcripts."""
    import sqlite3
    import os
    
    # Use the correct database path (absolute to avoid Cursor sandbox issues)
    db_path = os.environ.get(
        "KNOWLEDGE_SYSTEM_DB_PATH",
        "/Users/matthewgreer/Library/Application Support/Knowledge Chipper/knowledge_system.db"
    )
    
    # Query for sources that have transcripts
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        # Use the actual column names from the schema
        cursor.execute("""
            SELECT 
                t.source_id,
                ms.title,
                LENGTH(t.transcript_text) as transcript_length
            FROM transcripts t
            LEFT JOIN media_sources ms ON t.source_id = ms.source_id
            WHERE t.transcript_text IS NOT NULL AND LENGTH(t.transcript_text) > 0
            ORDER BY t.source_id DESC
            LIMIT 50
        """)
        
        sources = []
        for row in cursor.fetchall():
            sources.append({
                "source_id": row[0],
                "title": row[1] or "Unknown",
                "channel": "Unknown",
                "duration": 0,
                "transcript_length": row[2] or 0,
            })
        
        return sources


def load_transcript_from_db(source_id: str) -> tuple[str, list[Segment]]:
    """Load transcript and segments from database by source_id."""
    import sqlite3
    import json
    import os
    
    # Use the correct database path (absolute to avoid Cursor sandbox issues)
    db_path = os.environ.get(
        "KNOWLEDGE_SYSTEM_DB_PATH",
        "/Users/matthewgreer/Library/Application Support/Knowledge Chipper/knowledge_system.db"
    )
    
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        # Get the transcript content and segments JSON
        cursor.execute("""
            SELECT transcript_text, diarization_segments_json, transcript_segments_json 
            FROM transcripts 
            WHERE source_id = ?
        """, (source_id,))
        row = cursor.fetchone()
        
        if not row or not row[0]:
            raise ValueError(f"No transcript found for source_id: {source_id}")
        
        content = row[0]
        diarization_json = row[1]  # Segments with speaker info
        transcript_json = row[2]   # Basic timestamped segments
        
        segments = []
        
        # Prefer diarization segments (have speaker info)
        segments_data = None
        if diarization_json:
            if isinstance(diarization_json, str):
                segments_data = json.loads(diarization_json)
            else:
                segments_data = diarization_json
        elif transcript_json:
            if isinstance(transcript_json, str):
                segments_data = json.loads(transcript_json)
            else:
                segments_data = transcript_json
        
        if segments_data:
            for i, seg in enumerate(segments_data):
                # Handle different segment formats
                start = seg.get("start", seg.get("start_time", 0))
                end = seg.get("end", seg.get("end_time", 0))
                
                # Format timestamps
                def format_time(seconds):
                    if isinstance(seconds, str):
                        return seconds
                    s = int(seconds)
                    return f"{s//3600:02d}:{(s%3600)//60:02d}:{s%60:02d}"
                
                segments.append(Segment(
                    source_id=source_id,
                    segment_id=f"seg_{i:04d}",
                    speaker=seg.get("speaker", "Unknown"),
                    t0=format_time(start),
                    t1=format_time(end),
                    text=seg.get("text", ""),
                ))
        
        # If no segments in DB, parse from content
        if not segments:
            print(f"   No segments in database, parsing from transcript content...")
            _, segments = load_transcript(Path(f"temp_{source_id}.md"), content_override=content)
        
        return content, segments


def load_transcript(file_path: Path, content_override: str | None = None) -> tuple[str, list[Segment]]:
    """Load and parse a transcript file into segments."""
    if content_override:
        content = content_override
    else:
        content = file_path.read_text()
    
    # Check if it's a JSON transcript or markdown
    if file_path.suffix == ".json":
        data = json.loads(content)
        segments = []
        for i, seg in enumerate(data.get("segments", [])):
            segments.append(Segment(
                source_id=file_path.stem,
                segment_id=f"seg_{i:04d}",
                speaker=seg.get("speaker", "Unknown"),
                t0=seg.get("start", "00:00"),
                t1=seg.get("end", "00:00"),
                text=seg.get("text", ""),
            ))
        return content, segments
    
    # Parse markdown transcript
    # Look for timestamped segments like "**[00:00:00]** Speaker: text"
    # or "## 00:00:00 - Speaker" format
    segments = []
    lines = content.split("\n")
    current_segment = {"text": "", "speaker": "Unknown", "t0": "00:00", "t1": "00:00"}
    segment_count = 0
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # Check for timestamp patterns
        import re
        
        # Pattern 1: **[HH:MM:SS]** Speaker: text
        match1 = re.match(r'\*\*\[(\d{2}:\d{2}:\d{2})\]\*\*\s*(\w+):?\s*(.*)', line)
        # Pattern 2: ## HH:MM:SS - Speaker
        match2 = re.match(r'##?\s*(\d{2}:\d{2}:\d{2})\s*[-–]\s*(\w+)', line)
        # Pattern 3: [HH:MM:SS] Speaker: text
        match3 = re.match(r'\[(\d{2}:\d{2}:\d{2})\]\s*(\w+):?\s*(.*)', line)
        
        if match1 or match2 or match3:
            # Save previous segment if it has content
            if current_segment["text"].strip():
                segments.append(Segment(
                    source_id=file_path.stem,
                    segment_id=f"seg_{segment_count:04d}",
                    speaker=current_segment["speaker"],
                    t0=current_segment["t0"],
                    t1=current_segment["t1"],
                    text=current_segment["text"].strip(),
                ))
                segment_count += 1
            
            # Start new segment
            match = match1 or match2 or match3
            current_segment = {
                "t0": match.group(1),
                "t1": match.group(1),  # Will be updated with next segment's start
                "speaker": match.group(2),
                "text": match.group(3) if len(match.groups()) > 2 else "",
            }
        else:
            # Continue current segment
            current_segment["text"] += " " + line
    
    # Add final segment
    if current_segment["text"].strip():
        segments.append(Segment(
            source_id=file_path.stem,
            segment_id=f"seg_{segment_count:04d}",
            speaker=current_segment["speaker"],
            t0=current_segment["t0"],
            t1=current_segment["t1"],
            text=current_segment["text"].strip(),
        ))
    
    # If no segments found, create one large segment from the content
    if not segments:
        print("⚠️  No timestamped segments found, creating single segment from content")
        # Remove markdown headers and metadata
        clean_content = re.sub(r'^#.*$', '', content, flags=re.MULTILINE)
        clean_content = re.sub(r'^---.*?---', '', clean_content, flags=re.DOTALL)
        segments.append(Segment(
            source_id=file_path.stem,
            segment_id="seg_0000",
            speaker="Unknown",
            t0="00:00:00",
            t1="01:00:00",
            text=clean_content.strip()[:50000],  # Limit to 50k chars
        ))
    
    return content, segments


def create_llm(model_config: dict) -> System2LLM:
    """Create an LLM instance for the given model config."""
    provider, model = parse_model_uri(model_config["uri"])
    
    return System2LLM(
        provider=provider,
        model=model,
        temperature=0.1,
        max_tokens=8000,
    )


def run_extraction(
    llm: System2LLM, 
    segments: list[Segment], 
    model_name: str,
    max_segments: int = 10
) -> tuple[dict, float]:
    """
    Run extraction on segments and return results with timing.
    
    Args:
        llm: The LLM instance to use
        segments: List of segments to process
        model_name: Display name for logging
        max_segments: Maximum segments to process (for quick benchmarking)
    
    Returns:
        Tuple of (aggregated results dict, processing time in seconds)
    """
    print(f"\n🔄 Running extraction with {model_name}...")
    print(f"   Processing {min(len(segments), max_segments)} of {len(segments)} segments")
    
    miner = UnifiedMiner(llm)
    
    all_claims = []
    all_people = []
    all_jargon = []
    all_mental_models = []
    
    start_time = time.time()
    
    # Process limited segments for benchmarking
    for i, segment in enumerate(segments[:max_segments]):
        try:
            print(f"   Processing segment {i+1}/{min(len(segments), max_segments)}...", end="\r")
            output = miner.mine_segment(segment)
            
            all_claims.extend(output.claims)
            all_people.extend(output.people)
            all_jargon.extend(output.jargon)
            all_mental_models.extend(output.mental_models)
            
        except Exception as e:
            print(f"\n   ⚠️  Error processing segment {i}: {e}")
            continue
    
    elapsed = time.time() - start_time
    print(f"   ✅ Completed in {elapsed:.1f}s")
    
    return {
        "claims": all_claims,
        "people": all_people,
        "jargon": all_jargon,
        "mental_models": all_mental_models,
        "segments_processed": min(len(segments), max_segments),
    }, elapsed


def generate_summary(results: dict) -> str:
    """Generate a brief summary of extraction results."""
    claims = results.get("claims", [])
    
    if not claims:
        return "No claims extracted."
    
    # Get top 3 claims by any available scoring
    top_claims = claims[:3]
    
    summary_parts = []
    summary_parts.append(f"Extracted {len(claims)} claims from {results['segments_processed']} segments.")
    
    if top_claims:
        summary_parts.append("\n**Key claims:**")
        for i, claim in enumerate(top_claims, 1):
            claim_text = claim.get("claim_text", claim.get("canonical", ""))[:200]
            summary_parts.append(f"{i}. {claim_text}")
    
    return "\n".join(summary_parts)


def format_claims_table(claims: list[dict], max_items: int = 20) -> str:
    """Format claims as a markdown table."""
    if not claims:
        return "*No claims extracted*"
    
    lines = ["| # | Claim | Type | Speaker |", "|---|-------|------|---------|"]
    
    for i, claim in enumerate(claims[:max_items], 1):
        text = claim.get("claim_text", claim.get("canonical", ""))[:100]
        text = text.replace("|", "\\|").replace("\n", " ")
        claim_type = claim.get("claim_type", "unknown")
        speaker = claim.get("speaker", "Unknown")
        lines.append(f"| {i} | {text} | {claim_type} | {speaker} |")
    
    if len(claims) > max_items:
        lines.append(f"| ... | *{len(claims) - max_items} more claims* | | |")
    
    return "\n".join(lines)


def format_entity_list(entities: list, entity_type: str, max_items: int = 15) -> str:
    """Format entities as a bullet list."""
    if not entities:
        return f"*No {entity_type} extracted*"
    
    # Convert Pydantic models to dicts if needed
    def to_dict(e):
        if hasattr(e, 'model_dump'):
            return e.model_dump()
        return e if isinstance(e, dict) else {"name": str(e)}
    
    entities = [to_dict(e) for e in entities]
    
    # Deduplicate by name/term
    seen = set()
    unique_entities = []
    for entity in entities:
        # Handle different key formats
        name = (entity.get("name") or 
                entity.get("normalized_name") or 
                entity.get("term") or 
                entity.get("normalized") or 
                entity.get("surface", str(entity)))
        if name and name.lower() not in seen:
            seen.add(name.lower())
            unique_entities.append(entity)
    
    lines = []
    for entity in unique_entities[:max_items]:
        if entity_type == "people":
            # Handle different key formats from miner output
            name = (entity.get("normalized_name") or 
                    entity.get("name") or 
                    entity.get("normalized") or 
                    entity.get("surface", "Unknown"))
            entity_type_str = entity.get("entity_type", "person")
            lines.append(f"- **{name}** ({entity_type_str})")
        elif entity_type == "jargon":
            term = entity.get("term", "Unknown")
            definition = entity.get("definition", "")[:80]
            if definition:
                lines.append(f"- **{term}**: {definition}")
            else:
                lines.append(f"- **{term}**")
        elif entity_type == "mental_models":
            name = entity.get("name", "Unknown")
            definition = entity.get("definition", "")[:80]
            if definition:
                lines.append(f"- **{name}**: {definition}")
            else:
                lines.append(f"- **{name}**")
    
    if len(unique_entities) > max_items:
        lines.append(f"- *...and {len(unique_entities) - max_items} more*")
    
    return "\n".join(lines) if lines else f"*No {entity_type} extracted*"


def generate_markdown_report(
    transcript_path: Path,
    results: dict[str, dict],
    timings: dict[str, float],
) -> str:
    """Generate the final markdown comparison report."""
    
    report = []
    
    # Header
    report.append("# LLM Extraction Benchmark Results")
    report.append("")
    report.append(f"**Transcript:** `{transcript_path.name}`")
    report.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append("")
    
    # Summary table
    report.append("## Summary Comparison")
    report.append("")
    report.append("| Metric | " + " | ".join(BENCHMARK_MODELS[m]["name"] for m in results.keys()) + " |")
    report.append("|--------|" + "|".join(["--------"] * len(results)) + "|")
    
    # Processing time
    time_row = "| ⏱️ Processing Time |"
    for model_key in results.keys():
        time_row += f" {timings[model_key]:.1f}s |"
    report.append(time_row)
    
    # Claims count
    claims_row = "| 📝 Claims |"
    for model_key, data in results.items():
        claims_row += f" {len(data.get('claims', []))} |"
    report.append(claims_row)
    
    # People count
    people_row = "| 👥 People |"
    for model_key, data in results.items():
        people_row += f" {len(data.get('people', []))} |"
    report.append(people_row)
    
    # Jargon count
    jargon_row = "| 📚 Jargon |"
    for model_key, data in results.items():
        jargon_row += f" {len(data.get('jargon', []))} |"
    report.append(jargon_row)
    
    # Mental models count
    models_row = "| 💡 Mental Models |"
    for model_key, data in results.items():
        models_row += f" {len(data.get('mental_models', []))} |"
    report.append(models_row)
    
    report.append("")
    
    # Detailed results for each model
    for model_key, data in results.items():
        model_name = BENCHMARK_MODELS[model_key]["name"]
        
        report.append(f"---")
        report.append("")
        report.append(f"## {model_name}")
        report.append("")
        report.append(f"**Processing Time:** {timings[model_key]:.1f} seconds")
        report.append(f"**Segments Processed:** {data.get('segments_processed', 0)}")
        report.append("")
        
        # Summary
        report.append("### Summary")
        report.append("")
        report.append(generate_summary(data))
        report.append("")
        
        # Claims
        report.append("### Claims")
        report.append("")
        report.append(format_claims_table(data.get("claims", [])))
        report.append("")
        
        # People
        report.append("### People")
        report.append("")
        report.append(format_entity_list(data.get("people", []), "people"))
        report.append("")
        
        # Jargon
        report.append("### Jargon")
        report.append("")
        report.append(format_entity_list(data.get("jargon", []), "jargon"))
        report.append("")
        
        # Mental Models
        report.append("### Mental Models / Concepts")
        report.append("")
        report.append(format_entity_list(data.get("mental_models", []), "mental_models"))
        report.append("")
    
    # Footer
    report.append("---")
    report.append("")
    report.append("## Notes")
    report.append("")
    report.append("- **Local Qwen** runs on your machine via Ollama (no API cost)")
    report.append("- **GPT-4o-mini** is OpenAI's fast, cost-effective model (~$0.15/1M input tokens)")
    report.append("- **Claude 3.5 Sonnet** is Anthropic's high-quality model (~$3/1M input tokens)")
    report.append("- Processing time includes network latency for cloud models")
    report.append("- Results may vary based on prompt engineering and model updates")
    report.append("")
    
    return "\n".join(report)


def main():
    parser = argparse.ArgumentParser(
        description="Benchmark LLM extraction quality across multiple models",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # From file:
    python scripts/benchmark_llm_extraction.py output/transcripts/podcast.md
    
    # From database by source_id:
    python scripts/benchmark_llm_extraction.py --source-id vvj_J2tB2Ag
    
    # List available sources:
    python scripts/benchmark_llm_extraction.py --list-sources
    
    # Benchmark specific models:
    python scripts/benchmark_llm_extraction.py podcast.md --max-segments 5 --models qwen_local gpt_mini
        """
    )
    parser.add_argument(
        "transcript",
        type=Path,
        nargs="?",  # Make optional when using --source-id
        help="Path to transcript file (.md or .json)"
    )
    parser.add_argument(
        "--source-id", "-s",
        type=str,
        default=None,
        help="Load transcript from database by source_id (alternative to file path)"
    )
    parser.add_argument(
        "--list-sources", "-l",
        action="store_true",
        help="List available source_ids in the database"
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        default=None,
        help="Output markdown file (default: benchmark_results_TIMESTAMP.md)"
    )
    parser.add_argument(
        "--max-segments", "-n",
        type=int,
        default=10,
        help="Maximum segments to process per model (default: 10)"
    )
    parser.add_argument(
        "--models", "-m",
        nargs="+",
        choices=list(BENCHMARK_MODELS.keys()),
        default=list(BENCHMARK_MODELS.keys()),
        help="Models to benchmark (default: all)"
    )
    
    args = parser.parse_args()
    
    # Handle --list-sources
    if args.list_sources:
        print("\n📋 Available Sources in Database:\n")
        sources = list_available_sources()
        if not sources:
            print("   No transcripts found in database.")
        else:
            print(f"{'Source ID':<20} {'Title':<50} {'Length':<10}")
            print("-" * 80)
            for src in sources:
                title = (src['title'][:47] + "...") if len(src['title']) > 50 else src['title']
                length = f"{src['transcript_length']:,}" if src['transcript_length'] else "0"
                print(f"{src['source_id']:<20} {title:<50} {length:<10}")
        print()
        sys.exit(0)
    
    # Validate input source
    source_name = None
    if args.source_id:
        source_name = args.source_id
    elif args.transcript:
        if not args.transcript.exists():
            print(f"❌ Error: Transcript file not found: {args.transcript}")
            sys.exit(1)
        source_name = args.transcript.stem
    else:
        print("❌ Error: Must provide either a transcript file or --source-id")
        parser.print_help()
        sys.exit(1)
    
    # Set default output path
    if args.output is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        args.output = Path(f"benchmark_results_{timestamp}.md")
    
    print("=" * 60)
    print("🔬 LLM Extraction Benchmark")
    print("=" * 60)
    if args.source_id:
        print(f"📄 Source ID: {args.source_id}")
    else:
        print(f"📄 Transcript: {args.transcript}")
    print(f"📊 Output: {args.output}")
    print(f"🔢 Max segments: {args.max_segments}")
    print(f"🤖 Models: {', '.join(args.models)}")
    print()
    
    # Load transcript
    print("📖 Loading transcript...")
    try:
        if args.source_id:
            content, segments = load_transcript_from_db(args.source_id)
            transcript_path = Path(f"db://{args.source_id}")
        else:
            content, segments = load_transcript(args.transcript)
            transcript_path = args.transcript
        print(f"   Found {len(segments)} segments")
    except Exception as e:
        print(f"❌ Error loading transcript: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    # Run benchmarks
    results = {}
    timings = {}
    
    for model_key in args.models:
        model_config = BENCHMARK_MODELS[model_key]
        
        try:
            llm = create_llm(model_config)
            data, elapsed = run_extraction(
                llm, 
                segments, 
                model_config["name"],
                max_segments=args.max_segments
            )
            results[model_key] = data
            timings[model_key] = elapsed
            
        except Exception as e:
            print(f"\n❌ Error with {model_config['name']}: {e}")
            results[model_key] = {
                "claims": [],
                "people": [],
                "jargon": [],
                "mental_models": [],
                "segments_processed": 0,
                "error": str(e),
            }
            timings[model_key] = 0
    
    # Generate report
    print("\n📝 Generating report...")
    report = generate_markdown_report(transcript_path, results, timings)
    
    # Save report
    args.output.write_text(report)
    print(f"\n✅ Report saved to: {args.output}")
    
    # Print quick summary
    print("\n" + "=" * 60)
    print("📊 Quick Summary")
    print("=" * 60)
    for model_key, data in results.items():
        name = BENCHMARK_MODELS[model_key]["name"]
        claims = len(data.get("claims", []))
        time_taken = timings[model_key]
        print(f"  {name}: {claims} claims in {time_taken:.1f}s")
    print()


if __name__ == "__main__":
    main()

