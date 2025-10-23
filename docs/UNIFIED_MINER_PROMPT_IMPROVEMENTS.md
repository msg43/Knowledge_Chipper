# Unified Miner Prompt Improvements

## Overview
This document describes the comprehensive improvements made to the `unified_miner.txt` prompt to enhance extraction quality and consistency.

## What Was Improved

### 1. **Individual Claim Type Examples**
Added dedicated examples for each of the 5 claim types:
- **Factual**: Bitcoin price drops with specific data
- **Causal**: Supply chain disruptions causing inflation
- **Normative**: Investment diversification recommendations
- **Forecast**: Fed rate cut predictions with reasoning
- **Definition**: Technical terms like "stagflation"

**Why**: Previously, all claim types were demonstrated in a single complex example, making it harder for models to distinguish between types.

### 2. **Stance Classification Examples**
Added clear examples for all 4 stance types:
- **Asserts**: Confident presentation with supporting reasoning
- **Questions**: Expressions of doubt or skepticism
- **Opposes**: Active refutation with counterevidence
- **Neutral**: Objective reporting without endorsement

**Why**: Only "asserts" and "questions" were demonstrated before. "Opposes" and "neutral" are critical for balanced extraction.

### 3. **Enhanced Jargon Examples**
Added both good and bad examples:
- **Good**: SPVs (special purpose vehicles), backpropagation
- **Bad**: Common terms like "stock market", "investors", "company"

**Why**: Models often over-extract common business vocabulary. Anti-examples help establish the threshold for genuine jargon.

### 4. **People Extraction Edge Cases**
Added nuanced examples showing:
- **Extract**: Warren Buffett's investment philosophy, Keynes' economic theories
- **Don't Extract**: Casual mentions ("my friend Bob"), speaker self-introductions

**Why**: Distinguishes between substantive discussion and casual mentions, preventing noise in the people database.

### 5. **Mental Models Clarification**
Added strong framework examples:
- **Circle of Competence**: Investment decision framework
- **Falsificationism**: Scientific methodology
- **Porter's Five Forces**: Strategic analysis framework

Added anti-examples:
- **Don't Extract**: Casual mentions of "supply and demand", "opportunity cost"
- **Key Distinction**: Frameworks being *explained or applied* vs. concepts merely *mentioned*

**Why**: The original example ("wealth effect mechanism") was borderline - not really a framework. New examples show clear structured approaches/methodologies.

### 6. **Comprehensive Anti-Examples Section**
Organized by type with specific bad extractions to avoid:

**Bad Claims**:
- Procedural statements ("Today I want to talk about...")
- Meta-commentary ("As I mentioned earlier...")
- Trivially obvious facts ("The stock market exists")
- Vague value statements ("This is interesting")

**Bad Jargon**:
- Common vocabulary in technical contexts
- Everyday words

**Bad People**:
- Unnamed individuals
- Speaker self-introductions

**Bad Mental Models**:
- Vague appeals ("common sense")
- Casual concept mentions without framework explanation

**Why**: Explicit anti-examples help models avoid common over-extraction patterns.

## Structural Improvements

### Before
- 2 examples total
- 1 comprehensive example, 1 trivial example
- 1 anti-example section
- ~208 lines

### After
- 20+ focused examples
- Organized by type (Claims, Stance, Jargon, People, Mental Models)
- Separate sections for good/bad examples within each type
- Comprehensive examples showing all types together
- Extensive anti-examples organized by type
- ~472 lines (more than doubled, but much clearer)

## Expected Benefits

### 1. **Better Precision**
- Fewer false positives (trivial claims, common vocabulary)
- Clearer thresholds through anti-examples

### 2. **Better Recall**
- More complete stance classification (opposes, neutral now clear)
- Better mental model detection with framework focus

### 3. **Improved Consistency**
- Individual examples make it easier for models to learn patterns
- Anti-examples establish clear boundaries

### 4. **Model-Agnostic Improvements**
- Helps both stronger models (GPT-4, Claude) refine edge cases
- Helps weaker models (local Ollama) understand requirements through explicit examples

### 5. **Better Mental Models Quality**
- Fixed misconception that "wealth effect" is a mental model
- Clear emphasis on structured frameworks vs. simple concepts
- Should reduce noise in mental models database

## Testing Recommendations

To validate these improvements:

1. **Run on existing test content** - Compare extraction quality before/after
2. **Monitor precision** - Check if over-extraction decreases (fewer common terms as jargon, fewer trivial claims)
3. **Monitor recall** - Check if "opposes" and "neutral" stances are now detected
4. **Mental models quality** - Verify that only structured frameworks are extracted
5. **Edge case handling** - Test with procedural content, casual mentions, meta-commentary

## Notes

- The prompt is now significantly longer (~472 lines vs ~208), which may increase token costs slightly
- However, better extraction quality should reduce downstream correction needs
- The structure with XML-like tags makes it easy to add more examples in the future
- Consider A/B testing on a sample set to quantify improvements

## Related Files
- `/src/knowledge_system/processors/hce/prompts/unified_miner.txt` - The improved prompt
- `/src/knowledge_system/processors/hce/unified_miner.py` - Uses the prompt
- `/schemas/miner_output.v1.json` - Output schema (single source of truth)
