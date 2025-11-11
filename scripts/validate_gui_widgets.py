#!/usr/bin/env python3
"""
Standalone script to validate GUI widget initialization.

This can be run manually or as part of CI/CD to catch widget initialization bugs.

Usage:
    python scripts/validate_gui_widgets.py
    python scripts/validate_gui_widgets.py --fix  # Suggest fixes
    python scripts/validate_gui_widgets.py --verbose  # Show all details
"""

import argparse
import ast
import re
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple


class WidgetValidator:
    """Validates GUI widget initialization."""

    WIDGET_SUFFIXES = [
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
        "_progress",
        "_scroll",
        "_tab",
        "_tree",
        "_menu",
    ]

    VALUE_WIDGETS = [
        "QSpinBox",
        "QDoubleSpinBox",
        "QSlider",
        "QDial",
        "QScrollBar",
        "QProgressBar",
    ]

    TEXT_WIDGETS = [
        "QLineEdit",
        "QTextEdit",
        "QPlainTextEdit",
        "QLabel",
        "QComboBox",
        "QPushButton",
    ]

    def __init__(self, file_path: Path, verbose: bool = False):
        self.file_path = file_path
        self.verbose = verbose
        with open(file_path, encoding="utf-8") as f:
            self.content = f.read()
        self.tree = ast.parse(self.content)

    def find_widget_references_in_class(self, class_node: ast.ClassDef) -> set[str]:
        """Find all self.X references that look like widgets."""
        references = set()
        methods = set()

        # First, collect all method names to exclude them
        for node in ast.walk(class_node):
            if isinstance(node, ast.FunctionDef):
                methods.add(node.name)

        # Now find widget references, excluding methods
        for node in ast.walk(class_node):
            if isinstance(node, ast.Attribute):
                if isinstance(node.value, ast.Name) and node.value.id == "self":
                    attr_name = node.attr
                    # Skip if it's a method or starts with underscore (private/method)
                    if attr_name not in methods and not attr_name.startswith("_"):
                        if any(suffix in attr_name for suffix in self.WIDGET_SUFFIXES):
                            references.add(attr_name)

        return references

    def find_widget_initializations_in_init(self, class_node: ast.ClassDef) -> set[str]:
        """Find all self.X = ... assignments in __init__."""
        initializations = set()

        for node in ast.walk(class_node):
            if isinstance(node, ast.FunctionDef) and node.name == "__init__":
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

    def find_value_calls(self) -> dict[str, list[int]]:
        """Find all self.X.value() calls and their line numbers."""
        pattern = r"self\.(\w+)\.value\(\)"
        calls = {}

        for i, line in enumerate(self.content.split("\n"), 1):
            matches = re.findall(pattern, line)
            for widget in matches:
                if widget not in calls:
                    calls[widget] = []
                calls[widget].append(i)

        return calls

    def find_text_calls(self) -> dict[str, list[int]]:
        """Find all self.X.text() calls and their line numbers."""
        pattern = r"self\.(\w+)\.text\(\)"
        calls = {}

        for i, line in enumerate(self.content.split("\n"), 1):
            matches = re.findall(pattern, line)
            for widget in matches:
                if widget not in calls:
                    calls[widget] = []
                calls[widget].append(i)

        return calls

    def find_widget_type_initializations(self) -> dict[str, str]:
        """Find widget initializations and their types."""
        pattern = r"self\.(\w+)\s*=\s*(Q\w+)\("
        widgets = {}

        for match in re.finditer(pattern, self.content):
            widget_name = match.group(1)
            widget_type = match.group(2)
            widgets[widget_name] = widget_type

        return widgets

    def validate_class(self, class_node: ast.ClassDef) -> tuple[bool, list[dict]]:
        """
        Validate a single class.

        Returns:
            (is_valid, list_of_issues)
        """
        issues = []

        references = self.find_widget_references_in_class(class_node)
        initializations = self.find_widget_initializations_in_init(class_node)
        uninitialized = references - initializations

        if uninitialized:
            for widget in sorted(uninitialized):
                issues.append(
                    {
                        "type": "uninitialized",
                        "widget": widget,
                        "class": class_node.name,
                        "message": f"Widget '{widget}' referenced but never initialized in __init__",
                    }
                )

        # Check .value() calls
        value_calls = self.find_value_calls()
        widget_types = self.find_widget_type_initializations()

        for widget, lines in value_calls.items():
            if widget not in widget_types:
                issues.append(
                    {
                        "type": "missing_value_widget",
                        "widget": widget,
                        "lines": lines,
                        "message": f"'{widget}.value()' called but '{widget}' not initialized as a value widget",
                        "suggestion": f"Add: self.{widget} = QSpinBox()  # or QSlider, etc.",
                    }
                )
            elif widget_types[widget] not in self.VALUE_WIDGETS:
                issues.append(
                    {
                        "type": "wrong_widget_type",
                        "widget": widget,
                        "lines": lines,
                        "actual_type": widget_types[widget],
                        "message": f"'{widget}.value()' called but '{widget}' is {widget_types[widget]}, not a value widget",
                    }
                )

        # Check .text() calls
        text_calls = self.find_text_calls()

        for widget, lines in text_calls.items():
            if widget not in widget_types:
                issues.append(
                    {
                        "type": "missing_text_widget",
                        "widget": widget,
                        "lines": lines,
                        "message": f"'{widget}.text()' called but '{widget}' not initialized as a text widget",
                        "suggestion": f"Add: self.{widget} = QLineEdit()  # or QLabel, etc.",
                    }
                )

        return len(issues) == 0, issues

    def validate(self) -> tuple[bool, dict[str, list[dict]]]:
        """
        Validate all classes in the file.

        Returns:
            (is_valid, dict of class_name -> issues)
        """
        all_issues = {}

        for node in ast.walk(self.tree):
            if isinstance(node, ast.ClassDef):
                if "Tab" in node.name or "Widget" in node.name:
                    is_valid, issues = self.validate_class(node)
                    if not is_valid:
                        all_issues[node.name] = issues

        return len(all_issues) == 0, all_issues


