""" Progress Display using Rich Console.
Progress Display using Rich Console

Provides rich console display for progress tracking with tables and progress bars.
"""

from pathlib import Path
from typing import List

from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table

from .tracking import ProgressTracker, TaskInfo


class ProgressDisplay:
    """ Rich console display for progress tracking."""

    def __init__(self, tracker: ProgressTracker, show_details: bool = True) -> None:
        self.tracker = tracker
        self.show_details = show_details
        self.progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeElapsedColumn(),
            console=Console(),
        )

    def start(self) -> None:
        """ Start the progress display."""
        self.progress.start()
        self._update_display()

    def stop(self) -> None:
        """ Stop the progress display."""
        self.progress.stop()
        self._show_final_summary()

    def update(self) -> None:
        """ Update the progress display."""
        self._update_display()

    def _update_display(self) -> None:
        """ Update the progress display with current status."""
        summary = self.tracker.get_progress_summary()

        # Update main progress bar
        if not hasattr(self, "_main_task"):
            self._main_task = self.progress.add_task(
                f"[cyan]{summary['operation']}[/cyan]", total=summary["total_tasks"]
            )

        self.progress.update(
            self._main_task,
            completed=summary["completed"],
            description=f"[cyan]{summary['operation']}[/cyan] - {summary['completed']}/{summary['total_tasks']} completed",
        )

        # Show failed tasks if any
        failed_tasks = self.tracker.get_failed_tasks()
        if failed_tasks and self.show_details:
            self._show_failed_tasks(failed_tasks)

    def _show_failed_tasks(self, failed_tasks: list[TaskInfo]) -> None:
        """ Display failed tasks in a table."""
        if not failed_tasks:
            return

        table = Table(
            title="Failed Tasks", show_header=True, header_style="bold magenta"
        )
        table.add_column("Task ID", style="cyan")
        table.add_column("Input", style="green")
        table.add_column("Type", style="yellow")
        table.add_column("Error", style="red")
        table.add_column("Retries", justify="center")

        for task in failed_tasks[:5]:  # Show first 5 failed tasks
            table.add_row(
                task.id,
                Path(task.input_path).name,
                task.task_type,
                task.error_message or "Unknown error",
                str(task.retry_count),
            )

        if len(failed_tasks) > 5:
            table.add_row(
                "...", "...", "...", f"... and {len(failed_tasks) - 5} more", "..."
            )

        Console().print(table)

    def _show_final_summary(self) -> None:
        """ Show final summary when operation completes."""
        summary = self.tracker.get_progress_summary()

        # Create summary table
        table = Table(
            title=f"Operation Summary: {summary['operation']}",
            show_header=True,
            header_style="bold blue",
        )
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green", justify="right")

        # Add summary rows
        table.add_row("Total Tasks", str(summary["total_tasks"]))
        table.add_row("Completed", str(summary["completed"]))
        table.add_row("Failed", str(summary["failed"]))
        table.add_row("Skipped", str(summary["skipped"]))
        table.add_row("Success Rate", f"{summary['completion_percentage']:.1f}%")

        elapsed_minutes = summary["elapsed_seconds"] // 60
        elapsed_seconds = summary["elapsed_seconds"] % 60
        table.add_row("Total Time", f"{elapsed_minutes}m {elapsed_seconds}s")

        Console().print(table)

        # Show additional details if requested
        if self.show_details:
            failed_tasks = self.tracker.get_failed_tasks()
            if failed_tasks:
                self._show_failed_tasks(failed_tasks)
