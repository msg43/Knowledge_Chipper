#!/usr/bin/env python3
"""
Upload ALL data from local SQLite database to Supabase.

Pure 1:1 schema match - no transformations, no mappings.
Sends data exactly as stored in SQLite to matching Supabase tables.

Tables uploaded:
- media_sources
- claims
- evidence_spans
- jargon_terms
- claim_jargon (junction)
- people
- claim_people (junction)
- concepts
- claim_concepts (junction)

Usage:
    python3 upload_all_claims.py
"""

import json
import sqlite3
import sys
from pathlib import Path
from datetime import datetime

import requests

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from knowledge_system.services.device_auth import get_device_auth


def get_database_path() -> Path:
    """Get path to local Knowledge_Chipper database."""
    if sys.platform == "darwin":  # macOS
        app_support = Path.home() / "Library" / "Application Support" / "Knowledge Chipper"
    elif sys.platform == "win32":  # Windows
        import os
        app_support = Path(os.environ.get("APPDATA", Path.home())) / "Knowledge Chipper"
    else:  # Linux
        app_support = Path.home() / ".local" / "share" / "Knowledge Chipper"
    
    return app_support / "knowledge_system.db"


def row_to_dict(row: sqlite3.Row) -> dict:
    """Convert SQLite row to dict, handling datetime conversion."""
    d = dict(row)
    # Convert datetime objects to ISO strings
    for key, value in d.items():
        if isinstance(value, datetime):
            d[key] = value.isoformat()
    return d


