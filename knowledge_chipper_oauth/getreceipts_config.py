"""
GetReceipts.org Configuration for Knowledge_Chipper Integration

This module manages configuration settings for different environments
(development vs production) and provides easy switching between them.

Usage:
    from getreceipts_config import get_config, set_production

    # Use development configuration (default)
    config = get_config()

    # Switch to production
    set_production()
    config = get_config()

Author: GetReceipts.org Team
License: MIT
"""

import os
from typing import Any, Dict

# Development Configuration (Default)
# Use this when GetReceipts.org is running locally
DEVELOPMENT = {
    "base_url": "http://localhost:3000",
    "supabase_url": "https://sdkxuiqcwlmbpjvjdpkj.supabase.co",
    "supabase_anon_key": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InNka3h1aXFjd2xtYnBqdmpkcGtqIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTU4MTU3MzQsImV4cCI6MjA3MTM5MTczNH0.VoP6yX3GwyVjylgioTGchQYwPQ_K2xQFdHP5ani0vts",
    "environment": "development",
    "callback_port": 8080,
    "oauth_timeout": 300,  # 5 minutes
}

# Production Configuration
# Use this when connecting to live GetReceipts.org
PRODUCTION = {
    "base_url": "https://www.skipthepodcast.com",
    "supabase_url": "https://sdkxuiqcwlmbpjvjdpkj.supabase.co",
    "supabase_anon_key": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InNka3h1aXFjd2xtYnBqdmpkcGtqIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTU4MTU3MzQsImV4cCI6MjA3MTM5MTczNH0.VoP6yX3GwyVjylgioTGchQYwPQ_K2xQFdHP5ani0vts",
    "environment": "production",
    "callback_port": 8080,
    "oauth_timeout": 300,  # 5 minutes
}

# Current active configuration (starts with development)
_CURRENT_CONFIG = DEVELOPMENT


def get_config() -> dict[str, Any]:
    """
    Get the current configuration

    Returns:
        Dictionary with current configuration settings
    """
    # Try to load from environment variables first
    config = _CURRENT_CONFIG.copy()

    # Override with environment variables if they exist
    if os.getenv("GETRECEIPTS_BASE_URL"):
        config["base_url"] = os.getenv("GETRECEIPTS_BASE_URL")

    if os.getenv("SUPABASE_URL"):
        config["supabase_url"] = os.getenv("SUPABASE_URL")

    if os.getenv("SUPABASE_ANON_KEY"):
        config["supabase_anon_key"] = os.getenv("SUPABASE_ANON_KEY")

    if os.getenv("OAUTH_CALLBACK_PORT"):
        config["callback_port"] = int(os.getenv("OAUTH_CALLBACK_PORT"))

    return config


def set_production():
    """
    Switch to production configuration

    Call this before get_config() to use production URLs
    """
    global _CURRENT_CONFIG
    _CURRENT_CONFIG = PRODUCTION
    print("🔄 Switched to PRODUCTION configuration")


def set_development():
    """
    Switch to development configuration

    Call this to explicitly use development URLs (this is the default)
    """
    global _CURRENT_CONFIG
    _CURRENT_CONFIG = DEVELOPMENT
    print("🔄 Switched to DEVELOPMENT configuration")


def is_production() -> bool:
    """
    Check if currently using production configuration

    Returns:
        True if using production config, False if development
    """
    return _CURRENT_CONFIG["environment"] == "production"


def validate_config(config: dict[str, Any]) -> bool:
    """
    Validate that configuration has all required fields

    Args:
        config: Configuration dictionary to validate

    Returns:
        True if valid, False otherwise
    """
    required_fields = ["base_url", "supabase_url", "supabase_anon_key"]

    for field in required_fields:
        if not config.get(field) or config[field] in [
            "YOUR-PROJECT.supabase.co",
            "YOUR-SUPABASE-ANON-KEY-HERE",
        ]:
            print(f"❌ Configuration error: {field} not set or using placeholder value")
            return False

    return True


def print_config():
    """
    Print current configuration (hiding sensitive keys)
    """
    config = get_config()

    print(f"\n📋 Current Configuration ({config['environment']}):")
    print(f"  Base URL: {config['base_url']}")
    print(f"  Supabase URL: {config['supabase_url']}")
    print(
        f"  Anon Key: {config['supabase_anon_key'][:20]}..."
        if config["supabase_anon_key"]
        else "  Anon Key: NOT SET"
    )
    print(f"  Callback Port: {config['callback_port']}")
    print(f"  OAuth Timeout: {config['oauth_timeout']} seconds")

    if not validate_config(config):
        print("\n⚠️  Configuration incomplete! Please update with your actual values.")


# Configuration setup instructions
SETUP_INSTRUCTIONS = """
🔧 Configuration Setup Instructions:

1. Get your Supabase credentials from the GetReceipts team:
   - Supabase URL (https://your-project.supabase.co)
   - Supabase Anon Key (public key for client connections)

2. Update this file (getreceipts_config.py):
   - Replace 'YOUR-PROJECT.supabase.co' with your actual Supabase URL
   - Replace 'YOUR-SUPABASE-ANON-KEY-HERE' with your actual anon key

3. Or set environment variables:
   export SUPABASE_URL="https://your-project.supabase.co"
   export SUPABASE_ANON_KEY="your-actual-anon-key"
   export GETRECEIPTS_BASE_URL="http://localhost:3000"  # for development

4. For production deployment:
   from getreceipts_config import set_production
   set_production()

Example .env file:
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
GETRECEIPTS_BASE_URL=http://localhost:3000
OAUTH_CALLBACK_PORT=8080
"""


def print_setup_instructions():
    """Print setup instructions"""
    print(SETUP_INSTRUCTIONS)


# Auto-validate configuration on import
if __name__ == "__main__":
    # Run configuration check
    print_config()

    config = get_config()
    if not validate_config(config):
        print_setup_instructions()
    else:
        print("✅ Configuration looks good!")
else:
    # Quick validation on import
    config = get_config()
    if not validate_config(config):
        print(
            "⚠️  GetReceipts configuration needs setup. Run 'python getreceipts_config.py' for instructions."
        )
