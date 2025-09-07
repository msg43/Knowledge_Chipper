#!/usr/bin/env python3
"""
Check PacketStream setup and provide configuration guidance.
"""


def check_packetstream_setup():
    """Check PacketStream credential configuration from all sources."""

    print("🔍 Checking PacketStream Configuration")
    print("=" * 40)

    found_credentials = False

    # Check 1: Environment variables
    print("1. Checking environment variables...")
    import os

    env_username = os.getenv("PACKETSTREAM_USERNAME")
    env_auth_key = os.getenv("PACKETSTREAM_AUTH_KEY")

    if env_username and env_auth_key:
        print(f"   ✅ Found in environment:")
        print(f"   Username: {env_username}")
        print(f"   Auth Key: {'*' * len(env_auth_key)}")
        found_credentials = True
    else:
        print(f"   ❌ Not found in environment variables")
        print(f"   PACKETSTREAM_USERNAME: {'✅' if env_username else '❌'}")
        print(f"   PACKETSTREAM_AUTH_KEY: {'✅' if env_auth_key else '❌'}")

    # Check 2: Settings/Config
    print("\n2. Checking application settings...")
    try:
        from src.knowledge_system.config import KnowledgeSystemConfig

        config = KnowledgeSystemConfig()

        if hasattr(config.api_keys, "packetstream_username") and hasattr(
            config.api_keys, "packetstream_auth_key"
        ):
            config_username = config.api_keys.packetstream_username
            config_auth_key = config.api_keys.packetstream_auth_key

            if config_username and config_auth_key:
                print(f"   ✅ Found in application config:")
                print(f"   Username: {config_username}")
                print(f"   Auth Key: {'*' * len(config_auth_key)}")
                found_credentials = True
            else:
                print(f"   ❌ Empty in application config")
                print(f"   Username: {'✅' if config_username else '❌'}")
                print(f"   Auth Key: {'✅' if config_auth_key else '❌'}")
        else:
            print(f"   ❌ PacketStream fields not found in config")

    except Exception as e:
        print(f"   ❌ Error loading config: {e}")

    # Check 3: Test proxy processor initialization
    print("\n3. Testing proxy processor initialization...")
    try:
        from src.knowledge_system.processors.youtube_metadata_proxy import (
            YouTubeMetadataProxyProcessor,
        )

        processor = YouTubeMetadataProxyProcessor()

        if processor.proxy_manager:
            print(f"   ✅ Proxy processor initialized successfully")
            print(f"   Proxy manager: {type(processor.proxy_manager).__name__}")
            found_credentials = True
        else:
            print(f"   ❌ Proxy processor has no proxy manager")

    except Exception as e:
        print(f"   ❌ Error initializing proxy processor: {e}")

    # Summary and recommendations
    print(f"\n{'=' * 40}")
    if found_credentials:
        print("🎉 PacketStream credentials found!")
        print("\n✅ Your PacketStream setup appears to be working.")
        print("   You should now be able to use PacketStream for YouTube extraction.")
    else:
        print("❌ PacketStream credentials NOT found!")
        print("\n🔧 To configure PacketStream:")
        print("   1. Open the application")
        print("   2. Go to Settings → API Keys tab")
        print("   3. Enter your PacketStream Username")
        print("   4. Enter your PacketStream Auth Key")
        print("   5. Save settings")
        print("\n📝 Alternative - Environment variables:")
        print("   export PACKETSTREAM_USERNAME='your_username'")
        print("   export PACKETSTREAM_AUTH_KEY='your_auth_key'")

        print("\n🌐 Get PacketStream credentials:")
        print("   1. Sign up at: https://packetstream.io")
        print("   2. Get your username and auth key from dashboard")

    return found_credentials


if __name__ == "__main__":
    check_packetstream_setup()
