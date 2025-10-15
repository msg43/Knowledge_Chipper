"""
Direct GUI launcher entrypoint.

Avoids importing CLI modules to prevent unintended side-effects during app launch.
"""

from knowledge_system.utils.optional_deps import add_vendor_to_sys_path

from . import main as launch_gui


def main() -> None:
    """Launch the GUI directly."""
    # Ensure per-user vendor path is available before any optional imports
    add_vendor_to_sys_path()
    launch_gui()


if __name__ == "__main__":
    main()
