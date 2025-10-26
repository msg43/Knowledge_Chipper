"""
Comprehensive Real Testing Suite - Main Runner

This is the single entry point for all real GUI + real data testing.
It replaces all the redundant test files with a focused, comprehensive suite.

Usage:
    python -m pytest tests/comprehensive/ -v
    python -m pytest tests/comprehensive/test_real_gui_complete.py -v
    python -m pytest tests/comprehensive/test_real_integration_complete.py -v
    python -m pytest tests/comprehensive/test_real_system2_complete.py -v

Requirements:
- Ollama running with qwen2.5:7b-instruct model
- Real test files available (KenRogoff_Transcript.rtf, etc.)
- GUI dependencies installed
"""

import os
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

# Set testing mode
os.environ["KNOWLEDGE_CHIPPER_TESTING_MODE"] = "1"
os.environ["QT_QPA_PLATFORM"] = "offscreen"

# Import test modules
from .test_real_gui_complete import *
from .test_real_integration_complete import *
from .test_real_system2_complete import *

# Test discovery
__all__ = [
    "TestRealGUITranscription",
    "TestRealGUISummarization",
    "TestRealGUIWorkflows",
    "TestRealGUITabNavigation",
    "TestRealFileProcessing",
    "TestRealSystem2Mining",
    "TestRealUnifiedHCEStorage",
    "TestRealDatabaseValidation",
    "TestRealPerformanceMetrics",
    "TestRealJobCreation",
    "TestRealJobExecution",
    "TestRealStatusTracking",
    "TestRealLLMTracking",
    "TestRealErrorHandling",
    "TestRealSingletonBehavior",
    "TestRealMiningIntegration",
    "TestRealDatabaseOperations",
]
