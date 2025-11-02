#!/usr/bin/env python3
"""Add source_id to YAML frontmatter in audio_processor.py"""

import re

file_path = "src/knowledge_system/processors/audio_processor.py"

# Read the file
with open(file_path, 'r') as f:
    content = f.read()

# Find the section to replace
old_pattern = r'''        # YAML frontmatter
        lines\.append\("---"\)

        # Determine source type
        source_type = "Local Audio"  # Default
        if source_metadata is not None:'''

new_text = '''        # YAML frontmatter
        lines.append("---")

        # Add source_id FIRST (critical for ID extraction by Process Tab)
        source_id = None
        if source_metadata and source_metadata.get("source_id"):
            source_id = source_metadata["source_id"]
        
        if source_id:
            lines.append(f'source_id: "{source_id}"')

        # Determine source type
        source_type = "Local Audio"  # Default
        if source_metadata is not None:'''

# Replace
if old_pattern in content.replace('\n', ' ').replace('  ', ' '):
    print("❌ Pattern matching with regex is complex, using line-based approach")
    
# Use line-based approach
lines = content.split('\n')
new_lines = []
i = 0
while i < len(lines):
    if (i + 4 < len(lines) and
        '# YAML frontmatter' in lines[i] and
        'lines.append("---")' in lines[i+1] and
        '# Determine source type' in lines[i+3] and
        'source_type = "Local Audio"' in lines[i+4]):
        
        # Found the section, insert new code
        new_lines.append(lines[i])  # # YAML frontmatter
        new_lines.append(lines[i+1])  # lines.append("---")
        new_lines.append(lines[i+2])  # blank line
        new_lines.append('        # Add source_id FIRST (critical for ID extraction by Process Tab)')
        new_lines.append('        source_id = None')
        new_lines.append('        if source_metadata and source_metadata.get("source_id"):')
        new_lines.append('            source_id = source_metadata["source_id"]')
        new_lines.append('        ')
        new_lines.append('        if source_id:')
        new_lines.append('            lines.append(f\'source_id: "{source_id}"\')') 
        new_lines.append('')
        new_lines.append(lines[i+3])  # # Determine source type
        i += 5
        print("✅ Added source_id to YAML frontmatter")
    else:
        new_lines.append(lines[i])
        i += 1

# Write back
with open(file_path, 'w') as f:
    f.write('\n'.join(new_lines))

print(f"✅ Updated {file_path}")

