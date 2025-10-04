#!/usr/bin/env python3
"""
Cleanup script for removing non-proper name host entries from channel-host mappings.

This script identifies and removes mappings where the host name is not a real person's name
(e.g., "Try Guys", "Team Coco") and updates or removes those entries accordingly.
"""

import sys
from pathlib import Path

# Add src to path so we can import the knowledge system modules
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from knowledge_system.database.speaker_models import (
    ChannelHostMapping,
    get_speaker_db_service,
)
from knowledge_system.logger import get_logger

logger = get_logger(__name__)

# List of non-proper name entries to remove or research
PROBLEMATIC_HOSTS = [
    "Try Guys",  # Should be individual members: Keith Habersberger, Zach Kornfeld, Eugene Lee Yang
    "Team Coco",  # Already has Conan O'Brien as the actual host
    "Variety",  # Not a person, remove
    "Brothers",  # Not specific enough
    "Sisters",  # Not specific enough
    "Gang",  # Not specific enough
    "Group",  # Not specific enough
    "Team",  # Not specific enough when standalone
]

# Mappings to update with actual hosts
CORRECTIONS = {
    # For Try Guys, since it's multiple hosts, we'll remove it rather than pick one
    "The Try Guys Podcast": None,  # Remove - multiple hosts
    "Team Coco": "Conan O'Brien",  # Already correct in seed data
    "The Daily Beatles": None,  # Remove - "Variety" is not a person
}

# Single-name hosts that are actually stage names or known single names (keep these)
VALID_SINGLE_NAMES = [
    "Questlove",  # Ahmir Khalib Thompson, known professionally as Questlove
    "N.O.R.E.",  # Victor Santiago Jr., known as N.O.R.E.
    "Adam22",  # Adam Grandmaison, known as Adam22
    "Tony",  # Could be valid if it's a known personality
    "Arlee",  # Could be valid if it's a known personality
]


def main(dry_run=True):
    """Clean up problematic host entries in the database."""
    db_service = get_speaker_db_service()

    print("🔍 Scanning for problematic host entries...")

    with db_service.get_session() as session:
        # Find all mappings
        all_mappings = session.query(ChannelHostMapping).all()

        to_remove = []
        to_update = []
        single_names = []

        for mapping in all_mappings:
            # Check for known problematic hosts
            if mapping.host_name in PROBLEMATIC_HOSTS:
                to_remove.append(mapping)

            # Check for specific corrections
            elif mapping.channel_name in CORRECTIONS:
                if CORRECTIONS[mapping.channel_name] is None:
                    to_remove.append(mapping)
                else:
                    to_update.append((mapping, CORRECTIONS[mapping.channel_name]))

            # Flag single-name entries for review (but don't auto-remove valid ones)
            elif (
                " " not in mapping.host_name
                and mapping.host_name not in VALID_SINGLE_NAMES
            ):
                single_names.append(mapping)

        # Display findings
        print(f"\n📊 Summary:")
        print(f"  • Total mappings: {len(all_mappings)}")
        print(f"  • To remove: {len(to_remove)}")
        print(f"  • To update: {len(to_update)}")
        print(f"  • Single names to review: {len(single_names)}")

        if to_remove:
            print(f"\n❌ Mappings to remove:")
            for mapping in to_remove:
                print(f"  • {mapping.channel_name} → {mapping.host_name}")

        if to_update:
            print(f"\n✏️ Mappings to update:")
            for mapping, new_host in to_update:
                print(f"  • {mapping.channel_name}: {mapping.host_name} → {new_host}")

        if single_names:
            print(f"\n⚠️ Single-name hosts to review:")
            for mapping in single_names[:10]:  # Show first 10
                print(f"  • {mapping.channel_name} → {mapping.host_name}")
            if len(single_names) > 10:
                print(f"  ... and {len(single_names) - 10} more")

        if not dry_run and (to_remove or to_update):
            print("\n🔧 Applying cleanup...")
            # Remove problematic entries
            for mapping in to_remove:
                session.delete(mapping)
                logger.info(
                    f"Removed mapping: {mapping.channel_name} → {mapping.host_name}"
                )

            # Update corrections
            for mapping, new_host in to_update:
                mapping.host_name = new_host
                logger.info(f"Updated mapping: {mapping.channel_name} → {new_host}")

            session.commit()
            print("\n✅ Cleanup completed!")
        elif dry_run:
            print("\n🔍 DRY RUN - No changes made. Run with --apply to make changes.")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Clean up problematic speaker mappings"
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually make changes (default is dry run)",
    )

    args = parser.parse_args()
    main(dry_run=not args.apply)
