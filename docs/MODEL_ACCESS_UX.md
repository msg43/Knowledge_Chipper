# Model Access UX Documentation

**Last Updated: January 1, 2026**

## Overview

The Model Access UX system provides clear visibility into which LLM models users can access with their API keys, preventing frustration from cryptic API errors and wasted processing time on inaccessible models.

## Problem Statement

Users faced multiple pain points with model selection:

1. **Unclear Access Requirements**: No way to know if a model requires special approval
2. **Cryptic API Errors**: Generic 403/404 errors without actionable guidance
3. **Wasted Time**: Starting long processing jobs only to fail on inaccessible models
4. **Tier Confusion**: Unclear which models require usage tier upgrades (e.g., OpenAI Tier 5)

## Solution Components

### 1. Model Status Badges

Visual indicators in model dropdowns showing access requirements:

| Badge | Status | Meaning |
|-------|--------|---------|
| ✅ | Public | Generally available to all API key holders |
| 🔒 | Gated | Requires special access/approval or specific plan |
| 🧪 | Experimental | Preview/beta models (may require allowlist) |
| ⭐ | Tier Restricted | Requires specific usage tier |
| ⚠️ | Deprecated | No longer available |

### 2. Model Metadata Database

Curated information for 50+ popular models across providers:

```python
from src.knowledge_system.utils.model_metadata import get_model_metadata

# Example: Check if model requires special access
metadata = get_model_metadata("openai", "o1")
print(f"Status: {metadata.status}")  # "tier_restricted"
print(f"Tier: {metadata.tier_required}")  # "tier-5"
print(f"Note: {metadata.note}")  # "Requires usage tier 5"
```

**Tracked Information:**
- `status`: Access level (public, gated, experimental, etc.)
- `tier_required`: Minimum usage tier (e.g., "tier-5")
- `note`: Human-readable access requirements
- `display_name`: Formatted model name for UI

**Covered Models:**

**OpenAI:**
- GPT-5.x series (5.2, 5.1, 4.1)
- GPT-4o series (all variants)
- o1 series (requires Tier 5)
- GPT-4 Turbo, GPT-4, GPT-3.5 Turbo

**Anthropic:**
- Claude 4.5 series (Opus, Sonnet, Haiku)
- Claude 4 series
- Claude 3.5 series (all variants)
- Claude 3 series (Opus, Sonnet, Haiku)

**Google:**
- Gemini 3 series (Pro, Flash, Deep Think)
- Gemini 2.5 series
- Gemini 2.0 series (experimental)
- Gemini 1.5 series
- Gemini 1.0 Pro

### 3. Enhanced Error Messages

Replaced cryptic API errors with actionable user guidance:

#### Access Denied (403)
```
❌ Model Access Denied: You don't have access to 'o1' on openai.

This model may require:
• Higher usage tier (currently Tier 5)
• Special approval from provider
• Specific subscription plan
• Waitlist access

Please try a different model or contact openai support for access.
```

#### Model Not Found (404)
```
❌ Model Not Found: 'claude-opus-3' is not available on anthropic.

The model may have been:
• Deprecated or retired
• Renamed (try 'claude-3-opus-20240229')
• Not yet released in your region

Please select a different model from the dropdown.
```

#### Authentication Failed (401)
```
❌ Authentication Failed: Your anthropic API key is invalid or expired.

Please update your API key in Settings.
```

#### Rate Limited (429)
```
❌ Rate Limit Exceeded: Please wait and try again.

Your API usage has exceeded the rate limit. Wait a few moments before retrying.
```

### 4. Test Access API

Validate model accessibility before starting processing:

**Endpoint:** `POST /api/config/test-model-access`

**Request:**
```json
{
  "provider": "openai",
  "model": "o1"
}
```

**Response (Success):**
```json
{
  "success": true,
  "accessible": true,
  "error_message": null,
  "details": "Model 'o1' is accessible. Test call completed successfully."
}
```

**Response (Access Denied):**
```json
{
  "success": true,
  "accessible": false,
  "error_message": "Access Denied",
  "details": "You don't have access to 'o1' on openai. This model may require a higher usage tier, special approval, or specific subscription plan."
}
```

