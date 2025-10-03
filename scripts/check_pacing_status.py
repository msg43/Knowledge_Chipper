#!/usr/bin/env python3
"""
Check Intelligent Pacing Status

This script provides real-time monitoring of the intelligent pacing system,
showing download and processing pipeline status.

Usage:
    python scripts/check_pacing_status.py [--detailed] [--monitor] [--interval SECONDS]
"""

import argparse
import sys
import time
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from knowledge_system.utils.pacing_monitor import (
    get_pacing_monitor,
    print_current_status,
    print_detailed_report,
)


def main():
    parser = argparse.ArgumentParser(description="Check intelligent pacing status")
    parser.add_argument("--detailed", action="store_true", help="Show detailed report")
    parser.add_argument(
        "--monitor", action="store_true", help="Start continuous monitoring"
    )
    parser.add_argument(
        "--interval", type=int, default=30, help="Monitoring interval in seconds"
    )

    args = parser.parse_args()

    try:
        if args.monitor:
            print("Starting continuous pipeline monitoring...")
            print("Press Ctrl+C to stop")
            print("-" * 60)

            monitor = get_pacing_monitor()
            monitor.monitor_continuously(interval_seconds=args.interval)
        elif args.detailed:
            print_detailed_report()
        else:
            print_current_status()

    except KeyboardInterrupt:
        print("\nMonitoring stopped by user")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
