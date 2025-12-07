#!/usr/bin/env python3
"""
Populate claim_people junction table by matching people names in claim text.

This script:
1. Reads all people from the people table
2. Reads all claims from the claims table
3. For each claim, checks if any person name appears in the claim's canonical text
4. Creates claim_people links where matches are found

Run after upload_all_claims.py to ensure people edges appear in the graph.
"""

import sqlite3
import re
import sys
from pathlib import Path
from datetime import datetime


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


def populate_claim_people(db_path: Path) -> int:
    """
    Populate claim_people by matching person names in claim text.
    
    Returns: Number of links created
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Get all people
    cursor.execute("SELECT person_id, name, normalized_name FROM people")
    people = cursor.fetchall()
    print(f"Found {len(people)} people")
    
    # Get all claims
    cursor.execute("SELECT claim_id, canonical FROM claims")
    claims = cursor.fetchall()
    print(f"Found {len(claims)} claims")
    
    # Build a list of (pattern, person_id, name) tuples for matching
    # Use word boundaries to avoid partial matches
    person_patterns = []
    for person in people:
        name = person['name']
        person_id = person['person_id']
        
        # Create patterns for full name and variations
        patterns_for_person = []
        
        # Full name pattern
        escaped_name = re.escape(name)
        patterns_for_person.append(re.compile(r'\b' + escaped_name + r'\b', re.IGNORECASE))
        
        # Also try last name only for multi-word names (e.g., "Trump" from "Donald Trump")
        name_parts = name.split()
        if len(name_parts) > 1:
            last_name = name_parts[-1]
            if len(last_name) > 3:  # Avoid short names like "Xi"
                escaped_last = re.escape(last_name)
                patterns_for_person.append(re.compile(r'\b' + escaped_last + r'\b', re.IGNORECASE))
        
        # For each pattern, add to the list
        for pattern in patterns_for_person:
            person_patterns.append((pattern, person_id, name))
    
    # Track created links
    links_created = 0
    now = datetime.utcnow().isoformat()
    
    # For each claim, check for person mentions
    for claim in claims:
        claim_id = claim['claim_id']
        canonical = claim['canonical'] or ""
        
        for pattern, person_id, person_name in person_patterns:
            if pattern.search(canonical):
                # Check if link already exists
                cursor.execute(
                    "SELECT 1 FROM claim_people WHERE claim_id = ? AND person_id = ?",
                    (claim_id, person_id)
                )
                if not cursor.fetchone():
                    # Create link
                    cursor.execute(
                        """
                        INSERT INTO claim_people (claim_id, person_id, role, created_at)
                        VALUES (?, ?, 'mentioned', ?)
                        """,
                        (claim_id, person_id, now)
                    )
                    links_created += 1
                    print(f"  Linked: {claim_id[:30]}... -> {person_name}")
    
    conn.commit()
    conn.close()
    
    return links_created


def main():
    """Main entry point."""
    print("\n" + "=" * 60)
    print("POPULATE CLAIM_PEOPLE")
    print("Match people names in claim text")
    print("=" * 60)
    
    db_path = get_database_path()
    print(f"\nDatabase: {db_path}")
    
    if not db_path.exists():
        print(f"Database not found at {db_path}")
        sys.exit(1)
    
    links = populate_claim_people(db_path)
    
    print("\n" + "=" * 60)
    print(f"CREATED {links} CLAIM-PERSON LINKS")
    print("=" * 60)
    print("\nRun upload_all_claims.py again to upload the new links!")


if __name__ == "__main__":
    main()
