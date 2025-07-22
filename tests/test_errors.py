"""
Tests for error handling system.
"""

from knowledge_system.errors import (
    # Base exceptions
    KnowledgeSystemError,
    # Configuration errors
    ConfigurationError,
    SettingsValidationError,
    ConfigFileError,
    # File system errors
    FileSystemError,
    FileNotFoundError,
    FilePermissionError,
    DirectoryError,
    FileFormatError,
    # Processing errors
    ProcessingError,
    TranscriptionError,
    SummarizationError,
    MOCGenerationError,
    PDFProcessingError,
    VideoProcessingError,
    # Network and API errors
    NetworkError,
    APIError,
    YouTubeAPIError,
    LLMAPIError,
    RateLimitError,
    AuthenticationError,
    # Resource errors
    ResourceError,
    MemoryError,
    DiskSpaceError,
    GPUError,
    StateError,
    DatabaseError,
    # Validation errors
    ValidationError,
    InputValidationError,
    URLValidationError,
    ModelValidationError,
    # Operation errors
    OperationError,
    WorkflowError,
    TimeoutError,
    CancellationError,
    DependencyError,
    # Monitoring errors
    MonitoringError,
    FileWatchError,
    PlaylistMonitorError,
    # Utility functions
    wrap_exception,
    handle_api_error,
    format_error_message,
)


class TestKnowledgeSystemError:
    """Test the base KnowledgeSystemError class."""

    def test_basic_initialization(self):
        """Test basic error initialization."""
        error = KnowledgeSystemError("Test error message")
        assert str(error) == "Test error message [KnowledgeSystemError]"
        assert error.message == "Test error message"
        assert error.error_code == "KnowledgeSystemError"
        assert error.context == {}
        assert error.cause is None

    def test_initialization_with_context(self):
        """Test error initialization with context."""
        context = {"file": "test.txt", "line": 42}
        error = KnowledgeSystemError(
            "Test error", error_code="TEST_001", context=context
        )

        assert error.message == "Test error"
        assert error.error_code == "TEST_001"
        assert error.context == context
        assert "file=test.txt" in str(error)
        assert "line=42" in str(error)

    def test_initialization_with_cause(self):
        """Test error initialization with cause."""
        original = ValueError("Original error")
        error = KnowledgeSystemError("Wrapped error", cause=original)

        assert error.cause == original
        assert error.message == "Wrapped error"

    def test_to_dict(self):
        """Test error serialization to dictionary."""
        context = {"component": "test"}
        original = RuntimeError("Original")
        error = KnowledgeSystemError(
            "Test error", error_code="TEST_002", context=context, cause=original
        )

        error_dict = error.to_dict()
        expected = {
            "error_type": "KnowledgeSystemError",
            "message": "Test error",
            "error_code": "TEST_002",
            "context": context,
            "cause": "Original",
        }

        assert error_dict == expected

    def test_str_formatting(self):
        """Test string formatting with various combinations."""
        # Just message
        error1 = KnowledgeSystemError("Simple message")
        assert str(error1) == "Simple message [KnowledgeSystemError]"

        # Message with custom error code
        error2 = KnowledgeSystemError("Message", error_code="CUSTOM")
        assert str(error2) == "Message [CUSTOM]"

        # Message with context
        error3 = KnowledgeSystemError("Message", context={"key": "value"})
        assert str(error3) == "Message [KnowledgeSystemError] (key=value)"

        # Full format
        error4 = KnowledgeSystemError(
            "Message", error_code="FULL", context={"a": 1, "b": 2}
        )
        result = str(error4)
        assert "Message [FULL]" in result
        assert "a=1" in result
        assert "b=2" in result


class TestConfigurationErrors:
    """Test configuration-related errors."""

    def test_configuration_error(self):
        """Test ConfigurationError."""
        error = ConfigurationError("Config is invalid")
        assert isinstance(error, KnowledgeSystemError)
        assert error.message == "Config is invalid"

    def test_settings_validation_error(self):
        """Test SettingsValidationError."""
        error = SettingsValidationError("Invalid setting value")
        assert isinstance(error, ConfigurationError)
        assert isinstance(error, KnowledgeSystemError)

    def test_config_file_error(self):
        """Test ConfigFileError."""
        error = ConfigFileError(
            "Cannot parse config file", context={"file": "settings.yaml", "line": 10}
        )
        assert isinstance(error, ConfigurationError)
        assert error.context["file"] == "settings.yaml"


