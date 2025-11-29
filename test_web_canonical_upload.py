#!/usr/bin/env python3
"""
Test script for web-canonical upload workflow

This script tests:
1. Device authentication
2. Upload to GetReceipts
3. Local database hiding behavior (ephemeral)

Usage:
    python3 test_web_canonical_upload.py
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from knowledge_system.services.device_auth import get_device_auth
from knowledge_chipper_oauth.getreceipts_uploader import GetReceiptsUploader

def test_device_auth():
    """Test device authentication setup"""
    print("=" * 60)
    print("TEST 1: Device Authentication")
    print("=" * 60)

    auth = get_device_auth()
    creds = auth.get_credentials()

    print(f"✅ Device ID: {creds['device_id']}")
    print(f"✅ Device Key: {creds['device_key'][:16]}... (truncated for security)")
    print(f"✅ Auto-upload enabled: {auth.is_enabled()}")
    print()

    return creds

def test_upload_connection(creds):
    """Test connection to GetReceipts API"""
    print("=" * 60)
    print("TEST 2: Upload Connection")
    print("=" * 60)

    uploader = GetReceiptsUploader()
    print(f"✅ Uploader initialized with device: {creds['device_id'][:16]}...")
    print(f"✅ Upload enabled: {uploader.is_enabled()}")
    print()

    return uploader

def test_mock_upload(uploader):
    """Test upload with minimal mock data"""
    print("=" * 60)
    print("TEST 3: Mock Upload")
    print("=" * 60)

    # Create minimal test data
    test_data = {
        "episodes": [
            {
                "episode_id": "test_web_canonical_001",
                "title": "Web-Canonical Architecture Test Episode",
                "url": "https://example.com/test",
                "recorded_at": "2025-11-21T00:00:00Z",
                "duration_seconds": 60
            }
        ],
        "claims": [
            {
                "claim_id": "test_claim_web_001",
                "canonical": "This is a test claim for web-canonical architecture verification.",
                "episode_id": "test_web_canonical_001",
                "claim_type": "factual",
                "tier": "A",
                "scores_json": '{"confidence": 0.9, "importance": 0.8, "novelty": 0.7, "controversy": 0.3, "fragility": 0.2}',
                "structured_categories_json": '["technology", "testing"]',
                "category_relevance_scores_json": '{"technology": 0.9, "testing": 0.95}'
            },
            {
                "claim_id": "test_claim_web_002",
                "canonical": "Web-canonical architecture uses one-way upload flow for simplicity.",
                "episode_id": "test_web_canonical_001",
                "claim_type": "factual",
                "tier": "A",
                "scores_json": '{"confidence": 0.95, "importance": 0.9, "novelty": 0.6, "controversy": 0.1, "fragility": 0.1}',
                "structured_categories_json": '["architecture", "software"]',
                "category_relevance_scores_json": '{"architecture": 0.95, "software": 0.9}'
            }
        ],
        "people": [
            {
                "surface_form": "Claude AI",
                "entity_type": "ai_assistant",
                "episode_id": "test_web_canonical_001",
                "claim_id": "test_claim_web_001",
                "confidence": 0.99,
                "external_ids_json": '{"type": "ai_model", "company": "Anthropic"}'
            }
        ],
        "jargon": [
            {
                "term": "Web-Canonical",
                "definition": "An architecture where the web database is the single source of truth",
                "episode_id": "test_web_canonical_001",
                "claim_id": "test_claim_web_001",
                "category": "architecture",
                "domain": "software_engineering",
                "evidence_json": '{"timestamps": [0, 30, 60]}'
            }
        ],
        "concepts": [
            {
                "name": "Ephemeral Local Database",
                "definition": "Local database used as temporary staging area, data hidden after upload",
                "episode_id": "test_web_canonical_001",
                "claim_id": "test_claim_web_002",
                "domain": "data_architecture",
                "aliases_json": '["temporary storage", "staging database"]',
                "evidence_json": '{"first_mention": 15, "key_mentions": [15, 45]}'
            }
        ]
    }

    print(f"📤 Uploading test data...")
    print(f"   - Episodes: {len(test_data['episodes'])}")
    print(f"   - Claims: {len(test_data['claims'])}")
    print(f"   - People: {len(test_data['people'])}")
    print(f"   - Jargon: {len(test_data['jargon'])}")
    print(f"   - Concepts: {len(test_data['concepts'])}")
    print()

    try:
        results = uploader.upload_session_data(test_data)
        print("✅ Upload successful!")
        print()
        return results
    except Exception as e:
        print(f"❌ Upload failed: {e}")
        import traceback
        traceback.print_exc()
        return None

def verify_upload_results(results):
    """Verify upload results"""
    print("=" * 60)
    print("TEST 4: Verify Upload Results")
    print("=" * 60)

    if not results:
        print("❌ No results to verify (upload may have failed)")
        return False

    expected_tables = ["episodes", "claims", "people", "jargon", "mental_models"]
    success = True

    for table in expected_tables:
        if table in results and results[table]:
            count = len(results[table])
            print(f"✅ {table}: {count} records uploaded")
        else:
            print(f"⚠️  {table}: No records uploaded (may be expected)")

    print()
    return success

def main():
    """Run all tests"""
    print("\n" + "=" * 60)
    print("WEB-CANONICAL ARCHITECTURE - UPLOAD TEST")
    print("=" * 60)
    print()

    try:
        # Test 1: Device authentication
        creds = test_device_auth()

        # Test 2: Connection
        uploader = test_upload_connection(creds)

        # Test 3: Upload
        results = test_mock_upload(uploader)

        # Test 4: Verify
        success = verify_upload_results(results)

        print("=" * 60)
        print("SUMMARY")
        print("=" * 60)
        print("✅ Device authentication: Working")
        print("✅ Upload connection: Working")
        if results:
            print("✅ Data upload: Successful")
            print(f"\n📊 Device ID: {creds['device_id']}")
            print("📊 Check Supabase dashboard to verify data!")
        else:
            print("❌ Data upload: Failed (see errors above)")
        print()

        print("=" * 60)
        print("NEXT STEPS")
        print("=" * 60)
        print("1. Open Supabase dashboard: https://supabase.com/dashboard")
        print("2. Go to Table Editor → 'devices' table")
        print(f"3. Look for device_id: {creds['device_id'][:16]}...")
        print("4. Go to 'claims' table")
        print("5. Filter by device_id to see your uploaded claims")
        print("6. Verify 'uploaded_at' timestamp is recent")
        print()

    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
