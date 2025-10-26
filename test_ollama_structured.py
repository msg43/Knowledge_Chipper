#!/usr/bin/env python3
"""Test if Ollama's structured outputs work with different schema complexities."""

import json
import time

import requests

# Simple schema (no nesting, no regex)
SIMPLE_SCHEMA = {
    "type": "object",
    "required": ["name", "age"],
    "properties": {"name": {"type": "string"}, "age": {"type": "integer"}},
}

# Nested schema (like our miner_output.v1.json)
NESTED_SCHEMA = {
    "type": "object",
    "required": ["claims"],
    "properties": {
        "claims": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["claim_text", "evidence_spans"],
                "properties": {
                    "claim_text": {"type": "string"},
                    "evidence_spans": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": ["quote", "t0", "t1"],
                            "properties": {
                                "quote": {"type": "string"},
                                "t0": {
                                    "type": "string",
                                    "pattern": "^\\d{2}:\\d{2}(:\\d{2})?$",
                                },
                                "t1": {
                                    "type": "string",
                                    "pattern": "^\\d{2}:\\d{2}(:\\d{2})?$",
                                },
                            },
                        },
                    },
                },
            },
        }
    },
}

# Flat schema with timestamps (no nested arrays, but has regex)
FLAT_WITH_TIMESTAMPS = {
    "type": "object",
    "required": ["claims"],
    "properties": {
        "claims": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["claim_text", "timestamp"],
                "properties": {
                    "claim_text": {"type": "string"},
                    "timestamp": {
                        "type": "string",
                        "pattern": "^\\d{2}:\\d{2}(:\\d{2})?$",
                    },
                    "evidence_quote": {"type": "string"},
                },
            },
        }
    },
}

# Flat schema WITHOUT regex (just strings)
FLAT_NO_REGEX = {
    "type": "object",
    "required": ["claims"],
    "properties": {
        "claims": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["claim_text", "timestamp"],
                "properties": {
                    "claim_text": {"type": "string"},
                    "timestamp": {"type": "string"},
                    "evidence_quote": {"type": "string"},
                },
            },
        }
    },
}


def test_schema(name, schema, prompt="Tell me a fact about AI."):
    """Test if Ollama can generate with a given schema."""
    print(f"\n{'='*60}")
    print(f"Testing: {name}")
    print(f"{'='*60}")

    payload = {
        "model": "qwen2.5:7b-instruct",
        "messages": [{"role": "user", "content": prompt}],
        "format": schema,
        "stream": False,
        "options": {"temperature": 0.0},
    }

    try:
        start = time.time()
        response = requests.post(
            "http://localhost:11434/api/chat", json=payload, timeout=30
        )
        elapsed = time.time() - start

        if response.status_code == 200:
            result = response.json()
            content = result.get("message", {}).get("content", "")
            print(f"✅ SUCCESS ({elapsed:.2f}s)")
            print(f"Response: {content[:200]}...")
            return True, elapsed
        else:
            error = response.json().get("error", "Unknown error")
            print(f"❌ FAILED: {error}")
            return False, None
    except Exception as e:
        print(f"❌ EXCEPTION: {e}")
        return False, None


def main():
    print("OLLAMA STRUCTURED OUTPUT COMPATIBILITY TEST")
    print(f"Testing different schema complexities...")

    results = {}

    # Test 1: Simple schema
    results["simple"] = test_schema(
        "Simple (no nesting)", SIMPLE_SCHEMA, "Give me your name and age."
    )
    time.sleep(2)

    # Test 2: Flat with timestamps (regex)
    results["flat_regex"] = test_schema(
        "Flat with regex timestamps",
        FLAT_WITH_TIMESTAMPS,
        "Extract one claim from this: 'AI will transform healthcare in the next 5 years.'",
    )
    time.sleep(2)

    # Test 3: Flat without regex
    results["flat_no_regex"] = test_schema(
        "Flat without regex",
        FLAT_NO_REGEX,
        "Extract one claim from this: 'AI will transform healthcare in the next 5 years.'",
    )
    time.sleep(2)

    # Test 4: Nested schema (like miner_output.v1.json)
    results["nested"] = test_schema(
        "Nested with regex (miner_output.v1)",
        NESTED_SCHEMA,
        "Extract one claim with evidence from this: 'Studies show AI improves diagnosis accuracy by 20%.'",
    )

    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    for name, (success, elapsed) in results.items():
        status = "✅ WORKS" if success else "❌ FAILS"
        time_str = f"({elapsed:.2f}s)" if elapsed else ""
        print(f"{name:20s}: {status} {time_str}")

    # Conclusion
    print(f"\n{'='*60}")
    if results["nested"][0]:
        print("✅ Nested schema WORKS - no simplification needed!")
    else:
        print("❌ Nested schema FAILS")
        if results["flat_regex"][0]:
            print("   ✅ But flat + regex works → nesting is the problem")
        elif results["flat_no_regex"][0]:
            print("   ✅ But flat without regex works → regex is the problem")
        else:
            print("   ❌ All structured outputs fail → Ollama issue")


if __name__ == "__main__":
    main()
