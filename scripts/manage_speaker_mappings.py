#!/usr/bin/env python3
"""
Speaker Mapping Management Script

Allows you to view, edit, and delete channel-to-host mappings like:
"Eurodollar University" -> "Jeff Snider"

Usage:
    python scripts/manage_speaker_mappings.py list
    python scripts/manage_speaker_mappings.py add "Eurodollar University" "Jeff Snider"
    python scripts/manage_speaker_mappings.py edit "Eurodollar University" "Jeffrey Snider"
    python scripts/manage_speaker_mappings.py delete "Eurodollar University"
"""

import argparse
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


def list_mappings():
    """List all channel-to-host mappings."""
    db_service = get_speaker_db_service()
    mappings = db_service.get_all_channel_mappings()

    if not mappings:
        print("No channel-to-host mappings found.")
        return

    print("\nChannel-to-Host Mappings:")
    print("=" * 60)
    for mapping in mappings:
        print(f"Channel: '{mapping.channel_name}'")
        print(f"Host:    '{mapping.host_name}'")
        print(f"Used:    {mapping.use_count} times")
        print(f"Updated: {mapping.updated_at}")
        print("-" * 40)


def add_mapping(channel_name: str, host_name: str):
    """Add a new channel-to-host mapping."""
    db_service = get_speaker_db_service()

    success = db_service.create_or_update_channel_mapping(
        channel_name=channel_name,
        host_name=host_name,
        created_by="manual_edit",
        confidence=1.0,
    )

    if success:
        print(f"✅ Successfully added mapping: '{channel_name}' -> '{host_name}'")
    else:
        print(f"❌ Failed to add mapping for '{channel_name}'")


def edit_mapping(channel_name: str, new_host_name: str):
    """Edit an existing channel-to-host mapping."""
    db_service = get_speaker_db_service()

    # Check if mapping exists
    existing_host = db_service.get_channel_host_mapping(channel_name)
    if not existing_host:
        print(f"❌ No mapping found for channel '{channel_name}'")
        print("Use 'add' command to create a new mapping.")
        return

    print(f"Changing mapping for '{channel_name}':")
    print(f"  Old: '{existing_host}'")
    print(f"  New: '{new_host_name}'")

    success = db_service.create_or_update_channel_mapping(
        channel_name=channel_name,
        host_name=new_host_name,
        created_by="manual_edit",
        confidence=1.0,
    )

    if success:
        print(f"✅ Successfully updated mapping")
    else:
        print(f"❌ Failed to update mapping")


def delete_mapping(channel_name: str):
    """Delete a channel-to-host mapping."""
    db_service = get_speaker_db_service()

    # Check if mapping exists
    existing_host = db_service.get_channel_host_mapping(channel_name)
    if not existing_host:
        print(f"❌ No mapping found for channel '{channel_name}'")
        return

    print(f"Are you sure you want to delete the mapping:")
    print(f"  '{channel_name}' -> '{existing_host}'")
    confirm = input("Type 'yes' to confirm: ")

    if confirm.lower() != "yes":
        print("❌ Deletion cancelled")
        return

    try:
        with db_service.get_session() as session:
            mapping = (
                session.query(ChannelHostMapping)
                .filter_by(channel_name=channel_name)
                .first()
            )
            if mapping:
                session.delete(mapping)
                session.commit()
                print(f"✅ Successfully deleted mapping for '{channel_name}'")
            else:
                print(f"❌ Mapping not found")
    except Exception as e:
        print(f"❌ Error deleting mapping: {e}")


def main():
    parser = argparse.ArgumentParser(
        description="Manage speaker channel-to-host mappings"
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # List command
    subparsers.add_parser("list", help="List all channel-to-host mappings")

    # Add command
    add_parser = subparsers.add_parser("add", help="Add a new channel-to-host mapping")
    add_parser.add_argument(
        "channel_name", help="Channel name (e.g., 'Eurodollar University')"
    )
    add_parser.add_argument("host_name", help="Host name (e.g., 'Jeff Snider')")

    # Edit command
    edit_parser = subparsers.add_parser(
        "edit", help="Edit an existing channel-to-host mapping"
    )
    edit_parser.add_argument("channel_name", help="Channel name to edit")
    edit_parser.add_argument("new_host_name", help="New host name")

    # Delete command
    delete_parser = subparsers.add_parser(
        "delete", help="Delete a channel-to-host mapping"
    )
    delete_parser.add_argument("channel_name", help="Channel name to delete")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    try:
        if args.command == "list":
            list_mappings()
        elif args.command == "add":
            add_mapping(args.channel_name, args.host_name)
        elif args.command == "edit":
            edit_mapping(args.channel_name, args.new_host_name)
        elif args.command == "delete":
            delete_mapping(args.channel_name)
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
