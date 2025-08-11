"""
Tests for configuration management system.
"""

import os
import tempfile
from pathlib import Path

import pytest
import yaml

from knowledge_system.config import (
    APIKeysConfig,
    AppConfig,
    LLMConfig,
    MOCConfig,
    MonitoringConfig,
    PathsConfig,
    ProcessingConfig,
    Settings,
    TranscriptionConfig,
)
from knowledge_system.config import get_settings
from knowledge_system.config import get_settings as reload_settings


class TestAppConfig:
    """Test AppConfig model."""

    def test_default_values(self):
        """Test default configuration values."""
        config = AppConfig()
        assert config.name == "Knowledge_Chipper"
        assert config.version == "0.1.1"
        assert config.debug is False

    def test_custom_values(self):
        """Test custom configuration values."""
        config = AppConfig(name="Test App", version="1.0.0", debug=True)
        assert config.name == "Test App"
        assert config.version == "1.0.0"
        assert config.debug is True


class TestPathsConfig:
    """Test PathsConfig model."""

    def test_default_paths(self):
        """Test default path configuration."""
        config = PathsConfig()
        assert "KnowledgeSystem" in config.data_dir
        assert "output" in config.output_dir
        assert "cache" in config.cache_dir
        assert config.logs_dir == "./logs"

    def test_path_expansion(self):
        """Test path expansion for home directory."""
        config = PathsConfig(data_dir="~/test", output_dir="/absolute/path")
        # Should expand ~ but not change absolute paths
        assert not config.data_dir.startswith("~")
        assert config.output_dir == "/absolute/path"


class TestTranscriptionConfig:
    """Test TranscriptionConfig model."""

    def test_default_values(self):
        """Test default transcription settings."""
        config = TranscriptionConfig()
        assert config.whisper_model == "base"
        assert config.use_gpu is True
        assert config.diarization is False
        assert config.min_words == 50

    def test_valid_whisper_models(self):
        """Test valid whisper model validation."""
        valid_models = [
            "tiny",
            "base",
            "small",
            "medium",
            "large",
            "large-v2",
            "large-v3",
        ]
        for model in valid_models:
            config = TranscriptionConfig(whisper_model=model)
            assert config.whisper_model == model

    def test_invalid_whisper_model(self):
        """Test invalid whisper model raises validation error."""
        with pytest.raises(ValueError):
            TranscriptionConfig(whisper_model="invalid")

    def test_min_words_validation(self):
        """Test minimum words validation."""
        config = TranscriptionConfig(min_words=100)
        assert config.min_words == 100

        with pytest.raises(ValueError):
            TranscriptionConfig(min_words=0)


class TestLLMConfig:
    """Test LLMConfig model."""

    def test_default_values(self):
        """Test default LLM settings."""
        config = LLMConfig()
        assert config.provider == "openai"
        assert config.model == "gpt-4"
        assert config.max_tokens == 10000
        assert config.temperature == 0.1

    def test_valid_providers(self):
        """Test valid provider validation."""
        valid_providers = ["openai", "claude", "local"]
        for provider in valid_providers:
            config = LLMConfig(provider=provider)
            assert config.provider == provider

    def test_invalid_provider(self):
        """Test invalid provider raises validation error."""
        with pytest.raises(ValueError):
            LLMConfig(provider="invalid")

    def test_token_limits(self):
        """Test token limit validation."""
        config = LLMConfig(max_tokens=8000)
        assert config.max_tokens == 8000

        with pytest.raises(ValueError):
            LLMConfig(max_tokens=0)

        with pytest.raises(ValueError):
            LLMConfig(max_tokens=50000)

    def test_temperature_limits(self):
        """Test temperature validation."""
        config = LLMConfig(temperature=0.5)
        assert config.temperature == 0.5

        with pytest.raises(ValueError):
            LLMConfig(temperature=-0.1)

        with pytest.raises(ValueError):
            LLMConfig(temperature=2.1)


