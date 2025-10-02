#!/usr/bin/env python3
"""
Cursor Progress Wrapper - Python utility for long-running processes
Provides heartbeat, progress tracking, and structured logging.
"""

import argparse
import json
import os
import signal
import sys
import threading
import time
from collections.abc import Callable
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Dict, Optional


class CursorProgressWrapper:
    """
    A wrapper class that provides heartbeat, progress tracking, and structured logging
    for long-running processes to prevent Cursor tool timeouts.
    """

    def __init__(
        self,
        heartbeat_interval: int = 20,
        status_file: str | None = None,
        enable_heartbeat: bool = True,
    ):
        self.heartbeat_interval = heartbeat_interval
        self.status_file = status_file
        self.enable_heartbeat = enable_heartbeat
        self.heartbeat_thread: threading.Thread | None = None
        self.running = False
        self.start_time = time.time()

        # Ensure unbuffered output
        sys.stdout = os.fdopen(sys.stdout.fileno(), "w", 1)
        sys.stderr = os.fdopen(sys.stderr.fileno(), "w", 1)

        # Set up signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """Handle termination signals gracefully."""
        self.emit_error("interrupted", f"Process interrupted by signal {signum}")
        self.stop()
        sys.exit(1)

    def _heartbeat_worker(self):
        """Background thread that emits heartbeat messages."""
        while self.running:
            time.sleep(self.heartbeat_interval)
            if self.running:
                elapsed = time.time() - self.start_time
                self.emit_heartbeat(f"Process still running (elapsed: {elapsed:.1f}s)")

    def start(self):
        """Start the progress wrapper."""
        self.running = True
        self.start_time = time.time()

        if self.enable_heartbeat:
            self.heartbeat_thread = threading.Thread(
                target=self._heartbeat_worker, daemon=True
            )
            self.heartbeat_thread.start()

        self.emit_status("starting", 0, "Progress wrapper initialized")

    def stop(self):
        """Stop the progress wrapper."""
        self.running = False
        if self.heartbeat_thread and self.heartbeat_thread.is_alive():
            self.heartbeat_thread.join(timeout=1)

    def emit_status(self, phase: str, percent: float = 0, message: str = ""):
        """Emit a structured status update."""
        status = {
            "phase": phase,
            "percent": percent,
            "message": message,
            "timestamp": datetime.now().isoformat(),
            "elapsed": time.time() - self.start_time,
        }

        output = f"::status::{json.dumps(status)}"
        print(output, flush=True)

        if self.status_file:
            try:
                with open(self.status_file, "w") as f:
                    json.dump(status, f)
            except Exception:
                pass  # Don't fail on status file issues

    def emit_done(self, success: bool = True, message: str = ""):
        """Emit a completion status."""
        status = {
            "success": success,
            "message": message,
            "timestamp": datetime.now().isoformat(),
            "elapsed": time.time() - self.start_time,
        }

        output = f"::done::{json.dumps(status)}"
        print(output, flush=True)

        if self.status_file:
            try:
                with open(self.status_file, "w") as f:
                    json.dump(status, f)
            except Exception:
                pass

    def emit_error(self, step: str, message: str):
        """Emit an error status."""
        status = {
            "step": step,
            "message": message,
            "timestamp": datetime.now().isoformat(),
            "elapsed": time.time() - self.start_time,
        }

        output = f"::error::{json.dumps(status)}"
        print(output, flush=True)

        if self.status_file:
            try:
                with open(self.status_file, "w") as f:
                    json.dump(status, f)
            except Exception:
                pass

    def emit_heartbeat(self, message: str = ""):
        """Emit a heartbeat message."""
        output = f"[HB] {datetime.now().isoformat()}: {message}"
        print(output, flush=True)

    def log_info(self, message: str):
        """Log an info message."""
        output = f"[INFO] {datetime.now().isoformat()}: {message}"
        print(output, flush=True)

    def log_warn(self, message: str):
        """Log a warning message."""
        output = f"[WARN] {datetime.now().isoformat()}: {message}"
        print(output, flush=True)

    def log_error(self, message: str):
        """Log an error message."""
        output = f"[ERROR] {datetime.now().isoformat()}: {message}"
        print(output, file=sys.stderr, flush=True)

    def log_success(self, message: str):
        """Log a success message."""
        output = f"[SUCCESS] {datetime.now().isoformat()}: {message}"
        print(output, flush=True)

    @contextmanager
    def progress_context(self, total_steps: int = 100):
        """Context manager for progress tracking."""

        class ProgressTracker:
            def __init__(self, wrapper, total_steps):
                self.wrapper = wrapper
                self.total_steps = total_steps
                self.current_step = 0
                self.current_phase = "working"

            def update(self, step: int = None, phase: str = None, message: str = ""):
                if step is not None:
                    self.current_step = step
                if phase is not None:
                    self.current_phase = phase

                percent = (self.current_step / self.total_steps) * 100
                self.wrapper.emit_status(self.current_phase, percent, message)

            def increment(self, message: str = ""):
                self.current_step += 1
                percent = (self.current_step / self.total_steps) * 100
                self.wrapper.emit_status(self.current_phase, percent, message)

        tracker = ProgressTracker(self, total_steps)
        try:
            yield tracker
        except Exception as e:
            self.emit_error("progress_context", str(e))
            raise

    def run_with_progress(self, func: Callable, *args, **kwargs):
        """Run a function with progress tracking."""
        try:
            self.start()
            self.log_info("Starting function execution")

            result = func(self, *args, **kwargs)

            self.emit_done(True, "Function completed successfully")
            self.log_success("Function execution completed")

            return result

        except Exception as e:
            self.emit_error("execution", str(e))
            self.log_error(f"Function execution failed: {e}")
            raise
        finally:
            self.stop()


