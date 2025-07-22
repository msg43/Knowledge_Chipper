"""
Tests for the base processor class and processor registry.
"""

from pathlib import Path
from typing import Any, List
from unittest.mock import patch

import pytest

from knowledge_system.errors import ProcessingError, ValidationError
from knowledge_system.processors.base import (
    BaseProcessor,
    ProcessorRegistry,
    ProcessorResult,
    get_processor,
    get_processor_for_file,
    register_processor,
)
from knowledge_system.processors.registry import (
    get_all_processor_stats,
    list_processors,
)


class TestProcessorResult:
    """Test ProcessorResult class."""

    def test_init_success(self) -> None:
        """Test successful result initialization."""
        result = ProcessorResult(
            success=True,
            data="test data",
            metadata={"key": "value"},
            warnings=["warning1"],
        )

        assert result.success is True
        assert result.data == "test data"
        assert result.metadata == {"key": "value"}
        assert result.errors == []
        assert result.warnings == ["warning1"]
        assert isinstance(result.timestamp, float)

    def test_init_failure(self) -> None:
        """Test failure result initialization."""
        result = ProcessorResult(success=False, errors=["error1", "error2"])

        assert result.success is False
        assert result.data is None
        assert result.metadata == {}
        assert result.errors == ["error1", "error2"]
        assert result.warnings == []

    def test_bool_conversion(self) -> None:
        """Test boolean conversion."""
        success_result = ProcessorResult(success=True)
        failure_result = ProcessorResult(success=False)

        assert bool(success_result) is True
        assert bool(failure_result) is False

    def test_string_representation(self) -> None:
        """Test string representation."""
        success_result = ProcessorResult(success=True)
        assert str(success_result) == "ProcessorResult[SUCCESS]"

        failure_result = ProcessorResult(
            success=False, errors=["error1"], warnings=["warning1"]
        )
        assert str(
            failure_result) == "ProcessorResult[FAILED (1 errors) (1 warnings)]"

    def test_to_dict(self) -> None:
        """Test dictionary conversion."""
        result = ProcessorResult(
            success=True,
            data="test",
            metadata={"key": "value"},
            errors=["error"],
            warnings=["warning"],
        )

        result_dict = result.to_dict()

        assert result_dict["success"] is True
        assert result_dict["data"] == "test"
        assert result_dict["metadata"] == {"key": "value"}
        assert result_dict["errors"] == ["error"]
        assert result_dict["warnings"] == ["warning"]
        assert "timestamp" in result_dict


class MockProcessor(BaseProcessor):
    """Mock processor for testing."""

    def __init__(self, name: str = "MockProcessor", should_fail: bool = False):
        super().__init__(name)
        self.should_fail = should_fail
        self.process_calls = []
        self.validate_calls = []

    def process(self, input_data: Any, **kwargs: Any) -> ProcessorResult:
        """Mock process method."""
        self.process_calls.append((input_data, kwargs))

        if self.should_fail:
            return ProcessorResult(success=False, errors=[
                                   "Mock processing failed"])

        return ProcessorResult(
            success=True, data=f"processed: {input_data}", metadata={"mock": True}
        )

    def validate_input(self, input_data: Any) -> bool:
        """Mock validation method."""
        self.validate_calls.append(input_data)
        return input_data != "invalid"

    @property
    def supported_formats(self) -> List[str]:
        """Mock supported formats."""
        return [".txt", ".md"]


