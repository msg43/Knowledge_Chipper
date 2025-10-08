#!/usr/bin/env python3
"""
Comprehensive test suite for the unified HCE pipeline with System 2 integration.

This test suite validates:
- HCE pipeline components (miner, flagship evaluator)
- System 2 job orchestration for HCE tasks
- JSON schema validation for miner and flagship inputs/outputs
- LLM request/response tracking
- End-to-end processing with checkpoint persistence
"""

import asyncio
import json
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from knowledge_system.core.system2_orchestrator import (
    System2Orchestrator,
    get_orchestrator,
)
from knowledge_system.database import DatabaseService
from knowledge_system.database.system2_models import (
    Job,
    JobRun,
    LLMRequest,
    LLMResponse,
)
from knowledge_system.processors.hce.flagship_evaluator import (
    FlagshipEvaluator,
    evaluate_claims_flagship,
)
from knowledge_system.processors.hce.models.llm_any import AnyLLM
from knowledge_system.processors.hce.schema_validator import SchemaValidator
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


async def test_schema_validation():
    """Test JSON schema validation for miner and flagship."""
    print("\n📋 Testing JSON Schema Validation")
    print("-" * 30)

    try:
        validator = SchemaValidator()

        # Test miner input schema
        miner_input = {
            "segment": {
                "segment_id": "seg_test_001",
                "speaker": "narrator",
                "timestamp_start": "00:00:00",
                "timestamp_end": "00:00:10",
                "text": "Test segment text",
            }
        }

        miner_valid = validator.validate_miner_input(miner_input)
        print(f"  {'✅' if miner_valid else '❌'} Miner input validation: {miner_valid}")

        # Test flagship input schema
        flagship_input = {
            "content_summary": "Test content summary for validation"
            * 5,  # Make it long enough
            "claims_to_evaluate": [
                {
                    "claim_text": "Test claim text",
                    "claim_type": "factual",
                    "stance": "asserts",
                    "evidence_spans": [
                        {"quote": "Test quote", "t0": "00:00", "t1": "00:10"}
                    ],
                }
            ],
        }

        flagship_valid = validator.validate_flagship_input(flagship_input)
        print(
            f"  {'✅' if flagship_valid else '❌'} Flagship input validation: {flagship_valid}"
        )

        return miner_valid and flagship_valid

    except Exception as e:
        print(f"❌ Schema validation failed: {e}")
        import traceback

        traceback.print_exc()
        return False


async def test_system2_hce_orchestration():
    """Test System 2 orchestration for HCE tasks."""
    print("\n🎯 Testing System 2 HCE Orchestration")
    print("-" * 30)

    try:
        # Initialize System 2 components
        db_service = DatabaseService()
        orchestrator = get_orchestrator(db_service)

        # Create a mine job
        job_id = orchestrator.create_job(
            job_type="mine",
            input_id="test_episode_hce",
            config={"model": "gpt-4o-mini", "enable_schema_validation": True},
            auto_process=True,
        )

        print(f"  ✅ Created mine job: {job_id}")

        # Verify job in database
        with db_service.get_session() as session:
            job = session.query(Job).filter_by(job_id=job_id).first()
            if job is None:
                raise AssertionError(f"Job {job_id} not found in database")
            if job.job_type != "mine":
                raise AssertionError(f"Expected job_type 'mine', got '{job.job_type}'")
            print(f"  ✅ Job verified in database")
            print(f"      Type: {job.job_type}")
            print(f"      Input: {job.input_id}")
            print(f"      Auto-process: {job.auto_process}")

        return True

    except Exception as e:
        print(f"❌ System 2 HCE orchestration failed: {e}")
        import traceback

        traceback.print_exc()
        return False


async def test_llm_tracking_hce():
    """Test LLM request/response tracking for HCE operations."""
    print("\n🤖 Testing LLM Tracking for HCE")
    print("-" * 30)

    try:
        db_service = DatabaseService()
        orchestrator = get_orchestrator(db_service)

        # Create job and run for tracking
        job_id = orchestrator.create_job(
            job_type="mine",
            input_id="test_episode_llm_track",
            config={"model": "gpt-4o-mini"},
            auto_process=False,
        )

        run_id = orchestrator.create_job_run(job_id)
        orchestrator._current_job_run_id = run_id

        # Simulate LLM request for mining
        request_id = orchestrator.track_llm_request(
            provider="openai",
            model="gpt-4o-mini",
            request_payload={
                "messages": [
                    {"role": "system", "content": "You are a claim extraction system"},
                    {
                        "role": "user",
                        "content": "Extract claims from: The Federal Reserve announced...",
                    },
                ]
            },
        )

        # Simulate response
        orchestrator.track_llm_response(
            request_id,
            response_payload={
                "content": json.dumps(
                    {"claims": [{"claim_text": "Test claim", "claim_type": "factual"}]}
                ),
                "usage": {
                    "total_tokens": 150,
                    "prompt_tokens": 100,
                    "completion_tokens": 50,
                },
            },
            response_time_ms=2500,
        )

        # Verify tracking
        with db_service.get_session() as session:
            request = session.query(LLMRequest).filter_by(request_id=request_id).first()
            response = (
                session.query(LLMResponse).filter_by(request_id=request_id).first()
            )

            if request is None:
                raise AssertionError(f"LLM request {request_id} not found")
            if response is None:
                raise AssertionError(f"LLM response for {request_id} not found")

            print(f"  ✅ LLM request tracked: {request_id}")
            print(f"      Provider: {request.provider}")
            print(f"      Model: {request.model}")
            print(f"      Tokens: {response.total_tokens}")
            print(f"      Latency: {response.latency_ms}ms")

        return True

    except Exception as e:
        print(f"❌ LLM tracking for HCE failed: {e}")
        import traceback

        traceback.print_exc()
        return False


async def main():
    """Run all tests."""
    print("🧪 Comprehensive Unified HCE Pipeline Testing (System 2)")
    print("=" * 50)

    # System 2 tests first
    print("\n" + "=" * 50)
    print("🎯 SYSTEM 2 HCE TESTS")
    print("=" * 50)

    schema_ok = await test_schema_validation()
    system2_ok = await test_system2_hce_orchestration()
    llm_tracking_ok = await test_llm_tracking_hce()

    # Legacy HCE tests
    print("\n" + "=" * 50)
    print("🔄 LEGACY HCE TESTS")
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
    print("System 2 Tests:")
    print(f"  ✅ Schema Validation: {'PASS' if schema_ok else 'FAIL'}")
    print(f"  ✅ System 2 Orchestration: {'PASS' if system2_ok else 'FAIL'}")
    print(f"  ✅ LLM Tracking: {'PASS' if llm_tracking_ok else 'FAIL'}")
    print("\nLegacy HCE Tests:")
    print(f"  ✅ LLM Connection: {'PASS' if llm_ok else 'FAIL'}")
    print(f"  ✅ Unified Miner: {'PASS' if miner_outputs else 'FAIL'}")
    print(f"  ✅ Flagship Evaluator: {'PASS' if evaluation else 'FAIL'}")
    print(f"  ✅ End-to-End: {'PASS' if result and result.success else 'FAIL'}")

    # Overall success
    all_tests_pass = all(
        [
            schema_ok,
            system2_ok,
            llm_tracking_ok,
            llm_ok,
            bool(miner_outputs),
            bool(evaluation),
            result and result.success,
        ]
    )

    print("\n" + "=" * 50)
    print(f"{'✅ ALL TESTS PASSED' if all_tests_pass else '❌ SOME TESTS FAILED'}")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
