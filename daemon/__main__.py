"""
Entry point for running daemon as a module or standalone executable.

This allows:
    python -m daemon
    ./GetReceiptsDaemon (PyInstaller bundle)
"""

from daemon.main import main

if __name__ == "__main__":
    main()

