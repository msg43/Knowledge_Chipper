"""Test logger functionality."""

from knowledge_system.logger import get_logger


def test_get_logger():
    """Test that logger can be created."""
    logger = get_logger("test")
    assert logger is not None
    # Loguru logger doesn't have a name attribute, but it should be bound
    assert hasattr(logger, "bind")


def test_logger_with_module():
    """Test logger with module name."""
    logger = get_logger(__name__)
    assert logger is not None
    # Test that we can use the logger (it has logging methods)
    assert hasattr(logger, "info")
    assert hasattr(logger, "error")
