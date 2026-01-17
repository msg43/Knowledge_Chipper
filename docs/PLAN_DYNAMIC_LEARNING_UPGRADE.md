# Dynamic Learning System Upgrade Plan

**Version:** 2.1 (Revised January 2026)  
**Status:** Planning Phase

---

## Executive Summary

This plan upgrades Knowledge Chipper's two-pass extraction system to incorporate user feedback learning and real-time quality validation. The new architecture uses a **"Sandwich" Validation Model**:

1. **Taste Filter (Vector Similarity)**: Catches **style/taste** errors by matching against known rejections
2. **Truth Critic (LLM Reflexion)**: Catches **logic/factual** errors that vector search cannot detect for novel entities
3. **Taste Engine (Vector Store)**: Stores Accept/Reject feedback as embeddings - the ONLY source of "taste"
4. **Dynamic Prompt Injection**: RAG-based few-shot learning using semantic similarity
5. **Positive Echo (Scoring Boost)**: Actively surfaces good content that matches accepted patterns

### The "Taste vs. Truth" Distinction

| Validation Type | Method | Catches | Example |
|-----------------|--------|---------|---------|
| **Taste** | Vector Similarity | Style errors, duplicate patterns | "This claim is too trivial" (seen before) |
| **Truth** | LLM Reflexion | Logic errors, novel hallucinations | "Washington University is an Organization, not a Person" (never seen) |

**CRITICAL**: Both are required. Vector search finds duplicates of past mistakes. LLM reasoning catches *new* mistakes that haven't been rejected yet.

**Key Architectural Principles:**

- **No Static Personas**: System learns taste EXCLUSIVELY from vector history (no hardcoded behavior profiles)
- **Golden Set Bootstrap**: Cold start handled via versioned JSON file, not hardcoded Python
- **Hybrid Safety Filtering**: Similarity-based filtering with auto-discard, flag, and keep thresholds
- **Positive Echo**: High-similarity to accepted patterns → +2.0 importance boost
- **Async Processing**: Web sync uses queue + background worker (no synchronous embedding)
- **Signal Hierarchy**: Context uses Tags > Summaries > Title (explicitly EXCLUDES Description)

---

## Architecture Overview: The "Sandwich" Model

```mermaid
flowchart TD
    subgraph InputBundle [Input Bundle]
        Tags[Tags & Categories]
        LocalSum[Local LLM Summary]
        YTSum[YouTube AI Summary]
        Title[Video Title]
        Desc[Description - EXCLUDED]
    end
    
    subgraph Processing [Dynamic Learning Pipeline - "Sandwich" Validation]
        Tags --> ContextAgg[Context Aggregate]
        LocalSum --> ContextAgg
        YTSum --> ContextAgg
        Title --> ContextAgg
        Desc -.->|EXCLUDED| X[X]
        
        ContextAgg --> DynamicInject[Dynamic Prompt Injection]
        TasteDB[(TasteEngine ChromaDB)] --> DynamicInject
        
        DynamicInject --> Pass1[Pass 1: extraction_pass.py]
        
        Pass1 --> TasteFilter[Pass 1.5a: Taste Filter<br/>Vector Similarity - STYLE]
        TasteDB --> TasteFilter
        
        TasteFilter -->|flagged/kept entities| TruthCritic[Pass 1.5b: Truth Critic<br/>LLM Reflexion - LOGIC]
        TasteFilter -->|auto-discarded| Discard[Discarded]
        
        TasteFilter --> PositiveEcho[Positive Echo<br/>+2.0 Boost for >95% Accept Match]
        TasteDB --> PositiveEcho
        PositiveEcho --> TruthCritic
        
        TruthCritic --> Pass2[Pass 2: synthesis_pass.py]
        Pass2 --> Database[(SQLite Database)]
    end
    
    subgraph FeedbackLoop [Async Feedback Loop]
        WebUI[Web UI Accept/Reject] --> API[/feedback/sync endpoint]
        API --> Queue[(pending_feedback SQLite)]
        Queue --> Worker[feedback_processor.py]
        Worker --> TasteDB
    end
    
    subgraph ColdStart [Cold Start Bootstrap - Versioned]
        GoldenJSON[golden_feedback.json<br/>version: 1.0] --> VersionCheck{Version Changed?}
        VersionCheck -->|Yes| Loader[Re-ingest Golden Set]
        VersionCheck -->|No| Skip[Skip]
        Loader --> TasteDB
    end
```

### The "Sandwich" Validation Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    PASS 1: EXTRACTION                           │
│  (with dynamic few-shot injection from TasteEngine)             │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│              PASS 1.5a: TASTE FILTER (Vector)                   │
│  • Catches STYLE errors: trivial facts, vague claims           │
│  • >95% similar to REJECT → AUTO-DISCARD                       │
│  • 80-95% similar → FLAG for review                            │
│  • >95% similar to ACCEPT → POSITIVE ECHO (+2.0 boost)         │
│  • FAST: ~50ms per entity (embedding lookup)                   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│              PASS 1.5b: TRUTH CRITIC (LLM)                      │
│  • Catches LOGIC errors: "Washington Univ" as Person           │
│  • Validates entity classifications for novel inputs           │
│  • Runs ONLY on high-value entities (score ≥ 7.0)              │
│  • Reasoning-first: "First explain, then verdict"              │
│  • Can override, flag, or approve                              │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    PASS 2: SYNTHESIS                            │
└─────────────────────────────────────────────────────────────────┘
```

---

## Phase 1: The "Sandwich" Validation Layer

### 1.1 Design Philosophy: Taste vs. Truth

**CRITICAL INSIGHT**: You need BOTH validation types:

| Layer | Method | Purpose | Speed |
|-------|--------|---------|-------|
| **Taste Filter** | Vector Similarity | Catch style patterns (trivial, vague, duplicate mistakes) | ~50ms/entity |
| **Truth Critic** | LLM Reflexion | Catch logic errors for **novel** entities | ~2s/entity |

**Why both?**
- Vector search finds things *similar to past rejections* but cannot reason about *new* hallucinations
- "Washington University is a Person" can only be caught by LLM reasoning (unless you've rejected it before)
- The Taste Filter runs on ALL entities (fast); the Truth Critic runs on HIGH-VALUE entities only (selective)

### 1.2 Taste Filter (Vector Similarity)

Create [`src/knowledge_system/processors/two_pass/taste_filter.py`](src/knowledge_system/processors/two_pass/taste_filter.py):

```python
"""
Taste Filter - Post-Extraction STYLE Validation (Vector-Based)

Uses vector similarity against rejected/accepted examples to:
1. DISCARD entities near-identical to past rejections (>95% similar)
2. FLAG entities suspiciously similar to past rejections (80-95%)
3. BOOST entities similar to past acceptances (>95% = +2.0 importance)
"""

from dataclasses import dataclass
from typing import Literal
from .extraction_pass import ExtractionResult

@dataclass
class FilterVerdict:
    """Result for a single entity."""
    action: Literal["discard", "flag", "keep", "boost"]
    similarity_to_reject: float  # Highest similarity to rejected examples
    similarity_to_accept: float  # Highest similarity to accepted examples
    matched_example: str         # Text of matched example (if any)
    reason_category: str         # Category of matched example
    warning_message: str         # Human-readable explanation
    score_adjustment: float      # Importance score adjustment (e.g., +2.0 for boost)

@dataclass
class TasteFilterResult:
    """Complete result from taste filtering."""
    claims: list[dict]           # Filtered claims with verdicts
    jargon: list[dict]           # Filtered jargon
    people: list[dict]           # Filtered people
    mental_models: list[dict]    # Filtered mental models
    
    discarded_count: int         # Auto-discarded (reject similarity > 0.95)
    flagged_count: int           # Flagged for review (reject similarity 0.80-0.95)
    boosted_count: int           # Positive Echo boost (accept similarity > 0.95)
    kept_count: int              # Kept (similarity < 0.80)
    