**How It Works:**
1. Makes minimal API call (1 token) to validate access
2. Checks API key validity, model existence, and user permissions
3. Returns user-friendly error with resolution steps
4. Minimal cost (~$0.00001 per test)

**Usage in TypeScript:**
```typescript
import { daemonClient } from '@/lib/daemon-client';

const result = await daemonClient.testModelAccess("openai", "o1");

if (result.accessible) {
  console.log("✅ Model is accessible!");
} else {
  console.error(`❌ ${result.error_message}: ${result.details}`);
}
```

## User Flow

### Model Selection Flow

1. **Open Processing Options Panel**
   - System fetches model list with metadata from backend
   - Shows loading state while fetching

2. **Select Provider** (OpenAI, Anthropic, or Google)
   - Dropdown shows "Configured" badge if API key is set
   - Provider badge color indicates status

3. **Open Model Dropdown**
   - Models displayed with status badges:
     - ✅ Claude 3.5 Sonnet (Public)
     - 🔒 Claude Opus 4.5 (Gated)
     - ⭐ o1 (Tier Required)
   - Hover over model for access details

4. **Optional: Test Access**
   - Click "Test Access" button (if implemented in UI)
   - System validates model accessibility
   - Shows result: "✅ Accessible" or "❌ Access Denied"

5. **Select Model & Process**
   - Click "Process" to start extraction
   - If access fails, shows actionable error message

### Error Recovery Flow

If processing fails due to model access:

1. **User sees clear error message**
   ```
   ❌ Access Denied: You don't have access to 'o1'
   
   This model requires usage tier 5.
   
   Solutions:
   • Upgrade your OpenAI usage tier
   • Select a different model
   • Contact OpenAI support
   ```

2. **User has actionable options:**
   - Select a different model marked as ✅ Public
   - Upgrade their API usage tier
   - Contact provider support for access
   - Test other models to find accessible ones

## Implementation Details

### Backend Architecture

**File: `src/knowledge_system/utils/model_metadata.py`**
- Defines `ModelStatus` enum
- Contains `KNOWN_MODELS` database (50+ models)
- Provides `get_model_metadata()` helper
- Status badge and label formatters

**File: `daemon/api/routes.py`**
- `GET /config/models` enriched with metadata
- `POST /config/test-model-access` for validation
- Models include `status`, `status_badge`, `tier_required`, `note`

**File: `src/knowledge_system/core/llm_adapter.py`**
- Enhanced error handling in `complete()` method
- Detects error types: 403, 404, 401, 429
- Returns specific error messages with guidance

### Frontend Integration

**File: `GetReceipts/src/lib/daemon-client.ts`**
- `ModelMetadata` TypeScript interface
- `AvailableModelsResponse` includes metadata
- `getAvailableModels()` method

**File: `GetReceipts/src/components/processing-options.tsx`**
- Renders status badges in model dropdowns
- Displays model metadata inline
- Shows access notes on hover

## API Reference

### Get Models with Metadata

**Endpoint:** `GET /api/config/models`

**Query Parameters:**
- `provider` (optional): Filter by provider (openai, anthropic, google, local)
- `force_refresh` (optional): Bypass cache and fetch fresh data
- `include_metadata` (optional, default=true): Include access metadata

**Response:**
```json
{
  "providers": {
    "openai": [
      {
        "id": "gpt-4o",
        "display_name": "GPT-4o",
        "status": "public",
        "status_badge": "✅",
        "status_label": "Public",
        "tier_required": null,
        "note": null
      },
      {
        "id": "o1",
        "display_name": "o1",
        "status": "tier_restricted",
        "status_badge": "⭐",
        "status_label": "Tier Required",
        "tier_required": "tier-5",
        "note": "Requires usage tier 5"
      }
    ],
    "anthropic": [...],
    "google": [...]
  },
  "counts": {
    "openai": 15,
    "anthropic": 12,
    "google": 14
  }
}
```

### Test Model Access

**Endpoint:** `POST /api/config/test-model-access`

**Request Body:**
```json
{
  "provider": "openai",
  "model": "o1"
}
```

