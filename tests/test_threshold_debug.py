#!/usr/bin/env python3
"""
Test script to debug why the chunking threshold is so low.
"""

import sys
from pathlib import Path

# Add the source path to Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))


def test_threshold_calculation():
    """Test the threshold calculation to see why it's so low."""
    print("🧪 Testing Chunking Threshold Calculation")
    print("=" * 50)

    try:
        from knowledge_system.processors.summarizer import SummarizerProcessor

        # Create a summarizer instance with the same settings as GUI
        processor = SummarizerProcessor(
            provider="openai",
            model="gpt-4o-mini-2024-07-18",
            max_tokens=10000,  # This might be the issue - too high max_tokens
        )

        # Test with the actual prompt template
        text = "This is a sample text for testing." * 100  # Make it reasonably long
        prompt_template = "config/prompts/document summary.txt"

        print(f"Text length: {len(text)} characters")
        print(f"Prompt template: {prompt_template}")
        print(f"Max tokens setting: {processor.max_tokens}")

        # Call the threshold calculation method
        threshold = processor._calculate_smart_chunking_threshold(text, prompt_template)

        print(f"Calculated threshold: {threshold:,} tokens")

        # Let's also check what the prompt looks like
        sample_prompt = processor._generate_prompt("PLACEHOLDER_TEXT", prompt_template)
        prompt_without_placeholder = sample_prompt.replace("PLACEHOLDER_TEXT", "")

        print(f"Sample prompt length: {len(sample_prompt)} characters")
        print(
            f"Prompt without placeholder: {len(prompt_without_placeholder)} characters"
        )
        print(f"Sample prompt preview: {sample_prompt[:200]}...")

        # Check if the template file exists and what it contains
        template_path = Path(prompt_template)
        if template_path.exists():
            with open(template_path) as f:
                template_content = f.read()
            print(f"Template file size: {len(template_content)} characters")
            print(f"Template preview: {template_content[:200]}...")
        else:
            print(f"❌ Template file does not exist: {template_path}")

        return True

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_with_different_max_tokens():
    """Test with different max_tokens values to see the impact."""
    print("\n🧪 Testing Different Max Tokens Values")
    print("=" * 50)

    max_tokens_values = [1000, 4000, 10000, 20000]

    for max_tokens in max_tokens_values:
        try:
            from knowledge_system.processors.summarizer import SummarizerProcessor

            processor = SummarizerProcessor(
                provider="openai", model="gpt-4o-mini-2024-07-18", max_tokens=max_tokens
            )

            text = "Sample text"
            prompt_template = "config/prompts/document summary.txt"

            threshold = processor._calculate_smart_chunking_threshold(
                text, prompt_template
            )

            print(f"Max tokens: {max_tokens:,} → Threshold: {threshold:,} tokens")

        except Exception as e:
            print(f"Max tokens: {max_tokens:,} → Error: {e}")


if __name__ == "__main__":
    print("🚀 Debugging Chunking Threshold Issue\n")

    success = test_threshold_calculation()
    if success:
        test_with_different_max_tokens()
    else:
        print("❌ Threshold calculation failed")
        sys.exit(1)
