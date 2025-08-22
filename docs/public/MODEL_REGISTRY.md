# Model Registry

## Overview

The Knowledge Chipper uses a dynamic model registry that fetches available models from official sources (OpenAI API, Ollama registry) and maintains them in a local cache. Anthropic models must be manually maintained since they don't provide a public API.

## How It Works

1. **Official Sources**: 
   - OpenAI models are fetched from the OpenAI API (when API key is available)
   - Ollama models are fetched from the Ollama registry
   - Anthropic models are manually maintained in the cache file
2. **Local Caching**: Lists are cached indefinitely until explicitly refreshed
3. **Refresh Button**: Forces a fresh fetch from official sources
4. **Model Validation**: Before using any model, the system validates it exists/is accessible

## Benefits

- **Always Current**: OpenAI and Ollama models are fetched from official sources
- **Automatic Validation**: Models are validated before use to prevent errors
- **Works Offline**: Cached lists ensure the UI works even without internet
- **No Manual Updates**: OpenAI and Ollama models update automatically

## Model Validation

The system automatically validates models when you first use them:

### Smart Session Validation
- **First Use**: When you use a model for the first time in a session, it performs a thorough check
- **Subsequent Uses**: Reuses the validation result for faster processing
- **Automatic**: No user action needed - validation happens seamlessly
- **Clear Errors**: If validation fails, you get specific error messages:
  - "Invalid or missing API key"
  - "No access to model - check subscription" 
  - "Model not installed - run 'ollama pull model_name'"
  - "Rate limit exceeded"

### Benefits
- **Fast**: After first use, no validation delay
- **Reliable**: Catches issues before processing starts
- **Transparent**: Works behind the scenes
- **Session-based**: Revalidates each time you start the app

## Model Sources

### OpenAI
- Fetched from OpenAI API when API key is configured
- Filters to show only chat models (excludes embeddings, whisper, etc.)
- Falls back to cached list if API is unavailable

### Ollama (Local)
- Fetched from Ollama's model registry
- Shows both installed and available models
- Validates that models are installed before use

### Anthropic
- Manually maintained in the cache file
- No public API available for model listing
- Update by editing `~/.knowledge_chipper/cache/model_registry.json`

### Cache Location

Model lists are cached in:
```
~/.knowledge_chipper/cache/model_registry.json
```

## Cache File Format

The cache file structure:

```json
{
  "timestamp": "2024-01-15T12:00:00",
  "source": "Official APIs",
  "models": {
    "openai": ["gpt-4o-2024-08-06", "gpt-4o-mini-2024-07-18", ...],
    "anthropic": ["claude-3-5-sonnet-20241022", ...],
    "local": ["llama3.2:latest", "llama3.1:8b", ...]
  }
}
```

## User Overrides

Users can still add custom models via `config/model_overrides.yaml`:

```yaml
openai:
  - custom-gpt-model
anthropic:
  - custom-claude-model
```

These are merged with the fetched models.

## Manual Updates (Anthropic Only)

To add new Anthropic models:

1. Open `~/.knowledge_chipper/cache/model_registry.json`
2. Add the new model to the `anthropic` array
3. Save the file
4. The new model will appear in the dropdown

## Troubleshooting

### Models Not Updating
- Click the refresh button (🔄) next to the model dropdown
- For OpenAI: Ensure your API key is configured
- For Ollama: Ensure Ollama service is running
- Check logs for any errors

### Model Validation Errors
When you start processing, the system automatically validates your selected model.
If validation fails, you'll see one of these errors:

- **"Model not installed"** (Ollama): Run `ollama pull <model>` to install
- **"No access to model"**: Check your API subscription level
- **"Invalid API key"**: Verify your API key in settings
- **"Rate limit exceeded"**: Wait and try again later
- **"Model not found"**: Model may be deprecated - refresh the list

Use the refresh button (🔄) to update available models

### Cache Issues
- Delete `~/.knowledge_chipper/cache/model_registry.json` to reset
- The cache persists indefinitely - use refresh button to update
