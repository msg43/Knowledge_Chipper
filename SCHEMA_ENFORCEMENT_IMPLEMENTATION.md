# JSON Schema Enforcement Implementation

## Overview

This implementation adds **structured outputs with JSON schema enforcement** to your Knowledge Chipper system, specifically targeting Ollama models (Qwen, Llama, etc.) to ensure strict JSON compliance.

## The Problem

Previously, your system used basic JSON mode (`"format": "json"`) which only ensures syntactically valid JSON, not schema compliance. This led to:
- Models generating valid JSON but with wrong structure
- Missing required fields
- Incorrect data types
- Need for post-hoc validation and fallbacks

## The Solution

The new implementation uses **Ollama's structured outputs feature** which:
1. **Compiles JSON Schema into a grammar** (via llama.cpp)
2. **Masks invalid tokens** during generation
3. **Forces models to stay within schema constraints**
4. **Guarantees both valid JSON AND correct structure**

## Implementation Details

### 1. Pydantic Models (`src/knowledge_system/utils/pydantic_models.py`)

Created Pydantic models that exactly match your existing JSON schemas:

```python
class UnifiedMinerOutput(BaseModel):
    claims: List[Claim]
    jargon: List[Jargon]
    people: List[Person]
    mental_models: List[MentalModel]

class FlagshipEvaluationOutput(BaseModel):
    evaluated_claims: List[EvaluatedClaim]
    summary_assessment: SummaryAssessment
```

**Benefits:**
- Automatic JSON schema generation via `model_json_schema()`
- Runtime validation with `model_validate()`
- Type safety and IDE support
- Exact compatibility with existing schemas

### 2. Enhanced LLM Providers (`src/knowledge_system/utils/llm_providers.py`)

**LocalLLMProvider** now supports schema enforcement:

```python
def _call_ollama(self, prompt: str, schema: dict | None = None):
    payload = {
        "model": self.model,
        "prompt": prompt,
        "options": {
            "temperature": 0 if schema else self.temperature,  # temp=0 for schema
        },
    }
    
    if schema is not None:
        payload["format"] = schema  # Structured outputs with schema
        logger.info("🔒 Using structured outputs with schema enforcement")
    elif wants_json:
        payload["format"] = "json"  # Basic JSON mode fallback
```

**New Methods:**
- `generate_structured_json(prompt, schema_name)` - Uses schema enforcement
- Enhanced `generate()` with optional schema parameter
- Automatic fallback to regular JSON mode if schema fails

### 3. SuperChunk Adapter Updates (`src/knowledge_system/superchunk/llm_adapter.py`)

Added `generate_structured_json()` method that:
- Detects Ollama provider automatically
- Uses schema enforcement for local models
- Falls back to regular generation for cloud providers
- Maintains compatibility with existing code

### 4. HCE Processor Integration

**UnifiedMiner** and **FlagshipEvaluator** now:
- Try structured JSON generation first (for Ollama)
- Fall back to regular JSON generation if needed
- Maintain existing validation as backup
- Log when schema enforcement is active

```python
# Try structured JSON generation first (for Ollama models)
if hasattr(self.llm, 'generate_structured_json'):
    try:
        raw_result = self.llm.generate_structured_json(full_prompt, "miner_output")
        logger.info("🔒 Using structured outputs with schema enforcement")
    except Exception as e:
        logger.warning(f"Structured JSON generation failed, falling back: {e}")

# Fall back to regular JSON generation
if raw_result is None:
    raw_result = self.llm.generate_json(full_prompt)
```

## Usage

### Automatic (Recommended)

The system automatically uses schema enforcement when:
- Using Ollama models (local provider)
- The model supports structured outputs
- Schema enforcement is available

### Manual Usage

```python
from knowledge_system.utils.llm_providers import UnifiedLLMClient

client = UnifiedLLMClient(provider="local", model="qwen2.5:7b")

# This will use schema enforcement automatically
result = client.generate_structured_json(
    prompt="Extract claims from this content...",
    schema_name="miner_output"
)
```

## Model Compatibility

### Recommended Models (Best Schema Compliance)

1. **Qwen2.5:7b** - Excellent JSON compliance, 4GB download
2. **Qwen2.5:3b** - Good compliance, smaller size (2GB)
3. **Llama3.2:3b** - Good compliance, 2GB download
4. **Llama3.1:8b** - Very good compliance, larger size

### Configuration

Your system already prioritizes these models:
- `FALLBACK_MODEL = "qwen2.5:7b"`
- `MVP_MODEL = "qwen2.5:7b"`

## Benefits

### 1. **Guaranteed Schema Compliance**
- Models cannot generate invalid structures
- No more missing required fields
- Correct data types enforced

### 2. **Improved Reliability**
- Reduces fallback scenarios
- Fewer validation errors
- More consistent outputs

### 3. **Better Performance**
- Less post-processing needed
- Fewer retry attempts
- Faster pipeline execution

### 4. **Enhanced Debugging**
- Clear logging when schema enforcement is active
- Better error messages
- Easier troubleshooting

## Fallback Strategy

The implementation includes robust fallbacks:

1. **Primary**: Structured outputs with schema enforcement (Ollama)
2. **Secondary**: Basic JSON mode (all providers)
3. **Tertiary**: Post-hoc validation with error handling
4. **Final**: Empty structure fallback

## Testing

### Validation Script
Run `python validate_schema_implementation.py` to verify:
- Pydantic models work correctly
- Schema generation functions properly
- JSON serialization/deserialization works
- LLM providers import successfully

### Live Testing
Run `python test_schema_enforcement.py` to test with actual models (requires Ollama running).

## Configuration

### Settings

The system uses your existing configuration:
- `local_config.backend = "ollama"` (for Ollama support)
- `local_config.base_url = "http://localhost:11434"`
- Model selection via existing model registry

### Temperature Settings

- **Schema enforcement**: `temperature=0` (deterministic)
- **Regular generation**: Uses configured temperature

## Monitoring

Look for these log messages:
- `🔒 Using structured outputs with schema enforcement for model: qwen2.5:7b`
- `🔒 Using structured outputs with schema enforcement for miner`
- `🔒 Using structured outputs with schema enforcement for flagship evaluator`

## Future Enhancements

1. **Additional Schemas**: Easy to add more Pydantic models
2. **Cloud Provider Support**: Extend to OpenAI/Anthropic structured outputs
3. **Dynamic Schemas**: Generate schemas from user input
4. **Performance Metrics**: Track schema compliance rates

## Conclusion

This implementation provides **bulletproof JSON schema compliance** for your local models while maintaining full backward compatibility. The system automatically uses the best available method for each provider, ensuring maximum reliability with minimal configuration changes.

The ChatGPT approach you shared was exactly right - using Ollama's structured outputs with JSON schemas provides much stronger guarantees than basic JSON mode, and this implementation brings that capability to your Knowledge Chipper system.