class TestFileSystemErrors:
    """Test file system related errors."""

    def test_file_not_found_error(self):
        """Test FileNotFoundError."""
        error = FileNotFoundError(
            "File not found", context={"path": "/missing/file.txt"}
        )
        assert isinstance(error, FileSystemError)
        assert error.context["path"] == "/missing/file.txt"

    def test_file_permission_error(self):
        """Test FilePermissionError."""
        error = FilePermissionError("Permission denied")
        assert isinstance(error, FileSystemError)

    def test_directory_error(self):
        """Test DirectoryError."""
        error = DirectoryError("Cannot create directory")
        assert isinstance(error, FileSystemError)

    def test_file_format_error(self):
        """Test FileFormatError."""
        error = FileFormatError(
            "Unsupported file format", context={"format": "unknown", "file": "test.xyz"}
        )
        assert isinstance(error, FileSystemError)
        assert error.context["format"] == "unknown"


class TestProcessingErrors:
    """Test processing-related errors."""

    def test_transcription_error(self):
        """Test TranscriptionError."""
        error = TranscriptionError(
            "Transcription failed", context={"model": "whisper-base", "duration": 300}
        )
        assert isinstance(error, ProcessingError)
        assert error.context["model"] == "whisper-base"

    def test_summarization_error(self):
        """Test SummarizationError."""
        error = SummarizationError("LLM API failed")
        assert isinstance(error, ProcessingError)

    def test_moc_generation_error(self):
        """Test MOCGenerationError."""
        error = MOCGenerationError("MOC generation failed")
        assert isinstance(error, ProcessingError)

    def test_pdf_processing_error(self):
        """Test PDFProcessingError."""
        error = PDFProcessingError("Cannot extract text from PDF")
        assert isinstance(error, ProcessingError)

    def test_video_processing_error(self):
        """Test VideoProcessingError."""
        error = VideoProcessingError("Video codec not supported")
        assert isinstance(error, ProcessingError)


class TestAPIErrors:
    """Test API and network related errors."""

    def test_api_error_basic(self):
        """Test basic APIError."""
        error = APIError("API request failed")
        assert isinstance(error, NetworkError)
        assert error.status_code is None
        assert error.response_body is None

    def test_api_error_with_http_details(self):
        """Test APIError with HTTP details."""
        error = APIError(
            "Request failed",
            status_code=500,
            response_body='{"error": "Internal server error"}',
            context={"url": "https://api.example.com"},
        )

        assert error.status_code == 500
        assert error.response_body is not None
        assert '"error": "Internal server error"' in error.response_body
        assert error.context["status_code"] == 500
        assert error.context["response_body"] == '{"error": "Internal server error"}'

    def test_youtube_api_error(self):
        """Test YouTubeAPIError."""
        error = YouTubeAPIError("YouTube API quota exceeded", status_code=403)
        assert isinstance(error, APIError)
        assert error.status_code == 403

    def test_llm_api_error(self):
        """Test LLMAPIError with provider context."""
        error = LLMAPIError(
            "Model request failed", provider="openai", model="gpt-4", status_code=429
        )

        assert isinstance(error, APIError)
        assert error.provider == "openai"
        assert error.model == "gpt-4"
        assert error.context["provider"] == "openai"
        assert error.context["model"] == "gpt-4"

    def test_rate_limit_error(self):
        """Test RateLimitError with retry information."""
        error = RateLimitError(
    "Rate limit exceeded",
    retry_after=60,
     status_code=429)

        assert isinstance(error, APIError)
        assert error.retry_after == 60
        assert error.context["retry_after"] == 60

    def test_authentication_error(self):
        """Test AuthenticationError."""
        error = AuthenticationError(
            "Invalid API key", status_code=401, context={"provider": "openai"}
        )

        assert isinstance(error, APIError)
        assert error.status_code == 401
        assert error.context["provider"] == "openai"


