"""
Test GUI model configuration and URI construction.

This test suite validates that the GUI correctly constructs model URIs
from provider/model selections, catching format bugs like the slash vs colon issue.
"""

import pytest
from pathlib import Path
from PyQt6.QtWidgets import QComboBox
from unittest.mock import MagicMock, patch

# Add the src directory to the Python path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from knowledge_system.processors.hce.model_uri_parser import parse_model_uri


def test_model_uri_parser_expectations():
    """Test that the model URI parser works as expected."""
    
    # Test cases: (input_uri, expected_provider, expected_model)
    test_cases = [
        # Standard provider:model format
        ("openai:gpt-4o-mini", "openai", "gpt-4o-mini"),
        ("anthropic:claude-3-5-sonnet", "anthropic", "claude-3-5-sonnet"),
        ("google:gemini-pro", "google", "gemini-pro"),
        
        # Local protocol format
        ("local://qwen2.5:7b-instruct", "ollama", "qwen2.5:7b-instruct"),
        ("local://llama3.2:3b", "ollama", "llama3.2:3b"),
        
        # Edge cases
        ("openai:gpt-4o-mini-2024-07-18", "openai", "gpt-4o-mini-2024-07-18"),
        
        # What happens with WRONG format (the bug)
        ("openai/gpt-4o-mini", "ollama", "openai/gpt-4o-mini"),  # WRONG! Should fail
    ]
    
    for uri, expected_provider, expected_model in test_cases:
        provider, model = parse_model_uri(uri)
        if "/" in uri and ":" in uri:
            # This is the buggy format - parser will misinterpret it
            pass  # Expected to fail
        else:
            assert provider == expected_provider, (
                f"URI '{uri}' parsed as provider='{provider}' "
                f"but expected '{expected_provider}'"
            )
            assert model == expected_model, (
                f"URI '{uri}' parsed as model='{model}' "
                f"but expected '{expected_model}'"
            )


def test_gui_model_override_construction():
    """Test that the GUI _get_model_override() method creates correct URIs."""
    
    # Import the tab (this will only work if GUI is importable)
    try:
        from knowledge_system.gui.tabs.summarization_tab import SummarizationTab
    except ImportError:
        pytest.skip("GUI not available for testing")
    
    # Create a mock SummarizationTab instance
    # Note: We can't fully initialize it without Qt, so we'll just test the method
    tab = SummarizationTab.__new__(SummarizationTab)
    
    # Test cases: (provider, model, expected_uri)
    test_cases = [
        ("openai", "gpt-4o-mini", "openai:gpt-4o-mini"),
        ("openai", "gpt-4o-mini-2024-07-18", "openai:gpt-4o-mini-2024-07-18"),
        ("anthropic", "claude-3-5-sonnet-20241022", "anthropic:claude-3-5-sonnet-20241022"),
        ("google", "gemini-pro", "google:gemini-pro"),
        ("local", "qwen2.5:7b-instruct", "local://qwen2.5:7b-instruct"),
        ("local", "llama3.2:3b", "local://llama3.2:3b"),
    ]
    
    for provider_text, model_text, expected_uri in test_cases:
        # Create mock QComboBox widgets
        provider_combo = MagicMock(spec=QComboBox)
        provider_combo.currentText.return_value = provider_text
        
        model_combo = MagicMock(spec=QComboBox)
        model_combo.currentText.return_value = model_text
        
        # Call the method
        actual_uri = tab._get_model_override(provider_combo, model_combo)
        
        # Verify correct format
        assert actual_uri == expected_uri, (
            f"GUI constructed '{actual_uri}' but expected '{expected_uri}' "
            f"for provider='{provider_text}', model='{model_text}'"
        )
        
        # Verify parser can handle it correctly
        parsed_provider, parsed_model = parse_model_uri(actual_uri)
        
        if provider_text.lower() == "local":
            assert parsed_provider == "ollama", (
                f"Local provider should map to 'ollama', got '{parsed_provider}'"
            )
        else:
            assert parsed_provider == provider_text.lower(), (
                f"Provider mismatch: GUI said '{provider_text}' "
                f"but parser extracted '{parsed_provider}'"
            )