def print_issue(issue: dict, verbose: bool = False):
    """Pretty print an issue."""
    icon = {
        "uninitialized": "❌",
        "missing_value_widget": "⚠️ ",
        "missing_text_widget": "⚠️ ",
        "wrong_widget_type": "🔴",
    }.get(issue["type"], "⚠️ ")

    print(f"  {icon} {issue['message']}")

    if "lines" in issue:
        lines_str = ", ".join(str(l) for l in issue["lines"][:5])
        if len(issue["lines"]) > 5:
            lines_str += f" ... ({len(issue['lines'])} total)"
        print(f"      Used on lines: {lines_str}")

    if "suggestion" in issue and verbose:
        print(f"      💡 {issue['suggestion']}")


def main():
    parser = argparse.ArgumentParser(description="Validate GUI widget initialization")
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show detailed output including suggestions",
    )
    parser.add_argument("--file", "-f", type=Path, help="Validate a specific file")
    parser.add_argument("--fix", action="store_true", help="Show fix suggestions")

    args = parser.parse_args()

    # Find GUI tab files
    if args.file:
        files = [args.file]
    else:
        gui_tabs_dir = (
            Path(__file__).parent.parent / "src" / "knowledge_system" / "gui" / "tabs"
        )
        files = list(gui_tabs_dir.glob("*_tab.py"))

    if not files:
        print("❌ No GUI tab files found")
        return 1

    print(f"🔍 Validating {len(files)} GUI file(s)...\n")

    all_valid = True
    total_issues = 0

    for file_path in sorted(files):
        try:
            validator = WidgetValidator(file_path, verbose=args.verbose or args.fix)
            is_valid, issues_by_class = validator.validate()

            if is_valid:
                if args.verbose:
                    print(f"✅ {file_path.name}: All widgets properly initialized")
            else:
                all_valid = False
                print(f"❌ {file_path.name}:")

                for class_name, issues in issues_by_class.items():
                    print(f"\n  Class: {class_name}")
                    for issue in issues:
                        print_issue(issue, verbose=args.verbose or args.fix)
                        total_issues += 1

                print()

        except Exception as e:
            print(f"⚠️  {file_path.name}: Could not parse ({e})")
            if args.verbose:
                import traceback

                traceback.print_exc()

    print("\n" + "=" * 70)

    if all_valid:
        print("✅ All GUI files passed widget initialization validation!")
        return 0
    else:
        print(f"❌ Found {total_issues} widget initialization issue(s)")
        print("\nRun with --fix to see suggested fixes")
        return 1


if __name__ == "__main__":
    sys.exit(main())
