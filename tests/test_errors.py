"""Test error handling modules."""
import pytest
from knowledge_system.errors import (
    KnowledgeSystemError,
    ProcessingError,
    ConfigurationError,
    ValidationError
)


def test_knowledge_system_error():
    """Test base KnowledgeSystemError."""
    error = KnowledgeSystemError("Test error")
    assert str(error) == "Test error"
    assert isinstance(error, Exception)


def test_processing_error():
    """Test ProcessingError."""
    error = ProcessingError("Processing failed")
    assert str(error) == "Processing failed"
    assert isinstance(error, KnowledgeSystemError)


def test_configuration_error():
    """Test ConfigurationError."""
    error = ConfigurationError("Config invalid")
    assert str(error) == "Config invalid"
    assert isinstance(error, KnowledgeSystemError)


def test_validation_error():
    """Test ValidationError."""
    error = ValidationError("Validation failed")
    assert str(error) == "Validation failed"
    assert isinstance(error, KnowledgeSystemError)
