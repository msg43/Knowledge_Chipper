"""
GetReceipts.org Data Uploader for Knowledge_Chipper

This module handles uploading Knowledge_Chipper HCE data to GetReceipts.org
via HTTP API with automatic device authentication (Happy-style).

Usage:
    from knowledge_chipper_oauth.getreceipts_uploader import GetReceiptsUploader

    uploader = GetReceiptsUploader()  # Auto-authenticates with device credentials
    results = uploader.upload_session_data(session_data)

Author: GetReceipts.org Team
License: MIT
"""

import sys
from pathlib import Path
from typing import Any

import requests

# Add parent directory to path to import device_auth
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from knowledge_system.services.device_auth import get_device_auth


class GetReceiptsUploader:
    """
    Handles uploading Knowledge_Chipper data to GetReceipts.org

    This class:
    1. Auto-authenticates with device credentials (silent, Happy-style)
    2. Uploads data via HTTP API (bypasses RLS issues)
    3. Handles all data types (episodes, claims, evidence, knowledge artifacts)

    Architecture: Web-canonical with ephemeral local
    """

    def __init__(
        self,
        api_base_url: str = "https://getreceipts.org/api/knowledge-chipper",
        bypass_device_auth: bool = False,
    ):
        """
        Initialize the uploader with automatic device authentication

        Args:
            api_base_url: Base URL for GetReceipts API endpoints
            bypass_device_auth: If True, skip device authentication (uses anonymous upload)
        """
        self.api_base_url = api_base_url
        self.bypass_device_auth = bypass_device_auth
        
        if bypass_device_auth:
            print("⚠️  Device authentication BYPASSED - using anonymous upload")
            self.device_auth = None
            self.credentials = {
                'device_id': 'anonymous',
                'device_key': 'bypass'
            }
        else:
        self.device_auth = get_device_auth()
        self.credentials = self.device_auth.get_credentials()
        print(f"🔐 Using device ID: {self.credentials['device_id'][:8]}...")

    def is_enabled(self) -> bool:
        """Check if auto-upload is enabled"""
        if self.bypass_device_auth:
            return True  # Always enabled when bypassing auth
        return self.device_auth.is_enabled()

    def upload_session_data(self, session_data: dict[str, Any]) -> dict[str, Any]:
        """
        Upload complete Knowledge_Chipper session data to GetReceipts

        This method uploads all data via the HTTP API endpoint which:
        - Uses service role authentication internally
        - Bypasses RLS policies
        - Tracks device provenance
        - Supports version tracking for reprocessing

        Args:
            session_data: Dictionary containing all HCE data tables

        Returns:
            Dictionary with upload results (empty if disabled)
        """
        # Check if auto-upload is enabled
        if not self.is_enabled():
            print("⏭️  Auto-upload disabled - skipping GetReceipts upload")
            return {}

        print("🚀 Starting upload to GetReceipts.org...")

        # Add version tracking metadata if available
        if "processing_version" not in session_data:
            session_data["processing_version"] = self._generate_version_metadata(session_data)

        # Count records
        total_records = sum(
            len(session_data.get(key, []))
            for key in ["episodes", "claims", "evidence_spans", "people", "jargon", "concepts", "relations"]
        )

        print(f"📊 Total records to upload: {total_records}")
        if total_records == 0:
            print("⚠️  No data to upload")
            return {}

        try:
            # Build headers
            headers = {"Content-Type": "application/json"}
            
            if not self.bypass_device_auth:
                # Include device credentials only if not bypassing
                headers["X-Device-ID"] = self.credentials["device_id"]
                headers["X-Device-Key"] = self.credentials["device_key"]
            else:
                # When bypassing, use anonymous device ID
                headers["X-Device-ID"] = "anonymous-bypass"
                print("📤 Uploading without device authentication (bypass mode)")
            
            # Upload via HTTP API endpoint
            response = requests.post(
                f"{self.api_base_url}/upload",
                headers=headers,
                json=session_data,
                timeout=120  # 2 minute timeout for large uploads
            )

            # Check response
            if response.status_code in (200, 201, 207):  # 207 = Multi-Status (partial success)
                result = response.json()

                if result.get("success"):
                    print("✅ Upload completed successfully!")
                else:
                    print(f"⚠️  Upload completed with warnings: {result.get('message')}")

                # Print summary
                if "uploaded" in result:
                    self._print_upload_summary(result["uploaded"])

                return result
            else:
                error_data = response.json() if response.headers.get("content-type") == "application/json" else {}
                error_msg = error_data.get("message", response.text)
                print(f"❌ Upload failed ({response.status_code}): {error_msg}")
                raise Exception(f"Upload failed: {error_msg}")

        except requests.exceptions.Timeout:
            print("❌ Upload timed out - try uploading fewer records at once")
            raise
        except requests.exceptions.ConnectionError as e:
            print(f"❌ Connection error: {e}")
            print("💡 Check your internet connection and try again")
            raise
        except Exception as e:
            print(f"❌ Upload failed: {str(e)}")
            raise

    def _print_upload_summary(self, results: dict[str, int | list]):
        """Print a summary of upload results"""
        print("\n📊 Upload Summary:")

        total = 0
        for table, data in results.items():
            if table == "errors":
                continue  # Skip errors in count

            count = data if isinstance(data, int) else (len(data) if data else 0)
            if count > 0:
                print(f"  {table}: {count} records")
                total += count

        if "errors" in results and results["errors"]:
            print(f"\n⚠️  Errors: {len(results['errors'])}")
            for error in results["errors"][:5]:  # Show first 5 errors
                print(f"    - {error}")

        print(f"\n  Total: {total} records uploaded")
    
    def _generate_version_metadata(self, session_data: dict[str, Any]) -> dict[str, Any]:
        """
        Generate processing version metadata for tracking re-processing runs
        
        Returns:
            Dictionary with version tracking information
        """
        # Extract source_id from first claim or episode
        source_id = None
        if session_data.get("claims") and len(session_data["claims"]) > 0:
            source_id = session_data["claims"][0].get("source_id")
        elif session_data.get("media_sources") and len(session_data["media_sources"]) > 0:
            source_id = session_data["media_sources"][0].get("source_id")
        
        if not source_id:
            return {}
        
        # Calculate statistics
        claims = session_data.get("claims", [])
        avg_importance = sum(c.get("importance_score", 0) for c in claims) / len(claims) if claims else 0
        avg_confidence = sum(c.get("confidence_score", 0) for c in claims) / len(claims) if claims else 0
        
        return {
            "source_id": source_id,
            "version_number": 1,  # Will be incremented by server if already processed
            "model_used": session_data.get("config", {}).get("llm_model", "unknown"),
            "pipeline_version": session_data.get("config", {}).get("pipeline_version", "unknown"),
            "claims_count": len(claims),
            "people_count": len(session_data.get("people", [])),
            "jargon_count": len(session_data.get("jargon", [])),
            "concepts_count": len(session_data.get("concepts", [])),
            "avg_claim_importance": avg_importance,
            "avg_claim_confidence": avg_confidence
        }


# Example usage
if __name__ == "__main__":
    # Simple test of the upload system (auto-authenticates with device credentials)
    uploader = GetReceiptsUploader()

    try:
        # Check if enabled
        if not uploader.is_enabled():
            print("Auto-upload is disabled. Enable in Settings to upload.")
        else:
            # Example session data
            test_data = {
                "episodes": [
                    {
                        "episode_id": "test_http_001",
                        "title": "HTTP API Test Episode",
                        "url": "https://youtube.com/watch?v=test",
                    }
                ],
                "claims": [
                    {
                        "claim_id": "test_http_claim_001",
                        "canonical": "This is a test claim via HTTP API",
                        "episode_id": "test_http_001",
                        "claim_type": "factual",
                        "tier": "A",
                        "scores_json": '{"confidence": 0.9, "importance": 0.8}',
                    }
                ],
            }

            # Upload data (automatically uses device credentials)
            results = uploader.upload_session_data(test_data)
            print(f"\n✅ Upload successful!")
            print(f"Device ID: {uploader.credentials['device_id']}")
            print(f"Architecture: {results.get('architecture', 'N/A')}")

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
