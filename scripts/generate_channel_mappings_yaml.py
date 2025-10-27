#!/usr/bin/env python3
"""
Generate Channel Mappings YAML from Podcast List

Converts the 300+ podcast-to-host mappings into YAML format for immediate use.
This provides instant speaker attribution for popular podcasts.

Usage:
    python scripts/generate_channel_mappings_yaml.py
"""

import sys
from pathlib import Path

# Import the mappings from seed_podcast_mappings.py
sys.path.insert(0, str(Path(__file__).parent))
from seed_podcast_mappings import PODCAST_MAPPINGS


def generate_partial_names(host_name):
    """Generate common partial name variations for a host."""
    partial_names = []

    # Split name into parts
    parts = (
        host_name.replace("Dr. ", "").replace("Mr. ", "").replace("Ms. ", "").split()
    )

    if len(parts) >= 2:
        # Add first name
        partial_names.append(parts[0])
        # Add last name
        partial_names.append(parts[-1])
        # Add first + last initial (e.g., "Andrew H.")
        if len(parts) >= 2:
            partial_names.append(f"{parts[0]} {parts[-1][0]}.")
    elif len(parts) == 1:
        # Single name (e.g., "Questlove")
        partial_names.append(parts[0])

    # Remove duplicates while preserving order
    seen = set()
    unique_partials = []
    for name in partial_names:
        if name.lower() not in seen:
            seen.add(name.lower())
            unique_partials.append(name)

    return unique_partials[:3]  # Limit to 3 variations


def generate_yaml():
    """Generate YAML configuration from podcast mappings."""

    yaml_lines = [
        "# Channel-based speaker mappings",
        "# Auto-generated from 300+ popular podcasts",
        "# Maps YouTube channels to their regular hosts/speakers",
        "channel_mappings:",
    ]

    for channel_name, host_name in PODCAST_MAPPINGS:
        partial_names = generate_partial_names(host_name)

        yaml_lines.append(f'  "{channel_name}":')
        yaml_lines.append("    hosts:")
        yaml_lines.append(f'      - full_name: "{host_name}"')

        if partial_names:
            partial_names_str = ", ".join(f'"{name}"' for name in partial_names)
            yaml_lines.append(f"        partial_names: [{partial_names_str}]")
        else:
            yaml_lines.append("        partial_names: []")

        yaml_lines.append('        role: "host"')
        yaml_lines.append("")  # Blank line between entries

    return "\n".join(yaml_lines)


def main():
    print("🎙️  Generating channel mappings YAML from 300+ podcasts...")

    yaml_content = generate_yaml()

    # Write to config file
    output_path = (
        Path(__file__).parent.parent / "config" / "channel_mappings_generated.yaml"
    )

    with open(output_path, "w") as f:
        f.write(yaml_content)

    print(f"✅ Generated {len(PODCAST_MAPPINGS)} channel mappings")
    print(f"📁 Written to: {output_path}")
    print()
    print("Examples:")
    for channel, host in PODCAST_MAPPINGS[:5]:
        partials = generate_partial_names(host)
        print(f"  • {channel} → {host}")
        print(f"    Partial names: {', '.join(partials)}")
    print(f"  ... and {len(PODCAST_MAPPINGS) - 5} more")
    print()
    print("🔧 To use these mappings:")
    print("   1. Review the generated file")
    print("   2. Merge into config/speaker_attribution.yaml")
    print("   3. Or import directly in the speaker processor")


if __name__ == "__main__":
    main()
