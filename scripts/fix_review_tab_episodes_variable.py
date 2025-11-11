#!/usr/bin/env python3
"""
Fix all remaining 'episodes' variable references in review_tab_system2.py
These should be 'sources' after the Episode → MediaSource migration.
"""

from pathlib import Path

file_path = Path("src/knowledge_system/gui/tabs/review_tab_system2.py")
content = file_path.read_text()

fixes = []

# Fix 1: Line 261 - episodes variable in list comprehension
old = "                    self.episodes = {ep.source_id: ep for ep in episodes}"
new = "                    self.sources = {ep.source_id: ep for ep in sources}"
if old in content:
    content = content.replace(old, new)
    fixes.append("Line 261: self.episodes → self.sources, episodes → sources")

# Fix 2: Line 264 - episodes initialization
old = "                    self.episodes = {}"
new = "                    self.sources = {}"
if old in content:
    content = content.replace(old, new)
    fixes.append("Line 264: self.episodes = {} → self.sources = {}")

# Fix 3: Line 282 - episodes initialization in error handler
old = "            self.episodes = {}"
new = "            self.sources = {}"
if old in content:
    content = content.replace(old, new)
    fixes.append("Line 282: self.episodes = {} → self.sources = {}")

# Fix 4: Line 317 - episodes.get() in data method
old = "                episode = self.episodes.get(claim.source_id)"
new = "                episode = self.sources.get(claim.source_id)"
if old in content:
    content = content.replace(old, new)
    fixes.append("Line 317: self.episodes.get() → self.sources.get()")

# Fix 5: Line 694 - for episode in episodes loop
old = "                for episode in episodes:"
new = "                for episode in sources:"
if old in content:
    content = content.replace(old, new)
    fixes.append("Line 694: for episode in episodes → for episode in sources")

# Fix 6: Line 863 - episodes.get() in export
old = "                        episode = self.model.episodes.get(claim.source_id)"
new = "                        episode = self.model.sources.get(claim.source_id)"
count = content.count(old)
if old in content:
    content = content.replace(old, new)
    fixes.append(
        f"Lines 863, 914, 1058: self.model.episodes.get() → self.model.sources.get() ({count} occurrences)"
    )

# Fix 7: Line 966 - episodes.items() in export
old = "                for source_id, episode in self.model.episodes.items():"
new = "                for source_id, episode in self.model.sources.items():"
if old in content:
    content = content.replace(old, new)
    fixes.append("Line 966: self.model.episodes.items() → self.model.sources.items()")

# Fix 8: Line 967 - export_data["episodes"] key
old = '                    export_data["episodes"].append('
new = '                    export_data["sources"].append('
if old in content:
    content = content.replace(old, new)
    fixes.append('Line 967: export_data["episodes"] → export_data["sources"]')

# Fix 9: Line 963 - export_data initialization
old = '                export_data = {"episodes": [], "claims": []}'
new = '                export_data = {"sources": [], "claims": []}'
if old in content:
    content = content.replace(old, new)
    fixes.append('Line 963: export_data["episodes"] → export_data["sources"]')

# Fix 10: Line 1009 - success message
old = "                    f\"Successfully exported {len(self.model.claims)} claims and {len(export_data['episodes'])} episodes to {filename}\","
new = "                    f\"Successfully exported {len(self.model.claims)} claims and {len(export_data['sources'])} sources to {filename}\","
if old in content:
    content = content.replace(old, new)
    fixes.append('Line 1009: export message "episodes" → "sources"')

# Fix 11: Line 1101 - session_data initialization
old = '                "episodes": [],'
new = '                "sources": [],'
if old in content:
    content = content.replace(old, new)
    fixes.append('Line 1101: session_data["episodes"] → session_data["sources"]')

# Fix 12: Line 1116 - session_data append
old = '                    session_data["episodes"].append(claim_upload.episode_data)'
new = '                    session_data["sources"].append(claim_upload.episode_data)'
if old in content:
    content = content.replace(old, new)
    fixes.append('Line 1116: session_data["episodes"] → session_data["sources"]')

file_path.write_text(content)

print("✅ Fixed review_tab_system2.py")
print(f"\n📝 Applied {len(fixes)} fixes:")
for fix in fixes:
    print(f"   • {fix}")