**Response:**
```json
{
  "success": true,
  "accessible": false,
  "error_message": "Access Denied",
  "details": "You don't have access to 'o1' on openai. This model requires usage tier 5."
}
```

## Extending the System

### Adding New Models

Edit `src/knowledge_system/utils/model_metadata.py`:

```python
KNOWN_MODELS = {
    "openai": {
        # Add new model
        "gpt-5.3": ModelMetadata(
            "gpt-5.3",
            status=ModelStatus.GATED,
            note="Latest flagship - May require waitlist access"
        ),
        # ... existing models
    }
}
```

### Adding New Providers

1. Add provider to `KNOWN_MODELS` dict
2. Update `ModelMetadata` to include provider-specific fields
3. Add provider to frontend model fetching
4. Update UI to handle new provider

### Custom Status Badges

Modify `get_status_badge()` in `model_metadata.py`:

```python
def get_status_badge(status: ModelStatus) -> str:
    badges = {
        ModelStatus.PUBLIC: "✅",
        ModelStatus.GATED: "🔒",
        ModelStatus.EXPERIMENTAL: "🧪",
        ModelStatus.DEPRECATED: "⚠️",
        ModelStatus.TIER_RESTRICTED: "⭐",
        ModelStatus.CUSTOM_STATUS: "🎯",  # Add custom badge
    }
    return badges.get(status, "")
```

## Best Practices

### For Users

1. **Check Status Before Processing**
   - Look for ✅ Public models for immediate access
   - 🔒 Gated models may require account upgrades

2. **Use Test Access**
   - Test model access before long processing jobs
   - Saves time and avoids frustration

3. **Read Error Messages**
   - Error messages include actionable steps
   - Follow guidance to resolve access issues

### For Developers

1. **Keep Metadata Updated**
   - Review model metadata quarterly
   - Update as providers release new models

2. **Handle Unknown Models Gracefully**
   - Unknown models default to PUBLIC status
   - Add note: "Access requirements unknown"

3. **Log Access Failures**
   - Track which models users can't access
   - Helps identify metadata gaps

## Benefits

### For Users
- 🎯 **Clear Visibility**: Know which models you can access
- 💡 **Actionable Errors**: Understand why access failed and how to fix it
- 🧪 **Test Before Processing**: Validate access before starting work
- ⚡ **Save Time**: Avoid inaccessible models from the start

### For Developers
- 📊 **Better Telemetry**: Track which models users attempt
- 🔧 **Easier Debugging**: Specific error codes and messages
- 🚀 **Scalable**: Easy to add new models and providers
- 📚 **Self-Documenting**: Metadata serves as model catalog

## Future Enhancements

Potential improvements:

1. **Real-Time Access Validation**
   - Check model access on selection (not just on error)
   - Cache validation results per session

2. **Recommended Alternatives**
   - Suggest similar accessible models when access fails
   - "Can't access o1? Try gpt-4o instead"

3. **Tier Upgrade Prompts**
   - Link to provider tier upgrade pages
   - Show pricing for tier upgrades

4. **Access History**
   - Track which models user has successfully used
   - Mark them with ✅ Verified badge

5. **Provider Status Integration**
   - Check provider status pages for outages
   - Show "⚠️ Provider Experiencing Issues" banner

## Troubleshooting

### Model shows wrong status

**Problem:** Model marked as 🔒 Gated but you have access

**Solution:** Metadata may be outdated. Update `KNOWN_MODELS` in `model_metadata.py`

### Test Access always fails

**Problem:** Test calls timeout or fail

**Solution:** 
1. Check API key is configured
2. Verify internet connection
3. Check provider status page
4. Ensure sufficient API credits

### Badges not showing in UI

**Problem:** Dropdowns show model IDs without badges

**Solution:**
1. Check `include_metadata=true` in API call
2. Verify frontend is using `ModelMetadata` interface
3. Clear browser cache and reload

## Support

For questions or issues:
- Check the [CHANGELOG.md](../CHANGELOG.md) for recent updates
- Review [DYNAMIC_MODEL_REGISTRY.md](./DYNAMIC_MODEL_REGISTRY.md) for model fetching details
- File an issue in the GitHub repository

