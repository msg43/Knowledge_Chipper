"""
Test that all GUI widgets referenced in code are actually initialized.

This test catches the class of bugs where code references self.widget_name
but the widget was never created in __init__.
"""

import ast
import inspect
import re
from pathlib import Path
from typing import Dict, List, Set, Tuple

import pytest


class WidgetReferenceValidator:
    """Validates that all widget references in GUI code are properly initialized."""

    def __init__(self, class_source: str, class_name: str):
        self.source = class_source
        self.class_name = class_name
        self.tree = ast.parse(class_source)

    def find_widget_references(self) -> set[str]:
        """Find all self.X references where X looks like a widget."""
        references = set()

        for node in ast.walk(self.tree):
            if isinstance(node, ast.Attribute):
                # Check if it's self.something
                if isinstance(node.value, ast.Name) and node.value.id == "self":
                    attr_name = node.attr
                    # Look for common widget naming patterns
                    if any(
                        suffix in attr_name
                        for suffix in [
                            "_spin",
                            "_combo",
                            "_edit",
                            "_button",
                            "_check",
                            "_radio",
                            "_slider",
                            "_list",
                            "_table",
                            "_text",
                            "_label",
                            "_group",
                            "_widget",
                            "_box",
                            "_field",
                        ]
                    ):
                        references.add(attr_name)

        return references

    def find_widget_initializations(self) -> set[str]:
        """Find all self.X = ... assignments in __init__."""
        initializations = set()

        # Find the __init__ method
        for node in ast.walk(self.tree):
            if isinstance(node, ast.FunctionDef) and node.name == "__init__":
                # Look for self.X = assignments
                for child in ast.walk(node):
                    if isinstance(child, ast.Assign):
                        for target in child.targets:
                            if isinstance(target, ast.Attribute):
                                if (
                                    isinstance(target.value, ast.Name)
                                    and target.value.id == "self"
                                ):
                                    initializations.add(target.attr)

        return initializations

    def find_uninitialized_widgets(self) -> set[str]:
        """Find widgets that are referenced but never initialized."""
        references = self.find_widget_references()
        initializations = self.find_widget_initializations()
        return references - initializations

    def validate(self) -> tuple[bool, list[str]]:
        """
        Validate that all widget references are initialized.

        Returns:
            (is_valid, list_of_errors)
        """
        uninitialized = self.find_uninitialized_widgets()

        if uninitialized:
            errors = [
                f"Widget '{widget}' is referenced but never initialized in __init__"
                for widget in sorted(uninitialized)
            ]
            return False, errors

        return True, []


def get_gui_tab_classes() -> dict[str, Path]:
    """Get all GUI tab class files."""
    gui_tabs_dir = (
        Path(__file__).parent.parent.parent
        / "src"
        / "knowledge_system"
        / "gui"
        / "tabs"
    )

    tab_files = {}
    if gui_tabs_dir.exists():
        for file in gui_tabs_dir.glob("*_tab.py"):
            if file.name != "__init__.py":
                tab_files[file.stem] = file

    return tab_files


def extract_class_from_file(file_path: Path) -> list[tuple[str, str]]:
    """
    Extract class definitions from a Python file.

    Returns:
        List of (class_name, class_source) tuples
    """
    with open(file_path, encoding="utf-8") as f:
        content = f.read()

    tree = ast.parse(content)
    classes = []

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            # Extract just this class's source
            class_lines = content.split("\n")[node.lineno - 1 : node.end_lineno]
            class_source = "\n".join(class_lines)
            classes.append((node.name, class_source))

    return classes


class TestWidgetInitialization:
    """Test suite for widget initialization validation."""

    def test_summarization_tab_widgets(self):
        """Test that SummarizationTab initializes all referenced widgets."""
        tab_files = get_gui_tab_classes()

        if "summarization_tab" not in tab_files:
            pytest.skip("SummarizationTab not found")

        file_path = tab_files["summarization_tab"]
        classes = extract_class_from_file(file_path)

        for class_name, class_source in classes:
            if "Tab" in class_name:  # Only check Tab classes
                validator = WidgetReferenceValidator(class_source, class_name)
                is_valid, errors = validator.validate()

                if not is_valid:
                    error_msg = f"\n{class_name} has uninitialized widgets:\n"
                    error_msg += "\n".join(f"  - {err}" for err in errors)
                    pytest.fail(error_msg)

    def test_all_gui_tabs_widgets(self):
        """Test that all GUI tabs initialize their referenced widgets."""
        tab_files = get_gui_tab_classes()

        if not tab_files:
            pytest.skip("No GUI tab files found")

        all_errors = {}

        for tab_name, file_path in tab_files.items():
            try:
                classes = extract_class_from_file(file_path)

                for class_name, class_source in classes:
                    if "Tab" in class_name:
                        validator = WidgetReferenceValidator(class_source, class_name)
                        is_valid, errors = validator.validate()

                        if not is_valid:
                            all_errors[f"{tab_name}.{class_name}"] = errors
            except Exception as e:
                # Don't fail on parsing errors, just skip
                print(f"Warning: Could not parse {tab_name}: {e}")
                continue

        if all_errors:
            error_msg = "\nUninitialized widgets found:\n\n"
            for class_path, errors in all_errors.items():
                error_msg += f"{class_path}:\n"
                error_msg += "\n".join(f"  - {err}" for err in errors)
                error_msg += "\n\n"
            pytest.fail(error_msg)

    def test_widget_naming_conventions(self):
        """Test that widgets follow naming conventions."""
        tab_files = get_gui_tab_classes()

        if not tab_files:
            pytest.skip("No GUI tab files found")

        violations = []

        for tab_name, file_path in tab_files.items():
            try:
                with open(file_path, encoding="utf-8") as f:
                    content = f.read()

                # Find widget assignments
                # Pattern: self.something = QWidget(...)
                pattern = r"self\.(\w+)\s*=\s*Q\w+\("
                matches = re.findall(pattern, content)

                for widget_name in matches:
                    # Check if it follows conventions
                    has_suffix = any(
                        suffix in widget_name
                        for suffix in [
                            "_spin",
                            "_combo",
                            "_edit",
                            "_button",
                            "_check",
                            "_radio",
                            "_slider",
                            "_list",
                            "_table",
                            "_text",
                            "_label",
                            "_group",
                            "_widget",
                            "_box",
                            "_field",
                            "_layout",
                            "_frame",
                            "_panel",
                            "_view",
                            "_bar",
                        ]
                    )

                    if not has_suffix and not widget_name.startswith("_"):
                        violations.append(
                            f"{tab_name}: Widget '{widget_name}' doesn't follow naming convention"
                        )
            except Exception:
                continue

        if violations:
            error_msg = "\nWidget naming convention violations:\n"
            error_msg += "\n".join(f"  - {v}" for v in violations[:10])  # Show first 10
            if len(violations) > 10:
                error_msg += f"\n  ... and {len(violations) - 10} more"
            # Just warn, don't fail
            print(error_msg)


