#!/usr/bin/env python3
"""
Test script for JSON schema validation without requiring Ollama to be running.
This validates that our Pydantic models and schema generation work correctly.
"""

import json
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from knowledge_system.utils.pydantic_models import (
    Claim,
    EvidenceSpan,
    FlagshipEvaluationOutput,
    UnifiedMinerOutput,
    get_pydantic_model,
    get_schema_json,
)


def test_pydantic_models():
    """Test that Pydantic models work correctly."""
    print("🧪 Testing Pydantic Models")
    print("=" * 40)

    # Test creating a simple claim
    try:
        evidence = EvidenceSpan(
            quote="The CEO said revenue increased 25%", t0="00:01:30", t1="00:01:35"
        )

        claim = Claim(
            claim_text="Company revenue increased by 25% this quarter",
            claim_type="factual",
            stance="asserts",
            evidence_spans=[evidence],
        )

        print(f"✅ Created claim: {claim.claim_text}")
        print(f"✅ Claim type: {claim.claim_type}")
        print(f"✅ Evidence spans: {len(claim.evidence_spans)}")

    except Exception as e:
        print(f"❌ Failed to create claim: {e}")
        return False

    # Test creating a full miner output
    try:
        miner_output = UnifiedMinerOutput(
            claims=[claim], jargon=[], people=[], mental_models=[]
        )

        print(f"✅ Created miner output with {len(miner_output.claims)} claims")

    except Exception as e:
        print(f"❌ Failed to create miner output: {e}")
        return False

    return True


def test_schema_generation():
    """Test that JSON schemas are generated correctly."""
    print("\n🔧 Testing Schema Generation")
    print("=" * 40)

    # Test miner output schema
    try:
        schema = get_schema_json("miner_output")
        print(f"✅ Generated miner_output schema")
        print(f"   Type: {schema.get('type')}")
        print(f"   Properties: {list(schema.get('properties', {}).keys())}")

        # Check that required fields are present
        required = schema.get("required", [])
        expected_required = ["claims", "jargon", "people", "mental_models"]
        if all(field in required for field in expected_required):
            print(f"✅ All required fields present: {required}")
        else:
            print(
                f"❌ Missing required fields. Expected: {expected_required}, Got: {required}"
            )

    except Exception as e:
        print(f"❌ Failed to generate miner_output schema: {e}")
        return False

    # Test flagship output schema
    try:
        schema = get_schema_json("flagship_output")
        print(f"✅ Generated flagship_output schema")
        print(f"   Type: {schema.get('type')}")
        print(f"   Properties: {list(schema.get('properties', {}).keys())}")

    except Exception as e:
        print(f"❌ Failed to generate flagship_output schema: {e}")
        return False

    return True


def test_json_serialization():
    """Test JSON serialization and deserialization."""
    print("\n📄 Testing JSON Serialization")
    print("=" * 40)

    try:
        # Create test data
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

        # Serialize to JSON
        json_str = miner_output.model_dump_json()
        print(f"✅ Serialized to JSON: {len(json_str)} characters")

        # Parse back from JSON
        parsed_data = json.loads(json_str)
        print(f"✅ Parsed JSON successfully")

        # Validate with Pydantic
        validated = UnifiedMinerOutput.model_validate(parsed_data)
        print(f"✅ Validated with Pydantic: {len(validated.claims)} claims")

    except Exception as e:
        print(f"❌ JSON serialization failed: {e}")
        return False

    return True


def test_schema_structure():
    """Test that generated schemas have the right structure for Ollama."""
    print("\n🏗️  Testing Schema Structure for Ollama")
    print("=" * 40)

    try:
        schema = get_schema_json("miner_output")

        # Check top-level structure
        if schema.get("type") == "object":
            print("✅ Schema type is 'object'")
        else:
            print(f"❌ Schema type should be 'object', got: {schema.get('type')}")
            return False

        # Check properties structure
        properties = schema.get("properties", {})
        if "claims" in properties:
            claims_prop = properties["claims"]
            if claims_prop.get("type") == "array":
                print("✅ Claims property is array type")
            else:
                print(
                    f"❌ Claims property should be array, got: {claims_prop.get('type')}"
                )
                return False

        # Check that schema is valid JSON
        json_str = json.dumps(schema)
        print(f"✅ Schema is valid JSON: {len(json_str)} characters")

        # Check for required fields
        required = schema.get("required", [])
        if len(required) > 0:
            print(f"✅ Schema has {len(required)} required fields")
        else:
            print("❌ Schema should have required fields")
            return False

        print("✅ Schema structure is compatible with Ollama structured outputs")
        return True

    except Exception as e:
        print(f"❌ Schema structure test failed: {e}")
        return False


def main():
    """Run all tests."""
    print("🚀 Starting Schema Validation Tests")
    print("=" * 60)

    tests = [
        ("Pydantic Models", test_pydantic_models),
        ("Schema Generation", test_schema_generation),
        ("JSON Serialization", test_json_serialization),
        ("Schema Structure", test_schema_structure),
    ]

    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ Test '{test_name}' crashed: {e}")
            results.append((test_name, False))

    print("\n" + "=" * 60)
    print("📊 Test Results Summary")
    print("=" * 60)

    passed = 0
    total = len(results)

    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {test_name}")
        if result:
            passed += 1

    print(f"\n🎯 Results: {passed}/{total} tests passed")

    if passed == total:
        print("🎉 All tests passed! Schema enforcement is ready.")
        return True
    else:
        print("⚠️  Some tests failed. Check the output above.")
        return False


if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n⏹️  Testing interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Test suite failed: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
