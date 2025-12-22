#!/usr/bin/env python3
"""
Re-run evaluation on already-mined claims using Claude Sonnet 4.5.
"""

import sys
import json
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from knowledge_system.processors.hce.flagship_evaluator import evaluate_claims_simple
from knowledge_system.logger import get_logger

logger = get_logger(__name__)


def load_mined_claims_from_log(log_file: Path) -> tuple[list[dict], list[dict], list[dict], list[dict]]:
    """Extract mined claims from the extraction log."""
    # For now, let's re-run the mining quickly since we need the structured data
    # The log file has the output but not in a parseable format
    return [], [], [], []


def run_evaluation_on_transcript(source_id: str, transcript_file: Path):
    """Re-run just the evaluation stage."""
    
    print(f"\n{'='*80}")
    print(f"🎬 Re-evaluating: {source_id}")
    print(f"{'='*80}\n")
    
    # We need to re-mine to get structured claim data
    # Let me load the transcript and mine again (fast with Claude)
    from run_extraction_demo import load_transcript_from_file
    from knowledge_system.processors.hce.unified_miner import UnifiedMiner
    from knowledge_system.processors.hce.models.llm_system2 import System2LLM
    
    print("📖 Loading transcript...")
    content, segments = load_transcript_from_file(transcript_file, source_id)
    print(f"   ✅ Loaded {len(segments)} segments\n")
    
    print("🤖 Initializing Claude Sonnet 4.5 for mining...")
    miner_llm = System2LLM(
        provider="anthropic",
        model="claude-sonnet-4-20250514",
        temperature=0.1,
        max_tokens=8000,
    )
    print("   ✅ LLM initialized\n")
    
    # Quick re-mine
    print("⛏️  MINING CLAIMS (quick re-run)")
    print("-" * 80)
    miner = UnifiedMiner(miner_llm)
    
    all_claims = []
    all_people = []
    all_jargon = []
    all_mental_models = []
    
    for i, segment in enumerate(segments):
        print(f"   Mining segment {i+1}/{len(segments)}...", end="\r")
        try:
            output = miner.mine_segment(segment)
            all_claims.extend(output.claims)
            all_people.extend(output.people)
            all_jargon.extend(output.jargon)
            all_mental_models.extend(output.mental_models)
        except Exception as e:
            print(f"\n   ⚠️  Error on segment {i}: {e}")
            continue
    
    print(f"\n   ✅ Mining complete: {len(all_claims)} claims\n")
    
    # Now evaluate with the CORRECT API
    print("⚖️  EVALUATING CLAIMS WITH CLAUDE SONNET 4.5")
    print("-" * 80)
    
    # Use the simple evaluation function with Claude
    evaluated_claims = evaluate_claims_simple(
        claims=all_claims,
        model_uri="anthropic:claude-sonnet-4-20250514",
        content_summary="George Magnus lecture on China's economic prospects"
    )
    
    # Filter accepted claims
    accepted_claims = [c for c in evaluated_claims if c.get("accepted", False)]
    
    print(f"\n   ✅ Evaluation complete!")
    print(f"      - {len(accepted_claims)} claims accepted")
    print(f"      - {len(evaluated_claims) - len(accepted_claims)} claims rejected\n")
    
    # Tier distribution
    a_tier = [c for c in accepted_claims if c.get("importance", 0) >= 8]
    b_tier = [c for c in accepted_claims if 6 <= c.get("importance", 0) < 8]
    c_tier = [c for c in accepted_claims if 4 <= c.get("importance", 0) < 6]
    
    print(f"   📊 Tier Distribution:")
    print(f"      - A-tier (≥8): {len(a_tier)} claims")
    print(f"      - B-tier (6-7): {len(b_tier)} claims")
    print(f"      - C-tier (4-5): {len(c_tier)} claims\n")
    
    # Generate output markdown
    print("📝 Generating markdown output...")
    output_file = Path("output") / f"{source_id}_extracted_FINAL.md"
    
    with open(output_file, 'w') as f:
        f.write(f"# Extracted Knowledge: China's Economic Prospects\n\n")
        f.write(f"**Speaker:** George Magnus\n\n")
        f.write(f"**Source:** https://www.youtube.com/watch?v={source_id}\n\n")
        f.write(f"**Extracted:** {len(accepted_claims)} claims, {len(all_people)} people, ")
        f.write(f"{len(all_jargon)} jargon terms, {len(all_mental_models)} mental models\n\n")
        f.write(f"**Models:** Claude Sonnet 4.5 (mining + evaluation)\n\n")
        f.write("---\n\n")
        
        # A-Tier Claims
        if a_tier:
            f.write("## 🌟 A-Tier Claims (Importance ≥ 8)\n\n")
            for i, claim in enumerate(a_tier, 1):
                canonical = claim.get('canonical', claim.get('claim', 'Unknown'))
                importance = claim.get('importance', 0)
                novelty = claim.get('novelty', 0)
                confidence = claim.get('confidence', 0)
                reasoning = claim.get('reasoning', '')
                
                f.write(f"### {i}. {canonical}\n\n")
                f.write(f"**Importance:** {importance:.1f} | ")
                f.write(f"**Novelty:** {novelty:.1f} | ")
                f.write(f"**Confidence:** {confidence:.1f}\n\n")
                
                if reasoning:
                    f.write(f"**Reasoning:** {reasoning}\n\n")
                
                # Dimensions if available
                if 'dimensions' in claim:
                    dims = claim['dimensions']
                    f.write(f"**Dimensions:**\n")
                    for dim, val in dims.items():
                        f.write(f"- {dim}: {val}\n")
                    f.write("\n")
                
                # Profile scores if available
                if 'profile_scores' in claim:
                    scores = claim['profile_scores']
                    best_profile = max(scores.items(), key=lambda x: x[1])
                    f.write(f"**Best Profile:** {best_profile[0]} ({best_profile[1]:.1f})\n\n")
                
                f.write("---\n\n")
        
        # B-Tier Claims
        if b_tier:
            f.write("## ⭐ B-Tier Claims (Importance 6-7)\n\n")
            for i, claim in enumerate(b_tier, 1):
                canonical = claim.get('canonical', claim.get('claim', 'Unknown'))
                importance = claim.get('importance', 0)
                
                f.write(f"### {i}. {canonical}\n\n")
                f.write(f"**Importance:** {importance:.1f}\n\n")
                f.write("---\n\n")
        
        # C-Tier Claims (condensed)
        if c_tier:
            f.write("## 📌 C-Tier Claims (Importance 4-5)\n\n")
            for claim in c_tier:
                canonical = claim.get('canonical', claim.get('claim', 'Unknown'))
                importance = claim.get('importance', 0)
                f.write(f"- {canonical} (importance: {importance:.1f})\n")
            f.write("\n---\n\n")
        
        # People
        if all_people:
            f.write("## 👥 People Mentioned\n\n")
            # Deduplicate by name
            people_dict = {}
            for person in all_people:
                name = person.get('name', 'Unknown')
                if name not in people_dict:
                    people_dict[name] = person
            
            for name, person in sorted(people_dict.items()):
                description = person.get('description', '')
                f.write(f"### {name}\n\n")
                if description:
                    f.write(f"{description}\n\n")
                f.write("---\n\n")
        
        # Jargon (top 50 most important)
        if all_jargon:
            f.write("## 📚 Key Jargon & Technical Terms\n\n")
            # Deduplicate and take top 50
            jargon_dict = {}
            for term in all_jargon:
                term_name = term.get('term', 'Unknown')
                if term_name not in jargon_dict:
                    jargon_dict[term_name] = term
            
            for i, (term_name, term) in enumerate(sorted(jargon_dict.items())[:50], 1):
                definition = term.get('definition', '')
                domain = term.get('domain', '')
                f.write(f"### {i}. {term_name}\n\n")
                if domain:
                    f.write(f"**Domain:** {domain}\n\n")
                if definition:
                    f.write(f"{definition}\n\n")
                f.write("---\n\n")
        
        # Mental Models
        if all_mental_models:
            f.write("## 🧠 Mental Models & Frameworks\n\n")
            # Deduplicate
            models_dict = {}
            for model in all_mental_models:
                model_name = model.get('name', 'Unknown')
                if model_name not in models_dict:
                    models_dict[model_name] = model
            
            for model_name, model in sorted(models_dict.items()):
                definition = model.get('definition', '')
                f.write(f"### {model_name}\n\n")
                if definition:
                    f.write(f"{definition}\n\n")
                f.write("---\n\n")
    
    print(f"   ✅ Output saved to: {output_file}\n")
    print(f"{'='*80}")
    print("✅ EXTRACTION COMPLETE!")
    print(f"{'='*80}\n")
    
    # Print summary
    print("\n📊 FINAL SUMMARY")
    print("=" * 80)
    print(f"Total Claims Mined: {len(all_claims)}")
    print(f"Claims Accepted: {len(accepted_claims)} ({len(accepted_claims)/len(all_claims)*100:.1f}%)")
    print(f"  - A-tier: {len(a_tier)}")
    print(f"  - B-tier: {len(b_tier)}")
    print(f"  - C-tier: {len(c_tier)}")
    print(f"\nPeople: {len(set(p.get('name') for p in all_people))}")
    print(f"Jargon Terms: {len(set(j.get('term') for j in all_jargon))}")
    print(f"Mental Models: {len(set(m.get('name') for m in all_mental_models))}")
    print("=" * 80)


if __name__ == "__main__":
    source_id = "AmIiqY2VJkQ"
    transcript_file = Path("output/AmIiqY2VJkQ_complete.md")
    
    if not transcript_file.exists():
        print(f"❌ Transcript file not found: {transcript_file}")
        sys.exit(1)
    
    run_evaluation_on_transcript(source_id, transcript_file)

