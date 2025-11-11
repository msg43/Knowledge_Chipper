#!/usr/bin/env python3
"""
Test script to verify the Summarize tab database row selection fix.

This script simulates the user workflow:
1. Launch the GUI
2. Navigate to Summarize tab
3. Switch to Database mode
4. Verify Charlie Kirk video appears in the list
5. Simulate clicking on the row (not just the checkbox)
6. Verify the checkbox gets checked
7. Verify _get_file_list() returns the source

Run with: python test_summarize_tab_selection.py
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import QApplication

from src.knowledge_system.config import get_settings
from src.knowledge_system.gui.tabs.summarization_tab import SummarizationTab


def test_row_selection():
    """Test that clicking on a row toggles the checkbox."""
    app = QApplication(sys.argv)

    # Create the tab
    settings = get_settings()
    tab = SummarizationTab(settings)

    # Switch to database mode
    tab.database_radio.setChecked(True)

    # Refresh the database list
    print("Refreshing database list...")
    tab._refresh_database_list()

    # Find Charlie Kirk in the list
    charlie_kirk_row = None
    for row in range(tab.db_table.rowCount()):
        title_item = tab.db_table.item(row, 1)
        if title_item and "Charlie Kirk" in title_item.text():
            charlie_kirk_row = row
            print(f"Found Charlie Kirk at row {row}: {title_item.text()}")
            break

    if charlie_kirk_row is None:
        print("ERROR: Charlie Kirk video not found in database list!")
        return False

    # Get the checkbox before clicking
    checkbox = tab.db_table.cellWidget(charlie_kirk_row, 0)
    if not checkbox:
        print("ERROR: No checkbox found at row!")
        return False

    initial_state = checkbox.isChecked()
    print(f"Initial checkbox state: {'CHECKED' if initial_state else 'UNCHECKED'}")

    # Simulate clicking on the row (column 1 = title)
    print("Simulating click on title column...")
    tab._on_db_table_cell_clicked(charlie_kirk_row, 1)

    # Check the new state
    new_state = checkbox.isChecked()
    print(f"New checkbox state: {'CHECKED' if new_state else 'UNCHECKED'}")

    if new_state == initial_state:
        print("ERROR: Checkbox state did not change!")
        return False

    # Now check if _get_file_list() returns the source
    print("\nChecking _get_file_list()...")
    files = tab._get_file_list()
    print(f"_get_file_list() returned {len(files)} sources")

    if len(files) == 0:
        print("ERROR: _get_file_list() returned 0 sources!")
        return False

    print(f"Sources: {files}")

    # Verify it's a db:// source
    if not any(f.startswith("db://") for f in files):
        print("ERROR: No db:// sources found!")
        return False

    print("\n✅ SUCCESS: Row selection is working correctly!")
    return True


if __name__ == "__main__":
    success = test_row_selection()
    sys.exit(0 if success else 1)
