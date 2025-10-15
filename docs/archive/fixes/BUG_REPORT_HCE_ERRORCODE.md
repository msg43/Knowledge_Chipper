# HCE Pipeline Critical Bug Report: ErrorCode Enum String Formatting Issue

**Date**: 2024-10-14  
**Severity**: CRITICAL - Complete Pipeline Failure  
**Status**: UNRESOLVED  
**Component**: HCE Pipeline (Unified Miner, LLM System2)

---

## Executive Summary

The HCE (High-fidelity Claim Extraction) pipeline is completely non-functional due to a critical bug where `ErrorCode` enum values are being passed to Python string operations, causing a `TypeError: sequence item 0: expected str instance, ErrorCode found`. This results in:

- **0% success rate** for claim extraction
- **0 claims, 0 people, 0 concepts extracted** from any document
- Silent failure masquerading as successful processing
- Processing time ~0 seconds (immediate failure)

---

## Error Signature

```
TypeError: sequence item 0: expected str instance, ErrorCode found
```

This error appears in logs as:
```
WARNING | Unified mining failed for segment seg_XXXX: sequence item 0: expected str instance, ErrorCode found
WARNING | Structured JSON generation failed, falling back: sequence item 0: expected str instance, ErrorCode found
ERROR   | Failed to generate long summary: sequence item 0: expected str instance, ErrorCode found
```

---

## Root Cause Analysis

### Primary Issue
`ErrorCode` enum instances are being passed to Python string formatting operations (likely `str.join()` or similar) that expect string types. This happens when:

1. An exception is raised with an `ErrorCode` enum
2. The exception is caught and formatted for logging
3. Python's string formatting attempts to convert the exception to a string
4. Somewhere in the exception's representation, `ErrorCode` enums exist in a collection that gets joined

### Code Path
```
CLI/GUI Request
  ↓
SummarizerProcessor.__init__()
  ↓
UnifiedHCEPipeline.process()
  ↓
mine_episode_unified()
  ↓
UnifiedMiner.mine_segment()
  ↓
System2LLM.generate_structured_json()
  ↓
KnowledgeSystemError raised with ErrorCode
  ↓
Exception formatting fails (ErrorCode enum in string operation)
  ↓
All segments fail → 0 claims extracted
```

---

## Affected Files

### Core Files with ErrorCode Issues

1. **`src/knowledge_system/errors.py`**
   - Lines 64-90: `KnowledgeSystemError.__init__()` and `__str__()`
   - ErrorCode enums may exist in context dict, causing join failures
   - **Partial fix applied**: Added ErrorCode handling in `__str__()` method

2. **`src/knowledge_system/processors/hce/models/llm_system2.py`**
   - Lines 91-93, 117-119: Raises `KnowledgeSystemError` with `ErrorCode.LLM_PARSE_ERROR`
   - Exception creation and propagation path

3. **`src/knowledge_system/processors/hce/unified_miner.py`**
   - Lines 87-95: Exception handling for structured JSON generation
   - Lines 156-177: Exception handling for mining failures
   - **Partial fix applied**: Added try/except around exception formatting

4. **`src/knowledge_system/core/llm_adapter.py`**
   - Line 378: Compares `e.error_code == ErrorCode.LLM_API_ERROR` (should be `.value`)
   - **Fix applied**: Changed to `ErrorCode.LLM_API_ERROR.value`

5. **`src/knowledge_system/processors/hce/schema_validator.py`**
   - Lines 131-136: Raises `KnowledgeSystemError` with error list that might contain ErrorCodes
   - **Partial fix applied**: Convert errors to strings before joining

---

## Reproduction Steps

### Minimal Reproduction

```bash
cd /Users/matthewgreer/Projects/Knowledge_Chipper
source venv/bin/activate

# Any document will trigger the bug
python -m knowledge_system.cli summarize output/steve_bannon_test.md --output ./output --use-skim
```

### Expected Behavior
- Document should be processed
- Claims, people, and concepts should be extracted
- Processing time should be > 0 seconds
- Summary should contain meaningful content

### Actual Behavior
```
Unified mining extracted: 0 claims, 0 jargon terms, 0 people, 0 mental models
Flagship evaluation: 0 accepted, 0 rejected from 0 total
Pipeline complete: 0 final claims, 0 people, 0 concepts, 0 jargon terms, 0 categories

Resource Usage:
🎯 Total tokens: 0 (0 prompt + 0 completion)
⏱️  Total time: 0.2s
```

Every segment fails with ErrorCode formatting error, resulting in complete extraction failure.

---

## Technical Deep Dive

### The ErrorCode Enum Definition

