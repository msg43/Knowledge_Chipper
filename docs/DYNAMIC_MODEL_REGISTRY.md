# Dynamic Model Registry

**Last Updated**: December 31, 2025

## Overview

The Knowledge_Chipper system now dynamically fetches available LLM models from cloud provider APIs, ensuring users always have access to the latest models without requiring application updates.

## Architecture

### Backend (Knowledge_Chipper) - Multi-Tier System

```
┌─────────────────────────────────────────────────────────────────┐
│                      Model Registry                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  TIER 1 (Primary): OpenRouter.ai                                │
│  ┌────────────────────────────────────────────────────────┐     │
│  │  OpenRouter API (500+ models from 60+ providers)       │     │
│  │  • OpenAI  • Anthropic  • Google  • Meta  • Mistral   │     │
│  │  • DeepSeek  • Qwen  • xAI  • + 50 more providers     │     │
│  └───────────────────────────┬────────────────────────────┘     │
│                              │ (If fails ↓)                      │
│  TIER 2 (Backup): Individual Provider APIs                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                      │
│  │ OpenAI   │  │  Google  │  │Anthropic │                      │
│  │   API    │  │   API    │  │   API    │                      │
│  └─────┬────┘  └─────┬────┘  └─────┬────┘                      │
│        └───────────────┴──────────────┘                         │
│                       │ (If fails ↓)                            │
│  TIER 3 (Resilient): Local Cache                               │
│  ┌─────────────────────────────────────────────┐               │
│  │  ~/.knowledge_chipper/cache/                 │               │
│  │  model_registry.json                         │               │
│  └──────────────────┬──────────────────────────┘               │
│                     │ (If fails ↓)                              │
│  TIER 4 (Offline): Hardcoded Fallbacks                         │
│  ┌─────────────────────────────────────────────┐               │
│  │  Minimal model lists for offline mode        │               │
│  └──────────────────────────────────────────────┘               │
│                                                                   │
└────────────────────────────┬──────────────────────────────────┘
                             │ HTTP API
                             │
┌────────────────────────────▼──────────────────────────────────┐
│                        Daemon API                               │
│                  GET /api/config/models                         │
└────────────────────────────┬──────────────────────────────────┘
                             │ REST
                             │
┌────────────────────────────▼──────────────────────────────────┐
│                    Frontend (GetReceipts)                       │
│                Processing Options Component                     │
└─────────────────────────────────────────────────────────────────┘
```

## Implementation Details

### 1. Model Fetching (Backend)

#### OpenRouter (Primary Source - Tier 1)
```python
# Fetches from: https://openrouter.ai/api/v1/models
def _fetch_from_openrouter(self) -> dict[str, list[str]]:
    """Fetch 500+ models from 60+ providers via OpenRouter."""
    response = requests.get("https://openrouter.ai/api/v1/models")
    data = response.json()
    
    # Group models by provider
    models_by_provider = {}
    for model in data["data"]:
        model_id = model["id"]  # Format: "provider/model-name"
        provider, model_name = model_id.split("/", 1)
        
        if provider not in models_by_provider:
            models_by_provider[provider] = []
        models_by_provider[provider].append(model_name)
    
    return models_by_provider
```

**Status**: ✅ Fully Dynamic (No API key required)
**Coverage**: 500+ models from OpenAI, Anthropic, Google, Meta, Mistral, DeepSeek, Qwen, xAI, and 50+ more providers

#### OpenAI Models (Tier 2 Fallback)
```python
# Fetches from: https://api.openai.com/v1/models
def _fetch_openai_models(self) -> list[str]:
    client = openai.OpenAI(api_key=api_key)
    models = client.models.list()
    # Filter to chat models only (exclude embeddings, whisper, etc.)
    return [m.id for m in models.data if m.id.startswith("gpt-")]
```

**Status**: ✅ Fully Dynamic (Requires API key)

#### Google/Gemini Models
```python
# Fetches from: https://generativelanguage.googleapis.com/v1beta/models
def _fetch_google_models(self) -> list[str]:
    client = genai.Client(api_key=api_key)
    models_list = client.models.list()
    # Filter to models that support generateContent
    return [m.name for m in models_list 
            if 'generateContent' in m.supported_generation_methods]
```

