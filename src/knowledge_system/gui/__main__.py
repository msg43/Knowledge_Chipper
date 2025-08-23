"""
Direct GUI launcher entrypoint.

Avoids importing CLI modules to prevent unintended side-effects during app launch.
"""

from . import main as launch_gui


def main() -> None:
    """Launch the GUI directly."""
    launch_gui()


if __name__ == "__main__":
    main()