class TestResourceErrors:
    """Test resource-related errors."""

    def test_memory_error(self):
        """Test MemoryError."""
        error = MemoryError(
            "Out of memory", context={"requested_mb": 2048, "available_mb": 512}
        )
        assert isinstance(error, ResourceError)
        assert error.context["requested_mb"] == 2048

    def test_disk_space_error(self):
        """Test DiskSpaceError."""
        error = DiskSpaceError("Insufficient disk space")
        assert isinstance(error, ResourceError)

    def test_gpu_error(self):
        """Test GPUError."""
        error = GPUError(
    "CUDA out of memory", context={
        "gpu_id": 0, "required_gb": 8})
        assert isinstance(error, ResourceError)
        assert error.context["gpu_id"] == 0

    def test_database_error(self):
        """Test DatabaseError."""
        error = DatabaseError("Database connection failed")
        assert isinstance(error, StateError)


class TestValidationErrors:
    """Test validation-related errors."""

    def test_input_validation_error(self):
        """Test InputValidationError with field context."""
        error = InputValidationError(
            "Invalid input value",
            field_name="email",
            field_value="invalid-email",
            context={"expected_format": "email"},
        )

        assert isinstance(error, ValidationError)
        assert error.field_name == "email"
        assert error.field_value == "invalid-email"
        assert error.context["field_name"] == "email"
        assert error.context["field_value"] == "invalid-email"

    def test_url_validation_error(self):
        """Test URLValidationError."""
        error = URLValidationError(
    "Invalid YouTube URL", context={
        "url": "not-a-url"})
        assert isinstance(error, ValidationError)

    def test_model_validation_error(self):
        """Test ModelValidationError."""
        error = ModelValidationError("Model validation failed")
        assert isinstance(error, ValidationError)


class TestOperationErrors:
    """Test operation-related errors."""

    def test_workflow_error(self):
        """Test WorkflowError."""
        error = WorkflowError(
            "Workflow step failed",
            context={"step": "transcription", "file": "audio.mp3"},
        )
        assert isinstance(error, OperationError)
        assert error.context["step"] == "transcription"

    def test_timeout_error(self):
        """Test TimeoutError with duration context."""
        error = TimeoutError(
            "Operation timed out",
            timeout_seconds=30.0,
            context={"operation": "download"},
        )

        assert isinstance(error, OperationError)
        assert error.timeout_seconds == 30.0
        assert error.context["timeout_seconds"] == 30.0

    def test_cancellation_error(self):
        """Test CancellationError."""
        error = CancellationError("Operation was cancelled")
        assert isinstance(error, OperationError)

    def test_dependency_error(self):
        """Test DependencyError."""
        error = DependencyError(
            "Missing required dependency",
            context={"dependency": "whisper", "version": ">=20231117"},
        )
        assert isinstance(error, OperationError)


class TestMonitoringErrors:
    """Test monitoring-related errors."""

    def test_file_watch_error(self):
        """Test FileWatchError."""
        error = FileWatchError(
    "Cannot watch directory", context={
        "path": "/watch/me"})
        assert isinstance(error, MonitoringError)

    def test_playlist_monitor_error(self):
        """Test PlaylistMonitorError."""
        error = PlaylistMonitorError("Playlist monitoring failed")
        assert isinstance(error, MonitoringError)


