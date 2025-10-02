#!/usr/bin/env python3
"""
Test script to verify Qwen2.5 works better with JSON schema than Llama3.2.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from knowledge_system.processors.summarizer import SummarizerProcessor


def main():
    """Test Qwen2.5 with the unified pipeline."""

    # File paths - find the Steve Bannon file dynamically
    transcripts_dir = Path("output/transcripts")
    steve_bannon_files = [
        f for f in transcripts_dir.glob("*Steve Bannon*") if f.is_file()
    ]

    if not steve_bannon_files:
        print("❌ No Steve Bannon transcript found in output/transcripts/")
        return False

    input_file = steve_bannon_files[0]
    output_dir = Path("output")

    print(f"🎯 Testing Qwen2.5 with: {input_file.name}")
    print(f"📁 Output directory: {output_dir}")

    # Create processor with unified pipeline using Qwen2.5 (now the default)
    print("\n🔧 Creating SummarizerProcessor with Qwen2.5...")
    processor = SummarizerProcessor(
        provider="openai",
        model="gpt-4o-mini",
        max_tokens=10000,
        hce_options={
            "use_skim": True,
            # No model overrides - should use Qwen2.5 defaults now
        },
    )

    # Process the file
    print(f"\n🚀 Starting summarization with Qwen2.5 as default local model...")
    result = processor.process(input_file)

    if result.success:
        print(f"✅ Summarization completed successfully!")

        # Save the result
        output_file = output_dir / f"{input_file.stem}_qwen_summary.md"

        # Create formatted content
        content = f"# Summary of {input_file.stem.replace('_', ' ')}\n\n"
        content += "**Processing:** HCE Unified Pipeline with Qwen2.5\n"
        content += f"**Model:** gpt-4o-mini\n"
        content += f"**Local Model:** qwen2.5:7b (default)\n"
        content += f"**Provider:** openai\n"
        content += f"**Generated:** {result.metadata.get('timestamp', 'unknown')}\n\n"

        # Add the actual summary content
        content += result.data

        # Write to file
        output_file.write_text(content, encoding="utf-8")
        print(f"📄 Summary saved to: {output_file}")

        # Print some statistics
        if hasattr(result, "metadata") and result.metadata:
            print(f"\n📊 Processing Statistics:")
            for key, value in result.metadata.items():
                if key not in ["timestamp"]:
                    print(f"   {key}: {value}")

        return True
    else:
        print(f"❌ Summarization failed!")
        if hasattr(result, "errors") and result.errors:
            for error in result.errors:
                print(f"   Error: {error}")
        return False


if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"💥 Unexpected error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
