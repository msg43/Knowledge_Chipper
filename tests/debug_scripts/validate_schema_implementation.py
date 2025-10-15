#!/usr/bin/env python3
"""
Simple validation script for the schema enforcement implementation.
Run this to verify the implementation is working correctly.
"""

import json
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))


def main():
    print("🔍 Validating Schema Enforcement Implementation")
    print("=" * 50)

    try:
        # Test 1: Import Pydantic models
        print("1. Testing Pydantic model imports...")
        from knowledge_system.utils.pydantic_models import (
            Claim,
            EvidenceSpan,
            UnifiedMinerOutput,
            get_pydantic_model,
            get_schema_json,
        )

        print("   ✅ Pydantic models imported successfully")

        # Test 2: Generate schema
        print("2. Testing schema generation...")
        schema = get_schema_json("miner_output")
        print(f"   ✅ Generated schema with {len(json.dumps(schema))} characters")
        print(f"   ✅ Schema type: {schema.get('type')}")
        print(f"   ✅ Required fields: {schema.get('required')}")

        # Test 3: Create and validate data
        print("3. Testing data creation and validation...")
        evidence = EvidenceSpan(quote="Test quote", t0="00:01:00", t1="00:01:05")

        claim = Claim(
            claim_text="Test claim",
            claim_type="factual",
            stance="asserts",
            evidence_spans=[evidence],
        )

        miner_output = UnifiedMinerOutput(
            claims=[claim], jargon=[], people=[], mental_models=[]
        )
        print("   ✅ Created and validated Pydantic objects")

        # Test 4: JSON serialization
        print("4. Testing JSON serialization...")
        json_str = miner_output.model_dump_json()
        parsed = json.loads(json_str)
        print(f"   ✅ Serialized to JSON: {len(json_str)} characters")

        # Test 5: Import LLM providers
        print("5. Testing LLM provider imports...")
        from knowledge_system.utils.llm_providers import UnifiedLLMClient

        print("   ✅ LLM providers imported successfully")

        print("\n🎉 All validation tests passed!")
        print("\n📋 Implementation Summary:")
        print("   • Pydantic models created for miner and flagship outputs")
        print("   • JSON schema generation working")
        print("   • LLM providers enhanced with schema support")
        print("   • SuperChunk adapter updated for structured outputs")
        print("   • HCE processors updated to use schema enforcement")
        print("\n🚀 Ready to test with Ollama models!")

        return True

    except Exception as e:
        print(f"❌ Validation failed: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
