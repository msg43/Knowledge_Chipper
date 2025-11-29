#!/usr/bin/env python3
"""Quick script to check what tables exist in GetReceipts Supabase"""

import os
from supabase import create_client

# Get env from GetReceipts .env.local
supabase_url = "https://sdkxuiqcwlmbpjvjdpkj.supabase.co"
# Using anon key - just for checking table existence
supabase_anon = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InNka3h1aXFjd2xtYnBqdmpkcGtqIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTU4MTU3MzQsImV4cCI6MjA3MTM5MTczNH0.VoP6yX3GwyVjylgioTGchQYwPQ_K2xQFdHP5ani0vts"

supabase = create_client(supabase_url, supabase_anon)

print("🔍 Checking GetReceipts Supabase Schema\n")

# Try to query each table
tables = ["devices", "episodes", "claims", "people", "jargon", "concepts", "milestones", "evidence_spans", "relations"]

for table in tables:
    try:
        # Try to select 0 rows (just to check if table exists)
        result = supabase.table(table).select("*").limit(0).execute()
        print(f"✅ {table:20} - EXISTS")
    except Exception as e:
        error_msg = str(e)
        if "does not exist" in error_msg or "not found" in error_msg:
            print(f"❌ {table:20} - DOES NOT EXIST")
        else:
            print(f"⚠️  {table:20} - ERROR: {error_msg[:50]}...")

print("\n" + "="*60)
print("DIAGNOSIS:")
print("="*60)
print("""
If 'devices' exists but 'episodes', 'claims', etc. don't exist:
  → Your GetReceipts database hasn't been set up yet with the main schema
  → You need to run the main schema migration first

If 'episodes', 'claims' exist but don't have 'device_id' columns:
  → The ALTER TABLE statements in the migration failed
  → Re-run the migration (it's safe - uses IF NOT EXISTS)

If everything exists:
  → Schema cache issue - wait a few minutes and try again
""")
