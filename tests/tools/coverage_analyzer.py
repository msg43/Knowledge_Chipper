"""
Test coverage analysis and reporting tool.

Analyzes which GUI components, workflows, and code paths are covered by automated tests.
Generates detailed coverage reports with recommendations for additional testing.
"""

import ast
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Set, Tuple


@dataclass
class ComponentCoverage:
    """Coverage information for a component."""

    component_name: str
    component_type: str  # tab, dialog, workflow, utility
    total_methods: int
    tested_methods: int
    tested_method_names: list[str] = field(default_factory=list)
    untested_method_names: list[str] = field(default_factory=list)
    coverage_percentage: float = 0.0

    def __post_init__(self):
        if self.total_methods > 0:
            self.coverage_percentage = (self.tested_methods / self.total_methods) * 100


@dataclass
class WorkflowCoverage:
    """Coverage information for a workflow."""

    workflow_name: str
    steps_defined: int
    steps_tested: int
    tested_steps: list[str] = field(default_factory=list)
    untested_steps: list[str] = field(default_factory=list)
    coverage_percentage: float = 0.0

    def __post_init__(self):
        if self.steps_defined > 0:
            self.coverage_percentage = (self.steps_tested / self.steps_defined) * 100


class CoverageAnalyzer:
    """Analyze test coverage for GUI components and workflows."""

    def __init__(self, src_dir: Path, tests_dir: Path):
        self.src_dir = Path(src_dir)
        self.tests_dir = Path(tests_dir)
        self.gui_components: dict[str, ComponentCoverage] = {}
        self.workflows: dict[str, WorkflowCoverage] = {}
        self.tested_features: set[str] = set()

    def analyze_gui_components(self) -> dict[str, ComponentCoverage]:
        """Analyze coverage of GUI components."""
        gui_dir = self.src_dir / "knowledge_system" / "gui"

        if not gui_dir.exists():
            print(f"Warning: GUI directory not found: {gui_dir}")
            return {}

        # Analyze main window
        main_window_file = gui_dir / "main_window_pyqt6.py"
        if main_window_file.exists():
            self.gui_components["MainWindow"] = self._analyze_class_file(
                main_window_file, "MainWindow", "main"
            )

        # Analyze tabs
        tabs_dir = gui_dir / "tabs"
        if tabs_dir.exists():
            for tab_file in tabs_dir.glob("*.py"):
                if tab_file.stem.startswith("_"):
                    continue

                tab_name = self._extract_class_name_from_file(tab_file)
                if tab_name:
                    self.gui_components[tab_name] = self._analyze_class_file(
                        tab_file, tab_name, "tab"
                    )

        return self.gui_components

    def _extract_class_name_from_file(self, file_path: Path) -> str:
        """Extract the main class name from a Python file."""
        try:
            content = file_path.read_text()
            tree = ast.parse(content)

            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    # Return first class that looks like a GUI class
                    if any(
                        keyword in node.name
                        for keyword in ["Tab", "Widget", "Dialog", "Window"]
                    ):
                        return node.name

            # If no GUI-specific class found, return first class
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    return node.name
        except Exception as e:
            print(f"Error parsing {file_path}: {e}")

        return ""

    def _analyze_class_file(
        self, file_path: Path, class_name: str, component_type: str
    ) -> ComponentCoverage:
        """Analyze a class file for test coverage."""
        try:
            content = file_path.read_text()
            tree = ast.parse(content)

            # Find the class
            target_class = None
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef) and node.name == class_name:
                    target_class = node
                    break

            if not target_class:
                return ComponentCoverage(class_name, component_type, 0, 0)

            # Get all public methods
            all_methods = []
            for node in target_class.body:
                if isinstance(node, ast.FunctionDef):
                    # Skip private methods and special methods (except __init__)
                    if not node.name.startswith("_") or node.name == "__init__":
                        all_methods.append(node.name)

            # Find which methods are tested
            tested_methods = self._find_tested_methods(class_name)

            untested = [m for m in all_methods if m not in tested_methods]

            return ComponentCoverage(
                component_name=class_name,
                component_type=component_type,
                total_methods=len(all_methods),
                tested_methods=len(tested_methods),
                tested_method_names=list(tested_methods),
                untested_method_names=untested,
            )

        except Exception as e:
            print(f"Error analyzing {file_path}: {e}")
            return ComponentCoverage(class_name, component_type, 0, 0)

    def _find_tested_methods(self, class_name: str) -> set[str]:
        """Find which methods of a class are tested."""
        tested = set()

        # Search test files for method calls
        for test_file in self.tests_dir.rglob("test_*.py"):
            try:
                content = test_file.read_text()

                # Look for method calls on the class
                # Pattern: object.method_name() or class_name.method_name()
                import re

                pattern = rf"(?:gui_tester|main_window|{class_name.lower()})\.(\w+)\("
                matches = re.finditer(pattern, content, re.IGNORECASE)

                for match in matches:
                    method_name = match.group(1)
                    tested.add(method_name)

            except Exception as e:
                print(f"Error searching {test_file}: {e}")

        return tested

    def analyze_workflows(self) -> dict[str, WorkflowCoverage]:
        """Analyze coverage of workflows."""
        workflows_to_check = {
            "YouTube Download": [
                "Enter URL",
                "Select quality",
                "Enable cookies (optional)",
                "Click download",
                "Monitor progress",
                "Handle errors",
            ],
            "Transcription": [
                "Select input file",
                "Choose provider",
                "Select model",
                "Configure options",
                "Start transcription",
                "View results",
            ],
            "Summarization": [
                "Select input",
                "Choose LLM provider",
                "Select model",
                "Customize prompts",
                "Run summarization",
                "Export results",
            ],
            "Knowledge Mining": [
                "Configure mining options",
                "Select content types",
                "Run mining",
                "Generate YAML",
                "Review results",
            ],
            "Speaker Attribution": [
                "Load transcript",
                "Configure speakers",
                "Run attribution",
                "Review results",
                "Export",
            ],
            "Monitor (System 2)": [
                "View job list",
                "Check job status",
                "Pause/resume jobs",
                "Cancel jobs",
                "View job details",
            ],
        }

        for workflow_name, steps in workflows_to_check.items():
            tested_steps = self._find_tested_workflow_steps(workflow_name, steps)
            untested_steps = [s for s in steps if s not in tested_steps]

            self.workflows[workflow_name] = WorkflowCoverage(
                workflow_name=workflow_name,
                steps_defined=len(steps),
                steps_tested=len(tested_steps),
                tested_steps=tested_steps,
                untested_steps=untested_steps,
            )

        return self.workflows

    def _find_tested_workflow_steps(
        self, workflow_name: str, steps: list[str]
    ) -> list[str]:
        """Find which workflow steps are tested."""
        tested_steps = []

        # Map step descriptions to test patterns
        step_patterns = {
            "Enter URL": [r"set_text_field.*url", r"youtube_url"],
            "Select quality": [r"select_combo.*quality"],
            "Click download": [r"click_button.*download"],
            "Select input file": [r"select.*file", r"file.*input"],
            "Choose provider": [r"select_combo.*provider"],
            "Select model": [r"select_combo.*model"],
            "Configure options": [r"configure", r"settings"],
            "Run": [r"click_button.*run", r"click_button.*start", r"process"],
            "View results": [r"review", r"results"],
            "Export": [r"export", r"save"],
            "Monitor": [r"monitor", r"status", r"progress"],
        }

        # Search test files
        for test_file in self.tests_dir.rglob("test_*.py"):
            try:
                content = test_file.read_text().lower()

                for step in steps:
                    # Check if step is mentioned or related patterns found
                    if step.lower() in content:
                        tested_steps.append(step)
                        continue

                    # Check patterns
                    for key, patterns in step_patterns.items():
                        if key.lower() in step.lower():
                            import re

                            for pattern in patterns:
                                if re.search(pattern, content, re.IGNORECASE):
                                    tested_steps.append(step)
                                    break
                            if step in tested_steps:
                                break

            except Exception as e:
                print(f"Error searching {test_file}: {e}")

        return tested_steps

    def analyze_test_files(self) -> dict[str, int]:
        """Analyze test files to see what's being tested."""
        test_stats = {
            "total_test_files": 0,
            "total_test_functions": 0,
            "gui_test_files": 0,
            "unit_test_files": 0,
            "integration_test_files": 0,
        }

        for test_file in self.tests_dir.rglob("test_*.py"):
            test_stats["total_test_files"] += 1

            try:
                content = test_file.read_text()
                tree = ast.parse(content)

                # Count test functions
                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef) and node.name.startswith(
                        "test_"
                    ):
                        test_stats["total_test_functions"] += 1

                # Categorize test file
                if "gui" in test_file.stem:
                    test_stats["gui_test_files"] += 1
                elif "integration" in str(test_file.parent):
                    test_stats["integration_test_files"] += 1
                else:
                    test_stats["unit_test_files"] += 1

            except Exception as e:
                print(f"Error analyzing {test_file}: {e}")

        return test_stats

    def generate_coverage_report(self, output_file: Path) -> None:
        """Generate a comprehensive coverage report."""
        # Run all analyses
        self.analyze_gui_components()
        self.analyze_workflows()
        test_stats = self.analyze_test_files()

        with open(output_file, "w") as f:
            f.write("# Test Coverage Analysis Report\n\n")
            f.write(f"**Generated**: {Path.cwd()}\n\n")

            # Test Statistics
            f.write("## Test Statistics\n\n")
            f.write(f"- **Total Test Files**: {test_stats['total_test_files']}\n")
            f.write(
                f"- **Total Test Functions**: {test_stats['total_test_functions']}\n"
            )
            f.write(f"- **GUI Test Files**: {test_stats['gui_test_files']}\n")
            f.write(f"- **Unit Test Files**: {test_stats['unit_test_files']}\n")
            f.write(
                f"- **Integration Test Files**: {test_stats['integration_test_files']}\n\n"
            )

            # GUI Component Coverage
            f.write("## GUI Component Coverage\n\n")

            if self.gui_components:
                total_methods = sum(
                    c.total_methods for c in self.gui_components.values()
                )
                tested_methods = sum(
                    c.tested_methods for c in self.gui_components.values()
                )
                overall_coverage = (
                    (tested_methods / total_methods * 100) if total_methods > 0 else 0
                )

                f.write(
                    f"**Overall Coverage**: {overall_coverage:.1f}% ({tested_methods}/{total_methods} methods)\n\n"
                )

                f.write("| Component | Type | Coverage | Tested | Total |\n")
                f.write("|-----------|------|----------|--------|-------|\n")

                for component in sorted(
                    self.gui_components.values(),
                    key=lambda c: c.coverage_percentage,
                    reverse=True,
                ):
                    f.write(
                        f"| {component.component_name} | {component.component_type} | "
                        f"{component.coverage_percentage:.1f}% | {component.tested_methods} | {component.total_methods} |\n"
                    )

                f.write("\n### Components Needing More Tests\n\n")
                low_coverage = [
                    c
                    for c in self.gui_components.values()
                    if c.coverage_percentage < 50
                ]

                if low_coverage:
                    for component in sorted(
                        low_coverage, key=lambda c: c.coverage_percentage
                    ):
                        f.write(
                            f"#### {component.component_name} ({component.coverage_percentage:.1f}% coverage)\n\n"
                        )
                        if component.untested_method_names:
                            f.write("Untested methods:\n")
                            for method in component.untested_method_names[
                                :10
                            ]:  # Limit to 10
                                f.write(f"- `{method}()`\n")
                            if len(component.untested_method_names) > 10:
                                f.write(
                                    f"- ... and {len(component.untested_method_names) - 10} more\n"
                                )
                        f.write("\n")
                else:
                    f.write("✅ All components have good coverage (>50%)\n\n")
            else:
                f.write("⚠️ No GUI components analyzed\n\n")

            # Workflow Coverage
            f.write("## Workflow Coverage\n\n")

            if self.workflows:
                total_steps = sum(w.steps_defined for w in self.workflows.values())
                tested_steps = sum(w.steps_tested for w in self.workflows.values())
                overall_workflow_coverage = (
                    (tested_steps / total_steps * 100) if total_steps > 0 else 0
                )

                f.write(
                    f"**Overall Workflow Coverage**: {overall_workflow_coverage:.1f}% ({tested_steps}/{total_steps} steps)\n\n"
                )

                f.write("| Workflow | Coverage | Tested Steps | Total Steps |\n")
                f.write("|----------|----------|--------------|-------------|\n")

                for workflow in sorted(
                    self.workflows.values(),
                    key=lambda w: w.coverage_percentage,
                    reverse=True,
                ):
                    f.write(
                        f"| {workflow.workflow_name} | {workflow.coverage_percentage:.1f}% | "
                        f"{workflow.steps_tested} | {workflow.steps_defined} |\n"
                    )

                f.write("\n### Workflows Needing More Tests\n\n")
                incomplete_workflows = [
                    w for w in self.workflows.values() if w.coverage_percentage < 100
                ]

                if incomplete_workflows:
                    for workflow in sorted(
                        incomplete_workflows, key=lambda w: w.coverage_percentage
                    ):
                        f.write(
                            f"#### {workflow.workflow_name} ({workflow.coverage_percentage:.1f}% coverage)\n\n"
                        )
                        if workflow.untested_steps:
                            f.write("Untested steps:\n")
                            for step in workflow.untested_steps:
                                f.write(f"- {step}\n")
                        f.write("\n")
                else:
                    f.write("✅ All workflows are fully tested\n\n")
            else:
                f.write("⚠️ No workflows analyzed\n\n")

            # Recommendations
            f.write("## Recommendations\n\n")

            recommendations = []

            # Component recommendations
            if self.gui_components:
                low_coverage_components = [
                    c
                    for c in self.gui_components.values()
                    if c.coverage_percentage < 50
                ]
                if low_coverage_components:
                    recommendations.append(
                        f"🔴 **High Priority**: {len(low_coverage_components)} GUI components have <50% coverage. "
                        "Add tests for critical methods."
                    )

                medium_coverage_components = [
                    c
                    for c in self.gui_components.values()
                    if 50 <= c.coverage_percentage < 80
                ]
                if medium_coverage_components:
                    recommendations.append(
                        f"🟡 **Medium Priority**: {len(medium_coverage_components)} components have 50-80% coverage. "
                        "Add tests for remaining methods."
                    )

            # Workflow recommendations
            if self.workflows:
                incomplete_workflows = [
                    w for w in self.workflows.values() if w.coverage_percentage < 100
                ]
                if incomplete_workflows:
                    recommendations.append(
                        f"🔴 **High Priority**: {len(incomplete_workflows)} workflows are not fully tested. "
                        "Add end-to-end tests for missing steps."
                    )

            # General recommendations
            if test_stats["total_test_functions"] < 50:
                recommendations.append(
                    f"🔴 **High Priority**: Only {test_stats['total_test_functions']} test functions found. "
                    "Add more comprehensive tests."
                )

            if recommendations:
                for i, rec in enumerate(recommendations, 1):
                    f.write(f"{i}. {rec}\n\n")
            else:
                f.write(
                    "✅ **Excellent!** Test coverage looks good. Keep maintaining and expanding tests.\n\n"
                )

            # Summary
            f.write("## Summary\n\n")

            if self.gui_components:
                total_methods = sum(
                    c.total_methods for c in self.gui_components.values()
                )
                tested_methods = sum(
                    c.tested_methods for c in self.gui_components.values()
                )
                overall_coverage = (
                    (tested_methods / total_methods * 100) if total_methods > 0 else 0
                )

                if overall_coverage >= 80:
                    f.write("✅ **Excellent coverage** - The GUI is well-tested.\n\n")
                elif overall_coverage >= 60:
                    f.write(
                        "🟡 **Good coverage** - Most GUI components are tested, but some gaps remain.\n\n"
                    )
                elif overall_coverage >= 40:
                    f.write(
                        "🟠 **Moderate coverage** - Many GUI components need more tests.\n\n"
                    )
                else:
                    f.write(
                        "🔴 **Low coverage** - Significant testing gaps. Add more comprehensive tests.\n\n"
                    )

            f.write("**Next Steps**:\n")
            f.write("1. Review untested methods and workflows above\n")
            f.write("2. Add tests for high-priority items\n")
            f.write("3. Run `./tests/run_comprehensive_automated_tests.sh` to verify\n")
            f.write("4. Re-run this coverage analysis to track progress\n")

        print(f"Coverage report generated: {output_file}")


def main():
    """Main entry point for coverage analyzer."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Analyze test coverage for GUI components and workflows"
    )
    parser.add_argument(
        "--src-dir",
        type=Path,
        default=Path.cwd() / "src",
        help="Source directory containing code to analyze",
    )
    parser.add_argument(
        "--tests-dir",
        type=Path,
        default=Path.cwd() / "tests",
        help="Tests directory containing test files",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path.cwd() / "tests" / "reports" / "coverage_analysis.md",
        help="Output file for coverage report",
    )

    args = parser.parse_args()

    # Create output directory if needed
    args.output.parent.mkdir(parents=True, exist_ok=True)

    analyzer = CoverageAnalyzer(args.src_dir, args.tests_dir)
    analyzer.generate_coverage_report(args.output)

    print("\n" + "=" * 60)
    print("COVERAGE ANALYSIS COMPLETE")
    print("=" * 60)
    print(f"Report saved to: {args.output}")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
