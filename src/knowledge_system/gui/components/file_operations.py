"""File operations mixin for common file handling functionality."""

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

from PyQt6.QtWidgets import (
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLineEdit,
    QListWidget,
    QPushButton,
    QVBoxLayout,
)

if TYPE_CHECKING:
    pass


class FileOperationsMixin:
    """Mixin class providing common file operations for GUI tabs."""

    def create_file_input_section(
        self, title: str, file_list_attr: str, file_patterns: str = "All files (*.*)"
    ) -> QGroupBox:
        """Create a standard file input section with list and buttons."""
        group = QGroupBox(title)
        layout = QVBoxLayout()

        # Create file list widget
        file_list = QListWidget()
        file_list.setMinimumHeight(150)
        setattr(self, file_list_attr, file_list)
        layout.addWidget(file_list)

        # Create button layout
        button_layout = QHBoxLayout()

        # Add files button
        add_files_btn = QPushButton("Add Files")
        add_files_btn.clicked.connect(
            lambda: self._add_files(file_list_attr, file_patterns)
        )
        button_layout.addWidget(add_files_btn)

        # Add folder button
        add_folder_btn = QPushButton("Add Folder")
        add_folder_btn.clicked.connect(
            lambda: self._add_folder(file_list_attr, file_patterns)
        )
        button_layout.addWidget(add_folder_btn)

        # Clear button
        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(lambda: self._clear_files(file_list_attr))
        clear_btn.setStyleSheet("background-color: #d32f2f;")
        button_layout.addWidget(clear_btn)

        button_layout.addStretch()
        layout.addLayout(button_layout)

        group.setLayout(layout)
        return group

    def create_output_directory_field(
        self,
        label: str,
        field_attr: str,
        browse_callback: Callable[[], None] | None = None,
    ) -> tuple[QLineEdit, QPushButton]:
        """Create output directory field with browse button."""
        field = QLineEdit()
        setattr(self, field_attr, field)

        browse_btn = QPushButton("Browse")
        if browse_callback:
            browse_btn.clicked.connect(browse_callback)
        else:
            browse_btn.clicked.connect(
                lambda: self._select_output_directory(field_attr)
            )

        return field, browse_btn

    def _add_files(self, file_list_attr: str, file_patterns: str) -> None:
        """Add files to the specified file list."""
        file_list = getattr(self, file_list_attr)
        files, _ = QFileDialog.getOpenFileNames(
            self, "Select Files", "", file_patterns  # type: ignore
        )
        for file in files:
            if file not in self._get_file_list_items(file_list):
                file_list.addItem(file)

    def _add_folder(self, file_list_attr: str, file_patterns: str) -> None:
        """Add all matching files from a folder to the file list."""
        file_list = getattr(self, file_list_attr)
        folder = QFileDialog.getExistingDirectory(self, "Select Folder")  # type: ignore
        if folder:
            folder_path = Path(folder)

            # Extract extensions from file patterns
            extensions = self._extract_extensions_from_patterns(file_patterns)

            for file in folder_path.rglob("*"):
                if file.is_file() and (
                    not extensions or file.suffix.lower() in extensions
                ):
                    file_str = str(file)
                    if file_str not in self._get_file_list_items(file_list):
                        file_list.addItem(file_str)

    def _clear_files(self, file_list_attr: str) -> None:
        """Clear the specified file list."""
        file_list = getattr(self, file_list_attr)
        file_list.clear()

    def _select_output_directory(self, field_attr: str) -> None:
        """Select output directory for the specified field."""
        field = getattr(self, field_attr)
        folder = QFileDialog.getExistingDirectory(self, "Select Output Directory")  # type: ignore
        if folder:
            field.setText(folder)

    def _get_file_list_items(self, file_list: QListWidget) -> list[str]:
        """Get all items from a file list widget."""
        items = []
        for i in range(file_list.count()):
            item = file_list.item(i)
            if item:
                items.append(item.text())
        return items

    def _extract_extensions_from_patterns(self, file_patterns: str) -> list[str]:
        """Extract file extensions from Qt file patterns string."""
        extensions = []
        # Handle patterns like "Audio files (*.mp3 *.wav);;All files (*.*)"
        parts = file_patterns.split(";;")
        for part in parts:
            if "(*." in part:
                # Extract extensions between parentheses
                start = part.find("(") + 1
                end = part.find(")")
                if start > 0 and end > start:
                    pattern_part = part[start:end]
                    # Split by spaces and extract extensions
                    for pattern in pattern_part.split():
                        if pattern.startswith("*."):
                            ext = pattern[1:]  # Remove the *
                            if ext != ".*":  # Skip "All files"
                                extensions.append(ext.lower())
        return extensions

    def get_selected_files(self, file_list_attr: str) -> list[str]:
        """Get all files from the specified file list."""
        file_list = getattr(self, file_list_attr)
        return self._get_file_list_items(file_list)

    def validate_file_selection(self, file_list_attr: str, min_files: int = 1) -> bool:
        """Validate that enough files are selected."""
        files = self.get_selected_files(file_list_attr)
        if len(files) < min_files:
            self.show_warning(  # type: ignore
                "No Files Selected",
                f"Please select at least {min_files} file(s) for processing.",
            )
            return False
        return True

    def add_files_from_list(self, file_list_attr: str, file_paths: list[str]) -> None:
        """Add files from a list to the file list widget."""
        file_list = getattr(self, file_list_attr)
        existing_items = self._get_file_list_items(file_list)

        for file_path in file_paths:
            if file_path not in existing_items:
                file_list.addItem(file_path)