class TasteFilter:
    """
    TASTE validation via vector similarity.
    
    Catches STYLE errors: trivial facts, vague claims, patterns similar to past mistakes.
    
    Thresholds:
    - reject similarity > 0.95: AUTO-DISCARD (near-exact match to rejection)
    - reject similarity 0.80-0.95: FLAG (suspicious, needs human review)
    - accept similarity > 0.95: POSITIVE ECHO (+2.0 importance boost)
    - else: KEEP as-is
    
    NOTE: Cannot catch LOGIC errors (e.g., "Washington Univ is a Person").
    Use TruthCritic (LLM) for novel hallucinations.
    """
    
    # Similarity thresholds (cosine distance, lower = more similar)
    DISCARD_THRESHOLD = 0.05    # distance < 0.05 = similarity > 0.95
    FLAG_THRESHOLD = 0.20       # distance < 0.20 = similarity > 0.80
    BOOST_THRESHOLD = 0.05      # distance < 0.05 = similarity > 0.95 to ACCEPT
    
    # Positive Echo: Score boost for entities matching accepted patterns
    POSITIVE_ECHO_BOOST = 2.0   # +2.0 importance score
    
    def __init__(self, taste_engine):
        self.taste_engine = taste_engine
    
    def filter(self, extraction: ExtractionResult) -> TasteFilterResult:
        """
        Run taste filtering on extraction results.
        
        For each entity:
        1. Query TasteEngine for similar REJECTED examples (style check)
        2. Query TasteEngine for similar ACCEPTED examples (positive echo)
        3. Apply discard/flag/boost/keep verdict
        """
        filtered_claims = []
        filtered_jargon = []
        filtered_people = []
        filtered_models = []
        
        discarded = 0
        flagged = 0
        boosted = 0
        kept = 0
        
        # Process claims
        for claim in extraction.claims:
            verdict = self._check_entity(
                entity_text=claim.get('claim_text', ''),
                entity_type='claim'
            )
            
            if verdict.action == 'discard':
                discarded += 1
                # Log but don't include in output
                logger.info(f"AUTO-DISCARD claim (reject_sim={verdict.similarity_to_reject:.2f}): {claim.get('claim_text', '')[:50]}...")
                continue
            elif verdict.action == 'flag':
                flagged += 1
                claim['flagged'] = True
                claim['flag_reason'] = verdict.warning_message
                claim['similar_rejection'] = verdict.matched_example
            elif verdict.action == 'boost':
                # POSITIVE ECHO: Apply scoring boost
                boosted += 1
                current_importance = claim.get('importance_score', 5.0)
                claim['importance_score'] = min(10.0, current_importance + verdict.score_adjustment)
                claim['positive_echo'] = True
                claim['echo_reason'] = f"Matches accepted pattern: {verdict.matched_example[:50]}..."
                logger.info(f"POSITIVE ECHO (+{verdict.score_adjustment}): {claim.get('claim_text', '')[:50]}...")
            else:
                kept += 1
            
            filtered_claims.append(claim)
        
        # Process jargon (same logic with boost support)
        for term in extraction.jargon:
            verdict = self._check_entity(
                entity_text=term.get('term', ''),
                entity_type='jargon'
            )
            
            if verdict.action == 'discard':
                discarded += 1
                continue
            elif verdict.action == 'flag':
                flagged += 1
                term['flagged'] = True
                term['flag_reason'] = verdict.warning_message
            elif verdict.action == 'boost':
                boosted += 1
                current_importance = term.get('importance_score', 5.0)
                term['importance_score'] = min(10.0, current_importance + verdict.score_adjustment)
                term['positive_echo'] = True
            else:
                kept += 1
            
            filtered_jargon.append(term)
        
        # Process people
        for person in extraction.people:
            verdict = self._check_entity(
                entity_text=person.get('name', ''),
                entity_type='person'
            )
            
            if verdict.action == 'discard':
                discarded += 1
                continue
            elif verdict.action == 'flag':
                flagged += 1
                person['flagged'] = True
                person['flag_reason'] = verdict.warning_message
            elif verdict.action == 'boost':
                boosted += 1
                person['positive_echo'] = True
            else:
                kept += 1
            
            filtered_people.append(person)
        
        # Process mental models
        for model in extraction.mental_models:
            verdict = self._check_entity(
                entity_text=model.get('name', ''),
                entity_type='concept'
            )
            
            if verdict.action == 'discard':
                discarded += 1
                continue
            elif verdict.action == 'flag':
                flagged += 1
                model['flagged'] = True
                model['flag_reason'] = verdict.warning_message
            elif verdict.action == 'boost':
                boosted += 1
                model['positive_echo'] = True
            else:
                kept += 1
            
            filtered_models.append(model)
        
        return TasteFilterResult(
            claims=filtered_claims,
            jargon=filtered_jargon,
            people=filtered_people,
            mental_models=filtered_models,
            discarded_count=discarded,
            flagged_count=flagged,
            boosted_count=boosted,
            kept_count=kept,
        )
    
    def _check_entity(self, entity_text: str, entity_type: str) -> FilterVerdict:
        """
        Check a single entity against both REJECTED and ACCEPTED examples.
        
        Logic order (safety-first):
        1. Check against REJECTED pile first (discard/flag)
        2. If not rejected, check against ACCEPTED pile (boost)
        3. Else keep as-is
        """
        if not entity_text.strip():
            return FilterVerdict(
                action='keep',
                similarity_to_reject=0.0,
                similarity_to_accept=0.0,
                matched_example='',
                reason_category='',
                warning_message='',
                score_adjustment=0.0
            )
        
        # STEP 1: Check against REJECTED examples (safety-first)
        reject_results = self.taste_engine.query_similar(
            entity_text=entity_text,
            entity_type=entity_type,
            n_results=1,
            verdict_filter='reject'
        )
        
        reject_similarity = 0.0
        reject_match = None
        
        if reject_results:
            reject_match = reject_results[0]
            reject_similarity = 1.0 - reject_match['distance']
            
            # Check reject thresholds
            if reject_match['distance'] < self.DISCARD_THRESHOLD:  # > 95% similar to rejection
                return FilterVerdict(
                    action='discard',
                    similarity_to_reject=reject_similarity,
                    similarity_to_accept=0.0,
                    matched_example=reject_match['text'],
                    reason_category=reject_match['metadata'].get('reason_category', 'unknown'),
                    warning_message=f"Near-exact match to rejected example ({reject_similarity:.0%} similar)",
                    score_adjustment=0.0
                )
            elif reject_match['distance'] < self.FLAG_THRESHOLD:  # 80-95% similar to rejection
                return FilterVerdict(
                    action='flag',
                    similarity_to_reject=reject_similarity,
                    similarity_to_accept=0.0,
                    matched_example=reject_match['text'],
                    reason_category=reject_match['metadata'].get('reason_category', 'unknown'),
                    warning_message=f"Suspicious similarity to rejection: '{reject_match['text'][:50]}...' ({reject_similarity:.0%})",
                    score_adjustment=0.0
                )
        
        # STEP 2: Check against ACCEPTED examples (Positive Echo)
        accept_results = self.taste_engine.query_similar(
            entity_text=entity_text,
            entity_type=entity_type,
            n_results=1,
            verdict_filter='accept'
        )
        
        if accept_results:
            accept_match = accept_results[0]
            accept_similarity = 1.0 - accept_match['distance']
            
            if accept_match['distance'] < self.BOOST_THRESHOLD:  # > 95% similar to acceptance
                return FilterVerdict(
                    action='boost',
                    similarity_to_reject=reject_similarity,
                    similarity_to_accept=accept_similarity,
                    matched_example=accept_match['text'],
                    reason_category=accept_match['metadata'].get('reason_category', 'quality'),
                    warning_message='',
                    score_adjustment=self.POSITIVE_ECHO_BOOST  # +2.0
                )
        
        # STEP 3: No strong match either way - keep as-is
        return FilterVerdict(
            action='keep',
            similarity_to_reject=reject_similarity,
            similarity_to_accept=0.0,
            matched_example='',
            reason_category='',
            warning_message='',
            score_adjustment=0.0
        )
```

### 1.3 Truth Critic (LLM Reflexion)

Create [`src/knowledge_system/processors/two_pass/truth_critic.py`](src/knowledge_system/processors/two_pass/truth_critic.py):

```python
"""
Truth Critic - Post-Extraction LOGIC Validation (LLM-Based)

Catches factual/logical errors that vector similarity cannot detect:
- Entity misclassification ("Washington University" as Person)
- Logical inconsistencies
- Novel hallucinations not seen in past rejections

Runs ONLY on high-value entities (importance >= 7.0) to minimize latency.
Uses "Reasoning First" prompt strategy.
"""

from dataclasses import dataclass
from typing import Literal, Optional
import json

from ..core.llm_adapter import LLMAdapter
from ..logger import get_logger

logger = get_logger(__name__)

@dataclass
class CriticVerdict:
    """Verdict for a single entity from the Truth Critic."""
    action: Literal["approve", "override", "flag"]
    reasoning: str               # LLM's reasoning (shown first in output)
    original_type: str           # Original entity type
    corrected_type: Optional[str]  # Corrected type if override
    confidence: float            # Critic's confidence (0-1)
    warning_message: str         # Human-readable explanation

