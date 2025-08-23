"""Test logger functionality."""
import pytest
from knowledge_system.logger import get_logger


def test_get_logger():
    """Test that logger can be created."""
    logger = get_logger("test")
    assert logger is not None
    assert logger.name == "test"


def test_logger_with_module():
    """Test logger with module name."""
    logger = get_logger(__name__)
    assert logger is not None
    assert __name__ in logger.name
