"""
Main entry point for running knowledge_system as a module
Main entry point for running knowledge_system as a module.

Usage:
    python -m knowledge_system          # CLI
    python -m knowledge_system gui      # GUI
"""

import sys

from .cli import main as cli_main


def main() -> None:
    """ Main entry point - route to CLI or GUI based on arguments."""
    # Check if 'gui' is the first argument
    if len(sys.argv) > 1 and sys.argv[1] == "gui":
        # Remove 'gui' from args so PyQt doesn't see it
        sys.argv.pop(1)
        # Import gui_main here to avoid importing PyQt6 for CLI users
        from . import gui_main

        gui_main()
    else:
        cli_main()


if __name__ == "__main__":
    main()