@dataclass 
class CriticResult:
    """Complete result from Truth Critic validation."""
    verdicts: dict[str, CriticVerdict]  # entity_id -> verdict
    overrides_count: int
    flagged_count: int
    approved_count: int
    total_reviewed: int
    latency_seconds: float

class TruthCritic:
    """
    LLM-based LOGIC validation for novel entities.
    
    Purpose: Catch errors that vector similarity CANNOT detect:
    - "Washington University" classified as Person (it's an Organization)
    - "The CEO said" classified as Person (it's a title, not a name)
    - Logical contradictions in claims
    
    Strategy:
    - Runs AFTER TasteFilter (which handles style)
    - Only reviews high-value entities (importance >= 7.0) for latency
    - Uses "Reasoning First" prompt: explain WHY before giving verdict
    - Can override entity type, flag for review, or approve
    """
    
    # Only review entities with importance score >= this threshold
    REVIEW_THRESHOLD = 7.0
    
    # Maximum entities to review per extraction (latency budget)
    MAX_ENTITIES_PER_RUN = 10
    
    def __init__(self, llm_adapter: LLMAdapter = None):
        self.llm = llm_adapter or LLMAdapter()
        self._load_prompt_template()
    
    def _load_prompt_template(self):
        """Load the critic prompt template."""
        from pathlib import Path
        prompt_path = Path(__file__).parent / "prompts" / "truth_critic.txt"
        
        if prompt_path.exists():
            self.prompt_template = prompt_path.read_text()
        else:
            # Fallback inline template
            self.prompt_template = self._get_default_prompt()
    
    def _get_default_prompt(self) -> str:
        return '''You are a TRUTH CRITIC validating extracted entities.

Your job is to catch LOGIC errors, not style preferences:
- Entity type misclassification (e.g., "Washington University" labeled as Person)
- Titles/roles labeled as specific people (e.g., "the CEO" is not a named person)
- Logical impossibilities in claims

## ENTITY TO VALIDATE

Type: {{entity_type}}
Content: {{entity_text}}
Importance Score: {{importance_score}}
Context (from source): {{context_snippet}}

## INSTRUCTIONS

1. First, REASON about whether this entity is correctly classified
2. Consider: Is this actually a {{entity_type}}? Could it be misclassified?
3. Output your reasoning BEFORE your verdict

## OUTPUT FORMAT (JSON)

{
  "reasoning": "Your step-by-step logic here...",
  "verdict": "approve" | "override" | "flag",
  "corrected_type": null | "person" | "organization" | "concept" | "claim" | "jargon",
  "confidence": 0.0-1.0,
  "explanation": "Brief human-readable explanation"
}

Be conservative: only override if you're confident (>0.8) something is wrong.
Flag if uncertain. Approve if it looks correct.'''
    
    def validate(
        self, 
        extraction_result, 
        source_context: str = ""
    ) -> CriticResult:
        """
        Validate high-importance entities for logic errors.
        
        Args:
            extraction_result: Output from TasteFilter
            source_context: First ~500 chars of transcript for context
            
        Returns:
            CriticResult with verdicts for reviewed entities
        """
        import time
        start_time = time.time()
        
        # Collect high-value entities to review
        entities_to_review = self._select_entities_for_review(extraction_result)
        
        if not entities_to_review:
            return CriticResult(
                verdicts={},
                overrides_count=0,
                flagged_count=0,
                approved_count=0,
                total_reviewed=0,
                latency_seconds=0.0
            )
        
        # Review each entity
        verdicts = {}
        overrides = 0
        flagged = 0
        approved = 0
        
        for entity_id, entity_data in entities_to_review[:self.MAX_ENTITIES_PER_RUN]:
            verdict = self._review_entity(entity_data, source_context)
            verdicts[entity_id] = verdict
            
            if verdict.action == 'override':
                overrides += 1
            elif verdict.action == 'flag':
                flagged += 1
            else:
                approved += 1
        
        latency = time.time() - start_time
        
        logger.info(
            f"TruthCritic: reviewed {len(verdicts)} entities in {latency:.2f}s "
            f"({overrides} overrides, {flagged} flagged, {approved} approved)"
        )
        
        return CriticResult(
            verdicts=verdicts,
            overrides_count=overrides,
            flagged_count=flagged,
            approved_count=approved,
            total_reviewed=len(verdicts),
            latency_seconds=latency
        )
    
    def _select_entities_for_review(self, extraction_result) -> list[tuple[str, dict]]:
        """Select high-importance entities for review."""
        candidates = []
        
        # Check people (most common misclassification target)
        for i, person in enumerate(extraction_result.people):
            importance = person.get('importance_score', 5.0)
            if importance >= self.REVIEW_THRESHOLD:
                candidates.append((f"person_{i}", {
                    'type': 'person',
                    'text': person.get('name', ''),
                    'importance': importance,
                    'data': person
                }))
        
        # Check claims
        for i, claim in enumerate(extraction_result.claims):
            importance = claim.get('importance_score', 5.0)
            if importance >= self.REVIEW_THRESHOLD and not claim.get('flagged'):
                candidates.append((f"claim_{i}", {
                    'type': 'claim',
                    'text': claim.get('claim_text', ''),
                    'importance': importance,
                    'data': claim
                }))
        
        # Sort by importance (highest first)
        candidates.sort(key=lambda x: x[1]['importance'], reverse=True)
        
        return candidates
    
    def _review_entity(self, entity_data: dict, context: str) -> CriticVerdict:
        """Review a single entity with LLM."""
        prompt = self.prompt_template.replace(
            "{{entity_type}}", entity_data['type']
        ).replace(
            "{{entity_text}}", entity_data['text']
        ).replace(
            "{{importance_score}}", str(entity_data['importance'])
        ).replace(
            "{{context_snippet}}", context[:500] if context else "(no context provided)"
        )
        
        try:
            response = self.llm.generate(
                prompt=prompt,
                max_tokens=500,
                temperature=0.3  # Low temp for consistent judgment
            )
            
            # Parse JSON response
            result = json.loads(response)
            
            return CriticVerdict(
                action=result.get('verdict', 'approve'),
                reasoning=result.get('reasoning', ''),
                original_type=entity_data['type'],
                corrected_type=result.get('corrected_type'),
                confidence=result.get('confidence', 0.5),
                warning_message=result.get('explanation', '')
            )
            
        except Exception as e:
            logger.warning(f"TruthCritic failed for entity: {e}")
            # Default to approve on failure (conservative)
            return CriticVerdict(
                action='approve',
                reasoning=f"Review failed: {e}",
                original_type=entity_data['type'],
                corrected_type=None,
                confidence=0.0,
                warning_message="Critic review failed, defaulting to approve"
            )
```

### 1.4 Truth Critic Prompt Template

Create [`src/knowledge_system/processors/two_pass/prompts/truth_critic.txt`](src/knowledge_system/processors/two_pass/prompts/truth_critic.txt):

```text
# TRUTH CRITIC - Entity Validation

You are a TRUTH CRITIC. Your job is to catch LOGIC errors in entity extraction.

## WHAT YOU CATCH (Logic Errors)
- Entity TYPE misclassification
  - "Washington University" labeled as Person → Should be Organization
  - "the CEO" labeled as Person → This is a title, not a named individual
  - "GDP" labeled as Person → This is an economic concept
- Logical impossibilities in claims
- Self-contradictory statements

## WHAT YOU DON'T JUDGE (Style/Taste)
- Whether a claim is "interesting" or "trivial" (TasteFilter handles this)
- Personal preferences about content quality
- Duplicate detection (TasteFilter handles this)

## ENTITY TO VALIDATE

Type: {{entity_type}}
Content: {{entity_text}}
Importance Score: {{importance_score}}
Source Context: {{context_snippet}}

## REASONING-FIRST APPROACH

IMPORTANT: You must THINK BEFORE YOU JUDGE.

1. State what type of entity this is claimed to be
2. Consider: Does the content ACTUALLY match that type?
3. List any red flags (titles, organization names, etc.)
4. Only THEN give your verdict

## OUTPUT FORMAT

Return valid JSON:

```json
{
  "reasoning": "Step 1: This is claimed to be a [person]. Step 2: Looking at the text '[entity]', I notice... Step 3: This appears to be...",
  "verdict": "approve",
  "corrected_type": null,
  "confidence": 0.95,
  "explanation": "Correctly classified as a person."
}
```

Verdicts:
- "approve": Entity is correctly classified
- "override": Entity is WRONG type (provide corrected_type)  
- "flag": Uncertain, needs human review