class TestSettings:
    """Test main Settings class."""

    def test_default_initialization(self):
        """Test default settings initialization."""
        settings = Settings()
        assert isinstance(settings.app, AppConfig)
        assert isinstance(settings.paths, PathsConfig)
        assert isinstance(settings.transcription, TranscriptionConfig)
        assert isinstance(settings.llm, LLMConfig)
        assert isinstance(settings.api_keys, APIKeysConfig)
        assert isinstance(settings.processing, ProcessingConfig)
        assert isinstance(settings.moc, MOCConfig)
        assert isinstance(settings.monitoring, MonitoringConfig)

    def test_load_from_yaml_file(self):
        """Test loading settings from YAML file."""
        # Create temporary YAML file
        config_data = {
            "app": {"name": "Test App", "debug": True},
            "transcription": {"whisper_model": "large", "min_words": 100},
            "llm": {"provider": "claude", "model": "claude-3"},
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(config_data, f)
            temp_path = f.name

        try:
            settings = Settings(config_path=temp_path)
            assert settings.app.name == "Test App"
            assert settings.app.debug is True
            assert settings.transcription.whisper_model == "large"
            assert settings.transcription.min_words == 100
            assert settings.llm.provider == "claude"
            assert settings.llm.model == "claude-3"
        finally:
            os.unlink(temp_path)

    def test_load_nonexistent_file(self):
        """Test loading from nonexistent file raises error."""
        with pytest.raises(FileNotFoundError):
            Settings(config_path="nonexistent.yaml")

    def test_load_invalid_yaml(self):
        """Test loading invalid YAML raises error."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("invalid: yaml: content: [\n")
            temp_path = f.name

        try:
            with pytest.raises(ValueError):
                Settings(config_path=temp_path)
        finally:
            os.unlink(temp_path)

    def test_save_to_file(self):
        """Test saving settings to file."""
        settings = Settings()
        settings.app.name = "Modified App"
        settings.transcription.whisper_model = "large"

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            temp_path = f.name

        try:
            settings.save_to_file(temp_path)

            # Verify file was created and contains correct data
            assert Path(temp_path).exists()

            with open(temp_path) as f:
                data = yaml.safe_load(f)

            assert data["app"]["name"] == "Modified App"
            assert data["transcription"]["whisper_model"] == "large"
        finally:
            if Path(temp_path).exists():
                os.unlink(temp_path)

    def test_get_nested(self):
        """Test getting nested configuration values."""
        settings = Settings()

        # Test valid nested access
        assert settings.get_nested("app.name") == "Knowledge_Chipper"
        assert settings.get_nested("transcription.whisper_model") == "base"
        assert settings.get_nested("llm.max_tokens") == 10000

        # Test invalid nested access with default
        assert settings.get_nested("invalid.key", "default") == "default"
        assert settings.get_nested("app.invalid", None) is None

    def test_set_nested(self):
        """Test setting nested configuration values."""
        settings = Settings()

        # Test valid nested setting
        settings.set_nested("app.name", "New Name")
        assert settings.app.name == "New Name"

        settings.set_nested("transcription.min_words", 200)
        assert settings.transcription.min_words == 200

        # Test invalid nested setting
        with pytest.raises(KeyError):
            settings.set_nested("invalid.key", "value")

    def test_create_directories(self):
        """Test directory creation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            settings = Settings()
            settings.paths.data_dir = str(temp_path / "data")
            settings.paths.output_dir = str(temp_path / "output")
            settings.paths.cache_dir = str(temp_path / "cache")
            settings.paths.logs_dir = str(temp_path / "logs")

            settings.create_directories()

            assert (temp_path / "data").exists()
            assert (temp_path / "output").exists()
            assert (temp_path / "cache").exists()
            assert (temp_path / "logs").exists()

    def test_validate_api_keys(self):
        """Test API key validation."""
        settings = Settings()

        # Test OpenAI provider without key
        settings.llm.provider = "openai"
        validation = settings.validate_api_keys()
        assert validation["openai"] is False

        # Test OpenAI provider with key
        settings.api_keys.openai_api_key = "test-key"
        validation = settings.validate_api_keys()
        assert validation["openai"] is True

        # Test Claude provider
        settings.llm.provider = "claude"
        validation = settings.validate_api_keys()
        assert validation["anthropic"] is False

        # Test local provider (no key needed)
        settings.llm.provider = "local"
        validation = settings.validate_api_keys()
        assert validation["local"] is True

    def test_environment_variable_expansion(self):
        """Test environment variable expansion in YAML."""
        # Set environment variable
        os.environ["TEST_VALUE"] = "expanded_value"

        config_data = {
            "app": {"name": "${TEST_VALUE}"},
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(config_data, f)
            temp_path = f.name

        try:
            settings = Settings(config_path=temp_path)
            assert settings.app.name == "expanded_value"
        finally:
            os.unlink(temp_path)
            del os.environ["TEST_VALUE"]

    def test_api_keys_from_environment(self):
        """Test loading API keys from environment variables."""
        # Set environment variables
        os.environ["OPENAI_API_KEY"] = "test-openai-key"
        os.environ["ANTHROPIC_API_KEY"] = "test-anthropic-key"

        try:
            settings = Settings()
            assert settings.api_keys.openai_api_key == "test-openai-key"
            assert settings.api_keys.anthropic_api_key == "test-anthropic-key"
        finally:
            del os.environ["OPENAI_API_KEY"]
            del os.environ["ANTHROPIC_API_KEY"]

    def test_create_default_config(self):
        """Test creating default configuration file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            temp_path = f.name

        try:
            settings = Settings.create_default_config(temp_path)
            assert isinstance(settings, Settings)
            assert Path(temp_path).exists()

            # Verify file contains expected structure
            with open(temp_path) as f:
                data = yaml.safe_load(f)

            assert "app" in data
            assert "paths" in data
            assert "transcription" in data
            assert "llm" in data
        finally:
            if Path(temp_path).exists():
                os.unlink(temp_path)


class TestGlobalSettings:
    """Test global settings functions."""

    def test_get_settings(self):
        """Test getting global settings instance."""
        settings1 = get_settings()
        settings2 = get_settings()

        # Should return same instance
        assert settings1 is settings2

    def test_reload_settings(self):
        """Test reloading settings."""
        settings1 = get_settings()
        settings2 = reload_settings()

        # Should return new instance
        assert settings1 is not settings2