From `src/knowledge_system/errors.py`:
```python
class ErrorCode(Enum):
    VALIDATION_SCHEMA_ERROR_HIGH = "VALIDATION_SCHEMA_ERROR_HIGH"
    LLM_API_ERROR = "LLM_API_ERROR"
    LLM_PARSE_ERROR = "LLM_PARSE_ERROR"
    # ... more codes
```

### KnowledgeSystemError Implementation

```python
class KnowledgeSystemError(Exception):
    def __init__(
        self,
        message: str,
        error_code: str | ErrorCode | None = None,
        context: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ):
        super().__init__(message)
        self.message = message
        # Correctly converts ErrorCode to string
        if isinstance(error_code, ErrorCode):
            self.error_code = error_code.value
        else:
            self.error_code = error_code or self.__class__.__name__
        self.context = context or {}
        self.cause = cause
```

### The Problem

Despite the constructor converting `error_code` to a string, **ErrorCode enums still appear somewhere in the exception representation**, causing string operations to fail.

**Hypotheses:**

1. **Exception args tuple**: When `super().__init__(message)` is called, if `message` itself contains operations on ErrorCode, the args tuple may contain ErrorCode enums

2. **Context dict values**: If any value in the `context` dict is an ErrorCode enum, and something tries to format that context

3. **Nested exceptions**: The `cause` exception might contain ErrorCode enums in its representation

4. **Logger formatting**: The logging framework might be attempting to format exception arguments before our `__str__` method is called

---

## Attempted Fixes (Partial Success)

### Fix 1: ErrorCode Handling in KnowledgeSystemError.__str__()
**File**: `src/knowledge_system/errors.py`  
**Status**: Applied, but insufficient

```python
def __str__(self) -> str:
    """Return formatted error message."""
    parts = [self.message]
    
    if self.error_code:
        parts.append(f"[{self.error_code}]")
    
    if self.context:
        # Ensure all context values are properly stringified
        context_items = []
        for k, v in self.context.items():
            if isinstance(v, ErrorCode):
                context_items.append(f"{k}={v.value}")
            else:
                context_items.append(f"{k}={v}")
        context_str = ", ".join(context_items)
        parts.append(f"({context_str})")
    
    return " ".join(parts)
```

**Result**: Error persists, suggesting the problem occurs before `__str__()` is called

### Fix 2: Safe Exception Formatting in unified_miner.py
**File**: `src/knowledge_system/processors/hce/unified_miner.py`  
**Status**: Applied, catches formatting errors but doesn't fix root cause

```python
try:
    error_msg = str(e)
except Exception as format_error:
    error_msg = f"<exception formatting failed: {type(e).__name__}>"
    logger.debug(f"Exception formatting error: {format_error}")
```

**Result**: Prevents crash during logging but doesn't fix the underlying ErrorCode propagation

### Fix 3: ErrorCode Comparison Fix
**File**: `src/knowledge_system/core/llm_adapter.py`  
**Status**: Applied, fixes comparison but not the main issue

```python
# Before
if e.error_code == ErrorCode.LLM_API_ERROR:

# After
if e.error_code == ErrorCode.LLM_API_ERROR.value:
```

### Fix 4: String Conversion in schema_validator.py
**File**: `src/knowledge_system/processors/hce/schema_validator.py`  
**Status**: Applied, prevents one error path

```python
# Ensure all errors are strings before joining
error_strings = [str(e) for e in errors]
raise KnowledgeSystemError(
    f"Schema validation failed for {schema_name}: {'; '.join(error_strings)}",
    error_code=ErrorCode.VALIDATION_SCHEMA_ERROR_HIGH,
)
```

---

## Why These Fixes Are Insufficient

The error **still occurs**, which means:

1. The ErrorCode enum is getting into exception representations **before** our error handling code runs
2. Python's exception machinery or the logging framework is attempting string operations on the exception **before** our `__str__()` method is called
3. There may be multiple code paths where ErrorCode enums are being improperly handled

The error "sequence item 0: expected str instance, ErrorCode found" specifically indicates that:
- A list/tuple's **first element** is an ErrorCode enum
- Something is trying to `.join()` that list
- This happens during exception construction or formatting, not during our explicit handling

---

## Investigation Needed

### 1. Exception Construction Audit
Search for all locations where exceptions are created with ErrorCode:

```bash
grep -r "raise.*ErrorCode\." src/knowledge_system/
grep -r "KnowledgeSystemError.*ErrorCode" src/knowledge_system/
```

Look for patterns like:
```python
# WRONG - if this ever happens
raise Exception(ErrorCode.SOMETHING, "message")

# CORRECT
raise KnowledgeSystemError("message", ErrorCode.SOMETHING)
```

### 2. Logger Formatter Investigation
Check if the logging configuration attempts to format exception args:

