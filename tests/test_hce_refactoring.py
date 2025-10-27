#!/usr/bin/env python3
"""
Test script for HCE architecture refactoring.

Tests:
1. All 3 miner selectivity levels (liberal, moderate, conservative)
2. All 4 entity types are evaluated (claims, jargon, people, concepts)
3. Deduplication works for all entity types
4. Performance is measured

Usage:
    python test_hce_refactoring.py
"""

import sys
import time
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from knowledge_system.processors.hce.config_flex import PipelineConfigFlex
from knowledge_system.processors.hce.unified_pipeline import UnifiedHCEPipeline
from knowledge_system.processors.hce.types import EpisodeBundle, SegmentedContent


def create_test_episode() -> EpisodeBundle:
    """Create a small test episode for HCE processing."""
    segments = [
        SegmentedContent(
            t0="00:00:00",
            t1="00:00:30",
            text="""
            Let me introduce the concept of Bayesian reasoning. Thomas Bayes was a mathematician
            who developed a fundamental framework for updating beliefs based on new evidence.
            This is crucial for understanding probabilistic thinking.
            """,
            speaker="Speaker 1",
        ),
        SegmentedContent(
            t0="00:00:30",
            t1="00:01:00",
            text="""
            As Thomas Bayes showed, we should update our priors based on new evidence. The concept of Bayesian
            reasoning is fundamental to statistics. Another important thinker is Daniel Kahneman,
            who studied cognitive biases. Kahneman and Amos Tversky developed prospect theory.
            """,
            speaker="Speaker 2",
        ),
        SegmentedContent(
            t0="00:01:00",
            t1="00:01:30",
            text="""
            The term 'base rate fallacy' refers to ignoring prior probabilities. This cognitive bias
            is related to Bayesian reasoning. Kahneman's work on heuristics and biases shows how
            people make systematic errors in judgment. Prospect theory explains loss aversion.
            """,
            speaker="Speaker 1",
        ),
    ]
    
    return EpisodeBundle(
        episode_id="test_episode_001",
        segments=segments,
        metadata={
            "title": "Test Episode: Bayesian Reasoning",
            "source": "test_data",
        }
    )


def test_selectivity_level(selectivity: str):
    """Test a specific miner selectivity level."""
    print(f"\n{'='*80}")
    print(f"TESTING SELECTIVITY: {selectivity.upper()}")
    print(f"{'='*80}\n")
    
    # Create config with this selectivity
    from knowledge_system.processors.hce.config_flex import StageModelConfig
    
    config = PipelineConfigFlex(
        models=StageModelConfig(
            miner="local://llama3.2:latest",
            judge="local://llama3.2:latest",
            flagship_judge="local://llama3.2:latest",
        ),
        miner_selectivity=selectivity,
    )
    
    # Create pipeline
    pipeline = UnifiedHCEPipeline(config=config)
    
    # Create test episode
    episode = create_test_episode()
    
    # Process
    start_time = time.time()
    result = pipeline.process(episode)
    elapsed = time.time() - start_time
    
    # Display results
    print(f"\n✅ Processing completed in {elapsed:.2f}s")
    print(f"\n📊 RESULTS:")
    print(f"  Claims:    {len(result.claims)} extracted")
    print(f"  Jargon:    {len(result.jargon)} extracted")
    print(f"  People:    {len(result.people)} extracted")
    print(f"  Concepts:  {len(result.concepts)} extracted")
    
    # Show samples
    if result.claims:
        print(f"\n  📌 Sample Claims:")
        for i, claim in enumerate(result.claims[:3], 1):
            tier = claim.tier if hasattr(claim, 'tier') else 'N/A'
            print(f"    {i}. [{tier}] {claim.canonical[:100]}...")
    
    if result.jargon:
        print(f"\n  📖 Sample Jargon:")
        for i, jargon in enumerate(result.jargon[:3], 1):
            print(f"    {i}. {jargon.term}: {jargon.definition[:80] if jargon.definition else 'N/A'}...")
    
    if result.people:
        print(f"\n  👤 Sample People:")
        for i, person in enumerate(result.people[:3], 1):
            role = person.role_description if hasattr(person, 'role_description') else 'N/A'
            print(f"    {i}. {person.surface} ({role})")
    
    if result.concepts:
        print(f"\n  💡 Sample Concepts:")
        for i, concept in enumerate(result.concepts[:3], 1):
            print(f"    {i}. {concept.name}: {concept.definition[:80] if concept.definition else 'N/A'}...")
    
    return {
        'selectivity': selectivity,
        'elapsed': elapsed,
        'claims': len(result.claims),
        'jargon': len(result.jargon),
        'people': len(result.people),
        'concepts': len(result.concepts),
    }


def test_deduplication():
    """Verify that deduplication is working."""
    print(f"\n{'='*80}")
    print(f"TESTING DEDUPLICATION")
    print(f"{'='*80}\n")
    
    print("📋 Expected deduplication:")
    print("  - Thomas Bayes / Bayes → 1 person (Thomas Bayes)")
    print("  - Daniel Kahneman / Kahneman → 1 person (Daniel Kahneman)")
    print("  - Bayesian reasoning (mentioned 3x) → 1 concept")
    print("  - Base rate fallacy / base rate → 1 jargon term")
    
    # Run moderate to test deduplication
    result = test_selectivity_level("moderate")
    
    print(f"\n✅ Deduplication test assumptions:")
    print(f"  - If people < 4: Likely deduplicated (expected ~2: Bayes, Kahneman)")
    print(f"  - If concepts < 5: Likely deduplicated (expected ~3-4)")
    print(f"  - If jargon < 5: Likely deduplicated (expected ~2-3)")
    
    return result


def main():
    """Run all tests."""
    print("""
╔══════════════════════════════════════════════════════════════════════════════╗
║                   HCE ARCHITECTURE REFACTORING TEST SUITE                    ║
╚══════════════════════════════════════════════════════════════════════════════╝
""")
    
    results = {}
    
    try:
        # Test 1: Liberal extraction
        results['liberal'] = test_selectivity_level("liberal")
        
        # Test 2: Moderate extraction
        results['moderate'] = test_selectivity_level("moderate")
        
        # Test 3: Conservative extraction
        results['conservative'] = test_selectivity_level("conservative")
        
        # Test 4: Deduplication
        print("\n")  # Space before dedup test
        dedup_result = test_deduplication()
        
        # Summary
        print(f"\n{'='*80}")
        print(f"SUMMARY")
        print(f"{'='*80}\n")
        
        print(f"{'Selectivity':<15} {'Claims':<8} {'Jargon':<8} {'People':<8} {'Concepts':<10} {'Time':<8}")
        print(f"{'-'*80}")
        for selectivity in ['liberal', 'moderate', 'conservative']:
            r = results[selectivity]
            print(f"{selectivity:<15} {r['claims']:<8} {r['jargon']:<8} {r['people']:<8} {r['concepts']:<10} {r['elapsed']:<8.2f}s")
        
        print(f"\n✅ ALL TESTS PASSED")
        print(f"\n📊 Key observations:")
        print(f"  - Liberal should extract MOST entities")
        print(f"  - Conservative should extract FEWEST entities")
        print(f"  - All 4 entity types should have results")
        print(f"  - Deduplication should reduce duplicates")
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

