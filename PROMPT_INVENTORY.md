# Prompt Inventory - All Prompts in Knowledge_Chipper

This document catalogs all prompts currently used in the Knowledge_Chipper/SkipThePodcast system.

## Current Active Prompts (HCE Pipeline)

### Mining Stage Prompts (Pass 1 - Extraction)

#### 1. `unified_miner_transcript_own_V3.txt`
**Purpose:** Extract claims, jargon, people, and mental models from our own high-quality transcripts  
**Location:** `src/knowledge_system/processors/hce/prompts/`  
**Usage:** Default for "Transcript (Own)" content type with reliable speaker labels and timestamps  
**Key Features:** Comprehensive extraction with speaker attribution, evidence spans with timestamps

#### 2. `unified_miner_transcript_third_party.txt`
**Purpose:** Extract entities from third-party transcripts with missing/unreliable metadata  
**Location:** `src/knowledge_system/processors/hce/prompts/`  
**Usage:** For "Transcript (Third-party)" content type  
**Key Features:** Handles missing speaker labels, imprecise timestamps, transcription errors

#### 3. `unified_miner_document.txt`
**Purpose:** Extract entities from written documents (PDFs, books, articles, papers)  
**Location:** `src/knowledge_system/processors/hce/prompts/`  
**Usage:** For "Document (PDF/eBook)" and "Document (White Paper)" content types  
**Key Features:** Location-based references instead of timestamps, citation tracking, formal language handling

#### 4. `unified_miner.txt`
**Purpose:** Generic unified miner prompt (fallback)  
**Location:** `src/knowledge_system/processors/hce/prompts/`  
**Usage:** Fallback when content-type-specific prompts don't exist  
**Key Features:** General-purpose extraction for all entity types

#### 5. `unified_miner_liberal.txt`
**Purpose:** Liberal extraction variant - extracts everything including trivial claims  
**Location:** `src/knowledge_system/processors/hce/prompts/`  
**Usage:** When selectivity="liberal" setting is chosen  
**Key Features:** High recall, ~15 claims per segment, relies on evaluator to filter

#### 6. `unified_miner_moderate.txt`
**Purpose:** Moderate extraction variant - balanced approach  
**Location:** `src/knowledge_system/processors/hce/prompts/`  
**Usage:** When selectivity="moderate" setting is chosen (current default)  
**Key Features:** Balanced recall/precision, ~5 claims per segment

#### 7. `unified_miner_conservative.txt`
**Purpose:** Conservative extraction variant - only high-value claims  
**Location:** `src/knowledge_system/processors/hce/prompts/`  
**Usage:** When selectivity="conservative" setting is chosen  
**Key Features:** High precision, ~2 claims per segment, filters at extraction stage

### Evaluation Stage Prompts (Pass 2 - Ranking & Filtering)

#### 8. `flagship_evaluator.txt`
**Purpose:** Review and rank all extracted claims using 6-dimension scoring  
**Location:** `src/knowledge_system/processors/hce/prompts/`  
**Usage:** Main evaluation prompt for flagship model (Gemini 2.0 Flash, GPT-4o, Claude Sonnet 4.5)  
**Key Features:** 
- 6 dimensions: epistemic_value, actionability, novelty, verifiability, understandability, temporal_stability, scope
- Accept/reject decisions with reasoning
- Multi-profile scoring for personalized importance

#### 9. `concepts_evaluator.txt`
**Purpose:** Review, deduplicate, and rank mental models/frameworks  
**Location:** `src/knowledge_system/processors/hce/prompts/`  
**Usage:** Post-processing for mental models extracted by miners  
**Key Features:** Merge similar frameworks, filter vague appeals, rank by analytical sophistication

#### 10. `jargon_evaluator.txt`
**Purpose:** Review, deduplicate, and rank jargon terms  
**Location:** `src/knowledge_system/processors/hce/prompts/`  
**Usage:** Post-processing for jargon terms extracted by miners  
**Key Features:** Merge aliases, filter common terms, rank by importance and specificity

#### 11. `people_evaluator.txt`
**Purpose:** Review, deduplicate, and rank person mentions  
**Location:** `src/knowledge_system/processors/hce/prompts/`  
**Usage:** Post-processing for people/organizations extracted by miners  
**Key Features:** Merge name variants, identify roles, filter trivial mentions, rank by significance

### Summary Generation Prompts

#### 12. `short_summary.txt`
**Purpose:** Generate concise 1-2 paragraph overview of content  
**Location:** `src/knowledge_system/processors/hce/prompts/`  
**Usage:** Creates high-level context before detailed claim extraction  
**Key Features:** Main topic, context, participants, themes, tone

