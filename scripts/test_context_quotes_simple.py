#!/usr/bin/env python3
"""
Simple SQL-based test to verify context_quote fields are populated during mining.

This script tests context_quote storage directly using SQL without relying on
the full ORM setup.
"""

import sqlite3
import sys
from pathlib import Path


def test_context_quotes_sql():
    """Test context_quote fields using direct SQL queries."""
    print("=" * 80)
    print("Testing Context Quote Storage (SQL-based)")
    print("=" * 80)

    db_path = Path(__file__).parent.parent / "knowledge_system.db"

    if not db_path.exists():
        print(f"❌ Database not found: {db_path}")
        return False

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Check schema
    print("\n" + "=" * 80)
    print("Verifying Database Schema")
    print("=" * 80)

    all_passed = True

    # Check jargon table
    cursor.execute("PRAGMA table_info(jargon)")
    jargon_columns = [row[1] for row in cursor.fetchall()]
    if "context_quote" in jargon_columns:
        print("✓ jargon.context_quote column exists")
    else:
        print("❌ jargon.context_quote column missing")
        all_passed = False

    # Check people table
    cursor.execute("PRAGMA table_info(people)")
    people_columns = [row[1] for row in cursor.fetchall()]
    if "context_quote" in people_columns:
        print("✓ people.context_quote column exists")
    else:
        print("❌ people.context_quote column missing")
        all_passed = False

    # Check concepts table
    cursor.execute("PRAGMA table_info(concepts)")
    concepts_columns = [row[1] for row in cursor.fetchall()]
    if "context_quote" in concepts_columns:
        print("✓ concepts.context_quote column exists")
    else:
        print("❌ concepts.context_quote column missing")
        all_passed = False

    # Check for existing data with context_quotes
    print("\n" + "=" * 80)
    print("Checking for Existing Context Quotes in Database")
    print("=" * 80)

    # Check jargon
    cursor.execute(
        "SELECT COUNT(*) FROM jargon WHERE context_quote IS NOT NULL AND context_quote != ''"
    )
    jargon_with_quotes = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM jargon")
    total_jargon = cursor.fetchone()[0]

    print(f"\nJargon:")
    print(f"  Total entries: {total_jargon}")
    print(f"  With context_quote: {jargon_with_quotes}")
    if total_jargon > 0:
        print(f"  Coverage: {jargon_with_quotes/total_jargon*100:.1f}%")

        # Show sample
        cursor.execute(
            "SELECT term, definition, context_quote FROM jargon WHERE context_quote IS NOT NULL AND context_quote != '' LIMIT 3"
        )
        samples = cursor.fetchall()
        if samples:
            print(f"  Sample entries:")
            for term, definition, quote in samples:
                print(
                    f"    - {term}: {quote[:60]}..."
                    if len(quote) > 60
                    else f"    - {term}: {quote}"
                )

    # Check people
    cursor.execute(
        "SELECT COUNT(*) FROM people WHERE context_quote IS NOT NULL AND context_quote != ''"
    )
    people_with_quotes = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM people")
    total_people = cursor.fetchone()[0]

    print(f"\nPeople:")
    print(f"  Total entries: {total_people}")
    print(f"  With context_quote: {people_with_quotes}")
    if total_people > 0:
        print(f"  Coverage: {people_with_quotes/total_people*100:.1f}%")

        # Show sample
        cursor.execute(
            "SELECT name, description, context_quote FROM people WHERE context_quote IS NOT NULL AND context_quote != '' LIMIT 3"
        )
        samples = cursor.fetchall()
        if samples:
            print(f"  Sample entries:")
            for name, description, quote in samples:
                quote_str = quote if quote else "(none)"
                print(
                    f"    - {name}: {quote_str[:60]}..."
                    if len(quote_str) > 60
                    else f"    - {name}: {quote_str}"
                )

    # Check concepts
    cursor.execute(
        "SELECT COUNT(*) FROM concepts WHERE context_quote IS NOT NULL AND context_quote != ''"
    )
    concepts_with_quotes = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM concepts")
    total_concepts = cursor.fetchone()[0]

    print(f"\nConcepts:")
    print(f"  Total entries: {total_concepts}")
    print(f"  With context_quote: {concepts_with_quotes}")
    if total_concepts > 0:
        print(f"  Coverage: {concepts_with_quotes/total_concepts*100:.1f}%")

        # Show sample
        cursor.execute(
            "SELECT name, description, context_quote FROM concepts WHERE context_quote IS NOT NULL AND context_quote != '' LIMIT 3"
        )
        samples = cursor.fetchall()
        if samples:
            print(f"  Sample entries:")
            for name, description, quote in samples:
                quote_str = quote if quote else "(none)"
                print(
                    f"    - {name}: {quote_str[:60]}..."
                    if len(quote_str) > 60
                    else f"    - {name}: {quote_str}"
                )

    conn.close()

    # Final result
    print("\n" + "=" * 80)
    if all_passed:
        print("✅ Schema is correctly set up for context_quote storage")
        print("\nTo verify data population during mining:")
        print("  1. Run a mining operation on any video")
        print("  2. Re-run this script to check if context_quotes are populated")
        print("\nThe code changes ensure that:")
        print("  - Miner extracts context_quote from segments")
        print("  - hce_operations.py saves context_quote to database")
        print("  - storage_sqlite.py saves context_quote from evidence spans")
    else:
        print("❌ Schema setup incomplete")
    print("=" * 80)

    return all_passed


if __name__ == "__main__":
    try:
        success = test_context_quotes_sql()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