```bash
grep -r "logging.Formatter" src/knowledge_system/
grep -r "exc_info" src/knowledge_system/
```

### 3. Deep Exception Inspection
Add comprehensive debugging to catch ErrorCode in exception args:

```python
def log_exception_debug(e: Exception):
    import logging
    logger = logging.getLogger(__name__)
    
    logger.debug(f"Exception type: {type(e)}")
    logger.debug(f"Exception args: {e.args}")
    logger.debug(f"Args types: {[type(arg) for arg in e.args]}")
    
    if hasattr(e, '__dict__'):
        for k, v in e.__dict__.items():
            logger.debug(f"  {k}: {v} (type: {type(v)})")
            if isinstance(v, ErrorCode):
                logger.error(f"FOUND ErrorCode IN EXCEPTION DICT: {k}={v}")
```

### 4. Traceback Analysis
Enable full traceback logging to see exactly where the TypeError originates:

```python
import traceback
import logging

try:
    # code that fails
except Exception as e:
    logging.error(f"Full traceback:\n{traceback.format_exc()}")
    # Also log the exception object internals
    logging.error(f"Exception repr: {repr(e)}")
    logging.error(f"Exception args: {e.args}")
```

---

## Recommended Fix Strategy

### Phase 1: Defensive Programming (Immediate)
Add ErrorCode→string conversion at **every** exception creation point:

```python
# Create a safe wrapper
def raise_llm_error(message: str, error_code: ErrorCode):
    """Safely raise KnowledgeSystemError with ErrorCode."""
    # Ensure message doesn't contain ErrorCode references
    safe_message = str(message)
    raise KnowledgeSystemError(safe_message, error_code.value)  # Pass string value
```

### Phase 2: Exception Args Sanitization (Short-term)
Override `Exception.__init__()` in `KnowledgeSystemError` to sanitize args:

```python
class KnowledgeSystemError(Exception):
    def __init__(self, message: str, error_code=None, context=None, cause=None):
        # Convert any ErrorCode in message to string BEFORE passing to super()
        safe_message = self._sanitize_message(message)
        super().__init__(safe_message)  # Only pass sanitized string
        
        # Store error_code separately (already done)
        if isinstance(error_code, ErrorCode):
            self.error_code = error_code.value
        else:
            self.error_code = error_code
            
        self.context = self._sanitize_context(context or {})
        self.cause = cause
    
    @staticmethod
    def _sanitize_message(msg):
        """Ensure message is a plain string without ErrorCode references."""
        if isinstance(msg, str):
            return msg
        # Handle other types
        return str(msg)
    
    @staticmethod
    def _sanitize_context(context: dict):
        """Convert any ErrorCode values in context to strings."""
        return {
            k: (v.value if isinstance(v, ErrorCode) else v)
            for k, v in context.items()
        }
```

### Phase 3: Global Error Code Policy (Long-term)
1. **Never pass ErrorCode enums as positional arguments** to any exception
2. **Always use keyword argument** `error_code=ErrorCode.XXX`
3. **Add linting rule** to detect `raise SomeError(ErrorCode.XXX)`
4. **Add type hints** to enforce `error_code: str` in all exception __init__ methods

---

## Impact Assessment

### Systems Affected
- ✅ **CLI Summarization**: Completely broken (0% success rate)
- ✅ **GUI Summarization**: Completely broken (0% success rate)
- ✅ **HCE Pipeline**: Completely non-functional
- ⚠️ **Other LLM Operations**: Potentially affected if they use KnowledgeSystemError

### User Impact
- Users receive "success" messages but get no actual content
- Zero claims, entities, or insights extracted
- Silent data loss (appears successful but produces nothing)
- Complete waste of API tokens/costs (if LLM is called at all)

### Data Integrity
- No data corruption (nothing is extracted to corrupt)
- No data loss of existing data
- New processing produces empty results

---

## Testing Recommendations

### Unit Tests Needed

```python
def test_knowledge_system_error_with_error_code_enum():
    """Test that ErrorCode enums don't break exception formatting."""
    error = KnowledgeSystemError(
        "Test error",
        error_code=ErrorCode.LLM_PARSE_ERROR
    )
    
    # Should not raise TypeError
    error_str = str(error)
    assert "LLM_PARSE_ERROR" in error_str
    assert isinstance(error.error_code, str)

def test_knowledge_system_error_with_error_code_in_context():
    """Test that ErrorCode in context dict doesn't break formatting."""
    error = KnowledgeSystemError(
        "Test error",
        error_code=ErrorCode.LLM_PARSE_ERROR,
        context={"nested_code": ErrorCode.VALIDATION_SCHEMA_ERROR_HIGH}
    )
    
    # Should not raise TypeError
    error_str = str(error)
    assert "VALIDATION_SCHEMA_ERROR_HIGH" in error_str

def test_exception_logging_with_error_code():
    """Test that logging exceptions with ErrorCode doesn't fail."""
    import logging
    logger = logging.getLogger("test")
    
    try:
        raise KnowledgeSystemError(
            "Test error",
            ErrorCode.LLM_API_ERROR
        )
    except Exception as e:
        # Should not raise TypeError
        logger.error(f"Error occurred: {e}")
        logger.exception("Exception details")
```