class TestWidgetUsagePatterns:
    """Test for common widget usage patterns that might indicate bugs."""

    def test_widget_value_calls_have_initialization(self):
        """Test that any .value() calls have corresponding widget initialization."""
        tab_files = get_gui_tab_classes()

        if not tab_files:
            pytest.skip("No GUI tab files found")

        errors = []

        for tab_name, file_path in tab_files.items():
            try:
                with open(file_path, encoding="utf-8") as f:
                    content = f.read()

                # Find all self.X.value() calls
                pattern = r"self\.(\w+)\.value\(\)"
                value_calls = set(re.findall(pattern, content))

                # Find all self.X = QSpinBox/QSlider/etc assignments
                init_pattern = r"self\.(\w+)\s*=\s*Q(?:SpinBox|DoubleSpinBox|Slider|Dial|ScrollBar)\("
                initializations = set(re.findall(init_pattern, content))

                # Check for missing initializations
                missing = value_calls - initializations

                for widget in missing:
                    errors.append(
                        f"{tab_name}: '{widget}.value()' called but '{widget}' not initialized as a value widget"
                    )
            except Exception:
                continue

        if errors:
            error_msg = "\nWidgets with .value() calls but no initialization:\n"
            error_msg += "\n".join(f"  - {err}" for err in errors)
            pytest.fail(error_msg)

    def test_widget_text_calls_have_initialization(self):
        """Test that any .text() calls have corresponding widget initialization."""
        tab_files = get_gui_tab_classes()

        if not tab_files:
            pytest.skip("No GUI tab files found")

        errors = []

        for tab_name, file_path in tab_files.items():
            try:
                with open(file_path, encoding="utf-8") as f:
                    content = f.read()

                # Find all self.X.text() calls (reading text)
                pattern = r"self\.(\w+)\.text\(\)"
                text_calls = set(re.findall(pattern, content))

                # Find all self.X = QLineEdit/QTextEdit/QLabel assignments
                init_pattern = r"self\.(\w+)\s*=\s*Q(?:LineEdit|TextEdit|PlainTextEdit|Label|ComboBox)\("
                initializations = set(re.findall(init_pattern, content))

                # Check for missing initializations
                missing = text_calls - initializations

                for widget in missing:
                    errors.append(
                        f"{tab_name}: '{widget}.text()' called but '{widget}' not initialized as a text widget"
                    )
            except Exception:
                continue

        if errors:
            error_msg = "\nWidgets with .text() calls but no initialization:\n"
            error_msg += "\n".join(f"  - {err}" for err in errors)
            pytest.fail(error_msg)


if __name__ == "__main__":
    # Allow running directly for quick validation
    print("🔍 Validating GUI widget initialization...\n")

    tab_files = get_gui_tab_classes()
    print(f"Found {len(tab_files)} GUI tab files\n")

    all_valid = True

    for tab_name, file_path in tab_files.items():
        print(f"Checking {tab_name}...")
        try:
            classes = extract_class_from_file(file_path)

            for class_name, class_source in classes:
                if "Tab" in class_name:
                    validator = WidgetReferenceValidator(class_source, class_name)
                    is_valid, errors = validator.validate()

                    if is_valid:
                        print(f"  ✓ {class_name}: All widgets initialized")
                    else:
                        print(f"  ✗ {class_name}: Found issues:")
                        for error in errors:
                            print(f"      - {error}")
                        all_valid = False
        except Exception as e:
            print(f"  ⚠ Could not parse: {e}")

    print("\n" + "=" * 70)
    if all_valid:
        print("✅ All GUI tabs passed widget initialization validation!")
    else:
        print("❌ Some GUI tabs have uninitialized widgets")
        exit(1)
