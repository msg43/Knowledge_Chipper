#!/usr/bin/env python3
"""
Run complete claims-first extraction on a YouTube video.
Uses Claude Sonnet 4.5 for both mining and evaluation stages.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from knowledge_system.database.service import DatabaseService
from knowledge_system.processors.hce.unified_miner import UnifiedMiner
from knowledge_system.processors.hce.flagship_evaluator import FlagshipEvaluator
from knowledge_system.processors.hce.models.llm_system2 import System2LLM
from knowledge_system.processors.hce.types import Segment
from knowledge_system.logger import get_logger

logger = get_logger(__name__)


def load_transcript_from_file(file_path: Path, source_id: str = "unknown") -> tuple[str, list[Segment]]:
    """Load transcript from markdown file and convert to segments."""
    content = file_path.read_text()
    
    # Extract transcript section
    lines = content.split('\n')
    transcript_start = None
    transcript_lines = []
    
    for i, line in enumerate(lines):
        if line.strip() == '## Full Transcript':
            transcript_start = i
            continue
        if transcript_start is not None and i > transcript_start + 2:
            if line.startswith('**[') and '](' in line:
                # Timestamp line like **[00:06](https://...)** text
                transcript_lines.append(line)
    
    # Group lines into segments (every 10 lines for reasonable chunk size)
    segments = []
    chunk_size = 15
    for i in range(0, len(transcript_lines), chunk_size):
        chunk = transcript_lines[i:i+chunk_size]
        text = '\n'.join(chunk)
        
        # Extract first timestamp for segment ID
        first_line = chunk[0] if chunk else ""
        timestamp = "00:00"
        if '**[' in first_line and '](' in first_line:
            timestamp = first_line.split('**[')[1].split(']')[0]
        
        segment = Segment(
            source_id=source_id,
            segment_id=f"seg_{i//chunk_size:04d}",
            speaker="Unknown",
            t0=timestamp,
            t1=timestamp,
            text=text
        )
        segments.append(segment)
    
    return content, segments


def run_extraction(source_id: str, transcript_file: Path):
    """Run complete extraction pipeline."""
    
    print(f"\n{'='*80}")
    print(f"🎬 Processing: {source_id}")
    print(f"📄 Transcript: {transcript_file}")
    print(f"{'='*80}\n")
    
    # Load transcript
    print("📖 Loading transcript...")
    content, segments = load_transcript_from_file(transcript_file)
    print(f"   ✅ Loaded {len(segments)} segments\n")
    
    # Initialize Claude Sonnet 4.5 for both stages
    print("🤖 Initializing Claude Sonnet 4.5...")
    miner_llm = System2LLM(
        provider="anthropic",
        model="claude-sonnet-4-20250514",
        temperature=0.1,
        max_tokens=8000,
    )
    
    evaluator_llm = System2LLM(
        provider="anthropic",
        model="claude-sonnet-4-20250514",
        temperature=0.1,
        max_tokens=4000,
    )
    print("   ✅ LLMs initialized\n")
    
    # Stage 1: Mining
    print("⛏️  STAGE 1: MINING CLAIMS")
    print("-" * 80)
    miner = UnifiedMiner(miner_llm)
    
    all_claims = []
    all_people = []
    all_jargon = []
    all_mental_models = []
    
    for i, segment in enumerate(segments):
        print(f"   Processing segment {i+1}/{len(segments)}...", end="\r")
        try:
            output = miner.mine_segment(segment)
            all_claims.extend(output.claims)
            all_people.extend(output.people)
            all_jargon.extend(output.jargon)
            all_mental_models.extend(output.mental_models)
        except Exception as e:
            print(f"\n   ⚠️  Error on segment {i}: {e}")
            continue
    
    print(f"\n   ✅ Mining complete!")
    print(f"      - {len(all_claims)} claims")
    print(f"      - {len(all_people)} people")
    print(f"      - {len(all_jargon)} jargon terms")
    print(f"      - {len(all_mental_models)} mental models\n")
    
    # Stage 2: Evaluation
    print("⚖️  STAGE 2: EVALUATING CLAIMS")
    print("-" * 80)
    evaluator = FlagshipEvaluator(evaluator_llm)
    
    evaluated_claims = []
    for i, claim in enumerate(all_claims):
        print(f"   Evaluating claim {i+1}/{len(all_claims)}...", end="\r")
        try:
            result = evaluator.evaluate_claim(claim, source_id)
            if result.importance >= 4:  # Keep C-tier and above
                evaluated_claims.append(result)
        except Exception as e:
            print(f"\n   ⚠️  Error evaluating claim {i}: {e}")
            continue
    
    print(f"\n   ✅ Evaluation complete!")
    print(f"      - {len(evaluated_claims)} claims accepted (>= C-tier)")
    print(f"      - {len(all_claims) - len(evaluated_claims)} claims rejected\n")
    
    # Tier distribution
    a_tier = [c for c in evaluated_claims if c.importance >= 8]
    b_tier = [c for c in evaluated_claims if 6 <= c.importance < 8]
    c_tier = [c for c in evaluated_claims if 4 <= c.importance < 6]
    
    print(f"   📊 Tier Distribution:")
    print(f"      - A-tier (≥8): {len(a_tier)} claims")
    print(f"      - B-tier (6-7): {len(b_tier)} claims")
    print(f"      - C-tier (4-5): {len(c_tier)} claims\n")
    
    # Generate output markdown
    print("📝 Generating markdown output...")
    output_file = Path("output") / f"{source_id}_extracted.md"
    output_file.parent.mkdir(exist_ok=True)
    
    with open(output_file, 'w') as f:
        f.write(f"# Extracted Knowledge: {source_id}\n\n")
        f.write(f"**Source:** https://www.youtube.com/watch?v={source_id}\n\n")
        f.write(f"**Extracted:** {len(evaluated_claims)} claims, {len(all_people)} people, ")
        f.write(f"{len(all_jargon)} jargon terms, {len(all_mental_models)} mental models\n\n")
        f.write(f"**Models:** Claude Sonnet 4.5 (mining + evaluation)\n\n")
        f.write("---\n\n")
        
        # A-Tier Claims
        if a_tier:
            f.write("## 🌟 A-Tier Claims (Importance ≥ 8)\n\n")
            for i, claim in enumerate(a_tier, 1):
                f.write(f"### {i}. {claim.canonical}\n\n")
                f.write(f"**Importance:** {claim.importance:.1f} | ")
                f.write(f"**Novelty:** {claim.novelty:.1f} | ")
                f.write(f"**Confidence:** {claim.confidence:.1f}\n\n")
                if hasattr(claim, 'dimensions') and claim.dimensions:
                    f.write(f"**Dimensions:**\n")
                    for dim, val in claim.dimensions.items():
                        f.write(f"- {dim}: {val}\n")
                    f.write("\n")
                if hasattr(claim, 'profile_scores') and claim.profile_scores:
                    best_profile = max(claim.profile_scores.items(), key=lambda x: x[1])
                    f.write(f"**Best Profile:** {best_profile[0]} ({best_profile[1]:.1f})\n\n")
                f.write("---\n\n")
        
        # B-Tier Claims
        if b_tier:
            f.write("## ⭐ B-Tier Claims (Importance 6-7)\n\n")
            for i, claim in enumerate(b_tier, 1):
                f.write(f"### {i}. {claim.canonical}\n\n")
                f.write(f"**Importance:** {claim.importance:.1f}\n\n")
                f.write("---\n\n")
        
        # C-Tier Claims
        if c_tier:
            f.write("## 📌 C-Tier Claims (Importance 4-5)\n\n")
            for claim in c_tier:
                f.write(f"- {claim.canonical} (importance: {claim.importance:.1f})\n")
            f.write("\n---\n\n")
        
        # People
        if all_people:
            f.write("## 👥 People Mentioned\n\n")
            for person in all_people:
                name = person.get('name', 'Unknown')
                description = person.get('description', '')
                f.write(f"### {name}\n\n")
                if description:
                    f.write(f"{description}\n\n")
                f.write("---\n\n")
        
        # Jargon
        if all_jargon:
            f.write("## 📚 Jargon & Technical Terms\n\n")
            for term in all_jargon:
                term_name = term.get('term', 'Unknown')
                definition = term.get('definition', '')
                domain = term.get('domain', '')
                f.write(f"### {term_name}\n\n")
                if domain:
                    f.write(f"**Domain:** {domain}\n\n")
                if definition:
                    f.write(f"{definition}\n\n")
                f.write("---\n\n")
        
        # Mental Models
        if all_mental_models:
            f.write("## 🧠 Mental Models & Frameworks\n\n")
            for model in all_mental_models:
                model_name = model.get('name', 'Unknown')
                definition = model.get('definition', '')
                f.write(f"### {model_name}\n\n")
                if definition:
                    f.write(f"{definition}\n\n")
                f.write("---\n\n")
    
    print(f"   ✅ Output saved to: {output_file}\n")
    print(f"{'='*80}")
    print("✅ EXTRACTION COMPLETE!")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    source_id = "AmIiqY2VJkQ"
    transcript_file = Path("output/AmIiqY2VJkQ_complete.md")
    
    if not transcript_file.exists():
        print(f"❌ Transcript file not found: {transcript_file}")
        sys.exit(1)
    
    run_extraction(source_id, transcript_file)

