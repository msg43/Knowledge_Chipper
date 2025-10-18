# LLM Adapter Provider Implementation Fix

## Problem

The System 2 LLM Adapter (`src/knowledge_system/core/llm_adapter.py`) only had the Ollama provider implemented. When the HCE pipeline or other components tried to use OpenAI, Anthropic, or Google providers, they would fail with the error:

```
LLM request failed: Provider openai not implemented yet [INVALID_INPUT] [LLM_API_ERROR]
```

This occurred because the `_call_provider` method only had a case for `ollama` and raised an error for all other providers.

## Solution

Added full async implementations for three additional LLM providers:

### 1. OpenAI (`_call_openai`)
- Uses `AsyncOpenAI` client from the `openai` package
- Reads API key from `settings.api_keys.openai_api_key`
- Supports chat completions with configurable temperature and max_tokens
- Returns standardized response format with usage statistics

### 2. Anthropic (`_call_anthropic`)
- Uses `AsyncAnthropic` client from the `anthropic` package
- Reads API key from `settings.api_keys.anthropic_api_key`
- Handles Anthropic's content block format
- Maps Anthropic's usage fields (input_tokens/output_tokens) to standard format

### 3. Google Gemini (`_call_google`)
- Uses `google.generativeai` package
- Reads API key from `settings.api_keys.google_api_key`
- Converts chat messages to Gemini format
- Estimates token usage (Gemini doesn't always provide usage data)

## Implementation Details

All three implementations:
- Are fully async to work with the LLM Adapter's async architecture
- Include proper error handling with rate limit detection
- Return standardized response dictionaries with:
  - `content`: The generated text
  - `usage`: Token counts (prompt_tokens, completion_tokens, total_tokens)
  - `model`: The model name used
  - `provider`: The provider name
- Provide helpful error messages for missing API keys or package imports

## Files Modified

- `src/knowledge_system/core/llm_adapter.py`:
  - Updated `_call_provider` method to route to new provider methods
  - Added `_call_openai` method (lines 350-404)
  - Added `_call_anthropic` method (lines 406-465)
  - Added `_call_google` method (lines 467-531)

## Configuration Requirements

For each provider to work, the corresponding API key must be configured in one of:

1. `config/credentials.yaml`:
```yaml
api_keys:
  openai: sk-...
  anthropic: sk-ant-...
  google_api_key: ...
```

2. Environment variables:
```bash
export OPENAI_API_KEY=sk-...
export ANTHROPIC_API_KEY=sk-ant-...
export GOOGLE_API_KEY=...
```

## Testing

The implementation was verified to:
1. Import successfully without syntax errors
2. Match the patterns used in existing `llm_providers.py` implementations
3. Follow the async architecture of the LLM Adapter

## Next Steps

The HCE pipeline should now work with any of the four supported providers:
- `ollama` (local models)
- `openai` (GPT models)
- `anthropic` (Claude models)
- `google` (Gemini models)

Users can configure their preferred provider in the GUI or via model URIs like:
- `"openai:gpt-4o-mini"`
- `"anthropic:claude-3-sonnet"`
- `"google:gemini-pro"`
- `"local://qwen2.5:7b"` (maps to ollama)