**Status**: ✅ Fully Dynamic (NEW)

#### Anthropic Models
```python
# Fetches from: https://api.anthropic.com/v1/models
def _fetch_anthropic_models(self) -> list[str]:
    url = "https://api.anthropic.com/v1/models"
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
    }
    response = requests.get(url, headers=headers)
    # Filter to claude models only
    return [m["id"] for m in response.json()["data"] 
            if m["id"].startswith("claude-")]
```

**Status**: ✅ Fully Dynamic (NEW - Anthropic released models API in late 2024/early 2025)

### 2. Caching System

**Location**: `~/.knowledge_chipper/cache/model_registry.json`

**Structure**:
```json
{
  "timestamp": "2025-12-31T12:00:00Z",
  "source": "Official APIs",
  "models": {
    "openai": ["gpt-4o", "gpt-4o-mini", ...],
    "google": ["gemini-2.0-flash-exp", ...],
    "anthropic": ["claude-3-5-sonnet-20241022", ...],
    "local": ["qwen2.5:7b-instruct", ...]
  }
}
```

**Behavior**:
- Cache never expires automatically
- Only refreshes when `force_refresh=true` is passed
- Minimizes API calls and costs
- Preserves Anthropic models between refreshes

### 3. API Endpoint

**Endpoint**: `GET /api/config/models`

**Query Parameters**:
- `provider` (optional): Filter by specific provider (openai, anthropic, google, local)
- `force_refresh` (optional): Force refresh from APIs (default: false)

**Response (All Providers)**:
```json
{
  "providers": {
    "openai": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo"],
    "anthropic": ["claude-3-5-sonnet-20241022", ...],
    "google": ["gemini-2.0-flash-exp", ...],
    "local": ["qwen2.5:7b-instruct", ...]
  },
  "counts": {
    "openai": 15,
    "anthropic": 7,
    "google": 6,
    "local": 12
  }
}
```

**Response (Single Provider)**:
```json
{
  "provider": "google",
  "models": ["gemini-2.0-flash-exp", "gemini-1.5-pro-latest", ...],
  "count": 6
}
```

### 4. Frontend Integration

**Component**: `src/components/processing-options.tsx`

**Flow**:
1. On mount, fetch models from daemon: `daemonClient.getAvailableModels()`
2. Transform API response into UI format with labels
3. Display models in dropdown with automatic label formatting
4. Fall back to hardcoded models if daemon unavailable

**Label Formatting**:
- `gpt-4o` → "GPT-4O"
- `claude-3-5-sonnet-20241022` → "Claude 3 5 Sonnet"
- `gemini-2.0-flash-exp` → "Gemini 2.0 FLASH EXP"

## Fallback Strategy

### When APIs Fail

1. **First**: Try to load from local cache
2. **Second**: Use hardcoded fallback lists
3. **Always**: Log errors but don't block user

### Hardcoded Fallbacks (Updated Dec 2025)

```python
OPENAI_FALLBACK_MODELS = [
    "gpt-4o-2024-08-06",
    "gpt-4o-mini-2024-07-18",
    "gpt-4-turbo-2024-04-09",
    # ...
]

ANTHROPIC_FALLBACK_MODELS = [
    "claude-3-5-sonnet-20241022",
    "claude-3-5-haiku-20241022",
    # ...
]

GOOGLE_FALLBACK_MODELS = [
    "gemini-2.0-flash-exp",
    "gemini-1.5-pro-latest",
    "gemini-1.5-flash-latest",
    # ...
]
```

## User Override System

Users can manually add models via `config/model_overrides.yaml`:

```yaml
openai:
  - gpt-5-preview  # Future model
  
google:
  - gemini-3.0-ultra  # Hypothetical

anthropic:
  - claude-4-opus  # When released
```

These are merged with fetched/fallback models.

## Benefits

