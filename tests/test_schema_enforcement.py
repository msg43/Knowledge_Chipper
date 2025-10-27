#!/usr/bin/env python3
"""
Test script for JSON schema enforcement with Ollama models.
This script tests the new structured outputs feature to ensure models
adhere to JSON schemas properly.
"""

import json
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from knowledge_system.config import get_settings
from knowledge_system.utils.llm_providers import UnifiedLLMClient
from knowledge_system.utils.pydantic_models import get_pydantic_model, get_schema_json


def test_schema_enforcement():
    """Test schema enforcement with different models."""

    # Test models to try
    test_models = [
        "qwen2.5:7b",  # Primary recommendation
        "qwen2.5:3b",  # Smaller alternative
        "llama3.2:3b",  # Llama alternative
        "llama3.1:8b",  # Larger Llama
    ]

    # Test prompt for miner output
    test_prompt = """
Extract claims, jargon, people, and mental models from this content:

"The CEO of TechCorp, Sarah Johnson, mentioned that their new AI framework uses transformer architecture. She believes this will revolutionize how we approach machine learning. The concept of attention mechanisms is key to understanding modern NLP."

Please analyze this content and extract:
1. Any claims being made
2. Technical jargon or terms
3. People mentioned
4. Mental models or frameworks discussed

Return the results in the exact JSON format specified in the schema.
"""

    print("🧪 Testing JSON Schema Enforcement with Ollama Models")
    print("=" * 60)

    for model in test_models:
        print(f"\n🔍 Testing model: {model}")
        print("-" * 40)

        try:
            # Create client for local model
            client = UnifiedLLMClient(provider="local", model=model)

            # Test 1: Regular JSON generation (baseline)
            print("  📝 Testing regular JSON generation...")
            try:
                response = client.generate(test_prompt)
                print(f"    ✅ Generated {len(response.content)} characters")

                # Try to parse as JSON
                try:
                    parsed = json.loads(response.content)
                    print(f"    ✅ Valid JSON structure")
                except json.JSONDecodeError as e:
                    print(f"    ❌ Invalid JSON: {e}")

            except Exception as e:
                print(f"    ❌ Failed: {e}")
                continue

            # Test 2: Structured JSON generation with schema enforcement
            print("  🔒 Testing structured JSON with schema enforcement...")
            try:
                result = client.generate_structured_json(test_prompt, "miner_output")
                print(
                    f"    ✅ Generated structured output with {len(str(result))} characters"
                )

                # Validate with Pydantic model
                try:
                    model_class = get_pydantic_model("miner_output")
                    validated = model_class.model_validate(result)
                    print(f"    ✅ Schema validation passed")
                    print(f"    📊 Claims: {len(validated.claims)}")
                    print(f"    📊 Jargon: {len(validated.jargon)}")
                    print(f"    📊 People: {len(validated.people)}")
                    print(f"    📊 Mental models: {len(validated.mental_models)}")

                except Exception as e:
                    print(f"    ❌ Schema validation failed: {e}")

            except Exception as e:
                print(f"    ❌ Structured generation failed: {e}")

            print(f"  ✅ Model {model} test completed")

        except Exception as e:
            print(f"  ❌ Model {model} not available: {e}")
            continue

    print("\n" + "=" * 60)
    print("🎯 Schema enforcement testing completed!")


def test_schema_comparison():
    """Compare outputs with and without schema enforcement."""

    print("\n🔬 Comparing Schema Enforcement vs Regular JSON")
    print("=" * 60)

    model = "qwen2.5:7b"  # Use the best model
    client = UnifiedLLMClient(provider="local", model=model)

    test_prompt = """
Analyze this content and extract claims:

"The company's revenue increased by 25% this quarter. The CEO believes this growth is sustainable."

Return ONLY a JSON object with claims array, following the exact schema format.
"""

    # Test without schema enforcement
    print("📝 Without Schema Enforcement:")
    try:
        response1 = client.generate(test_prompt)
        print(f"  Response length: {len(response1.content)}")
        print(f"  Content preview: {response1.content[:200]}...")

        try:
            parsed1 = json.loads(response1.content)
            print(f"  ✅ Valid JSON")
        except json.JSONDecodeError as e:
            print(f"  ❌ Invalid JSON: {e}")

    except Exception as e:
        print(f"  ❌ Failed: {e}")

    # Test with schema enforcement
    print("\n🔒 With Schema Enforcement:")
    try:
        result2 = client.generate_structured_json(test_prompt, "miner_output")
        print(f"  Response length: {len(str(result2))}")
        print(f"  Content preview: {str(result2)[:200]}...")

        # Validate with Pydantic
        try:
            model_class = get_pydantic_model("miner_output")
            validated2 = model_class.model_validate(result2)
            print(f"  ✅ Schema-compliant output")
            print(f"  📊 Claims extracted: {len(validated2.claims)}")

        except Exception as e:
            print(f"  ❌ Schema validation failed: {e}")

    except Exception as e:
        print(f"  ❌ Failed: {e}")


if __name__ == "__main__":
    try:
        test_schema_enforcement()
        test_schema_comparison()
    except KeyboardInterrupt:
        print("\n⏹️  Testing interrupted by user")
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback

        traceback.print_exc()