Be CONSERVATIVE: Only override if confidence > 0.8
When in doubt, flag for human review.
```

### 1.5 Pipeline Integration (Full Sandwich)

Modify [`src/knowledge_system/processors/two_pass/pipeline.py`](src/knowledge_system/processors/two_pass/pipeline.py):

```python
# In TwoPassPipeline.process():

# ═══════════════════════════════════════════════════════════════════
# PASS 1.5a: TASTE FILTER (Vector - Style/Pattern Matching)
# ═══════════════════════════════════════════════════════════════════
if self.enable_taste_filter:
    logger.info("Running Taste Filter (style validation)...")
    filter_start = time.time()
    
    from .taste_filter import TasteFilter
    from ..services.taste_engine import get_taste_engine
    
    taste_engine = get_taste_engine()
    taste_filter = TasteFilter(taste_engine)
    
    filter_result = taste_filter.filter(extraction_result)
    
    # Replace extraction result with filtered version
    extraction_result.claims = filter_result.claims
    extraction_result.jargon = filter_result.jargon
    extraction_result.people = filter_result.people
    extraction_result.mental_models = filter_result.mental_models
    
    stats['taste_filter_time_seconds'] = time.time() - filter_start
    stats['taste_discarded'] = filter_result.discarded_count
    stats['taste_flagged'] = filter_result.flagged_count
    stats['taste_boosted'] = filter_result.boosted_count  # Positive Echo
    
    logger.info(
        f"Taste Filter: {filter_result.discarded_count} discarded, "
        f"{filter_result.flagged_count} flagged, "
        f"{filter_result.boosted_count} boosted (Positive Echo), "
        f"{filter_result.kept_count} kept"
    )

# ═══════════════════════════════════════════════════════════════════
# PASS 1.5b: TRUTH CRITIC (LLM - Logic/Fact Checking)
# ═══════════════════════════════════════════════════════════════════
if self.enable_truth_critic:
    logger.info("Running Truth Critic (logic validation)...")
    critic_start = time.time()
    
    from .truth_critic import TruthCritic
    
    truth_critic = TruthCritic()
    
    # Get first 500 chars of transcript for context
    source_context = transcript[:500] if transcript else ""
    
    critic_result = truth_critic.validate(extraction_result, source_context)
    
    # Apply critic verdicts
    extraction_result = self._apply_critic_verdicts(extraction_result, critic_result)
    
    stats['truth_critic_time_seconds'] = time.time() - critic_start
    stats['truth_overrides'] = critic_result.overrides_count
    stats['truth_flagged'] = critic_result.flagged_count
    
    logger.info(
        f"Truth Critic: {critic_result.total_reviewed} reviewed, "
        f"{critic_result.overrides_count} overrides, "
        f"{critic_result.flagged_count} flagged in {critic_result.latency_seconds:.2f}s"
    )

def _apply_critic_verdicts(self, extraction_result, critic_result):
    """Apply Truth Critic verdicts to extraction result."""
    for entity_id, verdict in critic_result.verdicts.items():
        if verdict.action == 'override':
            # Handle type correction
            logger.info(
                f"OVERRIDE: {entity_id} ({verdict.original_type} → {verdict.corrected_type}): "
                f"{verdict.reasoning[:100]}..."
            )
            # TODO: Move entity to correct type list
        elif verdict.action == 'flag':
            # Mark as flagged
            logger.info(f"FLAG: {entity_id}: {verdict.warning_message}")
            # Add flag to entity
    
    return extraction_result
```

---

## Phase 2: The Taste Engine (Vector Infrastructure)

### 2.1 Vector Store Selection

**Recommendation: ChromaDB** (lightweight, local, Python-native)

- No external server required
- Persistent storage on disk
- Built-in embedding support
- Simple API

### 2.2 Embedding Strategy

**Recommendation: sentence-transformers locally** (via `all-MiniLM-L6-v2`)

- Fast inference (~50ms per embedding)
- Small model (80MB)
- Good semantic quality for feedback matching
- Runs offline

### 2.3 TasteEngine Implementation

Create [`src/knowledge_system/services/taste_engine.py`](src/knowledge_system/services/taste_engine.py):

```python
"""
Taste Engine - Vector Store for User Feedback Learning

The ONLY source of "taste" in the system. No static personas, no hardcoded behavior.
All quality preferences are learned from Accept/Reject feedback stored as vectors.
"""

import json
import uuid
import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
from pathlib import Path
from dataclasses import dataclass
from typing import Literal, Optional
from datetime import datetime

from ..logger import get_logger

logger = get_logger(__name__)

@dataclass  
class FeedbackExample:
    """A single user feedback example."""
    entity_type: str           # "claim", "person", "jargon", "concept"
    entity_text: str           # The actual content that was judged
    verdict: Literal["accept", "reject"]
    reason_category: str       # e.g., "trivial_fact", "insight", "title_not_person"
    user_notes: str            # Optional user explanation
    source_id: str             # Source video/document ID (optional)
    created_at: str            # ISO timestamp
    
