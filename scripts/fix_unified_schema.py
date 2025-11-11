#!/usr/bin/env python3
"""
Fix duplicate source_id in unified_schema.sql
"""

from pathlib import Path

schema_file = Path("src/knowledge_system/database/migrations/unified_schema.sql")
content = schema_file.read_text()

# Fix the duplicate source_id declaration (lines 11-12)
# The second one should probably be episode_id or just removed
old_text = """-- Episodes table (namespaced for HCE)
CREATE TABLE IF NOT EXISTS hce_episodes (
  source_id TEXT PRIMARY KEY,
  source_id TEXT,
  title TEXT NOT NULL,"""

new_text = """-- Episodes table (namespaced for HCE)
CREATE TABLE IF NOT EXISTS hce_episodes (
  source_id TEXT PRIMARY KEY,
  title TEXT NOT NULL,"""

content = content.replace(old_text, new_text)
schema_file.write_text(content)

print("✅ Fixed duplicate source_id in unified_schema.sql")
