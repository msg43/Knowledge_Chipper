""" Common utilities for CLI commands to avoid duplication.
Common utilities for CLI commands to avoid duplication.

Shared classes, decorators, and utilities used across command modules.
"""

from typing import Optional

import click
from rich.console import Console

from ..config import Settings, get_settings
from ..logger import get_logger

# Shared console and logger
console = Console()
logger = get_logger(__name__)


class CLIContext:
    """ Context object for CLI commands."""

    def __init__(self) -> None:
        """ Initialize CLI context."""
        self.settings: Settings | None = None
        self.verbose: bool = False
        self.quiet: bool = False

    def get_settings(self) -> Settings:
        """ Get or initialize settings."""
        if self.settings is None:
            self.settings = get_settings()
        return self.settings


# Shared pass_context decorator
pass_context = click.make_pass_decorator(CLIContext, ensure=True)