class TestBaseProcessor:
    """Test BaseProcessor abstract class."""

    def test_init(self) -> None:
        """Test processor initialization."""
        processor = MockProcessor("TestProcessor")

        assert processor.name == "TestProcessor"
        assert processor.logger is not None
        assert processor.settings is not None
        assert processor._stats["processed_count"] == 0

    def test_init_default_name(self) -> None:
        """Test processor initialization with default name."""
        processor = MockProcessor()
        assert processor.name == "MockProcessor"

    def test_can_process(self) -> None:
        """Test can_process method."""
        processor = MockProcessor()

        assert processor.can_process("test.txt") is True
        assert processor.can_process("test.md") is True
        assert processor.can_process("test.TXT") is True  # Case insensitive
        assert processor.can_process("test.pdf") is False
        assert processor.can_process(Path("test.txt")) is True

    def test_process_safe_success(self) -> None:
        """Test successful processing with process_safe."""
        processor = MockProcessor()

        result = processor.process_safe("test input", param="value")

        assert result.success is True
        assert result.data == "processed: test input"
        assert result.metadata["processor"] == "MockProcessor"
        assert result.metadata["mock"] is True
        assert "duration" in result.metadata

        # Check calls were made
        assert len(processor.validate_calls) == 1
        assert len(processor.process_calls) == 1
        assert processor.process_calls[0] == ("test input", {"param": "value"})

    def test_process_safe_validation_failure(self) -> None:
        """Test processing with validation failure."""
        processor = MockProcessor()

        result = processor.process_safe("invalid")

        assert result.success is False
        assert "Input validation failed" in result.errors[0]
        assert result.metadata["processor"] == "MockProcessor"

        # Validate was called but process was not
        assert len(processor.validate_calls) == 1
        assert len(processor.process_calls) == 0

    def test_process_safe_processing_failure(self) -> None:
        """Test processing with processing failure."""
        processor = MockProcessor(should_fail=True)

        result = processor.process_safe("test input")

        assert result.success is False
        assert "Mock processing failed" in result.errors
        assert result.metadata["processor"] == "MockProcessor"

    def test_process_safe_exception_handling(self) -> None:
        """Test exception handling in process_safe."""
        processor = MockProcessor()

        # Mock the process method to raise an exception
        def failing_process(input_data, **kwargs):
            raise ValueError("Test exception")

        processor.process = failing_process

        with pytest.raises(ProcessingError) as exc_info:
            processor.process_safe("test input")

        assert "Unexpected error in MockProcessor" in str(exc_info.value)
        assert exc_info.value.context["processor"] == "MockProcessor"

    def test_process_safe_known_exception_passthrough(self) -> None:
        """Test that known exceptions are passed through."""
        processor = MockProcessor()

        def failing_process(input_data, **kwargs):
            raise ValidationError("Test validation error")

        processor.process = failing_process

        with pytest.raises(ValidationError):
            processor.process_safe("test input")

    def test_stats_tracking(self) -> None:
        """Test statistics tracking."""
        processor = MockProcessor()

        # Initial stats
        stats = processor.get_stats()
        assert stats["processed_count"] == 0
        assert stats["success_count"] == 0
        assert stats["error_count"] == 0
        assert stats["success_rate"] == 0.0
        assert stats["average_processing_time"] == 0.0

        # Process some data
        processor.process_safe("test1")
        processor.process_safe("invalid")  # Should fail validation
        processor.process_safe("test2")

        stats = processor.get_stats()
        assert stats["processed_count"] == 3
        assert stats["success_count"] == 2
        assert stats["error_count"] == 1
        assert stats["success_rate"] == 2 / 3
        assert stats["average_processing_time"] > 0

    def test_reset_stats(self) -> None:
        """Test statistics reset."""
        processor = MockProcessor()

        # Process some data
        processor.process_safe("test")

        # Reset stats
        processor.reset_stats()

        stats = processor.get_stats()
        assert stats["processed_count"] == 0
        assert stats["success_count"] == 0
        assert stats["error_count"] == 0

    def test_string_representations(self) -> None:
        """Test string representations."""
        processor = MockProcessor("TestProcessor")

        assert str(processor) == "MockProcessor(name=TestProcessor)"

        # Process some data to get stats
        processor.process_safe("test")

        repr_str = repr(processor)
        assert "MockProcessor(" in repr_str
        assert "name=TestProcessor" in repr_str
        assert "processed=1" in repr_str
        assert "success_rate=100.00%" in repr_str