### For Users
- ✅ Access to 500+ models from 60+ providers automatically
- ✅ Always see latest models without app updates
- ✅ Automatic access to new model releases (GPT-5, Claude 4, Gemini 3, etc.)
- ✅ No manual configuration needed
- ✅ Graceful degradation if APIs unavailable
- ✅ Works offline with cached models

### For Developers
- ✅ Dramatically reduced maintenance burden
- ✅ Single API call instead of multiple provider integrations
- ✅ No API keys needed for model discovery (OpenRouter is public)
- ✅ Easy to add new providers (automatic via OpenRouter)
- ✅ Comprehensive 4-tier fallback system
- ✅ Comprehensive error handling

### For Cost
- ✅ Minimal API calls (cached indefinitely)
- ✅ OpenRouter endpoint is free (no API key required)
- ✅ Only refreshes on explicit request
- ✅ No background polling
- ✅ Reduced API costs from individual providers

## Testing

### Manual Testing

1. **Test Dynamic Fetching**:
```bash
# Start daemon
python -m daemon.main

# Call endpoint
curl http://localhost:8765/api/config/models
```

2. **Test Force Refresh**:
```bash
curl "http://localhost:8765/api/config/models?force_refresh=true"
```

3. **Test Single Provider**:
```bash
curl "http://localhost:8765/api/config/models?provider=google"
```

4. **Test Fallback** (without API keys):
```bash
# Unset API keys
unset OPENAI_API_KEY
unset GOOGLE_API_KEY

# Should still return fallback models
curl http://localhost:8765/api/config/models
```

### Frontend Testing

1. Open GetReceipts `/contribute` page
2. Open Processing Options panel
3. Select different providers
4. Verify models populate correctly
5. Check browser console for errors

## Future Enhancements

### Potential Improvements

1. **Model Metadata**: Parse OpenRouter's pricing, context windows, and capabilities data
2. **Model Recommendations**: Suggest best model for use case based on benchmarks
3. **Usage Analytics**: Track which models are most popular
4. **Background Refresh**: Optional periodic refresh in daemon
5. **LLM Stats Integration**: Add benchmark scores and performance data
6. **Model Search**: Filter models by capability (coding, reasoning, vision, etc.)

### Adding New Providers

To add a new provider:

1. Add fetcher method to `model_registry_api.py`:
```python
def _fetch_newprovider_models(self) -> list[str]:
    # Fetch from provider API
    return models
```

2. Add fallback list to `model_registry.py`:
```python
NEWPROVIDER_FALLBACK_MODELS = [...]
```

3. Add getter function:
```python
def get_newprovider_models(force_refresh: bool = False) -> list[str]:
    # Implementation
```

4. Update `get_provider_models()` to include new provider

5. Update frontend types and UI

## Troubleshooting

### Models Not Showing

**Symptom**: Dropdown shows "No models available"

**Causes**:
1. Daemon not running
2. API keys not configured
3. Network issues

**Solution**:
1. Check daemon status
2. Verify API keys in Settings
3. Check browser console for errors
4. Try force refresh

### Stale Models

**Symptom**: New models not appearing

**Solution**:
```bash
# Force refresh cache
curl "http://localhost:8765/api/config/models?force_refresh=true"
```

### API Rate Limits

**Symptom**: Errors fetching models

**Solution**:
- Models are cached, so rate limits should be rare
- Wait and try again
- Use fallback models (automatic)

## Related Files

### Backend
- `src/knowledge_system/utils/model_registry_api.py` - Model fetching logic
- `src/knowledge_system/utils/model_registry.py` - Provider-specific functions
- `daemon/api/routes.py` - API endpoint
- `daemon/models/schemas.py` - Type definitions

### Frontend
- `src/lib/daemon-client.ts` - API client
- `src/components/processing-options.tsx` - UI component

### Documentation
- `CHANGELOG.md` - Change history
- `MANIFEST.md` - Project structure

## Conclusion

The dynamic model registry ensures Knowledge_Chipper users always have access to the latest LLM models from OpenAI and Google without requiring application updates. The system is designed with robust fallbacks, caching, and error handling to provide a seamless experience even when APIs are unavailable.

