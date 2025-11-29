#!/usr/bin/env python3
"""
Test script to upload data directly from Knowledge_Chipper database to GetReceipts

This script:
1. Extracts data from Knowledge_Chipper SQLite database
2. Converts to GetReceipts API format
3. Uploads via HTTP API with device authentication

Usage:
    python3 test_db_upload.py [--source-id SOURCE_ID] [--limit N]
"""

import sys
import argparse
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from knowledge_system.services.claims_upload_service import ClaimsUploadService
from knowledge_chipper_oauth.getreceipts_uploader import GetReceiptsUploader
from knowledge_system.logger import get_logger

logger = get_logger(__name__)


def convert_claims_to_session_data(claims_data):
    """Convert ClaimUploadData objects to GetReceipts session_data format."""
    session_data = {
        "episodes": [],
        "claims": [],
        "people": [],
        "concepts": [],
        "jargon": [],
        "questions": [],
    }
    
    seen_episodes = set()
    
    for claim in claims_data:
        source_id = claim.source_id
        
        # Add episode data (if not already added)
        if claim.episode_data and source_id not in seen_episodes:
            episode_data = dict(claim.episode_data)
            # Ensure source_id is set
            if 'source_id' not in episode_data:
                episode_data['source_id'] = source_id
            session_data["episodes"].append(episode_data)
            seen_episodes.add(source_id)
        
        # Add claim data
        claim_dict = {
            "source_id": source_id,
            "canonical": claim.canonical,
            "claim_type": claim.claim_type,
            "tier": claim.tier,
            "scores_json": claim.scores_json,
        }
        session_data["claims"].append(claim_dict)
        
        # Add associated data
        # People
        for person in claim.people:
            person_dict = {
                "source_id": source_id,
                "surface": person.get("surface"),
                "normalized": person.get("normalized"),
                "role": person.get("role"),
                "entity_type": person.get("entity_type", "person"),
            }
            session_data["people"].append(person_dict)
        
        # Concepts
        for concept in claim.concepts:
            concept_dict = {
                "source_id": source_id,
                "name": concept.get("name"),
                "description": concept.get("definition"),
            }
            session_data["concepts"].append(concept_dict)
        
        # Jargon
        for jargon in claim.jargon:
            jargon_dict = {
                "source_id": source_id,
                "term": jargon.get("term"),
                "definition": jargon.get("definition"),
            }
            session_data["jargon"].append(jargon_dict)
    
    return session_data


def main():
    parser = argparse.ArgumentParser(description="Upload Knowledge_Chipper DB data to GetReceipts")
    parser.add_argument("--source-id", help="Filter by specific source_id")
    parser.add_argument("--limit", type=int, help="Limit number of claims to upload")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be uploaded without uploading")
    args = parser.parse_args()
    
    print("=" * 60)
    print("KNOWLEDGE_CHIPPER → GETRECEIPTS UPLOAD TEST")
    print("=" * 60)
    print()
    
    # Initialize services
    print("📂 Initializing database connection...")
    upload_service = ClaimsUploadService()
    
    # Validate database
    is_valid, message = upload_service.is_database_valid()
    if not is_valid:
        print(f"❌ Database validation failed: {message}")
        return 1
    print(f"✅ Database valid: {upload_service.db_path}")
    print()
    
    # Get unuploaded claims
    print("🔍 Finding unuploaded claims...")
    claims = upload_service.get_unuploaded_claims()
    
    if args.source_id:
        claims = [c for c in claims if c.source_id == args.source_id]
        print(f"   Filtered to source_id: {args.source_id}")
    
    if args.limit:
        claims = claims[:args.limit]
        print(f"   Limited to {args.limit} claims")
    
    print(f"✅ Found {len(claims)} claims to upload")
    print()
    
    if not claims:
        print("⚠️  No claims to upload")
        return 0
    
    # Convert to session data format
    print("🔄 Converting to GetReceipts format...")
    session_data = convert_claims_to_session_data(claims)
    
    # Print summary
    print("\n📊 Data Summary:")
    print(f"   Episodes: {len(session_data['episodes'])}")
    print(f"   Claims: {len(session_data['claims'])}")
    print(f"   People: {len(session_data['people'])}")
    print(f"   Concepts: {len(session_data['concepts'])}")
    print(f"   Jargon: {len(session_data['jargon'])}")
    print()
    
    if args.dry_run:
        print("🔍 DRY RUN - Would upload:")
        print(f"   {len(session_data['claims'])} claims")
        print("   (Use without --dry-run to actually upload)")
        return 0
    
    # Initialize uploader
    print("🔐 Initializing uploader...")
    uploader = GetReceiptsUploader()
    
    if not uploader.is_enabled():
        print("❌ Auto-upload is disabled. Enable in Settings to upload.")
        return 1
    
    print(f"✅ Using device: {uploader.credentials['device_id'][:16]}...")
    print()
    
    # Upload
    print("🚀 Starting upload...")
    try:
        results = uploader.upload_session_data(session_data)
        
        print("\n✅ Upload completed!")
        print(f"\n📊 Results:")
        if "uploaded" in results:
            uploaded = results["uploaded"]
            print(f"   Episodes: {uploaded.get('episodes', {}).get('new', 0)} new, {uploaded.get('episodes', {}).get('merged', 0)} merged")
            print(f"   Claims: {uploaded.get('claims', {}).get('new', 0)} new, {uploaded.get('claims', {}).get('merged', 0)} merged")
            print(f"   People: {uploaded.get('people', {}).get('new', 0)} new, {uploaded.get('people', {}).get('merged', 0)} merged")
            print(f"   Concepts: {uploaded.get('concepts', {}).get('new', 0)} new, {uploaded.get('concepts', {}).get('merged', 0)} merged")
            print(f"   Jargon: {uploaded.get('jargon', {}).get('new', 0)} new, {uploaded.get('jargon', {}).get('merged', 0)} merged")
        
        if results.get("errors"):
            print(f"\n⚠️  Errors: {len(results['errors'])}")
            for error in results["errors"][:5]:
                print(f"   - {error}")
        
        # Mark claims as uploaded
        if results.get("success"):
            claim_ids = [(c.source_id, c.claim_id) for c in claims]
            upload_service.mark_claims_uploaded(claim_ids)
            print(f"\n✅ Marked {len(claim_ids)} claims as uploaded in local DB")
        
        return 0
        
    except Exception as e:
        print(f"\n❌ Upload failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())


