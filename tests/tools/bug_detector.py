"""
Automated bug detection and analysis tool.

Analyzes test results, logs, and error patterns to automatically detect bugs
and generate reports with reproduction steps.
"""

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set


@dataclass
class BugReport:
    """Represents a detected bug."""

    bug_id: str
    title: str
    severity: str  # critical, high, medium, low
    category: str  # crash, error, ui_issue, performance, data_corruption
    description: str
    reproduction_steps: list[str]
    error_messages: list[str]
    stack_traces: list[str]
    affected_components: list[str]
    test_cases_failed: list[str]
    first_seen: datetime
    occurrence_count: int = 1
    metadata: dict[str, Any] = field(default_factory=dict)


class BugDetector:
    """Automatically detect bugs from test results and logs."""

    def __init__(self, reports_dir: Path):
        self.reports_dir = Path(reports_dir)
        self.detected_bugs: list[BugReport] = []
        self.known_issues: set[str] = set()

    def analyze_test_results(self, test_report_path: Path) -> list[BugReport]:
        """Analyze test results to detect bugs."""
        bugs = []

        if not test_report_path.exists():
            return bugs

        content = test_report_path.read_text()

        # Detect different types of issues
        bugs.extend(self._detect_crashes(content))
        bugs.extend(self._detect_assertion_failures(content))
        bugs.extend(self._detect_timeout_issues(content))
        bugs.extend(self._detect_ui_errors(content))
        bugs.extend(self._detect_database_errors(content))

        return bugs

    def _detect_crashes(self, content: str) -> list[BugReport]:
        """Detect application crashes."""
        bugs = []

        # Look for segfaults, abort signals, etc.
        crash_patterns = [
            (r"Segmentation fault", "Segmentation Fault Detected"),
            (r"SIGABRT", "Application Abort Signal"),
            (r"Fatal Python error", "Fatal Python Error"),
            (r"Process terminated", "Process Terminated Unexpectedly"),
        ]

        for pattern, title in crash_patterns:
            matches = re.finditer(pattern, content, re.IGNORECASE)
            for match in matches:
                # Get context around the crash
                start = max(0, match.start() - 500)
                end = min(len(content), match.end() + 500)
                context = content[start:end]

                bug = BugReport(
                    bug_id=f"CRASH_{abs(hash(context))}",
                    title=title,
                    severity="critical",
                    category="crash",
                    description=f"Application crashed with {pattern}",
                    reproduction_steps=self._extract_reproduction_steps(context),
                    error_messages=[match.group()],
                    stack_traces=self._extract_stack_traces(context),
                    affected_components=self._identify_components(context),
                    test_cases_failed=self._extract_test_names(context),
                    first_seen=datetime.now(),
                )
                bugs.append(bug)

        return bugs

    def _detect_assertion_failures(self, content: str) -> list[BugReport]:
        """Detect assertion failures in tests."""
        bugs = []

        # Look for pytest assertion failures
        assertion_pattern = r"AssertionError:([^\n]+)\n(.*?)(?=\n\n|\Z)"
        matches = re.finditer(assertion_pattern, content, re.DOTALL)

        for match in matches:
            error_msg = match.group(1).strip()
            context = match.group(2).strip()

            bug = BugReport(
                bug_id=f"ASSERT_{abs(hash(error_msg))}",
                title=f"Assertion Failed: {error_msg[:100]}",
                severity="high",
                category="error",
                description=f"Test assertion failed: {error_msg}",
                reproduction_steps=self._extract_reproduction_steps(context),
                error_messages=[error_msg],
                stack_traces=self._extract_stack_traces(context),
                affected_components=self._identify_components(context),
                test_cases_failed=self._extract_test_names(
                    content[max(0, match.start() - 200) : match.start()]
                ),
                first_seen=datetime.now(),
            )
            bugs.append(bug)

        return bugs

    def _detect_timeout_issues(self, content: str) -> list[BugReport]:
        """Detect timeout issues."""
        bugs = []

        timeout_pattern = r"FAILED.*?timeout|TimeoutError|Timeout exceeded"
        matches = re.finditer(timeout_pattern, content, re.IGNORECASE)

        for match in matches:
            context = content[
                max(0, match.start() - 300) : min(len(content), match.end() + 300)
            ]

            bug = BugReport(
                bug_id=f"TIMEOUT_{abs(hash(context))}",
                title="Operation Timeout Detected",
                severity="medium",
                category="performance",
                description="Operation exceeded timeout threshold",
                reproduction_steps=self._extract_reproduction_steps(context),
                error_messages=[match.group()],
                stack_traces=self._extract_stack_traces(context),
                affected_components=self._identify_components(context),
                test_cases_failed=self._extract_test_names(context),
                first_seen=datetime.now(),
            )
            bugs.append(bug)

        return bugs

    def _detect_ui_errors(self, content: str) -> list[BugReport]:
        """Detect UI-related errors."""
        bugs = []

        ui_error_patterns = [
            (r"QWidget.*?deleted", "Widget Deleted Prematurely"),
            (r"QPainter.*?error", "QPainter Error"),
            (r"Qt.*?warning|Qt.*?critical", "Qt Framework Issue"),
            (r"GUI.*?failed|widget.*?not found", "UI Component Error"),
        ]

        for pattern, title in ui_error_patterns:
            matches = re.finditer(pattern, content, re.IGNORECASE)
            for match in matches:
                context = content[
                    max(0, match.start() - 300) : min(len(content), match.end() + 300)
                ]

                bug = BugReport(
                    bug_id=f"UI_{abs(hash(context))}",
                    title=title,
                    severity="high",
                    category="ui_issue",
                    description=f"UI error detected: {match.group()}",
                    reproduction_steps=self._extract_reproduction_steps(context),
                    error_messages=[match.group()],
                    stack_traces=self._extract_stack_traces(context),
                    affected_components=self._identify_components(context),
                    test_cases_failed=self._extract_test_names(context),
                    first_seen=datetime.now(),
                )
                bugs.append(bug)

        return bugs

    def _detect_database_errors(self, content: str) -> list[BugReport]:
        """Detect database-related errors."""
        bugs = []

        db_error_pattern = r"(sqlite|database|IntegrityError|OperationalError).*?error"
        matches = re.finditer(db_error_pattern, content, re.IGNORECASE)

        for match in matches:
            context = content[
                max(0, match.start() - 300) : min(len(content), match.end() + 300)
            ]

            bug = BugReport(
                bug_id=f"DB_{abs(hash(context))}",
                title="Database Error Detected",
                severity="high",
                category="data_corruption",
                description=f"Database operation failed: {match.group()}",
                reproduction_steps=self._extract_reproduction_steps(context),
                error_messages=[match.group()],
                stack_traces=self._extract_stack_traces(context),
                affected_components=["database", "System2Orchestrator"],
                test_cases_failed=self._extract_test_names(context),
                first_seen=datetime.now(),
            )
            bugs.append(bug)

        return bugs

    def _extract_stack_traces(self, content: str) -> list[str]:
        """Extract stack traces from content."""
        traces = []

        # Look for Python stack traces
        trace_pattern = r"Traceback \(most recent call last\):(.*?)(?=\n\n|\Z)"
        matches = re.finditer(trace_pattern, content, re.DOTALL)

        for match in matches:
            traces.append(match.group(1).strip())

        return traces

    def _extract_test_names(self, content: str) -> list[str]:
        """Extract test names from content."""
        test_names = []

        # Look for pytest test names
        test_pattern = r"test_[\w_]+|Test[\w_]+"
        matches = re.finditer(test_pattern, content)

        for match in matches:
            test_names.append(match.group())

        return list(set(test_names))  # Deduplicate

    def _identify_components(self, content: str) -> list[str]:
        """Identify affected components from content."""
        components = set()

        component_patterns = {
            r"youtube": "YouTube Downloader",
            r"transcription|whisper": "Transcription",
            r"summarization|llm": "Summarization",
            r"speaker.*?attribution": "Speaker Attribution",
            r"database|sqlite": "Database",
            r"gui|pyqt|widget": "GUI",
            r"orchestrator": "System2Orchestrator",
            r"mining": "Knowledge Mining",
        }

        for pattern, component in component_patterns.items():
            if re.search(pattern, content, re.IGNORECASE):
                components.add(component)

        return list(components)

    def _extract_reproduction_steps(self, content: str) -> list[str]:
        """Extract reproduction steps from content."""
        steps = []

        # Look for test method calls
        test_steps_pattern = r"(switch_to_tab|click_button|set_text_field|select_combo_item)\(['\"]([^'\"]+)"
        matches = re.finditer(test_steps_pattern, content)

        for match in matches:
            action = match.group(1)
            target = match.group(2)

            if action == "switch_to_tab":
                steps.append(f"Navigate to '{target}' tab")
            elif action == "click_button":
                steps.append(f"Click '{target}' button")
            elif action == "set_text_field":
                steps.append(f"Enter text in '{target}' field")
            elif action == "select_combo_item":
                steps.append(f"Select '{target}' from dropdown")

        return steps if steps else ["Run the failed test case"]

    def generate_bug_report_file(self, output_dir: Path) -> Path:
        """Generate a comprehensive bug report file."""
        output_dir.mkdir(parents=True, exist_ok=True)

        report_path = (
            output_dir / f"bug_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        )

        with open(report_path, "w") as f:
            f.write("# Automated Bug Detection Report\n\n")
            f.write(
                f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            )
            f.write(f"**Total Bugs Detected**: {len(self.detected_bugs)}\n\n")

            # Group by severity
            by_severity = {}
            for bug in self.detected_bugs:
                by_severity.setdefault(bug.severity, []).append(bug)

            # Write summary
            f.write("## Summary\n\n")
            for severity in ["critical", "high", "medium", "low"]:
                count = len(by_severity.get(severity, []))
                f.write(f"- **{severity.title()}**: {count}\n")
            f.write("\n")

            # Write detailed reports
            f.write("## Detailed Bug Reports\n\n")

            for severity in ["critical", "high", "medium", "low"]:
                bugs = by_severity.get(severity, [])
                if not bugs:
                    continue

                f.write(f"### {severity.title()} Priority\n\n")

                for bug in bugs:
                    f.write(f"#### {bug.title}\n\n")
                    f.write(f"- **Bug ID**: `{bug.bug_id}`\n")
                    f.write(f"- **Category**: {bug.category}\n")
                    f.write(
                        f"- **First Seen**: {bug.first_seen.strftime('%Y-%m-%d %H:%M:%S')}\n"
                    )
                    f.write(
                        f"- **Affected Components**: {', '.join(bug.affected_components)}\n\n"
                    )

                    f.write(f"**Description**: {bug.description}\n\n")

                    if bug.reproduction_steps:
                        f.write("**Reproduction Steps**:\n")
                        for i, step in enumerate(bug.reproduction_steps, 1):
                            f.write(f"{i}. {step}\n")
                        f.write("\n")

                    if bug.error_messages:
                        f.write("**Error Messages**:\n```\n")
                        for msg in bug.error_messages:
                            f.write(f"{msg}\n")
                        f.write("```\n\n")

                    if bug.stack_traces:
                        f.write("**Stack Trace**:\n```\n")
                        f.write(bug.stack_traces[0][:1000])  # Limit length
                        if len(bug.stack_traces[0]) > 1000:
                            f.write("\n... (truncated)")
                        f.write("\n```\n\n")

                    if bug.test_cases_failed:
                        f.write(
                            f"**Failed Tests**: {', '.join(bug.test_cases_failed[:5])}\n\n"
                        )

                    f.write("---\n\n")

        return report_path

    def analyze_all_reports(self, reports_dir: Path | None = None) -> Path:
        """Analyze all test reports in directory and generate bug report."""
        reports_dir = reports_dir or self.reports_dir

        # Find all test report files
        report_files = list(reports_dir.rglob("*.txt"))
        report_files.extend(list(reports_dir.rglob("*.log")))

        print(f"Analyzing {len(report_files)} report files...")

        for report_file in report_files:
            bugs = self.analyze_test_results(report_file)
            self.detected_bugs.extend(bugs)

        # Deduplicate bugs by ID
        seen_ids = set()
        unique_bugs = []
        for bug in self.detected_bugs:
            if bug.bug_id not in seen_ids:
                seen_ids.add(bug.bug_id)
                unique_bugs.append(bug)

        self.detected_bugs = unique_bugs

        print(f"Detected {len(self.detected_bugs)} unique bugs")

        # Generate report
        output_dir = reports_dir / "bug_reports"
        report_path = self.generate_bug_report_file(output_dir)

        print(f"Bug report generated: {report_path}")

        return report_path


def main():
    """Main entry point for bug detector."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Automated bug detection from test results"
    )
    parser.add_argument(
        "reports_dir", type=Path, help="Directory containing test reports"
    )

    args = parser.parse_args()

    detector = BugDetector(args.reports_dir)
    report_path = detector.analyze_all_reports()

    print("\n" + "=" * 60)
    print("BUG DETECTION COMPLETE")
    print("=" * 60)
    print(f"Total bugs detected: {len(detector.detected_bugs)}")
    print(f"Report saved to: {report_path}")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
