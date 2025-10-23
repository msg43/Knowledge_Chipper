"""Test utilities for GUI comprehensive tests."""

from .db_validator import DBValidator
from .fs_validator import assert_markdown_has_sections, read_markdown_with_frontmatter
from .test_utils import (
    create_sandbox,
    find_button_by_text,
    find_first_combo,
    process_events_for,
    set_env_sandboxes,
    switch_to_tab,
    wait_until,
)
from .ui_helpers import (
    add_file_to_summarize,
    add_file_to_transcribe,
    check_ollama_running,
    check_whisper_cpp_installed,
    enable_diarization,
    get_summarize_tab,
    get_transcribe_tab,
    set_language,
    set_model,
    set_provider,
    wait_for_completion,
)

__all__ = [
    "DBValidator",
    "assert_markdown_has_sections",
    "read_markdown_with_frontmatter",
    "create_sandbox",
    "find_button_by_text",
    "find_first_combo",
    "process_events_for",
    "set_env_sandboxes",
    "switch_to_tab",
    "wait_until",
    "add_file_to_summarize",
    "add_file_to_transcribe",
    "check_ollama_running",
    "check_whisper_cpp_installed",
    "enable_diarization",
    "get_summarize_tab",
    "get_transcribe_tab",
    "set_language",
    "set_model",
    "set_provider",
    "wait_for_completion",
]

