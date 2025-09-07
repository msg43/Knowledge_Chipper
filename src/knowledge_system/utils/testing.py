"""
Utilities for testing mode detection and management.

Provides a unified way to check if the application is running in testing mode
across all components of the Knowledge Chipper system.
"""

import os
from typing import Optional

from PyQt6.QtWidgets import QApplication


def is_testing_mode() -> bool:
    """
    Check if the application is currently running in testing mode.

    This function checks both the environment variable and QApplication property
    to provide a unified testing mode detection across the entire codebase.

    Returns:
        bool: True if testing mode is active, False otherwise
    """
    # Check environment variable (primary method)
    env_testing = os.environ.get("KNOWLEDGE_CHIPPER_TESTING_MODE") == "1"

    # Check QApplication property (fallback for GUI tests)
    app_testing = False
    app = QApplication.instance()
    if app:
        app_testing = app.property("KNOWLEDGE_CHIPPER_TESTING") == "true"

    # Return True if either flag is set
    return env_testing or app_testing


def get_testing_mode_info() -> dict:
    """
    Get detailed information about testing mode flags.

    Returns:
        dict: Information about testing mode detection
    """
    env_flag = os.environ.get("KNOWLEDGE_CHIPPER_TESTING_MODE", "NOT_SET")
    app_flag = "NOT_SET"

    app = QApplication.instance()
    if app:
        app_property = app.property("KNOWLEDGE_CHIPPER_TESTING")
        app_flag = str(app_property) if app_property else "NOT_SET"

    return {
        "is_testing": is_testing_mode(),
        "env_flag": env_flag,
        "app_flag": app_flag,
        "app_instance_exists": app is not None,
    }


def set_testing_mode(enabled: bool) -> None:
    """
    Set testing mode using both environment variable and QApplication property.

    Args:
        enabled: Whether to enable testing mode
    """
    if enabled:
        os.environ["KNOWLEDGE_CHIPPER_TESTING_MODE"] = "1"
        app = QApplication.instance()
        if app:
            app.setProperty("KNOWLEDGE_CHIPPER_TESTING", "true")
    else:
        os.environ.pop("KNOWLEDGE_CHIPPER_TESTING_MODE", None)
        app = QApplication.instance()
        if app:
            app.setProperty("KNOWLEDGE_CHIPPER_TESTING", "false")