class TasteEngine:
    """
    Vector store for user feedback examples.
    
    ARCHITECTURAL PRINCIPLE: This is the EXCLUSIVE source of "taste".
    - No static user personas
    - No hardcoded behavior profiles
    - All preferences learned from Accept/Reject history
    
    Cold start is handled by loading golden_feedback.json, NOT hardcoded Python.
    
    VERSIONING: When golden_feedback.json schema_version changes, 
    the golden set is automatically re-ingested (replacing old golden examples).
    """
    
    COLLECTION_NAME = "taste_feedback"
    GOLDEN_SET_PATH = Path(__file__).parent.parent / "data" / "golden_feedback.json"
    VERSION_FILE_PATH = Path(__file__).parent.parent / "data" / ".golden_version"
    
    def __init__(self, persist_dir: Path = None, auto_load_golden: bool = True):
        if persist_dir is None:
            from ..utils.macos_paths import get_application_support_dir
            persist_dir = get_application_support_dir() / "taste_engine"
        
        persist_dir.mkdir(parents=True, exist_ok=True)
        self.persist_dir = persist_dir
        
        # Initialize ChromaDB with persistence
        self.client = chromadb.PersistentClient(
            path=str(persist_dir),
            settings=Settings(anonymized_telemetry=False)
        )
        
        # Initialize embedding model
        self.embedder = SentenceTransformer('all-MiniLM-L6-v2')
        
        # Get or create collection
        self.collection = self.client.get_or_create_collection(
            name=self.COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"}
        )
        
        # Load/update golden set on startup
        if auto_load_golden:
            self._check_and_load_golden_set()
    
    def _check_and_load_golden_set(self) -> int:
        """
        Check golden set version and load/re-ingest if needed.
        
        VERSIONING LOGIC:
        1. If collection is empty → load golden set
        2. If golden set version changed → delete old golden examples, reload
        3. If version unchanged → skip
        
        This ensures "Base Taste" evolves with software updates.
        """
        if not self.GOLDEN_SET_PATH.exists():
            logger.warning(f"Golden set not found at {self.GOLDEN_SET_PATH}")
            return 0
        
        try:
            with open(self.GOLDEN_SET_PATH, 'r') as f:
                golden_data = json.load(f)
            
            new_version = golden_data.get('schema_version', '1.0.0')
            current_version = self._get_loaded_golden_version()
            
            # Check if we need to load/reload
            if self.collection.count() == 0:
                logger.info("TasteEngine empty - loading golden set")
                return self._ingest_golden_set(golden_data, new_version)
            elif current_version != new_version:
                logger.info(
                    f"Golden set version changed: {current_version} → {new_version}. "
                    f"Re-ingesting golden examples."
                )
                self._delete_golden_examples()
                return self._ingest_golden_set(golden_data, new_version)
            else:
                logger.debug(f"Golden set version {new_version} already loaded")
                return 0
                
        except Exception as e:
            logger.error(f"Failed to check/load golden set: {e}")
            return 0
    
    def _get_loaded_golden_version(self) -> str:
        """Get the currently loaded golden set version."""
        version_file = self.persist_dir / ".golden_version"
        if version_file.exists():
            return version_file.read_text().strip()
        return ""
    
    def _save_golden_version(self, version: str):
        """Save the loaded golden set version."""
        version_file = self.persist_dir / ".golden_version"
        version_file.write_text(version)
    
    def _delete_golden_examples(self):
        """Delete existing golden set examples before re-ingestion."""
        try:
            # Query for all golden set items
            results = self.collection.get(
                where={"source_id": "golden_set"},
                include=["metadatas"]
            )
            
            if results['ids']:
                self.collection.delete(ids=results['ids'])
                logger.info(f"Deleted {len(results['ids'])} old golden set examples")
        except Exception as e:
            logger.warning(f"Failed to delete old golden examples: {e}")
    
    def _ingest_golden_set(self, golden_data: dict, version: str) -> int:
        """
        Ingest golden feedback examples from parsed JSON data.
        
        This replaces hardcoded Python examples. The golden set provides
        ~20 perfect starter examples (10 Rejections, 10 Acceptances) to
        bootstrap the vector search immediately.
        """
        examples = golden_data.get('examples', [])
        loaded = 0
        
        for ex in examples:
            feedback = FeedbackExample(
                entity_type=ex['entity_type'],
                entity_text=ex['entity_text'],
                verdict=ex['verdict'],
                reason_category=ex.get('reason_category', 'golden_set'),
                user_notes=ex.get('user_notes', ''),
                source_id='golden_set',  # Mark as golden set for future deletion
                created_at=ex.get('created_at', datetime.utcnow().isoformat()),
            )
            self.add_feedback(feedback)
            loaded += 1
        
        # Save version to track what's loaded
        self._save_golden_version(version)
        
        logger.info(f"Loaded {loaded} golden set examples (version {version})")
        return loaded
    
    def add_feedback(self, feedback: FeedbackExample) -> str:
        """Add a feedback example to the vector store."""
        # Create embedding from entity text
        text_to_embed = f"{feedback.entity_type}: {feedback.entity_text}"
        embedding = self.embedder.encode(text_to_embed).tolist()
        
        # Generate unique ID
        feedback_id = f"fb_{uuid.uuid4().hex[:12]}"
        
        # Store in ChromaDB
        self.collection.add(
            ids=[feedback_id],
            embeddings=[embedding],
            metadatas=[{
                "entity_type": feedback.entity_type,
                "verdict": feedback.verdict,
                "reason_category": feedback.reason_category,
                "user_notes": feedback.user_notes,
                "source_id": feedback.source_id,
                "created_at": feedback.created_at,
            }],
            documents=[feedback.entity_text]
        )
        
        return feedback_id
    
    def query_similar(
        self, 
        entity_text: str, 
        entity_type: str,
        n_results: int = 5,
        verdict_filter: Optional[str] = None
    ) -> list[dict]:
        """
        Find similar past feedback examples.
        
        Args:
            entity_text: The entity to find similar examples for
            entity_type: Filter to same entity type
            n_results: Number of results to return
            verdict_filter: Optional "accept" or "reject" filter
            
        Returns:
            List of similar feedback examples with distances
        """
        if self.collection.count() == 0:
            return []
        
        text_to_embed = f"{entity_type}: {entity_text}"
        query_embedding = self.embedder.encode(text_to_embed).tolist()
        
        # Build where filter
        where_filter = {"entity_type": entity_type}
        if verdict_filter:
            where_filter["verdict"] = verdict_filter
        
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=where_filter,
            include=["documents", "metadatas", "distances"]
        )
        
        # Handle empty results
        if not results['documents'] or not results['documents'][0]:
            return []
        
        # Format results
        examples = []
        for i, doc in enumerate(results['documents'][0]):
            examples.append({
                "text": doc,
                "metadata": results['metadatas'][0][i],
                "distance": results['distances'][0][i],
                "similarity": 1.0 - results['distances'][0][i],
            })
        
        return examples
    
    def get_stats(self) -> dict:
        """Get statistics about stored feedback."""
        count = self.collection.count()
        
        # Count by verdict
        accept_count = 0
        reject_count = 0
        
        if count > 0:
            # Query all to count (ChromaDB doesn't have direct count with filter)
            all_results = self.collection.get(include=["metadatas"])
            for meta in all_results['metadatas']:
                if meta.get('verdict') == 'accept':
                    accept_count += 1
                elif meta.get('verdict') == 'reject':
                    reject_count += 1
        
        return {
            "total_examples": count,
            "accept_count": accept_count,
            "reject_count": reject_count,
            "collection_name": self.COLLECTION_NAME,
            "persist_dir": str(self.persist_dir),
        }
    
    def is_cold_start(self) -> bool:
        """Check if we're in cold start state (only golden set loaded)."""
        stats = self.get_stats()
        # Consider cold start if <= 20 examples (golden set size)
        return stats['total_examples'] <= 20


# Module-level singleton
_taste_engine: Optional[TasteEngine] = None

def get_taste_engine() -> TasteEngine:
    """Get the global TasteEngine instance."""
    global _taste_engine
    if _taste_engine is None:
        _taste_engine = TasteEngine()
    return _taste_engine
```

### 2.4 Golden Set JSON File (Versioned)

Create [`src/knowledge_system/data/golden_feedback.json`](src/knowledge_system/data/golden_feedback.json):

**IMPORTANT**: The `schema_version` field triggers re-ingestion when updated. When you release a new version of the golden set, increment this version and the TasteEngine will automatically re-ingest on next startup.

```json
{
  "schema_version": "1.0.0",
  "last_updated": "2026-01-16",
  "description": "Golden set of perfect examples for cold start bootstrap. 10 rejections + 10 acceptances.",
  "notes": "Increment schema_version when updating examples to trigger re-ingestion.",
  "examples": [
    {
      "entity_type": "claim",
      "entity_text": "The stock market exists and people trade stocks.",
      "verdict": "reject",
      "reason_category": "trivial_fact",
      "user_notes": "Obvious statement with no insight or actionable information."
    },
    {
      "entity_type": "claim",
      "entity_text": "Money is used to buy things.",
      "verdict": "reject",
      "reason_category": "trivial_fact",
      "user_notes": "Universal knowledge, provides zero value."
    },
    {
      "entity_type": "claim",
      "entity_text": "Things are changing in the economy.",
      "verdict": "reject",
      "reason_category": "too_vague",
      "user_notes": "Completely vague, no specific claim being made."
    },
    {
      "entity_type": "claim",
      "entity_text": "This is an interesting topic.",
      "verdict": "reject",
      "reason_category": "too_vague",
      "user_notes": "Meta-commentary, not a claim about the world."
    },
    {
      "entity_type": "claim",
      "entity_text": "Let me explain how this works.",
      "verdict": "reject",
      "reason_category": "procedural",
      "user_notes": "Procedural statement, not substantive content."
    },
    {
      "entity_type": "person",
      "entity_text": "US President",
      "verdict": "reject",
      "reason_category": "title_not_person",
      "user_notes": "Generic title, not a specific person. Extract actual names."
    },
    {
      "entity_type": "person",
      "entity_text": "the CEO",
      "verdict": "reject",
      "reason_category": "title_not_person",
      "user_notes": "Role/title without specific identity."
    },
    {
      "entity_type": "person",
      "entity_text": "my friend",
      "verdict": "reject",
      "reason_category": "vague_reference",
      "user_notes": "Vague unnamed reference, not a named individual."
    },
    {
      "entity_type": "jargon",
      "entity_text": "money",
      "verdict": "reject",
      "reason_category": "not_jargon",
      "user_notes": "Common vocabulary, not technical jargon."
    },
    {
      "entity_type": "jargon",
      "entity_text": "company",
      "verdict": "reject",
      "reason_category": "not_jargon",
      "user_notes": "Everyday word, not domain-specific terminology."
    },
    {
      "entity_type": "claim",
      "entity_text": "Quantitative easing primarily inflates asset prices rather than consumer prices because liquidity injections flow through financial intermediaries who invest in equities and bonds, creating a wealth effect that benefits asset holders while wage earners face inflation in housing and essentials.",
      "verdict": "accept",
      "reason_category": "causal_insight",
      "user_notes": "Complete causal argument with mechanism and implications."
    },
    {
      "entity_type": "claim",
      "entity_text": "The Fed's reverse repo facility acts as a floor for short-term rates by providing a risk-free overnight return, which prevents money market rates from falling below the RRP rate even when excess reserves flood the system.",
      "verdict": "accept",
      "reason_category": "mechanism_explanation",
      "user_notes": "Explains specific mechanism with clear cause-effect."
    },
    {
      "entity_type": "claim",
      "entity_text": "Dopamine regulates motivation and reward-seeking behavior, not pleasure itself - the distinction matters because it explains why addiction involves compulsive seeking even when the experience is no longer pleasurable.",
      "verdict": "accept",
      "reason_category": "corrects_misconception",
      "user_notes": "Corrects common misconception with practical implication."
    },
    {
      "entity_type": "claim",
      "entity_text": "Large language models exhibit emergent capabilities at specific parameter thresholds that cannot be predicted from smaller-scale experiments, suggesting that neural network scaling follows discontinuous rather than smooth capability growth.",
      "verdict": "accept",
      "reason_category": "novel_insight",
      "user_notes": "Non-obvious insight about AI scaling behavior."
    },
    {
      "entity_type": "claim",
      "entity_text": "The inverted yield curve predicts recessions not because it causes them, but because it reflects market expectations of future Fed rate cuts in response to anticipated economic weakness.",
      "verdict": "accept",
      "reason_category": "mechanism_explanation",
      "user_notes": "Explains predictive mechanism, not just correlation."
    },
    {
      "entity_type": "person",
      "entity_text": "Milton Friedman",
      "verdict": "accept",
      "reason_category": "named_individual",
      "user_notes": "Specific named individual relevant to discussion."
    },
    {
      "entity_type": "person",
      "entity_text": "Janet Yellen",
      "verdict": "accept",
      "reason_category": "named_individual",
      "user_notes": "Specific person whose actions/views are discussed."
    },
    {
      "entity_type": "jargon",
      "entity_text": "quantitative easing",
      "verdict": "accept",
      "reason_category": "technical_term",
      "user_notes": "Domain-specific monetary policy term requiring definition."
    },
    {
      "entity_type": "jargon",
      "entity_text": "yield curve inversion",
      "verdict": "accept",
      "reason_category": "technical_term",
      "user_notes": "Finance-specific term not obvious to general audience."
    },
    {
      "entity_type": "concept",
      "entity_text": "circle of competence",
      "verdict": "accept",
      "reason_category": "mental_model",
      "user_notes": "Named mental model/framework with practical application."
    }
  ]
}
```

### 2.5 Database Schema for Feedback Tracking

Create [`src/knowledge_system/database/migrations/2026_01_feedback_system.sql`](src/knowledge_system/database/migrations/2026_01_feedback_system.sql):

```sql
-- Feedback examples table (mirrors vector store for audit trail)
CREATE TABLE IF NOT EXISTS feedback_examples (
    feedback_id TEXT PRIMARY KEY,
    entity_type TEXT NOT NULL,      -- 'claim', 'person', 'jargon', 'concept'
    entity_text TEXT NOT NULL,
    verdict TEXT NOT NULL,          -- 'accept' or 'reject'
    reason_category TEXT,           -- e.g., 'trivial_fact', 'insight'
    user_notes TEXT,
    source_id TEXT,
    synced_from_web BOOLEAN DEFAULT FALSE,
    web_entity_id TEXT,             -- ID from GetReceipts.org
    vectorized BOOLEAN DEFAULT FALSE,  -- Has been added to ChromaDB
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (source_id) REFERENCES media_sources(source_id)
);

