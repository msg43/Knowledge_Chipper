#!/usr/bin/env python3
"""
Quick test script for the new proxy system.
Tests that the proxy abstraction layer is working correctly.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))


def test_proxy_imports():
    """Test that all proxy modules can be imported."""
    print("Testing proxy imports...")
    try:
        from knowledge_system.utils.proxy import (
            AnyIPProvider,
            BaseProxyProvider,
            BrightDataProvider,
            DirectConnectionProvider,
            GonzoProxyProvider,
            OxylabsProvider,
            PacketStreamProvider,
            ProxyService,
            ProxyType,
        )

        print("✅ All proxy modules imported successfully")
        return True
    except Exception as e:
        print(f"❌ Import failed: {e}")
        return False


def test_proxy_service_creation():
    """Test that ProxyService can be created."""
    print("\nTesting ProxyService creation...")
    try:
        from knowledge_system.utils.proxy import ProxyService

        proxy_service = ProxyService()
        print(f"✅ ProxyService created successfully")
        print(f"   Active provider: {proxy_service.provider_name}")
        print(f"   Is configured: {proxy_service.is_configured()}")
        return True
    except Exception as e:
        print(f"❌ ProxyService creation failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_direct_provider():
    """Test DirectConnectionProvider."""
    print("\nTesting DirectConnectionProvider...")
    try:
        from knowledge_system.utils.proxy import DirectConnectionProvider

        provider = DirectConnectionProvider()
        assert provider.is_configured() == True
        assert provider.provider_name == "Direct Connection"
        assert provider.get_proxy_url() == None
        assert provider.get_proxy_config() == {}

        success, msg = provider.test_connectivity()
        assert success == True

        print("✅ DirectConnectionProvider works correctly")
        return True
    except Exception as e:
        print(f"❌ DirectConnectionProvider test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_packetstream_provider():
    """Test PacketStreamProvider."""
    print("\nTesting PacketStreamProvider...")
    try:
        from knowledge_system.utils.proxy import PacketStreamProvider

        provider = PacketStreamProvider()
        print(f"   Provider name: {provider.provider_name}")
        print(f"   Is configured: {provider.is_configured()}")

        # Test proxy URL generation (should return None if not configured)
        proxy_url = provider.get_proxy_url()
        print(f"   Proxy URL: {proxy_url if proxy_url else 'None (not configured)'}")

        # Test proxy config
        proxy_config = provider.get_proxy_config()
        print(
            f"   Proxy config: {proxy_config if proxy_config else 'Empty (not configured)'}"
        )

        print("✅ PacketStreamProvider initialized successfully")
        return True
    except Exception as e:
        print(f"❌ PacketStreamProvider test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_stub_providers():
    """Test that stub providers are properly implemented."""
    print("\nTesting stub providers...")
    try:
        from knowledge_system.utils.proxy import (
            AnyIPProvider,
            BrightDataProvider,
            GonzoProxyProvider,
            OxylabsProvider,
        )

        providers = [
            ("AnyIP", AnyIPProvider()),
            ("Oxylabs", OxylabsProvider()),
            ("GonzoProxy", GonzoProxyProvider()),
            ("BrightData", BrightDataProvider()),
        ]

        for name, provider in providers:
            # All stubs should report not configured
            assert provider.is_configured() == False, f"{name} should not be configured"
            assert (
                provider.get_proxy_config() == {}
            ), f"{name} should return empty config"
            print(f"   ✅ {name} stub working correctly")

        print("✅ All stub providers working correctly")
        return True
    except Exception as e:
        print(f"❌ Stub provider test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_proxy_type_enum():
    """Test ProxyType enum."""
    print("\nTesting ProxyType enum...")
    try:
        from knowledge_system.utils.proxy import ProxyType

        assert ProxyType.PACKETSTREAM.value == "packetstream"
        assert ProxyType.ANYIP.value == "anyip"
        assert ProxyType.OXYLABS.value == "oxylabs"
        assert ProxyType.GONZOPROXY.value == "gonzoproxy"
        assert ProxyType.BRIGHTDATA.value == "brightdata"
        assert ProxyType.DIRECT.value == "direct"

        print("✅ ProxyType enum has all expected values")
        return True
    except Exception as e:
        print(f"❌ ProxyType enum test failed: {e}")
        return False


def main():
    """Run all tests."""
    print("=" * 60)
    print("Proxy System Test Suite")
    print("=" * 60)

    tests = [
        test_proxy_imports,
        test_proxy_type_enum,
        test_direct_provider,
        test_packetstream_provider,
        test_stub_providers,
        test_proxy_service_creation,
    ]

    results = []
    for test in tests:
        results.append(test())

    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"Passed: {passed}/{total}")

    if passed == total:
        print("✅ All tests passed!")
        return 0
    else:
        print(f"❌ {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
