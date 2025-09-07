"""
ETA (Estimated Time to Arrival) Calculator for long-running processes.

Provides accurate time estimation based on progress tracking.
"""

import time
from typing import Optional, Tuple


class ETACalculator:
    """Calculates and tracks ETA for long-running processes."""

    def __init__(self, smoothing_factor: float = 0.1, min_samples: int = 3):
        """
        Initialize ETA calculator.

        Args:
            smoothing_factor: Factor for exponential smoothing (0.0 to 1.0)
            min_samples: Minimum samples before providing reliable estimates
        """
        self.smoothing_factor = smoothing_factor
        self.min_samples = min_samples

        self.start_time: float | None = None
        self.last_update_time: float | None = None
        self.last_progress: float = 0.0
        self.avg_speed: float | None = None  # progress units per second
        self.sample_count: int = 0

    def start(self) -> None:
        """Start tracking progress."""
        self.start_time = time.time()
        self.last_update_time = self.start_time
        self.last_progress = 0.0
        self.avg_speed = None
        self.sample_count = 0

    def update(self, progress: float) -> tuple[str | None, float | None]:
        """
        Update progress and calculate ETA.

        Args:
            progress: Current progress (0.0 to 100.0)

        Returns:
            Tuple of (eta_string, eta_seconds) or (None, None) if insufficient data
        """
        if self.start_time is None:
            self.start()

        current_time = time.time()

        # Skip if progress hasn't advanced
        if progress <= self.last_progress:
            return None, None

        # Calculate instantaneous speed
        time_delta = current_time - self.last_update_time
        progress_delta = progress - self.last_progress

        if time_delta <= 0:
            return None, None

        instant_speed = progress_delta / time_delta

        # Update average speed using exponential smoothing
        if self.avg_speed is None:
            self.avg_speed = instant_speed
        else:
            self.avg_speed = (
                self.smoothing_factor * instant_speed
                + (1 - self.smoothing_factor) * self.avg_speed
            )

        # Update tracking variables
        self.last_update_time = current_time
        self.last_progress = progress
        self.sample_count += 1

        # Return ETA if we have enough samples and reasonable speed
        if self.sample_count >= self.min_samples and self.avg_speed > 0:
            remaining_progress = 100.0 - progress
            eta_seconds = remaining_progress / self.avg_speed
            eta_string = self._format_eta(eta_seconds)
            return eta_string, eta_seconds

        return None, None

    def _format_eta(self, seconds: float) -> str:
        """Format ETA seconds into human-readable string."""
        if seconds < 0:
            return "Calculating..."

        if seconds < 60:
            return f"{int(seconds)}s"
        elif seconds < 3600:
            minutes = int(seconds / 60)
            secs = int(seconds % 60)
            return f"{minutes}m {secs}s"
        else:
            hours = int(seconds / 3600)
            minutes = int((seconds % 3600) / 60)
            return f"{hours}h {minutes}m"

    def get_elapsed_time(self) -> str | None:
        """Get elapsed time since start."""
        if self.start_time is None:
            return None

        elapsed = time.time() - self.start_time
        return self._format_eta(elapsed)

    def reset(self) -> None:
        """Reset the calculator."""
        self.start_time = None
        self.last_update_time = None
        self.last_progress = 0.0
        self.avg_speed = None
        self.sample_count = 0


class MultiProcessETA:
    """ETA calculator for multi-step processes."""

    def __init__(self):
        self.calculators = {}
        self.current_step = None
        self.total_steps = 0
        self.completed_steps = 0

    def add_step(self, step_name: str, weight: float = 1.0) -> None:
        """Add a processing step with optional weight."""
        self.calculators[step_name] = {
            "calculator": ETACalculator(),
            "weight": weight,
            "completed": False,
        }
        self.total_steps += weight

    def start_step(self, step_name: str) -> None:
        """Start tracking a specific step."""
        if step_name in self.calculators:
            self.current_step = step_name
            self.calculators[step_name]["calculator"].start()

    def update_step(
        self, step_name: str, progress: float
    ) -> tuple[str | None, float | None]:
        """Update progress for a specific step."""
        if step_name not in self.calculators:
            return None, None

        calc_info = self.calculators[step_name]
        eta_str, eta_seconds = calc_info["calculator"].update(progress)

        # Mark step as completed if progress >= 100
        if progress >= 100.0 and not calc_info["completed"]:
            calc_info["completed"] = True
            self.completed_steps += calc_info["weight"]

        return eta_str, eta_seconds

    def get_overall_eta(self) -> tuple[str | None, float | None]:
        """Get ETA for the entire multi-step process."""
        if not self.calculators or self.total_steps == 0:
            return None, None

        # Calculate overall progress
        total_progress = 0.0
        for step_name, calc_info in self.calculators.items():
            step_progress = calc_info["calculator"].last_progress
            weight = calc_info["weight"]
            total_progress += (step_progress * weight) / 100.0

        overall_progress = (total_progress / self.total_steps) * 100.0

        # Use the current step's speed to estimate remaining time
        if self.current_step and self.current_step in self.calculators:
            current_calc = self.calculators[self.current_step]["calculator"]
            if current_calc.avg_speed and current_calc.avg_speed > 0:
                remaining_overall = 100.0 - overall_progress
                # Rough estimate based on current step speed
                eta_seconds = remaining_overall / current_calc.avg_speed
                eta_string = current_calc._format_eta(eta_seconds)
                return eta_string, eta_seconds

        return None, None
