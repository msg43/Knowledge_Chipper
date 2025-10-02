#!/usr/bin/env python3
"""
Cursor Smart Command Detector - Intelligently detects if commands need wrapping
Uses heuristics and machine learning-like patterns to predict command duration
"""

import hashlib
import json
import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple


class CursorSmartDetector:
    """
    Smart detector that learns which commands are likely to be long-running
    and automatically applies timeout prevention.
    """

    def __init__(self, project_root: str):
        self.project_root = Path(project_root)
        self.stats_file = self.project_root / "tmp" / "cursor_command_stats.json"
        self.stats_file.parent.mkdir(exist_ok=True)

        # Load historical command statistics
        self.command_stats = self._load_stats()

        # Patterns that strongly suggest long-running commands
        self.long_running_patterns = [
            # Installation and setup
            r"install",
            r"setup\.py",
            r"requirements\.txt",
            r"package\.json",
            r"npm\s+install",
            r"pip\s+install",
            r"yarn\s+install",
            # Building and compilation
            r"build",
            r"compile",
            r"make",
            r"cmake",
            r"gcc",
            r"clang",
            r"cargo\s+build",
            r"go\s+build",
            r"mvn\s+compile",
            # Testing
            r"test",
            r"pytest",
            r"unittest",
            r"jest",
            r"mocha",
            r"coverage",
            r"tox",
            r"nox",
            # Machine learning and data processing
            r"train",
            r"fit",
            r"epoch",
            r"model",
            r"dataset",
            r"tensorflow",
            r"pytorch",
            r"sklearn",
            r"pandas",
            # File operations
            r"rsync",
            r"scp",
            r"download",
            r"upload",
            r"sync",
            r"cp\s+.*\s+.*",
            r"mv\s+.*\s+.*",  # Large file operations
            # Network operations
            r"curl.*-o",
            r"wget",
            r"fetch",
            r"clone",
            # Media processing
            r"ffmpeg",
            r"convert",
            r"imagemagick",
            r"video",
            # Database operations
            r"migrate",
            r"backup",
            r"restore",
            r"dump",
            # Docker and containers
            r"docker\s+build",
            r"docker\s+pull",
            r"docker\s+run",
            r"kubernetes",
            r"kubectl",
            # Size indicators (large numbers often mean long operations)
            r"\d{4,}",
            r"--epochs\s+\d+",
            r"--batch-size\s+\d+",
        ]

        # Commands that are definitely fast
        self.fast_commands = {
            "ls",
            "cd",
            "pwd",
            "echo",
            "cat",
            "head",
            "tail",
            "grep",
            "awk",
            "sed",
            "sort",
            "uniq",
            "wc",
            "which",
            "type",
            "alias",
            "history",
            "ps",
            "kill",
            "jobs",
            "bg",
            "fg",
            "clear",
            "exit",
            "source",
            "export",
            "env",
            "date",
            "whoami",
            "hostname",
            "uname",
            "help",
            "man",
            "info",
            "less",
            "more",
            "vi",
            "vim",
            "nano",
            "git status",
            "git log",
            "git diff",
            "git branch",
        }

        # Patterns that indicate fast/info commands
        self.fast_patterns = [
            r"--help",
            r"-h\b",
            r"--version",
            r"-V\b",
            r"--list",
            r"status",
            r"info",
            r"--dry-run",
            r"--check",
        ]

        # Commands that are usually long-running
        self.slow_commands = {
            "python",
            "python3",
            "pip",
            "pip3",
            "pytest",
            "make",
            "npm install",
            "yarn install",
            "docker build",
            "rsync",
            "scp",
            "curl",
            "wget",
            "ffmpeg",
            "convert",
        }

    def _load_stats(self) -> dict:
        """Load command execution statistics from previous runs."""
        if self.stats_file.exists():
            try:
                with open(self.stats_file) as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                pass

        return {
            "command_durations": {},
            "wrap_decisions": {},
            "last_updated": time.time(),
        }

    def _save_stats(self):
        """Save command execution statistics."""
        try:
            with open(self.stats_file, "w") as f:
                json.dump(self.command_stats, f, indent=2)
        except OSError:
            pass  # Fail silently if we can't save stats

    def _command_hash(self, command: str) -> str:
        """Create a hash for a command pattern (ignoring specific arguments)."""
        # Normalize the command for pattern matching
        normalized = command.lower().strip()

        # Remove specific file paths and replace with placeholders
        import re

        normalized = re.sub(r"/[^\s]+", "<PATH>", normalized)
        normalized = re.sub(r"\d+", "<NUM>", normalized)
        normalized = re.sub(r"--\w+=[^\s]+", "<FLAG>", normalized)

        return hashlib.md5(normalized.encode()).hexdigest()[:12]

    def record_command_duration(self, command: str, duration: float, was_wrapped: bool):
        """Record how long a command took to execute."""
        cmd_hash = self._command_hash(command)

        if cmd_hash not in self.command_stats["command_durations"]:
            self.command_stats["command_durations"][cmd_hash] = {
                "command_pattern": command[:100],  # Store example
                "durations": [],
                "wrap_count": 0,
                "no_wrap_count": 0,
            }

        stats = self.command_stats["command_durations"][cmd_hash]
        stats["durations"].append(duration)

        # Keep only last 10 durations to avoid unbounded growth
        if len(stats["durations"]) > 10:
            stats["durations"] = stats["durations"][-10:]

        if was_wrapped:
            stats["wrap_count"] += 1
        else:
            stats["no_wrap_count"] += 1

        self.command_stats["last_updated"] = time.time()
        self._save_stats()

    def predict_duration(self, command: str) -> float:
        """Predict how long a command will take based on historical data."""
        cmd_hash = self._command_hash(command)

        if cmd_hash in self.command_stats["command_durations"]:
            durations = self.command_stats["command_durations"][cmd_hash]["durations"]
            if durations:
                # Return average of recent durations
                return sum(durations) / len(durations)

        # Fallback: analyze command patterns
        import re

        # Check for fast command patterns
        for fast_cmd in self.fast_commands:
            if command.strip().startswith(fast_cmd):
                return 0.1  # Very fast

        # Check for fast argument patterns
        for pattern in self.fast_patterns:
            if re.search(pattern, command.lower()):
                return 0.1  # Very fast

        # Check for slow command patterns
        for slow_cmd in self.slow_commands:
            if slow_cmd in command.lower():
                return 30.0  # Likely slow

        # Check for long-running patterns
        for pattern in self.long_running_patterns:
            if re.search(pattern, command.lower()):
                return 20.0  # Probably slow

        # Default prediction for unknown commands
        return 5.0

    def should_wrap_command(
        self, command: str, threshold: float = 10.0
    ) -> tuple[bool, str]:
        """
        Determine if a command should be wrapped based on prediction.

        Returns:
            (should_wrap, reason)
        """
        # Never wrap our own commands
        if "cursor_" in command:
            return False, "cursor internal command"

        # Check for explicit fast commands
        cmd_lower = command.lower().strip()
        for fast_cmd in self.fast_commands:
            if cmd_lower.startswith(fast_cmd):
                return False, f"known fast command: {fast_cmd}"

        # Check for fast patterns (help, version, etc.)
        import re

        for pattern in self.fast_patterns:
            if re.search(pattern, cmd_lower):
                return False, f"fast pattern detected: {pattern}"

        # Predict duration
        predicted_duration = self.predict_duration(command)

        if predicted_duration >= threshold:
            return (
                True,
                f"predicted duration: {predicted_duration:.1f}s >= {threshold}s",
            )

        # Check historical wrap success rate
        cmd_hash = self._command_hash(command)
        if cmd_hash in self.command_stats["command_durations"]:
            stats = self.command_stats["command_durations"][cmd_hash]
            total_runs = stats["wrap_count"] + stats["no_wrap_count"]
            if total_runs >= 3:  # Have enough data
                wrap_rate = stats["wrap_count"] / total_runs
                if wrap_rate > 0.7:  # Usually wrapped
                    return True, f"historically wrapped {wrap_rate:.1%} of the time"

        return False, f"predicted duration: {predicted_duration:.1f}s < {threshold}s"

    def analyze_command(self, command: str) -> dict:
        """Provide detailed analysis of a command."""
        predicted_duration = self.predict_duration(command)
        should_wrap, reason = self.should_wrap_command(command)
        cmd_hash = self._command_hash(command)

        analysis = {
            "command": command,
            "command_hash": cmd_hash,
            "predicted_duration": predicted_duration,
            "should_wrap": should_wrap,
            "reason": reason,
            "historical_data": None,
        }

        if cmd_hash in self.command_stats["command_durations"]:
            stats = self.command_stats["command_durations"][cmd_hash]
            analysis["historical_data"] = {
                "average_duration": sum(stats["durations"]) / len(stats["durations"])
                if stats["durations"]
                else None,
                "run_count": len(stats["durations"]),
                "wrap_rate": stats["wrap_count"]
                / (stats["wrap_count"] + stats["no_wrap_count"])
                if (stats["wrap_count"] + stats["no_wrap_count"]) > 0
                else 0,
            }

        return analysis


