#!/usr/bin/env python3
"""
Script showing how to control parallel workers in HCE processing.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from knowledge_system.processors.hce.config_flex import (
    PipelineConfigFlex,
    StageModelConfig,
)
from knowledge_system.processors.hce.unified_pipeline import UnifiedHCEPipeline


def demonstrate_worker_control():
    """Demonstrate different ways to control parallel workers."""

    print("🔧 Parallel Worker Control Examples")
    print("=" * 50)

    # Example 1: Single worker (recommended for 72B models)
    print("\n1. Single Worker (Sequential Processing)")
    print("-" * 40)
    config_single = PipelineConfigFlex(
        models=StageModelConfig(
            miner="qwen2.5:72b-instruct", judge="qwen2.5:72b-instruct"
        ),
        max_workers=1,  # Force sequential processing
        enable_parallel_processing=True,
    )

    pipeline_single = UnifiedHCEPipeline(config_single)
    print(f"✅ Single worker configuration created")
    print(f"   Miner model: {config_single.models.miner}")
    print(f"   Max workers: {config_single.max_workers}")

    # Example 2: Auto-calculate workers (default behavior)
    print("\n2. Auto-Calculate Workers (Default)")
    print("-" * 40)
    config_auto = PipelineConfigFlex(
        models=StageModelConfig(
            miner="qwen2.5:32b-instruct", judge="qwen2.5:72b-instruct"
        ),
        max_workers=None,  # Auto-calculate based on system resources
        enable_parallel_processing=True,
    )

    pipeline_auto = UnifiedHCEPipeline(config_auto)
    print(f"✅ Auto-calculate configuration created")
    print(f"   Miner model: {config_auto.models.miner}")
    print(f"   Max workers: {config_auto.max_workers} (auto-calculated)")

    # Example 3: Disable parallel processing entirely
    print("\n3. Disable Parallel Processing")
    print("-" * 40)
    config_disabled = PipelineConfigFlex(
        models=StageModelConfig(
            miner="qwen2.5:72b-instruct", judge="qwen2.5:72b-instruct"
        ),
        enable_parallel_processing=False,  # Force sequential regardless of max_workers
    )

    pipeline_disabled = UnifiedHCEPipeline(config_disabled)
    print(f"✅ Parallel processing disabled")
    print(f"   Miner model: {config_disabled.models.miner}")
    print(f"   Parallel processing: {config_disabled.enable_parallel_processing}")

    # Example 4: Manual worker count
    print("\n4. Manual Worker Count")
    print("-" * 40)
    config_manual = PipelineConfigFlex(
        models=StageModelConfig(
            miner="qwen2.5:32b-instruct", judge="qwen2.5:32b-instruct"
        ),
        max_workers=3,  # Exactly 3 workers
        enable_parallel_processing=True,
    )

    pipeline_manual = UnifiedHCEPipeline(config_manual)
    print(f"✅ Manual worker count configuration created")
    print(f"   Miner model: {config_manual.models.miner}")
    print(f"   Max workers: {config_manual.max_workers}")

    print("\n" + "=" * 50)
    print("📋 Configuration Summary")
    print("=" * 50)

    configs = [
        ("Single Worker", config_single),
        ("Auto-Calculate", config_auto),
        ("Disabled", config_disabled),
        ("Manual (3)", config_manual),
    ]

    for name, config in configs:
        max_workers = config.max_workers
        if (
            hasattr(config, "enable_parallel_processing")
            and not config.enable_parallel_processing
        ):
            max_workers = "Sequential (disabled)"
        elif max_workers is None:
            max_workers = "Auto-calculated"

        print(f"{name:15} | Workers: {max_workers:15} | Model: {config.models.miner}")

    print("\n🎯 Recommendations for Your 128GB Setup:")
    print("   • Single 72B model: max_workers=1 (sequential)")
    print("   • Multiple 32B models: max_workers=3-4")
    print("   • Mixed setup: 1x 72B flagship + 2x 32B miners")


def show_auto_calculation():
    """Show how auto-calculation works."""
    print("\n🧮 Auto-Calculation Details")
    print("=" * 50)

    from knowledge_system.processors.hce.parallel_processor import ParallelHCEProcessor

    # Create processor to see auto-calculation
    processor = ParallelHCEProcessor()
    print(f"✅ Auto-calculated workers: {processor.max_workers}")

    # Show the calculation logic
    import psutil

    memory = psutil.virtual_memory()
    available_gb = memory.available / (1024**3)
    cpu_cores = psutil.cpu_count(logical=False) or 4

    print(f"   Available RAM: {available_gb:.1f} GB")
    print(f"   CPU cores: {cpu_cores}")
    print(
        f"   Memory-based limit: {int(available_gb / 0.2)} workers (200MB per worker)"
    )
    print(f"   CPU-based limit: {min(cpu_cores * 2, 12)} workers")
    print(f"   Final calculation: {processor.max_workers} workers")


if __name__ == "__main__":
    try:
        demonstrate_worker_control()
        show_auto_calculation()
        print("\n✅ All examples completed successfully!")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