#### 13. `long_summary.txt`
**Purpose:** Generate comprehensive 3-5 paragraph synthesis from extracted claims  
**Location:** `src/knowledge_system/processors/hce/prompts/`  
**Usage:** Final output - integrates top claims, entities, and themes into narrative  
**Key Features:** Context, core insights, tensions/contradictions, intellectual contribution

## Speaker Attribution Prompts

#### 14. LLM Speaker Suggester Prompt (inline)
**Purpose:** Suggest speaker names based on metadata and transcript samples  
**Location:** `src/knowledge_system/utils/llm_speaker_suggester.py` (lines 434-455+)  
**Usage:** Initial speaker name inference from metadata and first 5 statements per speaker  
**Key Features:** Skeptical evaluation of diarization splits, phonetic matching, metadata priority

#### 15. LLM Speaker Validator Prompt (inline)
**Purpose:** Validate proposed speaker assignments using speech content analysis  
**Location:** `src/knowledge_system/utils/llm_speaker_validator.py` (lines 238-273)  
**Usage:** "First skim" validation before user confirmation  
**Key Features:** Confidence scoring, accept/reject/uncertain recommendations, alternative suggestions

## Question Mapper Prompts

#### 16. `discovery.txt`
**Purpose:** Identify key questions that extracted claims answer  
**Location:** `src/knowledge_system/processors/question_mapper/prompts/`  
**Usage:** Question discovery phase - groups related claims by inquiry  
**Key Features:** Question types (factual, causal, normative, comparative, procedural, forecasting)

#### 17. `assignment.txt`
**Purpose:** Assign claims to questions with relation types  
**Location:** `src/knowledge_system/processors/question_mapper/prompts/`  
**Usage:** Question assignment phase - maps claims to discovered questions  
**Key Features:** 7 relation types (answers, partial_answer, supports_answer, contradicts, prerequisite, follow_up, context)

## Legacy/Deprecated Prompts

#### 18. `unified_miner_transcript_own.txt`
**Purpose:** Earlier version of transcript mining prompt  
**Location:** `src/knowledge_system/processors/hce/prompts/`  
**Status:** Superseded by V3 variant  

#### 19. `unified_miner_transcript_own_V2.txt`
**Purpose:** Second version of transcript mining prompt  
**Location:** `src/knowledge_system/processors/hce/prompts/`  
**Status:** Superseded by V3 variant

## Planned Prompts (Whole-Document Mining)

### From WHOLE_DOCUMENT_MINING_DETAILED_PLAN.md

#### 20. Whole-Document Mining Prompt (Pass 1)
**Purpose:** Extract and score all entities from entire document in single API call  
**Status:** Planned - not yet implemented  
**Key Features:** 
- Process complete transcript (no segmentation)
- Extract claims, jargon, people, mental models
- Score on 6 dimensions
- Rank by importance
- Infer speakers with confidence
- Filter trivial claims
- All in one pass

#### 21. Whole-Document Summary Prompt (Pass 2)
**Purpose:** Generate world-class long summary from Pass 1 results  
**Status:** Planned - not yet implemented  
**Key Features:**
- Synthesize from top-ranked claims
- Integrate all entity types
- Use YouTube AI summary as additional context
- 3-5 paragraph narrative

## Prompt Selection Logic

### Content Type Selection
The system dynamically selects prompts based on content type:

```python
content_type_files = {
    "transcript_own": "unified_miner_transcript_own_V3.txt",
    "transcript_third_party": "unified_miner_transcript_third_party.txt",
    "document": "unified_miner_document.txt"
}
```

### Selectivity Selection
Within each content type, selectivity level determines extraction aggressiveness:

```python
selectivity_files = {
    "liberal": "unified_miner_liberal.txt",
    "moderate": "unified_miner_moderate.txt",
    "conservative": "unified_miner_conservative.txt"
}
```

### Fallback Chain
1. Try content-type-specific prompt
2. If not found, try selectivity-based prompt
3. If not found, use generic `unified_miner.txt`

## Prompt Versioning

Prompts use version suffixes when multiple iterations exist:
- `unified_miner_transcript_own.txt` (original)
- `unified_miner_transcript_own_V2.txt` (second iteration)
- `unified_miner_transcript_own_V3.txt` (current, third iteration)

## Notes

- All prompts return structured JSON output (except long_summary.txt which returns plain text)
- Prompts include extensive examples and anti-examples
- Prompts enforce strict output schemas with validation
- Most prompts include "worked examples" to demonstrate expected behavior
- Prompts are designed to be model-agnostic (work with GPT-4, Claude, Gemini, Qwen, etc.)