def main():
    """Command-line interface for the smart detector."""
    import argparse

    parser = argparse.ArgumentParser(description="Cursor Smart Command Detector")
    parser.add_argument("command", nargs="*", help="Command to analyze")
    parser.add_argument(
        "--analyze", action="store_true", help="Provide detailed analysis"
    )
    parser.add_argument(
        "--record",
        nargs=3,
        metavar=("COMMAND", "DURATION", "WRAPPED"),
        help="Record command execution (command, duration, was_wrapped)",
    )
    parser.add_argument("--stats", action="store_true", help="Show statistics")
    parser.add_argument("--project-root", default=".", help="Project root directory")

    args = parser.parse_args()

    detector = CursorSmartDetector(args.project_root)

    if args.record:
        command, duration_str, wrapped_str = args.record
        duration = float(duration_str)
        was_wrapped = wrapped_str.lower() in ("true", "1", "yes")
        detector.record_command_duration(command, duration, was_wrapped)
        print(f"Recorded: {command} took {duration}s (wrapped: {was_wrapped})")

    elif args.stats:
        print("Command Statistics:")
        print(json.dumps(detector.command_stats, indent=2))

    elif args.command:
        command = " ".join(args.command)

        if args.analyze:
            analysis = detector.analyze_command(command)
            print(json.dumps(analysis, indent=2))
        else:
            should_wrap, reason = detector.should_wrap_command(command)
            print(f"Should wrap: {should_wrap}")
            print(f"Reason: {reason}")

            # Exit with appropriate code for shell scripts
            sys.exit(0 if should_wrap else 1)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
