#!/usr/bin/env python3
"""
Fix .zshrc issues:
1. Remove stray 'fi' on line 74
2. Fix malformed OPENAI_API_KEY line 44
"""

from pathlib import Path

zshrc = Path.home() / ".zshrc"
lines = zshrc.read_text().splitlines()

fixed_lines = []
for i, line in enumerate(lines, 1):
    # Skip line 74 (the stray 'fi')
    if i == 74 and line.strip() == "fi":
        print(f"✅ Removed stray 'fi' from line {i}")
        continue

    # Fix line 44 (malformed OPENAI_API_KEY)
    if (
        i == 44
        and line.startswith("export OPENAI_API_KEY=")
        and "export OPENAI_API_KEY=" in line[20:]
    ):
        # This line has the key duplicated, keep only the second one
        parts = line.split('export OPENAI_API_KEY="', 1)
        if len(parts) == 2:
            fixed_line = 'export OPENAI_API_KEY="' + parts[1]
            fixed_lines.append(fixed_line)
            print(f"✅ Fixed malformed OPENAI_API_KEY on line {i}")
            continue

    fixed_lines.append(line)

# Write back with proper newline at end
zshrc.write_text("\n".join(fixed_lines) + "\n")

print(f"\n✅ Fixed ~/.zshrc")
print(f"   Total lines: {len(lines)} → {len(fixed_lines)}")
print(f"\n💾 Backup saved at: ~/.zshrc.backup.20251102_131758")
