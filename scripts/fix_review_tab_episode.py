#!/usr/bin/env python3
"""
Fix review_tab_system2.py to remove Episode references.
Episode table was removed in ID unification - use MediaSource instead.
"""

file_path = "src/knowledge_system/gui/tabs/review_tab_system2.py"

# Read the file
with open(file_path) as f:
    content = f.read()

# Replace imports
content = content.replace(
    "from ...database.models import Claim, Episode",
    "from ...database.models import Claim, MediaSource",
)

# Replace Episode type hints and variables
content = content.replace(
    "self.episodes: dict[str, Episode] = {}",
    "self.sources: dict[str, MediaSource] = {}",
)

# Replace Episode queries
content = content.replace(
    "episodes = session.query(Episode).all()",
    "sources = session.query(MediaSource).all()",
)

# Replace Episode references in column handling
content = content.replace('if col_name == "Episode":', 'if col_name == "Source":')

content = content.replace(
    'if col_name not in ["Episode", "Modified"]:',
    'if col_name not in ["Source", "Modified"]:',
)

# Replace column definition
content = content.replace('("Episode", "episode_title"),', '("Source", "title"),')

# Replace comment
content = content.replace(
    "# Episode and Modified columns are not editable",
    "# Source and Modified columns are not editable",
)

# Write back
with open(file_path, "w") as f:
    f.write(content)

print(f"✅ Fixed {file_path}")
print("   - Replaced Episode with MediaSource")
print("   - Updated column references")
print("   - Updated queries")
