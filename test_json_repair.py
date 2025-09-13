#!/usr/bin/env python3
"""
Test script to validate JSON repair functionality in LLM responses.
This script tests the JSON repair mechanisms implemented for handling malformed JSON from qwen2.5:32b and other models.
"""

import json
import os
import sys

# Add the src directory to the path so we can import the module
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from knowledge_system.processors.hce.models.llm_any import AnyLLM


def test_json_repair():
    """Test the JSON repair functionality with various malformed JSON examples."""

    # Create an instance of AnyLLM
    llm = AnyLLM("local://test-model")

    # Test cases with different types of JSON errors
    test_cases = [
        # Case 1: Trailing comma
        ('{"key": "value",}', "trailing comma"),
        # Case 2: Missing closing brace
        ('{"key": "value"', "missing closing brace"),
        # Case 3: Unescaped newline in string
        ('{"key": "value with\nnewline"}', "unescaped newline"),
        # Case 4: Multiple issues combined
        ('{"key": "value",\n"nested": {"inner": "value",}', "multiple issues"),
        # Case 5: Control characters
        ('{"key": "value\x00test"}', "control characters"),
        # Case 6: The exact error pattern from the warning
        (
            '{"key1": "value1", "key2": "value2", "key3": "some text with unescaped quote " and more", "key4": "value4"}',
            "unescaped quote in middle",
        ),
    ]

    print("Testing JSON repair functionality...\n")

    success_count = 0
    total_count = len(test_cases)

    for i, (malformed_json, description) in enumerate(test_cases, 1):
        print(f"Test {i}: {description}")
        print(
            f"Input:  {malformed_json[:100]}{'...' if len(malformed_json) > 100 else ''}"
        )

        try:
            # Try to parse the original JSON (should fail)
            json.loads(malformed_json)
            print("  ⚠️  Original JSON unexpectedly parsed successfully")
        except json.JSONDecodeError:
            print("  ✓ Original JSON failed to parse as expected")

        # Test the repair function
        repaired = llm._attempt_json_repair(malformed_json, "test-model")

        if repaired is not None:
            print(f"  ✅ Repair successful: {type(repaired).__name__}")
            if isinstance(repaired, dict):
                print(f"     Keys: {list(repaired.keys())}")
            elif isinstance(repaired, list):
                print(f"     Length: {len(repaired)}")
            success_count += 1
        else:
            print("  ❌ Repair failed")

        print()

    print(f"Summary: {success_count}/{total_count} repairs successful")

    if success_count == total_count:
        print("🎉 All JSON repair tests passed!")
        return True
    else:
        print(f"⚠️  {total_count - success_count} tests failed")
        return False


def test_specific_qwen_error():
    """Test with a JSON structure similar to what might cause the qwen2.5:32b error."""
    print("Testing qwen2.5:32b-style error scenario...\n")

    llm = AnyLLM("local://qwen2.5:32b")

    # Simulate the type of malformed JSON that might come from qwen2.5:32b
    # Based on "line 7 column 178 (char 400)", this suggests a longer JSON structure
    malformed_json = """
{
  "summary": "This is a test summary",
  "key_points": [
    "Point 1",
    "Point 2",
    "Point 3",
  ],
  "analysis": "This analysis contains some text that might have "unescaped quotes" which could cause issues at position 178 or so",
  "conclusion": "Test conclusion",
  "metadata": {
    "source": "test",
    "timestamp": "2025-09-13",
  }
}
"""

    print("Testing qwen2.5:32b error pattern...")
    print(f"JSON length: {len(malformed_json)} characters")

    try:
        json.loads(malformed_json)
        print("  ⚠️  Original JSON unexpectedly parsed successfully")
    except json.JSONDecodeError as e:
        print(f"  ✓ Original JSON failed as expected: {e}")

    repaired = llm._attempt_json_repair(malformed_json, "qwen2.5:32b")

    if repaired is not None:
        print("  ✅ qwen2.5:32b-style JSON repair successful!")
        print(f"     Type: {type(repaired).__name__}")
        if isinstance(repaired, dict):
            print(f"     Keys: {list(repaired.keys())}")
        return True
    else:
        print("  ❌ qwen2.5:32b-style JSON repair failed")
        return False


if __name__ == "__main__":
    print("JSON Repair Test Suite")
    print("=" * 50)

    # Run general tests
    general_success = test_json_repair()
    print()

    # Run qwen-specific test
    qwen_success = test_specific_qwen_error()
    print()

    if general_success and qwen_success:
        print("🎉 All tests passed! JSON repair functionality is working correctly.")
        sys.exit(0)
    else:
        print("❌ Some tests failed. Check the implementation.")
        sys.exit(1)