def read_all_data(db_path: Path) -> dict:
    """Read all data from SQLite using exact table/column names."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    data = {
        "media_sources": [],
        "claims": [],
        "evidence_spans": [],
        "jargon_terms": [],
        "claim_jargon": [],
        "people": [],
        "claim_people": [],
        "concepts": [],
        "claim_concepts": []
    }
    
    # 1. Read media_sources (exact SQLite table)
    print("\n1. Reading media_sources...")
    cursor.execute("SELECT * FROM media_sources")
    for row in cursor.fetchall():
        d = row_to_dict(row)
        # Cast duration_seconds to int (schema expects INTEGER)
        if d.get("duration_seconds") is not None:
            d["duration_seconds"] = int(float(d["duration_seconds"]))
        data["media_sources"].append(d)
    print(f"   Found {len(data['media_sources'])} media_sources")
    
    # 2. Read claims (exact SQLite table)
    print("\n2. Reading claims...")
    cursor.execute("SELECT * FROM claims")
    for row in cursor.fetchall():
        data["claims"].append(row_to_dict(row))
    print(f"   Found {len(data['claims'])} claims")
    
    # 3. Read evidence_spans (exact SQLite table)
    print("\n3. Reading evidence_spans...")
    cursor.execute("SELECT * FROM evidence_spans")
    for row in cursor.fetchall():
        data["evidence_spans"].append(row_to_dict(row))
    print(f"   Found {len(data['evidence_spans'])} evidence_spans")
    
    # 4. Read jargon_terms (exact SQLite table)
    print("\n4. Reading jargon_terms...")
    cursor.execute("SELECT * FROM jargon_terms")
    for row in cursor.fetchall():
        data["jargon_terms"].append(row_to_dict(row))
    print(f"   Found {len(data['jargon_terms'])} jargon_terms")
    
    # 5. Read claim_jargon junction table
    print("\n5. Reading claim_jargon...")
    cursor.execute("SELECT * FROM claim_jargon")
    for row in cursor.fetchall():
        data["claim_jargon"].append(row_to_dict(row))
    print(f"   Found {len(data['claim_jargon'])} claim_jargon links")
    
    # 6. Read people (exact SQLite table)
    print("\n6. Reading people...")
    cursor.execute("SELECT * FROM people")
    for row in cursor.fetchall():
        data["people"].append(row_to_dict(row))
    print(f"   Found {len(data['people'])} people")
    
    # 7. Read claim_people junction table
    print("\n7. Reading claim_people...")
    cursor.execute("SELECT * FROM claim_people")
    for row in cursor.fetchall():
        data["claim_people"].append(row_to_dict(row))
    print(f"   Found {len(data['claim_people'])} claim_people links")
    
    # 8. Read concepts (exact SQLite table)
    print("\n8. Reading concepts...")
    cursor.execute("SELECT * FROM concepts")
    for row in cursor.fetchall():
        data["concepts"].append(row_to_dict(row))
    print(f"   Found {len(data['concepts'])} concepts")
    
    # 9. Read claim_concepts junction table
    print("\n9. Reading claim_concepts...")
    cursor.execute("SELECT * FROM claim_concepts")
    for row in cursor.fetchall():
        data["claim_concepts"].append(row_to_dict(row))
    print(f"   Found {len(data['claim_concepts'])} claim_concepts links")
    
    conn.close()
    return data


def upload_data(data: dict) -> dict:
    """Upload data directly to GetReceipts API."""
    print("\n" + "=" * 60)
    print("UPLOADING TO SUPABASE")
    print("=" * 60)
    
    # Count records
    total = sum(len(v) for v in data.values())
    print(f"\nTotal records to upload: {total}")
    for table, records in data.items():
        if records:
            print(f"  {table}: {len(records)}")
    
    if total == 0:
        print("\nNo data to upload!")
        return {}
    
    # Get device credentials for authentication
    auth = get_device_auth()
    creds = auth.get_credentials()
    print(f"\nDevice ID: {creds['device_id'][:16]}...")
    
    # Upload via HTTP API
    api_url = "https://getreceipts.org/api/knowledge-chipper/upload"
    
    print(f"\nUploading to: {api_url}")
    
    try:
        response = requests.post(
            api_url,
            headers={
                "Content-Type": "application/json",
                "X-Device-ID": creds["device_id"],
                "X-Device-Key": creds["device_key"]
            },
            json=data,
            timeout=120
        )
        
        if response.status_code in (200, 201, 207):
            result = response.json()
            return result
        else:
            error_msg = response.text
            try:
                error_data = response.json()
                error_msg = error_data.get("message", response.text)
            except:
                pass
            print(f"\nUpload failed ({response.status_code}): {error_msg}")
            return {"error": error_msg}
            
    except requests.exceptions.Timeout:
        print("\nUpload timed out")
        return {"error": "timeout"}
    except requests.exceptions.ConnectionError as e:
        print(f"\nConnection error: {e}")
        return {"error": str(e)}
    except Exception as e:
        print(f"\nUpload failed: {e}")
        return {"error": str(e)}


def main():
    """Main entry point."""
    print("\n" + "=" * 60)
    print("UPLOAD ALL DATA TO SUPABASE")
    print("Pure 1:1 SQLite Schema Match")
    print("=" * 60)
    
    # Find database
    db_path = get_database_path()
    print(f"\nDatabase: {db_path}")
    
    if not db_path.exists():
        print(f"Database not found at {db_path}")
        sys.exit(1)
    
    # Read all data
    print("\n" + "=" * 60)
    print("READING LOCAL DATABASE")
    print("=" * 60)
    
    data = read_all_data(db_path)
    
    # Check if there's data
    total = sum(len(v) for v in data.values())
    if total == 0:
        print("\nNo data found in local database!")
        return
    
    # Upload
    results = upload_data(data)
    
    # Print results
    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)
    
    if results.get("success"):
        print(f"\n{results.get('message')}")
        print(f"\nUploaded:")
        uploaded = results.get("uploaded", {})
        for table, count in uploaded.items():
            if table != "errors" and count:
                print(f"  {table}: {count}")
    elif results.get("error"):
        print(f"\nError: {results.get('error')}")
    else:
        print(f"\n{results.get('message', 'Unknown result')}")
        if results.get("uploaded", {}).get("errors"):
            print("\nErrors:")
            for err in results["uploaded"]["errors"]:
                print(f"  - {err}")
    
    print("\n" + "=" * 60)
    print("DONE")
    print("=" * 60)


if __name__ == "__main__":
    main()
