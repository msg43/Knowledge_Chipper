#!/usr/bin/env python3
"""Quick script to fix indentation in diarization.py"""

file_path = "src/knowledge_system/processors/diarization.py"

# Read the file
with open(file_path, 'r') as f:
    lines = f.readlines()

# Fix indentation for lines 311-358 (0-indexed, so 310-357)
for i in range(310, 358):
    if i < len(lines) and lines[i].startswith("                            "):
        # Remove 4 spaces from the beginning
        lines[i] = lines[i][4:]

# Write back
with open(file_path, 'w') as f:
    f.writelines(lines)

print("Indentation fixed!")
