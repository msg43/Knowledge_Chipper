#!/usr/bin/env python3
"""
Quick test to check if the linting issue persists.
"""


def test_proxy_processor():
    """Test that the proxy processor can be instantiated."""

    print("🧪 Testing proxy processor instantiation...")

    try:
        from src.knowledge_system.processors.youtube_metadata_proxy import (
            YouTubeMetadataProxyProcessor,
        )

        # Try to create instance
        processor = YouTubeMetadataProxyProcessor()
        print("   ✅ YouTubeMetadataProxyProcessor instantiated successfully")

        # Check abstract methods are implemented
        assert hasattr(processor, "validate_input")
        assert hasattr(processor, "supported_formats")
        print("   ✅ Abstract methods are implemented")

        # Test validate_input
        result = processor.validate_input("https://www.youtube.com/watch?v=test")
        print(f"   ✅ validate_input works: {result}")

        # Test supported_formats
        formats = processor.supported_formats
        print(f"   ✅ supported_formats: {formats}")

        return True

    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False


if __name__ == "__main__":
    test_proxy_processor()