### Integration Tests Needed

```python
def test_hce_pipeline_basic_extraction():
    """Test that HCE pipeline can extract content from a simple document."""
    document = "Steve Jobs founded Apple in 1976."
    
    # Should extract at least 1 claim
    result = run_hce_pipeline(document)
    assert result.claims_count > 0
    assert result.people_count > 0  # Should find "Steve Jobs"
    assert result.processing_time > 0  # Should actually process

def test_unified_miner_error_handling():
    """Test that UnifiedMiner handles errors gracefully."""
    # Trigger an error condition
    bad_segment = create_invalid_segment()
    
    miner = UnifiedMiner(llm)
    # Should not raise TypeError about ErrorCode
    result = miner.mine_segment(bad_segment)
    
    # Should return empty result, not crash
    assert isinstance(result, UnifiedMinerOutput)
    assert len(result.claims) == 0
```

---

## Priority & Next Steps

### Priority: **P0 - CRITICAL**
This bug completely breaks core functionality. All HCE extraction features are non-functional.

### Immediate Actions (Today)
1. Apply Phase 1 defensive fixes to all exception creation points
2. Add comprehensive exception debugging in unified_miner.py
3. Capture full traceback and exception internals to identify exact source

### Short-term Actions (This Week)
1. Implement Phase 2 exception args sanitization
2. Add unit tests for ErrorCode handling
3. Audit all `raise` statements in HCE codebase
4. Test with real documents to verify fix

### Long-term Actions (Next Sprint)
1. Implement Phase 3 global error code policy
2. Add linting rules to prevent ErrorCode misuse
3. Create comprehensive test suite for exception handling
4. Document proper ErrorCode usage patterns

---

## Additional Context

### Related Issues
- Profile parameter removal (COMPLETED - unrelated to this bug)
- JobType import fixes (COMPLETED - unrelated to this bug)
- CLI model reference fixes (COMPLETED - unrelated to this bug)

### Timeline
- Bug discovered: 2024-10-14 during profile parameter removal testing
- Initial investigation: 2024-10-14
- Partial fixes applied: 2024-10-14
- **Bug persists**: Root cause not yet identified

### Contact
For questions about this bug report, refer to the agent session logs from 2024-10-14.

---

## Appendix A: Sample Error Logs

```
2025-10-14 21:13:05.993 | ERROR   | knowledge_system.processors.hce.unified_pipeline:_generate_short_summary:293 | Failed to generate short summary: sequence item 0: expected str instance, ErrorCode found

2025-10-14 21:13:05.994 | WARNING | logging:callHandlers:1744 | Structured JSON generation failed, falling back: sequence item 0: expected str instance, ErrorCode found

2025-10-14 21:13:05.994 | WARNING | logging:callHandlers:1744 | Unified mining failed for segment seg_0000: sequence item 0: expected str instance, ErrorCode found

[... repeats for all 91 segments ...]

2025-10-14 21:13:18.425 | INFO | knowledge_system.processors.hce.unified_pipeline:process:119 | Unified mining extracted: 0 claims, 0 jargon terms, 0 people, 0 mental models

2025-10-14 21:13:18.425 | INFO | knowledge_system.processors.hce.unified_pipeline:process:154 | Flagship evaluation: 0 accepted, 0 rejected from 0 total

2025-10-14 21:13:18.426 | ERROR | knowledge_system.processors.hce.unified_pipeline:_generate_long_summary:391 | Failed to generate long summary: sequence item 0: expected str instance, ErrorCode found
```

## Appendix B: Code Locations Reference

```
src/knowledge_system/
├── errors.py                               # ErrorCode enum, KnowledgeSystemError class
├── core/
│   └── llm_adapter.py                      # Line 378: ErrorCode comparison
├── processors/
│   └── hce/
│       ├── models/
│       │   └── llm_system2.py              # Lines 91-93, 117-119: Raises with ErrorCode
│       ├── unified_miner.py                # Lines 87-95, 156-177: Exception handling
│       ├── schema_validator.py             # Lines 131-136: Raises with error list
│       └── unified_pipeline.py             # Orchestrates pipeline, logs failures
```

---

**Report Generated**: 2024-10-14  
**Report Version**: 1.0  
**Status**: Investigation Ongoing
