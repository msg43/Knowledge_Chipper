#!/usr/bin/env python3
"""
Comprehensive test suite for the unified HCE pipeline.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from knowledge_system.processors.hce.flagship_evaluator import (
    FlagshipEvaluator,
    evaluate_claims_flagship,
)
from knowledge_system.processors.hce.models.llm_any import AnyLLM
from knowledge_system.processors.hce.types import EpisodeBundle, Segment
from knowledge_system.processors.hce.unified_miner import (
    UnifiedMiner,
    mine_episode_unified,
)
from knowledge_system.processors.summarizer import SummarizerProcessor


def test_llm_connection():
    """Test basic LLM connectivity."""
    print("🔌 Testing LLM Connection")
    print("-" * 30)

    try:
        llm = AnyLLM("openai://gpt-4o-mini")
        response = llm.generate_json(
            'Return a simple JSON object with a greeting: {"message": "Hello, World!"}'
        )
        print(f"✅ LLM Response: {response}")
        return True
    except Exception as e:
        print(f"❌ LLM Connection failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_unified_miner():
    """Test the unified miner directly."""
    print("\n⛏️ Testing Unified Miner")
    print("-" * 30)

    try:
        # Create test episode
        episode = EpisodeBundle(
            episode_id="test_episode",
            segments=[
                Segment(
                    episode_id="test_episode",
                    segment_id="seg_0001",
                    speaker="narrator",
                    t0="000000",
                    t1="000010",
                    text="Jerome Powell, the Federal Reserve Chairman, announced that quantitative easing creates a wealth effect.",
                )
            ],
        )

        # Test mining
        outputs = mine_episode_unified(episode, "openai://gpt-4o-mini")

        print(f"✅ Mining completed: {len(outputs)} segment outputs")
        for i, output in enumerate(outputs):
            print(f"  Segment {i}: {output.total_extractions()} total extractions")
            print(f"    Claims: {len(output.claims)}")
            print(f"    Jargon: {len(output.jargon)}")
            print(f"    People: {len(output.people)}")
            print(f"    Mental Models: {len(output.mental_models)}")

        return outputs

    except Exception as e:
        print(f"❌ Unified Miner failed: {e}")
        import traceback

        traceback.print_exc()
        return []


def test_flagship_evaluator(miner_outputs):
    """Test the flagship evaluator."""
    print("\n🏆 Testing Flagship Evaluator")
    print("-" * 30)

    if not miner_outputs:
        print("⚠️ No miner outputs to evaluate")
        return None

    try:
        content_summary = "Test content about Federal Reserve monetary policy"
        evaluation = evaluate_claims_flagship(
            content_summary, miner_outputs, "openai://gpt-4o"
        )

        print(f"✅ Evaluation completed:")
        print(f"  Total processed: {evaluation.total_claims_processed}")
        print(f"  Accepted: {evaluation.claims_accepted}")
        print(f"  Rejected: {evaluation.claims_rejected}")
        print(f"  Quality: {evaluation.overall_quality}")

        return evaluation

    except Exception as e:
        print(f"❌ Flagship Evaluator failed: {e}")
        import traceback

        traceback.print_exc()
        return None


def test_end_to_end():
    """Test the complete end-to-end pipeline."""
    print("\n🔄 Testing End-to-End Pipeline")
    print("-" * 30)

    test_text = """
    The Federal Reserve's quantitative easing program has fundamentally altered the relationship between monetary policy and asset prices.
    According to Fed Chairman Jerome Powell, this creates what economists call a 'wealth effect' where rising asset prices boost consumer spending.

    However, some critics argue this approach primarily benefits wealthy asset holders rather than the broader economy.
    The concept of 'trickle-down economics' suggests that benefits to the wealthy eventually reach lower-income groups, but empirical evidence for this mechanism remains contested.

    Modern monetary theory (MMT) proposes an alternative framework where government spending is constrained by inflation rather than fiscal deficits.
    This represents a paradigm shift from traditional Keynesian economics.
    """

    try:
        processor = SummarizerProcessor(
            provider="openai",
            model="gpt-4",
            hce_options={
                "miner_model_override": "openai://gpt-4o-mini",
                "flagship_judge_model": "openai://gpt-4o",
            },
        )

        result = processor.process(test_text)

        if result.success:
            print("✅ End-to-end processing successful!")
            print(f"📊 Metadata: {result.metadata}")
            print(f"📄 Summary length: {len(result.data)} characters")
            if result.metadata.get("claims_count", 0) > 0:
                print("✅ Claims were successfully extracted!")
            else:
                print("⚠️ No claims extracted - may indicate JSON parsing issues")
        else:
            print("❌ End-to-end processing failed!")
            print(f"Errors: {result.errors}")

        return result

    except Exception as e:
        print(f"❌ End-to-end test failed: {e}")
        import traceback

        traceback.print_exc()
        return None


def main():
    """Run all tests."""
    print("🧪 Comprehensive Unified HCE Pipeline Testing")
    print("=" * 50)

    # Test 1: LLM Connection
    llm_ok = test_llm_connection()
    if not llm_ok:
        print("❌ Cannot proceed without LLM connection")
        return

    # Test 2: Unified Miner
    miner_outputs = test_unified_miner()

    # Test 3: Flagship Evaluator
    evaluation = test_flagship_evaluator(miner_outputs)

    # Test 4: End-to-End
    result = test_end_to_end()

    # Summary
    print("\n📋 Test Summary")
    print("=" * 50)
    print(f"✅ LLM Connection: {'PASS' if llm_ok else 'FAIL'}")
    print(f"✅ Unified Miner: {'PASS' if miner_outputs else 'FAIL'}")
    print(f"✅ Flagship Evaluator: {'PASS' if evaluation else 'FAIL'}")
    print(f"✅ End-to-End: {'PASS' if result and result.success else 'FAIL'}")


if __name__ == "__main__":
    main()
