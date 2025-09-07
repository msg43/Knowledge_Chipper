"""
GetReceipts.org Integration Module for Knowledge_Chipper

This module provides seamless integration with GetReceipts.org for uploading
processed claims data to the shared knowledge database.

Usage:
    from knowledge_system.integrations.getreceipts_integration import upload_to_getreceipts

    # After HCE processing:
    results = upload_to_getreceipts(session_data)
"""

import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

# Add the OAuth package to the path
oauth_package_path = (
    Path(__file__).parent.parent.parent.parent / "knowledge_chipper_oauth"
)
if str(oauth_package_path) not in sys.path:
    sys.path.append(str(oauth_package_path))

from ..logger import get_logger

logger = get_logger(__name__)


def upload_to_getreceipts(
    session_data: dict[str, Any], use_production: bool = True, authenticate: bool = True
) -> dict[str, Any]:
    """
    Upload Knowledge_Chipper session data to GetReceipts.org

    This function handles the complete OAuth authentication and data upload flow
    for sharing processed claims with the GetReceipts.org community.

    Args:
        session_data: Dictionary containing HCE processing results
        use_production: Whether to use production GetReceipts.org (default: True)
        authenticate: Whether to perform OAuth authentication (default: True)

    Returns:
        Dictionary with upload results for each data type

    Raises:
        Exception: If configuration is incomplete, authentication fails, or upload fails
    """

    try:
        # Import OAuth package modules
        from getreceipts_config import get_config, set_production, validate_config
        from getreceipts_uploader import GetReceiptsUploader

        logger.info("🚀 Starting GetReceipts.org upload process...")

        # Configure environment
        if use_production:
            set_production()
            logger.info("🔄 Using production GetReceipts.org configuration")

        # Validate configuration
        config = get_config()
        if not validate_config(config):
            raise Exception(
                "GetReceipts configuration incomplete - check knowledge_chipper_oauth/getreceipts_config.py"
            )

        logger.info(f"📋 Configuration valid - connecting to {config['base_url']}")

        # Initialize uploader
        uploader = GetReceiptsUploader(
            supabase_url=config["supabase_url"],
            supabase_anon_key=config["supabase_anon_key"],
            base_url=config["base_url"],
        )

        # Authenticate if required
        if authenticate:
            logger.info("🔐 Starting OAuth authentication...")
            auth_result = uploader.authenticate()
            logger.info(
                f"✅ Authenticated as: {auth_result['user_info']['name']} ({auth_result['user_info']['email']})"
            )

        # Log data summary
        data_summary = {}
        for table, data in session_data.items():
            count = len(data) if isinstance(data, list) else 1 if data else 0
            data_summary[table] = count

        logger.info(f"📊 Uploading data: {data_summary}")

        # Upload data
        upload_results = uploader.upload_session_data(session_data)

        # Log success
        upload_summary = {}
        for table, data in upload_results.items():
            count = len(data) if data else 0
            upload_summary[table] = count

        logger.info(f"✅ Upload completed successfully: {upload_summary}")
        return upload_results

    except Exception as e:
        logger.error(f"❌ GetReceipts.org upload failed: {e}")
        raise


def check_getreceipts_availability() -> bool:
    """
    Check if GetReceipts.org OAuth endpoints are available

    Returns:
        True if OAuth endpoints are available, False otherwise
    """

    try:
        import requests
        from getreceipts_config import get_config, set_production

        set_production()
        config = get_config()

        oauth_url = f"{config['base_url']}/auth/signin"
        response = requests.head(oauth_url, timeout=10, allow_redirects=True)

        if response.status_code == 200:
            logger.info("✅ GetReceipts.org OAuth endpoints are available")
            return True
        else:
            logger.warning(
                f"⚠️ GetReceipts.org OAuth endpoints unavailable (status: {response.status_code})"
            )
            return False

    except Exception as e:
        logger.warning(f"⚠️ Could not check GetReceipts.org availability: {e}")
        return False


def get_upload_summary(session_data: dict[str, Any]) -> str:
    """
    Generate a human-readable summary of data to be uploaded

    Args:
        session_data: HCE session data dictionary

    Returns:
        Formatted summary string
    """

    summary_parts = []

    for table, data in session_data.items():
        if not data:
            continue

        count = len(data) if isinstance(data, list) else 1

        # Format table names nicely
        table_name = table.replace("_", " ").title()
        if table_name.endswith("s"):
            singular = table_name[:-1]
        else:
            singular = table_name

        if count == 1:
            summary_parts.append(f"{count} {singular}")
        else:
            summary_parts.append(f"{count} {table_name}")

    if not summary_parts:
        return "No data to upload"

    return ", ".join(summary_parts)


# Configuration check on import
def _check_oauth_package():
    """Check if OAuth package is properly configured"""
    try:
        from getreceipts_config import get_config, validate_config

        config = get_config()
        if not validate_config(config):
            logger.warning(
                "⚠️ GetReceipts OAuth package needs configuration. See knowledge_chipper_oauth/getreceipts_config.py"
            )
    except ImportError:
        logger.warning(
            "⚠️ GetReceipts OAuth package not found. Ensure knowledge_chipper_oauth/ is in the project root."
        )
    except Exception as e:
        logger.warning(f"⚠️ GetReceipts OAuth package error: {e}")


# Run configuration check
_check_oauth_package()
