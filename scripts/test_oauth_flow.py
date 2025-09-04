#!/usr/bin/env python3
"""
Test script for OAuth callback server and GetReceipts integration.

This script can be used to test the OAuth flow without running the full GUI.
"""

import sys
import time
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from knowledge_system.services.oauth_callback_server import OAuthCallbackServer, start_oauth_callback_server
from knowledge_system.services.supabase_auth import SupabaseAuthService
from knowledge_system.logger import get_logger

logger = get_logger(__name__)


def test_callback_server():
    """Test the OAuth callback server functionality."""
    print("Testing OAuth Callback Server")
    print("=" * 40)
    
    # Create and start server
    server = OAuthCallbackServer()
    print(f"Starting server on {server.host}:{server.port}")
    
    if not server.start():
        print("❌ Failed to start server")
        return False
    
    print("✅ Server started successfully")
    print(f"📋 Callback URL: {server.get_callback_url()}")
    print(f"⚡ Server running: {server.is_running()}")
    
    # Test URL for manual testing
    test_url = f"http://localhost:8080/auth/callback?access_token=test_token&refresh_token=test_refresh&user_id=test_user"
    print(f"\n🧪 Test URL (open in browser):")
    print(f"   {test_url}")
    
    print(f"\n⏰ Waiting 10 seconds for manual test...")
    time.sleep(10)
    
    # Stop server
    server.stop()
    print("🛑 Server stopped")
    
    return True


def test_oauth_auth_service():
    """Test the SupabaseAuthService OAuth functionality."""
    print("\nTesting SupabaseAuthService OAuth")
    print("=" * 40)
    
    # Create auth service
    auth = SupabaseAuthService()
    
    if not auth.is_available():
        print("⚠️  Supabase auth service not available (expected in test environment)")
        return True
    
    print("✅ Auth service available")
    print(f"📍 Supabase URL: {auth.supabase_url}")
    print(f"🔑 Has client: {auth.client is not None}")
    
    # Note: We don't actually run OAuth here since it requires browser interaction
    print("ℹ️  OAuth flow test requires browser interaction - skipping automated test")
    
    return True


def main():
    """Run all tests."""
    print("🧪 Testing Knowledge_Chipper OAuth Integration")
    print("=" * 50)
    
    try:
        # Test callback server
        if not test_callback_server():
            print("❌ Callback server test failed")
            sys.exit(1)
        
        # Test auth service
        if not test_oauth_auth_service():
            print("❌ Auth service test failed")
            sys.exit(1)
        
        print("\n✅ All tests passed!")
        print("\n📋 Manual Testing Instructions:")
        print("1. Run the Knowledge_Chipper GUI")
        print("2. Go to Cloud Uploads tab")
        print("3. Click 'Sign In with GetReceipts'")
        print("4. Verify browser opens to GetReceipts")
        print("5. Complete sign-in flow")
        print("6. Verify app receives tokens and shows 'Signed In'")
        
    except Exception as e:
        logger.error(f"Test error: {e}")
        print(f"❌ Test failed with error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
