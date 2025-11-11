#!/usr/bin/env python3
"""
Fix final remaining 'episodes' references in review_tab_system2.py
"""

from pathlib import Path

file_path = Path("src/knowledge_system/gui/tabs/review_tab_system2.py")
content = file_path.read_text()

fixes = []

# Fix 1: Line 258 - comment
old = "                # Load episodes"
new = "                # Load sources"
if old in content:
    content = content.replace(old, new)
    fixes.append("Line 258: comment 'Load episodes' → 'Load sources'")

# Fix 2: Line 263 - log message
old = '                    logger.warning(f"Could not load episodes: {e}")'
new = '                    logger.warning(f"Could not load sources: {e}")'
if old in content:
    content = content.replace(old, new)
    fixes.append("Line 263: log message 'episodes' → 'sources'")

# Fix 3: Line 697 - log message
old = '            logger.warning(f"Could not populate episodes dropdown: {e}")'
new = '            logger.warning(f"Could not populate sources dropdown: {e}")'
if old in content:
    content = content.replace(old, new)
    fixes.append("Line 697: log message 'episodes' → 'sources'")

# Fix 4: Line 965 - comment
old = "                # Export episodes"
new = "                # Export sources"
if old in content:
    content = content.replace(old, new)
    fixes.append("Line 965: comment 'Export episodes' → 'Export sources'")

# Fix 5: Line 1058 - the one that was missed before
old = "                episode = self.model.episodes.get(claim.source_id)"
new = "                episode = self.model.sources.get(claim.source_id)"
if old in content:
    content = content.replace(old, new)
    fixes.append("Line 1058: self.model.episodes.get() → self.model.sources.get()")

file_path.write_text(content)

print("✅ Fixed final episodes references in review_tab_system2.py")
print(f"\n📝 Applied {len(fixes)} fixes:")
for fix in fixes:
    print(f"   • {fix}")