-- Pending feedback queue for async processing
CREATE TABLE IF NOT EXISTS pending_feedback (
    queue_id INTEGER PRIMARY KEY AUTOINCREMENT,
    feedback_json TEXT NOT NULL,    -- Raw JSON from web sync
    received_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processed_at TIMESTAMP,
    error_message TEXT
);

CREATE INDEX idx_feedback_entity_type ON feedback_examples(entity_type);
CREATE INDEX idx_feedback_verdict ON feedback_examples(verdict);
CREATE INDEX idx_feedback_vectorized ON feedback_examples(vectorized);
CREATE INDEX idx_pending_processed ON pending_feedback(processed_at);
```

---

## Phase 3: Async Web Sync Architecture

### 3.1 Design Principle

**The `/feedback/sync` endpoint must NOT calculate embeddings synchronously.**

Embedding calculation (~50ms per item) would block the API response. Instead:

1. API pushes raw JSON to `pending_feedback` SQLite queue
2. Background worker processes queue asynchronously
3. Worker calculates embeddings and updates ChromaDB

### 3.2 Sync Endpoint (Queue Only)

Modify [`src/knowledge_system/services/entity_sync.py`](src/knowledge_system/services/entity_sync.py):

```python
def sync_feedback_from_web(self) -> dict:
    """
    Pull Accept/Reject decisions from GetReceipts.org.
    
    ASYNC ARCHITECTURE: This does NOT compute embeddings.
    It queues raw JSON for the background worker to process.
    """
    try:
        # Fetch feedback from API
        response = requests.get(
            f"{self.api_url}/api/entity-feedback",
            headers=self._get_auth_headers(),
            params={"since": self._get_last_sync_timestamp()},
            timeout=30
        )
        
        if not response.ok:
            return {"success": False, "reason": f"http_{response.status_code}"}
        
        feedbacks = response.json().get("feedbacks", [])
        
        if not feedbacks:
            return {"success": True, "queued": 0, "message": "No new feedback"}
        
        # Queue for async processing (do NOT embed here)
        queued_count = self._queue_feedback_for_processing(feedbacks)
        
        return {
            "success": True,
            "queued": queued_count,
            "message": f"Queued {queued_count} feedback items for async processing"
        }
        
    except Exception as e:
        logger.error(f"Failed to sync feedback: {e}")
        return {"success": False, "error": str(e)}

def _queue_feedback_for_processing(self, feedbacks: list[dict]) -> int:
    """
    Queue feedback items for async processing.
    
    Writes to pending_feedback SQLite table.
    The feedback_processor worker will handle embedding + ChromaDB insertion.
    """
    import json
    from datetime import datetime
    
    with self.db.get_session() as session:
        for fb in feedbacks:
            session.execute(
                text("""
                    INSERT INTO pending_feedback (feedback_json, received_at)
                    VALUES (:json, :received_at)
                """),
                {
                    "json": json.dumps(fb),
                    "received_at": datetime.utcnow().isoformat()
                }
            )
        session.commit()
    
    return len(feedbacks)
```

### 3.3 Background Worker

Create [`src/knowledge_system/workers/feedback_processor.py`](src/knowledge_system/workers/feedback_processor.py):

```python
"""
Feedback Processor - Background Worker for Async Embedding

Processes the pending_feedback queue and updates ChromaDB.
Runs as a background thread/task in the daemon.
"""

import json
import time
import threading
from datetime import datetime
from typing import Optional

from sqlalchemy import text

from ..database import DatabaseService
from ..services.taste_engine import get_taste_engine, FeedbackExample
from ..logger import get_logger

logger = get_logger(__name__)


