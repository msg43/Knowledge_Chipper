#!/usr/bin/env python3
"""
CLI tool for running Question Mapper on existing HCE data.

Usage:
    # Process a single source
    python scripts/run_question_mapper.py --source SOURCE_ID

    # Process all unmapped sources (with manual review)
    python scripts/run_question_mapper.py --all

    # Process all unmapped sources with auto-approval
    python scripts/run_question_mapper.py --all --auto-approve

    # Batch process first 10 unmapped sources
    python scripts/run_question_mapper.py --all --limit 10
"""

import argparse
import logging
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from knowledge_system.core.llm_adapter import LLMAdapter
from knowledge_system.database.service import DatabaseService
from knowledge_system.processors.question_mapper import (
    process_all_unmapped_sources,
    process_source_questions,
)

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(
        description="Run Question Mapper on HCE-processed sources"
    )
    parser.add_argument(
        "--source", type=str, help="Source ID to process (e.g., YouTube video ID)"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Process all sources that have claims but no questions",
    )
    parser.add_argument(
        "--auto-approve",
        action="store_true",
        help="Auto-approve discovered questions (skip manual review)",
    )
    parser.add_argument(
        "--limit", type=int, help="Limit number of sources to process (with --all)"
    )
    parser.add_argument(
        "--llm-provider",
        type=str,
        default="ollama",
        help="LLM provider (ollama, openai, anthropic)",
    )
    parser.add_argument(
        "--llm-model", type=str, default="qwen2.5:14b", help="LLM model name"
    )

    args = parser.parse_args()

    # Validate arguments
    if not args.source and not args.all:
        parser.error("Must specify either --source or --all")

    if args.source and args.all:
        parser.error("Cannot specify both --source and --all")

    # Create services
    logger.info(f"Initializing with LLM: {args.llm_provider}/{args.llm_model}")
    llm_adapter = LLMAdapter(provider=args.llm_provider, model=args.llm_model)
    db_service = DatabaseService()

    # Process based on mode
    if args.source:
        # Single source mode
        logger.info(f"Processing source: {args.source}")
        result = process_source_questions(
            source_id=args.source,
            llm_adapter=llm_adapter,
            db_service=db_service,
            auto_approve=args.auto_approve,
        )

        if result["success"]:
            print("\n✅ Question mapping complete!")
            print(f"   Source: {result['source_id']}")
            print(f"   Questions discovered: {result['questions_discovered']}")
            print(f"   Questions finalized: {result['questions_finalized']}")
            print(f"   Claims assigned: {result['claims_assigned']}")
            print(f"   Processing time: {result['processing_time']:.2f}s")
            print(f"   LLM calls: {result['llm_calls']}")

            if not args.auto_approve and result['questions_discovered'] > 0:
                print(
                    "\n💡 Questions require review - use the GUI 'Questions' tab to approve/reject"
                )

        else:
            print(f"\n❌ Question mapping failed: {result.get('error', 'Unknown error')}")
            sys.exit(1)

    else:
        # Batch mode
        logger.info("Processing all unmapped sources...")
        results = process_all_unmapped_sources(
            llm_adapter=llm_adapter,
            db_service=db_service,
            auto_approve=args.auto_approve,
            limit=args.limit,
        )

        # Summary
        successful = [r for r in results if r.get("success")]
        failed = [r for r in results if not r.get("success")]

        total_discovered = sum(r.get("questions_discovered", 0) for r in successful)
        total_finalized = sum(r.get("questions_finalized", 0) for r in successful)
        total_assigned = sum(r.get("claims_assigned", 0) for r in successful)
        total_time = sum(r.get("processing_time", 0) for r in successful)

        print("\n" + "=" * 60)
        print("BATCH PROCESSING SUMMARY")
        print("=" * 60)
        print(f"Sources processed: {len(results)}")
        print(f"  ✅ Successful: {len(successful)}")
        print(f"  ❌ Failed: {len(failed)}")
        print(f"\nQuestions discovered: {total_discovered}")
        print(f"Questions finalized: {total_finalized}")
        print(f"Claims assigned: {total_assigned}")
        print(f"Total processing time: {total_time:.2f}s")

        if not args.auto_approve and total_discovered > 0:
            print(
                f"\n💡 {total_discovered} questions require review - use the GUI 'Questions' tab"
            )

        if failed:
            print(f"\n⚠️  {len(failed)} source(s) failed:")
            for r in failed[:5]:  # Show first 5
                print(f"   - {r.get('source_id', 'unknown')}: {r.get('error', 'unknown')}")
            if len(failed) > 5:
                print(f"   ... and {len(failed) - 5} more")

        print("=" * 60)


if __name__ == "__main__":
    main()
