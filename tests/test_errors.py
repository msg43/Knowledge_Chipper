"""Test error handling modules."""

from knowledge_system.errors import (
    ConfigurationError,
    KnowledgeSystemError,
    ProcessingError,
    ValidationError,
)


def test_knowledge_system_error():
    """Test base KnowledgeSystemError."""
    error = KnowledgeSystemError("Test error")
    assert str(error) == "Test error [KnowledgeSystemError]"
    assert isinstance(error, Exception)


def test_processing_error():
    """Test ProcessingError."""
    error = ProcessingError("Processing failed")
    assert str(error) == "Processing failed [ProcessingError]"
    assert isinstance(error, KnowledgeSystemError)


def test_configuration_error():
    """Test ConfigurationError."""
    error = ConfigurationError("Config invalid")
    assert str(error) == "Config invalid [ConfigurationError]"
    assert isinstance(error, KnowledgeSystemError)


def test_validation_error():
    """Test ValidationError."""
    error = ValidationError("Validation failed")
    assert str(error) == "Validation failed [ValidationError]"
    assert isinstance(error, KnowledgeSystemError)