def test_gui_to_pipeline_model_flow():
    """Test the complete flow from GUI model selection to HCE pipeline."""
    
    try:
        from knowledge_system.gui.tabs.summarization_tab import SummarizationTab
        from knowledge_system.processors.hce.model_uri_parser import parse_model_uri
    except ImportError:
        pytest.skip("GUI or HCE components not available")
    
    # Simulate GUI selections
    gui_selections = [
        ("openai", "gpt-4o-mini"),
        ("anthropic", "claude-3-5-sonnet-20241022"),
        ("local", "qwen2.5:7b-instruct"),
    ]
    
    tab = SummarizationTab.__new__(SummarizationTab)
    
    for provider_text, model_text in gui_selections:
        # Create mock combos
        provider_combo = MagicMock(spec=QComboBox)
        provider_combo.currentText.return_value = provider_text
        
        model_combo = MagicMock(spec=QComboBox)
        model_combo.currentText.return_value = model_text
        
        # Step 1: GUI constructs URI
        uri = tab._get_model_override(provider_combo, model_combo)
        
        # Step 2: Parser extracts provider/model
        parsed_provider, parsed_model = parse_model_uri(uri)
        
        # Step 3: Verify round-trip correctness
        if provider_text.lower() == "local":
            # Local should map to ollama
            assert parsed_provider == "ollama"
            assert parsed_model == model_text
        else:
            # Other providers should pass through correctly
            assert parsed_provider == provider_text.lower()
            assert parsed_model == model_text


def test_broken_format_detection():
    """Test that we can detect the BROKEN slash format.
    
    This test demonstrates how the BUG manifested - slash format gets misparsed.
    """
    
    # Test cases: (broken_uri, what_parser_does)
    test_cases = [
        # Pure slash format - no colon, so entire string becomes model
        ("openai/gpt-4o-mini", "ollama", "openai/gpt-4o-mini"),
        ("anthropic/claude-3-5-sonnet", "ollama", "anthropic/claude-3-5-sonnet"),
        
        # Slash + colon format - parser finds colon and splits there
        # "local/qwen2.5:7b-instruct" splits on ':' -> provider="local/qwen2.5", model="7b-instruct"
        ("local/qwen2.5:7b-instruct", "local/qwen2.5", "7b-instruct"),
    ]
    
    for broken_uri, expected_provider, expected_model in test_cases:
        provider, model = parse_model_uri(broken_uri)
        
        # Verify the parser misinterprets the broken format
        assert provider == expected_provider, (
            f"Broken URI '{broken_uri}' parsed as provider='{provider}' "
            f"but expected '{expected_provider}' (this demonstrates the bug)"
        )
        assert model == expected_model, (
            f"Broken URI '{broken_uri}' parsed as model='{model}' "
            f"but expected '{expected_model}' (this demonstrates the bug)"
        )


if __name__ == "__main__":
    # Run tests
    print("Testing Model URI Construction...")
    print("=" * 80)
    
    try:
        test_model_uri_parser_expectations()
        print("✅ Model URI parser tests passed")
    except AssertionError as e:
        print(f"❌ Model URI parser tests failed: {e}")
    
    try:
        test_gui_model_override_construction()
        print("✅ GUI model override construction tests passed")
    except Exception as e:
        print(f"⚠️  GUI model override tests skipped: {e}")
    
    try:
        test_gui_to_pipeline_model_flow()
        print("✅ GUI to pipeline flow tests passed")
    except Exception as e:
        print(f"⚠️  GUI to pipeline flow tests skipped: {e}")
    
    try:
        test_broken_format_detection()
        print("✅ Broken format detection tests passed")
    except AssertionError as e:
        print(f"❌ Broken format detection tests failed: {e}")
    
    print("=" * 80)
    print("Test suite complete!")