def create_sample_long_running_process():
    """Create a sample long-running process for testing."""

    def sample_process(wrapper):
        """A sample long-running process that demonstrates the wrapper."""
        import random

        wrapper.log_info("Starting sample long-running process")

        # Simulate different phases
        phases = [
            ("initialization", 20, "Setting up environment"),
            ("data_processing", 50, "Processing data files"),
            ("analysis", 20, "Running analysis"),
            ("cleanup", 10, "Cleaning up resources"),
        ]

        total_work = sum(duration for _, duration, _ in phases)
        completed_work = 0

        for phase_name, duration, description in phases:
            wrapper.log_info(f"Starting phase: {phase_name}")
            wrapper.emit_status(
                phase_name, (completed_work / total_work) * 100, description
            )

            # Simulate work with random delays
            for i in range(duration):
                time.sleep(random.uniform(0.1, 0.3))  # Simulate work

                # Occasionally emit progress updates
                if i % 5 == 0:
                    progress = ((completed_work + i) / total_work) * 100
                    wrapper.emit_status(
                        phase_name, progress, f"{description} ({i}/{duration})"
                    )

                # Simulate occasional warnings
                if random.random() < 0.05:
                    wrapper.log_warn(f"Minor issue in {phase_name} step {i}")

            completed_work += duration
            wrapper.log_success(f"Completed phase: {phase_name}")

        wrapper.log_success("Sample process completed successfully")
        return {"status": "success", "phases_completed": len(phases)}

    return sample_process


def main():
    parser = argparse.ArgumentParser(description="Cursor Progress Wrapper")
    parser.add_argument(
        "--heartbeat-interval",
        type=int,
        default=20,
        help="Heartbeat interval in seconds (default: 20)",
    )
    parser.add_argument(
        "--status-file", type=str, help="File to write status updates to"
    )
    parser.add_argument(
        "--no-heartbeat", action="store_true", help="Disable heartbeat messages"
    )
    parser.add_argument("--test", action="store_true", help="Run test process")
    parser.add_argument(
        "command", nargs="*", help="Command to run with progress wrapper"
    )

    args = parser.parse_args()

    wrapper = CursorProgressWrapper(
        heartbeat_interval=args.heartbeat_interval,
        status_file=args.status_file,
        enable_heartbeat=not args.no_heartbeat,
    )

    if args.test:
        # Run test process
        test_func = create_sample_long_running_process()
        try:
            result = wrapper.run_with_progress(test_func)
            print(f"\nTest completed successfully: {result}")
        except Exception as e:
            print(f"\nTest failed: {e}")
            sys.exit(1)

    elif args.command:
        # Run external command with wrapper
        import subprocess

        try:
            wrapper.start()
            wrapper.log_info(f"Starting command: {' '.join(args.command)}")
            wrapper.emit_status("running", 10, "Command started")

            # Set up environment for unbuffered output
            env = os.environ.copy()
            env["PYTHONUNBUFFERED"] = "1"
            env["NODE_UNBUFFERED"] = "1"

            process = subprocess.Popen(
                args.command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1,
                env=env,
            )

            # Stream output
            while True:
                output = process.stdout.readline()
                if output == "" and process.poll() is not None:
                    break
                if output:
                    print(output.strip(), flush=True)

            exit_code = process.poll()

            if exit_code == 0:
                wrapper.emit_done(True, "Command completed successfully")
                wrapper.log_success("Command execution completed")
            else:
                wrapper.emit_error(
                    "execution", f"Command failed with exit code {exit_code}"
                )
                wrapper.log_error(f"Command failed with exit code {exit_code}")
                sys.exit(exit_code)

        except KeyboardInterrupt:
            wrapper.emit_error("interrupted", "Command interrupted by user")
            if "process" in locals():
                process.terminate()
            sys.exit(1)
        except Exception as e:
            wrapper.emit_error("execution", str(e))
            wrapper.log_error(f"Command execution failed: {e}")
            sys.exit(1)
        finally:
            wrapper.stop()

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
