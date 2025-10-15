#!/usr/bin/env python3
"""Manual test script for Ollama integration with System 2 LLM Adapter."""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from knowledge_system.core.llm_adapter import get_llm_adapter


async def test_ollama():
    """Test Ollama integration with the LLM adapter."""

    print("=" * 60)
    print("Ollama Integration Test Suite")
    print("=" * 60)

    adapter = get_llm_adapter()

    # Test 1: Simple completion
    print("\n[Test 1] Simple completion...")
    try:
        result = await adapter.complete(
            provider="ollama",
            model="qwen2.5:7b-instruct",
            messages=[{"role": "user", "content": "Say hello in one sentence."}],
        )
        print(f"✓ Response: {result['content'][:100]}")
        print(f"  Tokens: {result['usage']['total_tokens']}")
    except Exception as e:
        print(f"✗ Failed: {e}")
        return False

    # Test 2: JSON generation
    print("\n[Test 2] JSON generation...")
    try:
        result = await adapter.complete(
            provider="ollama",
            model="qwen2.5:7b-instruct",
            messages=[
                {
                    "role": "user",
                    "content": 'Return JSON with status field: {"status": "ok"}',
                }
            ],
            format="json",
        )
        print(f"✓ JSON Response: {result['content'][:100]}")

        # Try to parse as JSON
        import json

        parsed = json.loads(result["content"])
        print(f"  Parsed successfully: {list(parsed.keys())}")
    except Exception as e:
        print(f"✗ Failed: {e}")
        return False

    # Test 3: Retry with exponential backoff
    print("\n[Test 3] Retry logic...")
    try:
        result = await adapter.complete_with_retry(
            provider="ollama",
            model="qwen2.5:7b-instruct",
            messages=[{"role": "user", "content": "Test retry"}],
            max_retries=3,
        )
        print(f"✓ Retry logic works: {result['content'][:50]}")
    except Exception as e:
        print(f"✗ Failed: {e}")
        return False

    # Test 4: Hardware tier detection
    print("\n[Test 4] Hardware tier detection...")
    stats = adapter.get_stats()
    print(f"✓ Hardware tier: {stats['hardware_tier']}")
    print(f"  Max concurrent: {stats['max_concurrent']}")
    print(f"  Memory usage: {stats['memory_usage']:.1f}%")

    # Test 5: Rate limiting
    print("\n[Test 5] Concurrent requests (rate limiting)...")
    try:
        tasks = [
            adapter.complete(
                provider="ollama",
                model="qwen2.5:7b-instruct",
                messages=[{"role": "user", "content": f"Count to {i}"}],
            )
            for i in range(3)
        ]
        results = await asyncio.gather(*tasks)
        print(f"✓ Successfully completed {len(results)} concurrent requests")
    except Exception as e:
        print(f"✗ Failed: {e}")
        return False

    print("\n" + "=" * 60)
    print("✓ All tests passed!")
    print("=" * 60)
    return True


async def check_ollama_running():
    """Check if Ollama is running and accessible."""
    import aiohttp

    print("\n[Pre-check] Verifying Ollama is running...")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "http://localhost:11434/api/tags",
                timeout=aiohttp.ClientTimeout(total=5),
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    models = [m["name"] for m in data.get("models", [])]
                    print(f"✓ Ollama is running")
                    print(f"  Available models: {', '.join(models)}")

                    if "qwen2.5:7b-instruct" not in models:
                        print(f"\n⚠ Warning: qwen2.5:7b-instruct not found!")
                        print(f"  Run: ollama pull qwen2.5:7b-instruct")
                        return False
                    return True
                else:
                    print(f"✗ Ollama returned status {response.status}")
                    return False
    except Exception as e:
        print(f"✗ Cannot connect to Ollama: {e}")
        print("\nPlease ensure Ollama is running:")
        print("  - macOS/Linux: ollama serve")
        print("  - Or check if it's running in the background")
        return False


async def main():
    """Main test runner."""
    # Check Ollama first
    if not await check_ollama_running():
        sys.exit(1)

    # Run tests
    success = await test_ollama()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
