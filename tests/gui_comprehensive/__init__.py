"""
GUI Comprehensive Testing Package for Knowledge Chipper.

This package provides comprehensive automated testing for the Knowledge Chipper GUI,
covering all permutations of input types, GUI tabs, and processing operations.
"""

__version__ = "1.0.0"
__author__ = "Knowledge Chipper Development Team"

# Handle imports for both module and direct execution
try:
    from .test_framework import GUITestFramework
    from .gui_automation import GUIAutomation
    from .validation import OutputValidator
except ImportError:
    from test_framework import GUITestFramework
    from gui_automation import GUIAutomation
    from validation import OutputValidator

__all__ = [
    "GUITestFramework",
    "GUIAutomation", 
    "OutputValidator",
]