class FeedbackProcessor:
    """
    Background worker that processes pending feedback queue.
    
    Architecture:
    - Polls pending_feedback table every N seconds
    - Processes items in batches
    - Calculates embeddings and adds to ChromaDB
    - Marks items as processed
    """
    
    POLL_INTERVAL_SECONDS = 5
    BATCH_SIZE = 20
    
    def __init__(self, db_service: DatabaseService = None):
        self.db = db_service or DatabaseService()
        self.taste_engine = get_taste_engine()
        self._running = False
        self._thread: Optional[threading.Thread] = None
    
    def start(self):
        """Start the background worker thread."""
        if self._running:
            return
        
        self._running = True
        self._thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._thread.start()
        logger.info("FeedbackProcessor worker started")
    
    def stop(self):
        """Stop the background worker."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=10)
        logger.info("FeedbackProcessor worker stopped")
    
    def _worker_loop(self):
        """Main worker loop."""
        while self._running:
            try:
                processed = self._process_batch()
                if processed > 0:
                    logger.info(f"Processed {processed} pending feedback items")
            except Exception as e:
                logger.error(f"FeedbackProcessor error: {e}")
            
            time.sleep(self.POLL_INTERVAL_SECONDS)
    
    def _process_batch(self) -> int:
        """Process a batch of pending feedback items."""
        # Fetch unprocessed items
        with self.db.get_session() as session:
            results = session.execute(
                text("""
                    SELECT queue_id, feedback_json
                    FROM pending_feedback
                    WHERE processed_at IS NULL
                    ORDER BY received_at ASC
                    LIMIT :limit
                """),
                {"limit": self.BATCH_SIZE}
            ).fetchall()
        
        if not results:
            return 0
        
        processed_ids = []
        
        for row in results:
            queue_id = row[0]
            feedback_json = row[1]
            
            try:
                fb_data = json.loads(feedback_json)
                
                # Create FeedbackExample
                example = FeedbackExample(
                    entity_type=fb_data["entity_type"],
                    entity_text=fb_data["entity_text"],
                    verdict=fb_data["verdict"],
                    reason_category=fb_data.get("reason_category", "unspecified"),
                    user_notes=fb_data.get("user_notes", ""),
                    source_id=fb_data.get("source_id", ""),
                    created_at=fb_data.get("created_at", datetime.utcnow().isoformat()),
                )
                
                # Add to TasteEngine (this calculates embedding)
                self.taste_engine.add_feedback(example)
                
                processed_ids.append(queue_id)
                
            except Exception as e:
                logger.error(f"Failed to process feedback {queue_id}: {e}")
                # Mark as failed
                with self.db.get_session() as session:
                    session.execute(
                        text("""
                            UPDATE pending_feedback
                            SET processed_at = :now, error_message = :error
                            WHERE queue_id = :id
                        """),
                        {
                            "now": datetime.utcnow().isoformat(),
                            "error": str(e),
                            "id": queue_id
                        }
                    )
                    session.commit()
        
        # Mark successful items as processed
        if processed_ids:
            with self.db.get_session() as session:
                for qid in processed_ids:
                    session.execute(
                        text("""
                            UPDATE pending_feedback
                            SET processed_at = :now
                            WHERE queue_id = :id
                        """),
                        {"now": datetime.utcnow().isoformat(), "id": qid}
                    )
                session.commit()
        
        return len(processed_ids)


# Module-level instance
_processor: Optional[FeedbackProcessor] = None

def get_feedback_processor() -> FeedbackProcessor:
    """Get the global FeedbackProcessor instance."""
    global _processor
    if _processor is None:
        _processor = FeedbackProcessor()
    return _processor

def start_feedback_processor():
    """Start the feedback processor worker."""
    processor = get_feedback_processor()
    processor.start()

def stop_feedback_processor():
    """Stop the feedback processor worker."""
    if _processor:
        _processor.stop()
```

### 3.4 Daemon Integration

Modify [`daemon/main.py`](daemon/main.py) to start/stop the worker:

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    from src.knowledge_system.workers.feedback_processor import start_feedback_processor
    start_feedback_processor()
    logger.info("Started FeedbackProcessor worker")
    
    yield
    
    # Shutdown
    from src.knowledge_system.workers.feedback_processor import stop_feedback_processor
    stop_feedback_processor()
    logger.info("Stopped FeedbackProcessor worker")

app = FastAPI(lifespan=lifespan)
```

---

## Phase 4: Dynamic Prompt Injection (Context Aggregate)

### 4.1 Signal Hierarchy

**CRITICAL: Video Description is EXCLUDED**

The description field contains too much noise (links, merchandise, sponsor reads, timestamps) that pollutes high-quality signals. Instead, use this hierarchy:

| Priority | Source | Signal Quality | Notes |
|----------|--------|----------------|-------|
| 1 (Highest) | Tags & Categories | Very High | Platform-assigned, curated |
| 2 | Local LLM Summary | High | Dense semantic content |
| 3 | YouTube AI Summary | High | Dense (if available) |
| 4 (Lowest) | Video Title | Medium | Often clickbait but still useful |
| EXCLUDED | Description | Low (Noisy) | Links, merch, sponsors |

### 4.2 Updated Extraction Pass

Update [`src/knowledge_system/processors/two_pass/extraction_pass.py`](src/knowledge_system/processors/two_pass/extraction_pass.py):

```python
def _inject_dynamic_examples(
    self, 
    prompt: str, 
    transcript: str, 
    metadata: dict
) -> str:
    """
    Query TasteEngine for relevant past feedback and inject as examples.
    
    Uses CONTEXT AGGREGATE from signal hierarchy (not transcript scanning).
    """
    try:
        from ..services.taste_engine import get_taste_engine
        
        taste_engine = get_taste_engine()
        
        # Check if we have feedback (beyond golden set)
        stats = taste_engine.get_stats()
        if stats['total_examples'] == 0:
            logger.warning("TasteEngine empty - this should not happen (golden set should be loaded)")
            return prompt
        
        # Build context aggregate using SIGNAL HIERARCHY
        context_aggregate = self._build_context_aggregate(metadata)
        
        if not context_aggregate:
            logger.debug("Empty context aggregate - skipping dynamic injection")
            return prompt
        
        # Query for relevant REJECT examples
        reject_examples = taste_engine.query_similar(
            entity_text=context_aggregate,
            entity_type="claim",
            n_results=3,
            verdict_filter="reject"
        )
        
        # Query for relevant ACCEPT examples
        accept_examples = taste_engine.query_similar(
            entity_text=context_aggregate,
            entity_type="claim",
            n_results=2,
            verdict_filter="accept"
        )
        
        # Filter by minimum similarity
        MIN_SIMILARITY = 0.3
        reject_examples = [e for e in reject_examples if e['similarity'] >= MIN_SIMILARITY]
        accept_examples = [e for e in accept_examples if e['similarity'] >= MIN_SIMILARITY]
        
        if not reject_examples and not accept_examples:
            logger.debug("No sufficiently similar examples found")
            return prompt
        
        # Build injection section
        examples_section = "\n\n# DYNAMIC LEARNING EXAMPLES\n\n"
        examples_section += "Based on feedback history, here are relevant patterns for this content:\n\n"
        
        if reject_examples:
            examples_section += "## AVOID THESE PATTERNS (Past Rejections):\n\n"
            for ex in reject_examples:
                category = ex['metadata'].get('reason_category', 'unspecified')
                examples_section += f"<rejected_example>\n"
                examples_section += f"  <content>{ex['text']}</content>\n"
                examples_section += f"  <category>{category}</category>\n"
                if ex['metadata'].get('user_notes'):
                    examples_section += f"  <reason>{ex['metadata']['user_notes']}</reason>\n"
                examples_section += f"</rejected_example>\n\n"
        
        if accept_examples:
            examples_section += "## EMULATE THESE PATTERNS (Past Accepts):\n\n"
            for ex in accept_examples:
                examples_section += f"<accepted_example>\n"
                examples_section += f"  <content>{ex['text']}</content>\n"
                examples_section += f"</accepted_example>\n\n"
        
        # Insert before EXTRACTION INSTRUCTIONS
        if "# EXTRACTION INSTRUCTIONS" in prompt:
            prompt = prompt.replace(
                "# EXTRACTION INSTRUCTIONS",
                examples_section + "# EXTRACTION INSTRUCTIONS"
            )
            logger.info(
                f"Injected {len(reject_examples)} reject + {len(accept_examples)} accept examples "
                f"(context aggregate: {len(context_aggregate)} chars)"
            )
        
        return prompt
        
    except Exception as e:
        logger.warning(f"Dynamic example injection failed: {e}")
        return prompt

def _build_context_aggregate(self, metadata: dict) -> str:
    """
    Build context aggregate using SIGNAL HIERARCHY.
    
    Priority:
    1. Tags & Categories (highest signal)
    2. Local LLM Summary (high density)
    3. YouTube AI Summary (high density)
    4. Video Title (medium signal)
    
    EXPLICITLY EXCLUDES: Description (too noisy - links, merch, sponsors)
    """
    aggregate_parts = []
    
    # Priority 1: Tags & Categories (HIGHEST SIGNAL)
    tags = metadata.get('tags', [])
    if tags:
        # Take top 10 most relevant tags
        tag_text = ", ".join(tags[:10])
        aggregate_parts.append(f"Topics: {tag_text}")
    
    categories = metadata.get('categories', [])
    if categories:
        cat_text = ", ".join(categories[:5])
        aggregate_parts.append(f"Categories: {cat_text}")
    
    # Priority 2: Local LLM Summary (if available from previous processing)
    local_summary = metadata.get('short_summary') or metadata.get('long_summary')
    if local_summary:
        # Truncate to first 500 chars for embedding efficiency
        aggregate_parts.append(f"Summary: {local_summary[:500]}")
    
    # Priority 3: YouTube AI Summary (HIGH DENSITY)
    yt_ai_summary = metadata.get('youtube_ai_summary')
    if yt_ai_summary:
        aggregate_parts.append(f"AI Summary: {yt_ai_summary[:500]}")
    
    # Priority 4: Video Title (MEDIUM SIGNAL)
    title = metadata.get('title', '')
    if title:
        aggregate_parts.append(f"Title: {title}")
    
    # EXPLICITLY EXCLUDED: description
    # Reason: Contains links, merchandise, sponsor reads, timestamps, and other noise
    # that would pollute the semantic signal
    
    # Combine into single aggregate
    context_aggregate = " | ".join(aggregate_parts)
    
    # Log what we're using
    logger.debug(f"Context aggregate built from: {[p.split(':')[0] for p in aggregate_parts]}")
    
    return context_aggregate
```

### 4.3 Remove Hardcoded Cold Start

**IMPORTANT**: The `_inject_cold_start_examples()` method is REMOVED.

Cold start is now handled EXCLUSIVELY by the golden set JSON file loaded into TasteEngine on startup. There should never be a state where TasteEngine is truly empty.

```python
# REMOVED - No longer needed
# def _inject_cold_start_examples(self, prompt: str) -> str:
#     """This method has been removed."""
#     pass
```

---

## Phase 5: Configuration and Integration

### 5.1 Pipeline Configuration

Add to [`daemon/config/settings.py`](daemon/config/settings.py):

```python
class DynamicLearningConfig(BaseSettings):
    """Configuration for dynamic learning system."""
    
    # ═══════════════════════════════════════════════════════════════
    # TASTE FILTER (Vector - Style Validation)
    # ═══════════════════════════════════════════════════════════════
    enable_taste_filter: bool = True
    discard_threshold: float = 0.95    # reject similarity > this = auto-discard
    flag_threshold: float = 0.80       # reject similarity > this = flag for review
    
    # Positive Echo (scoring boost for matches to accepted patterns)
    positive_echo_boost: float = 2.0   # Score boost for >95% accept similarity
    positive_echo_threshold: float = 0.95  # Accept similarity threshold for boost
    
    # ═══════════════════════════════════════════════════════════════
    # TRUTH CRITIC (LLM - Logic Validation)
    # ═══════════════════════════════════════════════════════════════
    enable_truth_critic: bool = True
    critic_review_threshold: float = 7.0  # Only review entities with importance >= this
    critic_max_entities: int = 10         # Max entities to review per extraction (latency)
    critic_temperature: float = 0.3       # LLM temperature for consistent judgment
    
    # ═══════════════════════════════════════════════════════════════
    # TASTE ENGINE (Vector Store)
    # ═══════════════════════════════════════════════════════════════
    enable_taste_engine: bool = True
    taste_db_path: Optional[str] = None  # Default: ~/Library/Application Support/...
    embedding_model: str = "all-MiniLM-L6-v2"
    auto_load_golden_set: bool = True
    
    # ═══════════════════════════════════════════════════════════════
    # DYNAMIC INJECTION
    # ═══════════════════════════════════════════════════════════════
    max_reject_examples: int = 3
    max_accept_examples: int = 2
    min_similarity_threshold: float = 0.3
    
    # ═══════════════════════════════════════════════════════════════
    # FEEDBACK PROCESSING
    # ═══════════════════════════════════════════════════════════════
    feedback_worker_enabled: bool = True
    feedback_poll_interval_seconds: int = 5
    feedback_batch_size: int = 20
    feedback_sync_interval_seconds: int = 300  # 5 minutes
```

### 5.2 Daemon API Updates

Add to [`daemon/api/routes.py`](daemon/api/routes.py):

```python
@router.get("/feedback/stats")
async def get_feedback_stats():
    """Get TasteEngine statistics."""
    from src.knowledge_system.services.taste_engine import get_taste_engine
    engine = get_taste_engine()
    stats = engine.get_stats()
    stats['is_cold_start'] = engine.is_cold_start()
    return stats

@router.post("/feedback/sync")
async def sync_feedback():
    """
    Trigger feedback sync from GetReceipts.org.
    
    NOTE: This queues feedback for async processing.
    Embeddings are NOT calculated synchronously.
    """
    from src.knowledge_system.services.entity_sync import get_entity_sync_service
    sync = get_entity_sync_service()
    return sync.sync_feedback_from_web()

@router.get("/feedback/queue-status")
async def get_queue_status():
    """Get status of pending feedback queue."""
    from src.knowledge_system.database import DatabaseService
    from sqlalchemy import text
    
    db = DatabaseService()
    with db.get_session() as session:
        pending = session.execute(
            text("SELECT COUNT(*) FROM pending_feedback WHERE processed_at IS NULL")
        ).scalar()
        processed = session.execute(
            text("SELECT COUNT(*) FROM pending_feedback WHERE processed_at IS NOT NULL")
        ).scalar()
        failed = session.execute(
            text("SELECT COUNT(*) FROM pending_feedback WHERE error_message IS NOT NULL")
        ).scalar()
    
    return {
        "pending": pending,
        "processed": processed,
        "failed": failed,
    }
```

---

## Implementation Checklist

### Phase 1a: Taste Filter (Vector - Style)
- [ ] Create `taste_filter.py` with `TasteFilter` class
- [ ] Implement four-tier threshold logic (discard/flag/boost/keep)
- [ ] Implement Positive Echo (+2.0 boost for accept similarity >95%)
- [ ] Add filter invocation to `pipeline.py`
- [ ] Test auto-discard at >95% reject similarity
- [ ] Test flagging at 80-95% reject similarity
- [ ] Test Positive Echo boost at >95% accept similarity

### Phase 1b: Truth Critic (LLM - Logic)
- [ ] Create `truth_critic.py` with `TruthCritic` class
- [ ] Create `prompts/truth_critic.txt` template
- [ ] Implement "Reasoning First" JSON output parsing
- [ ] Add critic invocation to `pipeline.py` (after Taste Filter)
- [ ] Add `enable_truth_critic` config flag
- [ ] Set review threshold (importance >= 7.0)
- [ ] Test entity type override detection (e.g., "Washington Univ" as Person)
- [ ] Test latency stays under 5s for max 10 entities

### Phase 2: Taste Engine (with Versioning)
- [ ] Add `chromadb` and `sentence-transformers` to requirements
- [ ] Create `taste_engine.py` with `TasteEngine` class
- [ ] Create `src/knowledge_system/data/golden_feedback.json` (20 examples)
- [ ] Add `schema_version` field to golden_feedback.json
- [ ] Implement `_check_and_load_golden_set()` with version checking
- [ ] Implement `_delete_golden_examples()` for re-ingestion
- [ ] Implement `.golden_version` file tracking
- [ ] Create SQLite migrations for feedback tables
- [ ] Test golden set loads on cold start
- [ ] Test golden set re-ingests when version changes

### Phase 3: Async Feedback Processing
- [ ] Create `pending_feedback` SQLite table
- [ ] Update `entity_sync.py` to queue (not embed)
- [ ] Create `feedback_processor.py` background worker
- [ ] Integrate worker start/stop in daemon lifespan
- [ ] Test async queue processing

### Phase 4: Dynamic Injection
- [ ] Implement `_build_context_aggregate()` with signal hierarchy
- [ ] Update `_inject_dynamic_examples()` to use context aggregate
- [ ] Verify Description is EXCLUDED from aggregate
- [ ] Test injection with golden set examples

### Phase 5: Integration
- [ ] Add config options to `settings.py` (enable_taste_filter, enable_truth_critic)
- [ ] Add daemon API endpoints
- [ ] Create test suite
- [ ] Update MANIFEST.md
- [ ] Document "Sandwich" architecture in README

---

## Dependencies to Add

```txt
# requirements.txt additions
chromadb>=0.4.0
sentence-transformers>=2.2.0
```

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Golden set not found | Log warning, proceed without (degraded mode) |
| Golden set version mismatch | Auto re-ingest on version change; delete old golden examples first |
| ChromaDB corruption | SQLite backup table mirrors vector store |
| Embedding model OOM | all-MiniLM-L6-v2 is only 80MB, safe on all hardware |
| Queue grows unbounded | Batch processing + retention policy (delete after 7 days) |
| Web sync fails | Local-first: TasteEngine works without web |
| False positives in filter | Flag threshold (0.80) is conservative; flagged != discarded |
| Truth Critic latency | Only reviews importance >= 7.0; max 10 entities per run |
| Truth Critic hallucination | Conservative defaults: approve on parse failure, flag when uncertain |
| Positive Echo over-boosting | Boost capped at +2.0; final score capped at 10.0 |

---

## Architectural Principles Summary

1. **"Sandwich" Validation**: Both Taste Filter (vector/style) AND Truth Critic (LLM/logic) are required
2. **Taste vs. Truth**:
   - **Taste Filter**: Catches style errors via vector similarity (fast, ~50ms/entity)
   - **Truth Critic**: Catches logic errors via LLM reasoning (selective, high-value entities only)
3. **No Static Personas**: Taste learned EXCLUSIVELY from vector history
4. **Golden Set Bootstrap**: Cold start via **versioned** JSON file (auto re-ingests on version change)
5. **Positive Echo**: High similarity to accepted patterns → +2.0 importance boost (not just filtering negatives)
6. **Hybrid Safety Filter**: Auto-discard >95% reject sim, flag 80-95%, boost >95% accept sim
7. **Async Everything**: Web sync queues, worker processes
8. **Signal Hierarchy**: Tags > Summaries > Title (Description EXCLUDED)