class TestUtilityFunctions:
    """Test utility functions for error handling."""

    def test_wrap_exception(self):
        """Test wrap_exception function."""
        original = ValueError("Original error")
        wrapped = wrap_exception(
            func_name="test_function",
            original_exception=original,
            context={"param": "value"},
        )

        assert isinstance(wrapped, KnowledgeSystemError)
        assert wrapped.cause == original
        assert "test_function" in wrapped.message
        assert "Original error" in wrapped.message
        assert wrapped.context["function"] == "test_function"
        assert wrapped.context["param"] == "value"

    def test_wrap_exception_custom_type(self):
        """Test wrap_exception with custom error type."""
        original = IOError("File not found")
        wrapped = wrap_exception(
            func_name="read_file",
            original_exception=original,
            error_type=FileSystemError,
        )

        assert isinstance(wrapped, FileSystemError)
        assert wrapped.cause == original

    def test_handle_api_error_authentication(self):
        """Test handle_api_error for authentication errors."""

        # Mock response object
        class MockResponse:
            status_code = 401
            text = "Unauthorized"

        response = MockResponse()
        error = handle_api_error(
            response=response, provider="openai", operation="chat_completion"
        )

        assert isinstance(error, AuthenticationError)
        assert error.status_code == 401
        assert error.response_body == "Unauthorized"
        assert error.context["provider"] == "openai"

    def test_handle_api_error_rate_limit(self):
        """Test handle_api_error for rate limit errors."""

        class MockResponse:
            status_code = 429
            text = "Rate limit exceeded"

        response = MockResponse()
        error = handle_api_error(
            response=response,
            provider="claude",
            operation="text_generation",
            context={"model": "claude-3"},
        )

        assert isinstance(error, RateLimitError)
        assert error.status_code == 429
        assert error.context["model"] == "claude-3"

    def test_handle_api_error_generic(self):
        """Test handle_api_error for generic API errors."""

        class MockResponse:
            status_code = 500
            text = "Internal server error"

        response = MockResponse()
        error = handle_api_error(
            response=response, provider="youtube", operation="fetch_metadata"
        )

        assert isinstance(error, APIError)
        assert not isinstance(error, AuthenticationError)
        assert not isinstance(error, RateLimitError)
        assert error.status_code == 500

    def test_format_error_message_knowledge_system_error(self):
        """Test format_error_message with KnowledgeSystemError."""
        original = ValueError("Original cause")
        error = KnowledgeSystemError(
            "Test error", context={"key": "value"}, cause=original
        )

        # With context and cause
        message = format_error_message(
    error, include_context=True, include_cause=True)
        assert "Test error" in message
        assert "key=value" in message
        assert "Caused by: Original cause" in message

        # Without cause
        message = format_error_message(error, include_cause=False)
        assert "Test error" in message
        assert "Caused by:" not in message

    def test_format_error_message_standard_exception(self):
        """Test format_error_message with standard exception."""
        error = ValueError("Standard error")
        message = format_error_message(error)
        assert message == "Standard error"

    def test_inheritance_hierarchy(self):
        """Test that exception inheritance hierarchy is correct."""
        # Test configuration errors
        assert issubclass(SettingsValidationError, ConfigurationError)
        assert issubclass(ConfigurationError, KnowledgeSystemError)

        # Test processing errors
        assert issubclass(TranscriptionError, ProcessingError)
        assert issubclass(ProcessingError, KnowledgeSystemError)

        # Test API errors
        assert issubclass(YouTubeAPIError, APIError)
        assert issubclass(LLMAPIError, APIError)
        assert issubclass(APIError, NetworkError)
        assert issubclass(NetworkError, KnowledgeSystemError)

        # Test all inherit from base
        error_types = [
            ConfigurationError,
            FileSystemError,
            ProcessingError,
            NetworkError,
            ResourceError,
            ValidationError,
            OperationError,
            MonitoringError,
        ]

        for error_type in error_types:
            assert issubclass(error_type, KnowledgeSystemError)


class TestSpecificErrors:
    """Test specific error types."""

    def test_timeout_error(self):
        """Test TimeoutError with duration context."""
        error = TimeoutError(
            "Operation timed out",
            timeout_seconds=30.0,
            context={"operation": "download"},
        )

        assert isinstance(error, OperationError)
        assert error.timeout_seconds == 30.0
        assert error.context["timeout_seconds"] == 30.0

    def test_file_watch_error(self):
        """Test FileWatchError."""
        error = FileWatchError(
    "Cannot watch directory", context={
        "path": "/watch/me"})
        assert isinstance(error, MonitoringError)
        assert error.context["path"] == "/watch/me"
