#!/usr/bin/env python3
"""
Quick test of the unified HCE pipeline.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from knowledge_system.processors.summarizer import SummarizerProcessor


def test_unified_pipeline():
    """Test the unified pipeline with sample text."""

    # Sample text about economics
    test_text = """
    The Federal Reserve's quantitative easing program has fundamentally altered the relationship between monetary policy and asset prices.
    According to Fed Chairman Jerome Powell, this creates what economists call a 'wealth effect' where rising asset prices boost consumer spending.

    However, some critics argue this approach primarily benefits wealthy asset holders rather than the broader economy.
    The concept of 'trickle-down economics' suggests that benefits to the wealthy eventually reach lower-income groups, but empirical evidence for this mechanism remains contested.

    Modern monetary theory (MMT) proposes an alternative framework where government spending is constrained by inflation rather than fiscal deficits.
    This represents a paradigm shift from traditional Keynesian economics.
    """

    print("🚀 Testing Unified HCE Pipeline")
    print("=" * 50)

    try:
        # Create processor with test configuration
        processor = SummarizerProcessor(
            provider="openai",
            model="gpt-4",
            hce_options={
                "miner_model_override": "openai://gpt-4o-mini",
                "flagship_judge_model": "openai://gpt-4o",
            },
        )

        print("✅ Processor created successfully")

        # Process the text
        print("\n📝 Processing sample text...")
        result = processor.process(test_text)

        if result.success:
            print("✅ Processing successful!")
            print(f"\n📊 Metadata: {result.metadata}")
            print(f"\n📄 Summary:\n{result.data}")
        else:
            print("❌ Processing failed!")
            print(f"Errors: {result.errors}")

    except Exception as e:
        print(f"❌ Test failed with exception: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    test_unified_pipeline()
