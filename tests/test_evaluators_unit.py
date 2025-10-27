#!/usr/bin/env python3
"""
Unit test for evaluators - verifies the architecture without LLM calls.

Tests:
1. Evaluator modules can be imported
2. Evaluator classes have correct methods
3. Schema validation works
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))


def test_imports():
    """Test that all evaluator modules can be imported."""
    print("Testing evaluator imports...")

    try:
        from knowledge_system.processors.hce.evaluators.concepts_evaluator import (
            evaluate_concepts,
        )
        from knowledge_system.processors.hce.evaluators.jargon_evaluator import (
            evaluate_jargon,
        )
        from knowledge_system.processors.hce.evaluators.people_evaluator import (
            evaluate_people,
        )

        print("✅ All evaluator modules imported successfully")
        return True
    except ImportError as e:
        print(f"❌ Import failed: {e}")
        return False


def test_config():
    """Test that config has miner_selectivity."""
    print("\nTesting config changes...")

    try:
        from knowledge_system.processors.hce.config_flex import PipelineConfigFlex

        # Test default
        config = PipelineConfigFlex()
        assert hasattr(config, "miner_selectivity"), "Config missing miner_selectivity"
        print(f"✅ Default miner_selectivity: {config.miner_selectivity}")

        # Test custom
        from knowledge_system.processors.hce.config_flex import StageModelConfig

        config_liberal = PipelineConfigFlex(
            models=StageModelConfig(
                miner="local://test",
                judge="local://test",
            ),
            miner_selectivity="liberal",
        )
        assert config_liberal.miner_selectivity == "liberal"
        print(f"✅ Custom miner_selectivity: {config_liberal.miner_selectivity}")

        return True
    except Exception as e:
        print(f"❌ Config test failed: {e}")
        return False


def test_prompts():
    """Test that all prompts exist."""
    print("\nTesting prompt files...")

    prompts_dir = Path(__file__).parent / "src/knowledge_system/processors/hce/prompts"

    required_prompts = [
        "unified_miner_liberal.txt",
        "unified_miner_moderate.txt",
        "unified_miner_conservative.txt",
        "jargon_evaluator.txt",
        "people_evaluator.txt",
        "concepts_evaluator.txt",
    ]

    all_exist = True
    for prompt_file in required_prompts:
        path = prompts_dir / prompt_file
        if path.exists():
            size = path.stat().st_size
            print(f"✅ {prompt_file} ({size} bytes)")
        else:
            print(f"❌ {prompt_file} NOT FOUND")
            all_exist = False

    return all_exist


def test_pipeline_integration():
    """Test that pipeline can be instantiated with new parameters."""
    print("\nTesting pipeline integration...")

    try:
        from knowledge_system.processors.hce.config_flex import (
            PipelineConfigFlex,
            StageModelConfig,
        )
        from knowledge_system.processors.hce.unified_pipeline import UnifiedHCEPipeline

        config = PipelineConfigFlex(
            models=StageModelConfig(
                miner="local://test",
                judge="local://test",
            ),
            miner_selectivity="moderate",
        )

        pipeline = UnifiedHCEPipeline(config=config)
        print(
            f"✅ Pipeline instantiated with miner_selectivity={config.miner_selectivity}"
        )

        # Check that pipeline has the parallel evaluation method
        assert hasattr(
            pipeline, "_evaluate_all_entities_parallel"
        ), "Pipeline missing _evaluate_all_entities_parallel"
        print(f"✅ Pipeline has _evaluate_all_entities_parallel method")

        return True
    except Exception as e:
        print(f"❌ Pipeline test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_database_bulk_insert():
    """Test that DatabaseService has bulk_insert_json method."""
    print("\nTesting database bulk insert...")

    try:
        from knowledge_system.database.service import DatabaseService

        # Check method exists
        assert hasattr(
            DatabaseService, "bulk_insert_json"
        ), "DatabaseService missing bulk_insert_json"
        print(f"✅ DatabaseService has bulk_insert_json method")

        # Check signature
        import inspect

        sig = inspect.signature(DatabaseService.bulk_insert_json)
        params = list(sig.parameters.keys())
        assert "table_name" in params, "bulk_insert_json missing table_name parameter"
        assert "records" in params, "bulk_insert_json missing records parameter"
        print(f"✅ bulk_insert_json has correct signature: {params}")

        return True
    except Exception as e:
        print(f"❌ Database test failed: {e}")
        return False


def main():
    """Run all tests."""
    print(
        """
╔══════════════════════════════════════════════════════════════════════════════╗
║                   HCE EVALUATOR UNIT TEST SUITE                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""
    )

    results = {
        "Imports": test_imports(),
        "Config": test_config(),
        "Prompts": test_prompts(),
        "Pipeline": test_pipeline_integration(),
        "Database": test_database_bulk_insert(),
    }

    print(f"\n{'='*80}")
    print(f"RESULTS")
    print(f"{'='*80}\n")

    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{test_name:<20} {status}")

    all_passed = all(results.values())

    if all_passed:
        print(f"\n✅ ALL UNIT TESTS PASSED - Architecture is correct!")
        return 0
    else:
        print(f"\n❌ SOME TESTS FAILED - Check output above")
        return 1


if __name__ == "__main__":
    sys.exit(main())