class TestProcessorRegistry:
    """Test ProcessorRegistry class."""

    def test_init(self) -> None:
        """Test registry initialization."""
        registry = ProcessorRegistry()
        assert registry._processors == {}
        assert registry.logger is not None

    def test_register_processor(self) -> None:
        """Test processor registration."""
        registry = ProcessorRegistry()
        processor = MockProcessor("TestProcessor")

        registry.register(processor)

        assert "TestProcessor" in registry._processors
        assert registry.get("TestProcessor") is processor

    def test_register_processor_with_name_override(self) -> None:
        """Test processor registration with name override."""
        registry = ProcessorRegistry()
        processor = MockProcessor("TestProcessor")

        registry.register(processor, "CustomName")

        assert "CustomName" in registry._processors
        assert registry.get("CustomName") is processor
        assert registry.get("TestProcessor") is None

    def test_register_processor_overwrite_warning(self) -> None:
        """Test warning when overwriting processor."""
        registry = ProcessorRegistry()
        processor1 = MockProcessor("TestProcessor")
        processor2 = MockProcessor("TestProcessor")

        registry.register(processor1)

        with patch.object(registry.logger, "warning") as mock_warning:
            registry.register(processor2)
            mock_warning.assert_called_once()

    def test_get_nonexistent_processor(self) -> None:
        """Test getting non-existent processor."""
        registry = ProcessorRegistry()
        assert registry.get("NonExistent") is None

    def test_get_for_file(self) -> None:
        """Test getting processor for file."""
        registry = ProcessorRegistry()
        processor = MockProcessor("TestProcessor")
        registry.register(processor)

        # Should find processor for supported format
        found_processor = registry.get_for_file("test.txt")
        assert found_processor is processor

        # Should not find processor for unsupported format
        found_processor = registry.get_for_file("test.pdf")
        assert found_processor is None

    def test_list_processors(self) -> None:
        """Test listing processors."""
        registry = ProcessorRegistry()
        processor1 = MockProcessor("Processor1")
        processor2 = MockProcessor("Processor2")

        registry.register(processor1)
        registry.register(processor2)

        processors = registry.list_processors()
        assert set(processors) == {"Processor1", "Processor2"}

    def test_get_all_stats(self) -> None:
        """Test getting all processor statistics."""
        registry = ProcessorRegistry()
        processor1 = MockProcessor("Processor1")
        processor2 = MockProcessor("Processor2")

        registry.register(processor1)
        registry.register(processor2)

        # Process some data
        processor1.process_safe("test")
        processor2.process_safe("test")

        all_stats = registry.get_all_stats()

        assert "Processor1" in all_stats
        assert "Processor2" in all_stats
        assert all_stats["Processor1"]["processed_count"] == 1
        assert all_stats["Processor2"]["processed_count"] == 1


class TestGlobalRegistry:
    """Test global registry functions."""

    def setup_method(self) -> None:
        """Setup for each test method."""
        # Clear global registry
        from knowledge_system.processors.base import _registry

        _registry._processors.clear()

    def test_register_processor(self) -> None:
        """Test global processor registration."""
        processor = MockProcessor("GlobalProcessor")

        register_processor(processor)

        assert get_processor("GlobalProcessor") is processor

    def test_get_processor_for_file(self) -> None:
        """Test global get processor for file."""
        processor = MockProcessor("GlobalProcessor")
        register_processor(processor)

        found_processor = get_processor_for_file("test.txt")
        assert found_processor is processor

    def test_list_processors(self) -> None:
        """Test global list processors."""
        processor1 = MockProcessor("Global1")
        processor2 = MockProcessor("Global2")

        register_processor(processor1)
        register_processor(processor2)

        processors = list_processors()
        assert set(processors) == {"Global1", "Global2"}

    def test_get_all_processor_stats(self) -> None:
        """Test global get all processor stats."""
        processor = MockProcessor("GlobalProcessor")
        register_processor(processor)

        # Process some data
        processor.process_safe("test")

        all_stats = get_all_processor_stats()
        assert "GlobalProcessor" in all_stats
        assert all_stats["GlobalProcessor"]["processed_count"] == 1


class TestAbstractMethods:
    """Test that abstract methods must be implemented."""

    def test_cannot_instantiate_base_processor(self) -> None:
        """Test that BaseProcessor cannot be instantiated directly."""
        with pytest.raises(TypeError):
            BaseProcessor()  # type: ignore

    def test_must_implement_abstract_methods(self) -> None:
        """Test that subclasses must implement abstract methods."""

        class IncompleteProcessor(BaseProcessor):
            pass

        with pytest.raises(TypeError):
            IncompleteProcessor()  # type: ignore


def test_processor_registry():
    from knowledge_system.processors import registry

    class DummyProcessor:
        pass

    # Register dummy
    registry.register_processor(
    DummyProcessor,
    extensions=[".dummy"],
     name="Dummy")
    # Lookup by extension
    assert registry.get_processor_for_input("file.dummy") == DummyProcessor

    # Lookup by URL pattern
    class DummyURLProcessor:
        pass

    registry.register_processor(
        DummyURLProcessor, url_patterns=[r"https://dummy.com/.*"], name="DummyURL"
    )
    assert (
        registry.get_processor_for_input(
            "https://dummy.com/abc") == DummyURLProcessor
    )
    # List processors
    names = registry.list_processors()
    assert "Dummy" in names
    assert "DummyURL" in names
