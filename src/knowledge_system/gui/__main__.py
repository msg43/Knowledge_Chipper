"""
Backward compatibility launcher for GUI.

DEPRECATED: Use 'python -m knowledge_system gui' instead.
"""

import subprocess
import sys


def main() -> None:
    """Redirect to the new command format."""
    print("=" * 60)
    print("DEPRECATED: python -m knowledge_system.gui")
    print("Use this instead: python -m knowledge_system gui")
    print("=" * 60)
    print()
    print("Launching GUI with new command format...")

    # Launch with the new format
    try:
        subprocess.run([sys.executable, "-m", "knowledge_system", "gui"], check=True)
    except KeyboardInterrupt:
        print("\nGUI launch cancelled.")
    except Exception as e:
        print(f"Failed to launch GUI: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
