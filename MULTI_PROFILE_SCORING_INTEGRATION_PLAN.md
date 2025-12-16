# Multi-Profile Claim Scoring Integration Plan

## Executive Summary

This document details the integration of multi-profile scoring into the Knowledge Chipper flagship evaluator system. The key innovation is **separation of concerns**: the LLM evaluates semantic dimensions once, then pure arithmetic calculates importance scores for unlimited user profiles at zero marginal cost.

**Core Benefit**: Adding 100 user profiles costs the same as adding 1 profile - just 1 LLM call per claim.

## Table of Contents

1. [Current System Analysis](#current-system-analysis)
2. [Proposed Architecture](#proposed-architecture)
3. [Schema Changes](#schema-changes)
4. [Implementation Steps](#implementation-steps)
5. [Database Changes](#database-changes)
6. [Testing Strategy](#testing-strategy)
7. [Migration Path](#migration-path)
8. [Cost Analysis](#cost-analysis)

---

## Current System Analysis

### Current Scoring (3 Dimensions)

The flagship evaluator currently scores claims on 3 dimensions:

```python
{
    "importance": 8,      # 1-10 scale
    "novelty": 7,         # 1-10 scale
    "confidence_final": 9 # 1-10 scale
}
```

**Problems**:
1. **Single "importance" score** - too subjective, importance for whom?
2. **No user context** - treats all users the same
3. **Conflates multiple dimensions** - epistemic value + actionability + novelty all mixed together
4. **Binary tier cutoffs** - arbitrary thresholds (A ≥ 8.0, B ≥ 6.5, C ≥ 5.0)
5. **No temporal awareness** - doesn't distinguish timeless insights from dated facts
6. **No actionability metric** - can't identify claims that enable decisions

### Current Flagship Evaluator Flow

```
Content Summary + Claims
        ↓
    LLM Evaluation (1 call per claim)
        ↓
    {importance, novelty, confidence}
        ↓
    Tier Assignment (A/B/C)
        ↓
    Ranking by importance
```

---

## Proposed Architecture

### New Scoring (5 Dimensions + Multi-Profile)

```python
# Step 1: LLM evaluates dimensions ONCE ($0.01 per claim)
dimensions = {
    "epistemic_value": 9,      # Reduces uncertainty, teaches understanding
    "actionability": 6,         # Enables decisions, practical utility
    "novelty": 8,               # Surprisingness, challenges assumptions
    "verifiability": 8,         # Evidence strength, source credibility
    "understandability": 7      # Clarity, accessibility
}

# Step 2: Calculate for 12 profiles (FREE - pure arithmetic)
profile_scores = {
    "scientist": 8.4,          # High epistemic_value (50%) + verifiability (30%)
    "investor": 7.1,           # High actionability (50%) + verifiability (25%)
    "philosopher": 8.2,        # High epistemic_value (40%) + novelty (30%)
    "educator": 7.8,           # High understandability (40%) + epistemic_value (30%)
    # ... 8 more profiles
}

# Step 3: Take MAX across profiles
final_importance = max(profile_scores.values())  # 8.4
best_profile = "scientist"
tier = "A"  # Because 8.4 ≥ 8.0
```

### Key Innovation: Dimension-Based Scoring

**LLM evaluates semantic dimensions once**:
- Epistemic Value: "Does this reduce uncertainty about how the world works?"
- Actionability: "Can someone make better decisions with this information?"
- Novelty: "Is this surprising or does it challenge assumptions?"
- Verifiability: "How strong is the evidence and how reliable are the sources?"
- Understandability: "How clear and accessible is this claim?"

**Code calculates profile scores unlimited times**:
```python
def score_for_profile(dimensions: dict, profile: UserProfile) -> float:
    """Pure arithmetic - no LLM calls!"""
    score = 0.0
    for dimension, weight in profile.weights.items():
        score += weight * dimensions.get(dimension, 0.0)
    return score
```

### Multi-Profile Aggregation Strategies

Three approaches, each with different selectivity:

#### 1. Max-Scoring (Most Inclusive)
```python
final_importance = max(all_profile_scores)
```
- **Rationale**: "Is this A-tier for ANYONE?"
- **Effect**: Rescues niche-but-valuable claims
- **Example**: Neuroscience claim scores high for scientist (8.4) but lower for investor (7.1) → Final: 8.4 (A-tier)

#### 2. Top-K Averaging (More Selective)
```python
top_k = sorted(all_profile_scores)[:k]
final_importance = mean(top_k)
```
- **Rationale**: "Is this A-tier for at least K profiles?"
- **Effect**: Requires broader appeal
- **Example**: k=2 → avg(8.4, 8.2) = 8.3 (A-tier)

#### 3. Percentile-Based (Tunable)
```python
final_importance = percentile(all_profile_scores, p)
```
- **Rationale**: Tune from max (p=100) to median (p=50)
- **Effect**: Adjustable selectivity
- **Example**: p=90 → 90th percentile score

**Recommended Default**: Max-scoring (most inclusive, rescues niche insights)

---

## Schema Changes

### 1. Flagship Output Schema (flagship_output.v2.json)

**Add dimension scores to evaluated_claims**:

```json
{
  "evaluated_claims": [
    {
      "original_claim_text": "...",
      "decision": "accept",

      // OLD: Single importance score
      "importance": 8,

      // NEW: Dimension scores (from LLM)
      "dimensions": {
        "epistemic_value": 9,
        "actionability": 6,
        "novelty": 8,
        "verifiability": 8,
        "understandability": 7
      },

      // NEW: Profile scores (calculated from dimensions)
      "profile_scores": {
        "scientist": 8.4,
        "investor": 7.1,
        "philosopher": 8.2,
        "educator": 7.8,
        "student": 7.6,
        "skeptic": 8.3,
        "policy_maker": 7.5,
        "tech_professional": 7.3,
        "health_professional": 8.0,
        "journalist": 7.7,
        "generalist": 7.8,
        "pragmatist": 7.1
      },

      // NEW: Max-scoring result
      "importance": 8.4,
      "best_profile": "scientist",
      "tier": "A",

      // KEPT: Existing fields
      "novelty": 8,
      "confidence_final": 8,
      "reasoning": "...",
      "rank": 1
    }
  ]
}
```

**Schema validation**:
- `dimensions`: Required object with 5 required float fields (0-10)
- `profile_scores`: Optional object (can be calculated later)
- `importance`: Derived from max(profile_scores) or dimensions if profiles not calculated yet
- `best_profile`: Optional string (which profile gave highest score)

### 2. Flagship Prompt Changes

**Current prompt** (`flagship_evaluator.txt`):
```
Score claims on key dimensions for quality assessment

### IMPORTANCE SCORING (1-10 Scale)
Consider:
- Intellectual significance and depth
- Relevance to core themes and arguments
- Potential impact on understanding the topic
- Non-obviousness and insight value
- Centrality to the speaker's message
```

**New prompt** (`flagship_evaluator_v2.txt`):
```
Score claims on 5 independent dimensions for quality assessment

### DIMENSION SCORING (1-10 Scale)

1. EPISTEMIC VALUE (Does this reduce uncertainty?)
   - Teaches how the world works
   - Explains mechanisms or causal relationships
   - Provides theoretical understanding
   - Helps build mental models
   Score: 1 (trivial) to 10 (fundamental insight)

2. ACTIONABILITY (Can this inform decisions?)
   - Enables better choices
   - Provides practical guidance
   - Offers implementation details
   - Delivers market/strategic intelligence
   Score: 1 (purely theoretical) to 10 (highly actionable)

3. NOVELTY (Is this surprising?)
   - Challenges conventional wisdom
   - Presents unexpected connections
   - Reveals non-obvious insights
   - Introduces new perspectives
   Score: 1 (obvious) to 10 (groundbreaking)

4. VERIFIABILITY (How strong is the evidence?)
   - Quality of supporting evidence
   - Source credibility and expertise
   - Logical coherence
   - Reproducibility and falsifiability
   Score: 1 (speculation) to 10 (rigorously proven)

5. UNDERSTANDABILITY (How clear is this?)
   - Clarity of expression
   - Accessibility to non-experts
   - Minimal jargon or well-explained terms
   - Concrete examples provided
   Score: 1 (opaque) to 10 (crystal clear)

IMPORTANT: Score each dimension INDEPENDENTLY. Do not conflate them.
A claim can be high epistemic value but low actionability (pure theory).
A claim can be high novelty but low verifiability (speculation).
```

### 3. Database Schema Changes

**Add to claims table**:

```sql
ALTER TABLE claims ADD COLUMN dimensions JSON;
ALTER TABLE claims ADD COLUMN profile_scores JSON;
ALTER TABLE claims ADD COLUMN best_profile TEXT;

-- Example dimensions JSON:
-- {"epistemic_value": 9, "actionability": 6, "novelty": 8, "verifiability": 8, "understandability": 7}

-- Example profile_scores JSON:
-- {"scientist": 8.4, "investor": 7.1, "philosopher": 8.2, ...}
```

**Benefits**:
1. **Recalculable**: Can change profile weights and recalculate scores without re-running LLM
2. **Queryable**: Can find claims with high epistemic_value or high actionability
3. **Analyzable**: Can study dimension distributions across episodes/domains
4. **Extensible**: Can add new profiles later and score all existing claims

---

## Implementation Steps

### Phase 1: Prototype Testing (1 day)

**Goal**: Validate that multi-profile scoring produces sensible tier distributions.

1. **Run prototype on existing claims**:
   ```bash
   python multi_profile_scoring_prototype.py
   ```

2. **Export 100 claims from database**:
   ```sql
   SELECT claim_text, importance, novelty, confidence_final, tier
   FROM claims
   ORDER BY RANDOM()
   LIMIT 100;
   ```

3. **Manually score dimensions for test claims**:
   - Pick 10 representative claims
   - Manually assign dimension scores
   - Calculate profile scores with prototype
   - Compare tier distributions

4. **Validate approach**:
   - Do max-scoring results feel right?
   - Are niche-but-valuable claims rescued?
   - Are trivial claims still rejected?

**Success Criteria**:
- Max-scoring produces 10-20% A-tier claims (vs current ~15%)
- No clearly trivial claims in A-tier
- Niche insights (e.g., technical neuroscience) get promoted

### Phase 2: Schema and Prompt Updates (2 days)

1. **Create new schema** (`schemas/flagship_output.v2.json`):
   - Add `dimensions` object (required)
   - Add `profile_scores` object (optional)
   - Add `best_profile` string (optional)
   - Keep backward compatibility with v1

2. **Create new prompt** (`prompts/flagship_evaluator_v2.txt`):
   - Update scoring section with 5 dimensions
   - Add clear definitions and examples
   - Keep existing accept/reject logic

3. **Update schema validator** (`schema_validator.py`):
   - Add repair logic for v2 schema
   - Handle missing profile_scores (calculate from dimensions)
   - Handle v1→v2 migration (map old importance to epistemic_value)

4. **Update flagship evaluator** (`flagship_evaluator.py`):
   - Add `EvaluatedClaim.dimensions` property
   - Add `EvaluatedClaim.profile_scores` property
   - Add `EvaluatedClaim.best_profile` property
   - Keep backward compatibility

### Phase 3: Profile Scoring Module (2 days)

1. **Create profiles module** (`src/knowledge_system/scoring/profiles.py`):
   ```python
   from dataclasses import dataclass
   from typing import Dict

   @dataclass
   class UserProfile:
       name: str
       description: str
       weights: Dict[str, float]

       def __post_init__(self):
           """Validate weights sum to 1.0"""
           total = sum(self.weights.values())
           if abs(total - 1.0) > 0.01:
               raise ValueError(f"Weights must sum to 1.0, got {total}")

   # Standard profiles
   STANDARD_PROFILES = {
       "scientist": UserProfile(...),
       "investor": UserProfile(...),
       # ... 10 more
   }
   ```

2. **Create scorer module** (`src/knowledge_system/scoring/multi_profile_scorer.py`):
   ```python
   def score_for_profile(dimensions: Dict[str, float], profile: UserProfile) -> float:
       """Calculate importance score for a specific profile."""
       score = sum(profile.weights[dim] * dimensions.get(dim, 0.0)
                   for dim in profile.weights)
       return round(score, 2)

   def score_all_profiles(dimensions: Dict[str, float]) -> Dict[str, float]:
       """Score claim across all profiles."""
       return {name: score_for_profile(dimensions, profile)
               for name, profile in STANDARD_PROFILES.items()}

   def get_importance_max(dimensions: Dict[str, float]) -> Tuple[float, str, Dict[str, float]]:
       """Get importance using max-scoring approach."""
       all_scores = score_all_profiles(dimensions)
       best_profile = max(all_scores.items(), key=lambda x: x[1])
       return best_profile[1], best_profile[0], all_scores
   ```

3. **Integrate into flagship evaluator**:
   ```python
   # After LLM returns dimensions
   from knowledge_system.scoring.multi_profile_scorer import get_importance_max

   dimensions = llm_result["dimensions"]
   importance, best_profile, profile_scores = get_importance_max(dimensions)

   # Add to output
   claim["dimensions"] = dimensions
   claim["profile_scores"] = profile_scores
   claim["importance"] = importance
   claim["best_profile"] = best_profile
   ```

### Phase 4: Database Migration (1 day)

1. **Add columns**:
   ```sql
   ALTER TABLE claims ADD COLUMN dimensions JSON;
   ALTER TABLE claims ADD COLUMN profile_scores JSON;
   ALTER TABLE claims ADD COLUMN best_profile TEXT;
   ```

2. **Backfill existing claims** (optional):
   ```python
   # For claims with old single importance score, approximate dimensions
   # This is a ROUGH estimate - real re-scoring would be better
   for claim in old_claims:
       old_importance = claim['importance']
       old_novelty = claim['novelty']

       # Rough approximation
       dimensions = {
           'epistemic_value': old_importance,
           'actionability': old_importance * 0.6,
           'novelty': old_novelty,
           'verifiability': claim['confidence_final'],
           'understandability': 7.0  # Assume medium
       }

       # Calculate profile scores
       profile_scores = score_all_profiles(dimensions)
       importance, best_profile, _ = get_importance_max(dimensions)

       # Update database
       db.execute("""
           UPDATE claims
           SET dimensions = ?, profile_scores = ?,
               importance = ?, best_profile = ?
           WHERE id = ?
       """, (json.dumps(dimensions), json.dumps(profile_scores),
             importance, best_profile, claim['id']))
   ```

3. **Add indexes for querying**:
   ```sql
   CREATE INDEX idx_claims_best_profile ON claims(best_profile);
   ```

### Phase 5: Testing and Validation (2 days)

1. **Unit tests**:
   - Test dimension scoring with mock LLM
   - Test profile score calculation (arithmetic)
   - Test max-scoring vs top-k vs percentile
   - Test tier assignment

2. **Integration tests**:
   - Process 10 test episodes with v2 evaluator
   - Compare tier distributions to v1
   - Validate schema conformance
   - Check profile score correctness

3. **Production smoke test**:
   - Process 100 real episodes
   - Monitor LLM costs (should be same as before)
   - Check tier distribution (expect slight increase in A-tier)
   - Validate no regressions

### Phase 6: Deployment and Monitoring (1 day)

1. **Deploy to production**:
   - Update flagship evaluator to use v2 prompt
   - Enable multi-profile scoring
   - Monitor LLM API costs

2. **Create analytics queries**:
   ```sql
   -- Tier distribution by best_profile
   SELECT best_profile, tier, COUNT(*) as count
   FROM claims
   GROUP BY best_profile, tier
   ORDER BY best_profile, tier;

   -- Claims with high epistemic_value
   SELECT claim_text, json_extract(dimensions, '$.epistemic_value') as ev
   FROM claims
   WHERE json_extract(dimensions, '$.epistemic_value') >= 8.0
   ORDER BY ev DESC
   LIMIT 20;

   -- Claims with high actionability
   SELECT claim_text, json_extract(dimensions, '$.actionability') as action
   FROM claims
   WHERE json_extract(dimensions, '$.actionability') >= 8.0
   ORDER BY action DESC
   LIMIT 20;
   ```

3. **Document for users**:
   - Add profile descriptions to docs
   - Explain dimension scoring
   - Show example tier distributions

---

## Database Changes

### New Schema

```sql
CREATE TABLE IF NOT EXISTS claims (
    -- Existing columns
    id INTEGER PRIMARY KEY,
    claim_text TEXT NOT NULL,
    tier TEXT CHECK(tier IN ('A', 'B', 'C', 'D')),

    -- OLD: Single scores (keep for backward compatibility)
    importance REAL,
    novelty REAL,
    confidence_final REAL,

    -- NEW: Dimension scores (from LLM)
    dimensions JSON,  -- {"epistemic_value": 9, "actionability": 6, ...}

    -- NEW: Profile scores (calculated from dimensions)
    profile_scores JSON,  -- {"scientist": 8.4, "investor": 7.1, ...}

    -- NEW: Best profile (max-scoring winner)
    best_profile TEXT,

    -- Other existing columns
    episode_id TEXT,
    claim_type TEXT,
    domain TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_claims_best_profile ON claims(best_profile);
CREATE INDEX idx_claims_tier ON claims(tier);
```

### Migration Strategy

**Option 1: Lazy Migration** (Recommended)
- New claims: Use v2 schema with dimensions
- Old claims: Keep old importance scores, add dimensions on demand
- Profile scores: Calculate from dimensions when requested

**Option 2: Bulk Re-scoring**
- Re-run flagship evaluator on all existing claims
- Cost: ~$0.01 per claim × 10,000 claims = $100
- Benefit: Uniform scoring across all claims

**Option 3: Approximate Backfill**
- Map old importance → estimated dimensions
- Calculate profile scores from estimates
- Cost: Free (pure arithmetic)
- Accuracy: Lower (rough approximation)

---

## Testing Strategy

### 1. Unit Tests

```python
def test_profile_weights_sum_to_one():
    """Ensure all profiles have weights summing to 1.0"""
    for name, profile in STANDARD_PROFILES.items():
        total = sum(profile.weights.values())
        assert abs(total - 1.0) < 0.01, f"{name} weights sum to {total}"

def test_score_for_profile():
    """Test profile scoring arithmetic"""
    dimensions = {
        "epistemic_value": 9,
        "actionability": 6,
        "novelty": 8,
        "verifiability": 8,
        "understandability": 7
    }

    scientist_profile = STANDARD_PROFILES["scientist"]
    score = score_for_profile(dimensions, scientist_profile)

    # Manual calculation: 9×0.50 + 8×0.30 + 8×0.15 + 6×0.05 = 8.4
    expected = 4.5 + 2.4 + 1.2 + 0.3
    assert abs(score - expected) < 0.1

def test_max_scoring_rescues_niche_claims():
    """Test that max-scoring promotes niche-but-valuable claims"""
    # High epistemic value, low actionability
    niche_claim = {
        "epistemic_value": 9,
        "actionability": 3,
        "novelty": 8,
        "verifiability": 8,
        "understandability": 6
    }

    importance, best_profile, _ = get_importance_max(niche_claim)

    # Should score high for scientist (weights epistemic_value 50%)
    assert importance >= 8.0
    assert best_profile == "scientist"

def test_trivial_claims_still_rejected():
    """Test that trivial claims score low for ALL profiles"""
    trivial_claim = {
        "epistemic_value": 2,
        "actionability": 1,
        "novelty": 1,
        "verifiability": 10,
        "understandability": 10
    }

    importance, _, all_scores = get_importance_max(trivial_claim)

    # Even max score should be < 5.0
    assert importance < 5.0
    # All profiles should score < 5.0
    assert all(score < 5.0 for score in all_scores.values())
```

### 2. Integration Tests

```python
def test_flagship_evaluator_v2_output():
    """Test that v2 evaluator produces correct schema"""
    content_summary = "Discussion of dopamine and motivation"
    claims = [{
        "claim_text": "Dopamine regulates motivation, not pleasure",
        "evidence_spans": [...]
    }]

    evaluator = FlagshipEvaluator(llm, prompt_path="prompts/flagship_evaluator_v2.txt")
    output = evaluator.evaluate_claims(content_summary, claims)

    # Check v2 schema conformance
    assert "dimensions" in output.evaluated_claims[0].raw
    assert "profile_scores" in output.evaluated_claims[0].raw
    assert "best_profile" in output.evaluated_claims[0].raw

    # Check dimensions are complete
    dimensions = output.evaluated_claims[0].raw["dimensions"]
    required_dims = ["epistemic_value", "actionability", "novelty",
                     "verifiability", "understandability"]
    for dim in required_dims:
        assert dim in dimensions
        assert 0 <= dimensions[dim] <= 10

def test_tier_distribution_shift():
    """Test that v2 scoring produces slightly more A-tier claims"""
    # Process 100 test claims with v1
    v1_output = process_with_v1_evaluator(test_claims)
    v1_a_tier_count = sum(1 for c in v1_output if c.tier == "A")

    # Process same claims with v2
    v2_output = process_with_v2_evaluator(test_claims)
    v2_a_tier_count = sum(1 for c in v2_output if c.tier == "A")

    # Expect slight increase (10-20% more A-tier)
    assert v2_a_tier_count >= v1_a_tier_count
    assert v2_a_tier_count <= v1_a_tier_count * 1.2
```

### 3. Cost Validation

```python
def test_llm_cost_constant_across_profiles():
    """Test that LLM costs don't increase with profile count"""
    dimensions = {"epistemic_value": 9, ...}

    # Baseline: Score for 1 profile (1 LLM call)
    start_time = time.time()
    score_for_profile(dimensions, STANDARD_PROFILES["scientist"])
    time_1_profile = time.time() - start_time

    # Test: Score for 12 profiles (should still be FREE)
    start_time = time.time()
    score_all_profiles(dimensions)
    time_12_profiles = time.time() - start_time

    # Both should be <1ms (pure arithmetic)
    assert time_1_profile < 0.001
    assert time_12_profiles < 0.001

    # Adding profiles should not increase cost
    assert time_12_profiles < time_1_profile * 2
```

---

## Migration Path

### Backward Compatibility

**Ensure old code continues to work**:

1. **EvaluatedClaim class**:
   ```python
   class EvaluatedClaim:
       def __init__(self, raw_data: dict):
           # OLD: Single importance score
           self.importance = raw_data.get("importance", 1)

           # NEW: Dimension scores (if available)
           self.dimensions = raw_data.get("dimensions", None)

           # NEW: Profile scores (if available)
           self.profile_scores = raw_data.get("profile_scores", None)

           # NEW: Best profile (if available)
           self.best_profile = raw_data.get("best_profile", None)

           # Backward compatibility: If no profile_scores, calculate from dimensions
           if self.dimensions and not self.profile_scores:
               from knowledge_system.scoring.multi_profile_scorer import get_importance_max
               self.importance, self.best_profile, self.profile_scores = get_importance_max(self.dimensions)
   ```

2. **Schema validator**:
   ```python
   def _attempt_repair(self, data, schema_name):
       if schema_name == "flagship_output":
           # Migrate v1 → v2
           for claim in data.get("evaluated_claims", []):
               # If dimensions missing but importance present, approximate
               if "importance" in claim and "dimensions" not in claim:
                   claim["dimensions"] = {
                       "epistemic_value": claim["importance"],
                       "actionability": claim["importance"] * 0.6,
                       "novelty": claim.get("novelty", 5),
                       "verifiability": claim.get("confidence_final", 5),
                       "understandability": 7.0
                   }

               # If dimensions present but profile_scores missing, calculate
               if "dimensions" in claim and "profile_scores" not in claim:
                   from knowledge_system.scoring.multi_profile_scorer import get_importance_max
                   importance, best_profile, profile_scores = get_importance_max(claim["dimensions"])
                   claim["profile_scores"] = profile_scores
                   claim["importance"] = importance
                   claim["best_profile"] = best_profile
   ```

### Gradual Rollout

**Phase 1: Test in parallel**
- Run both v1 and v2 evaluators on new episodes
- Compare tier distributions
- Log differences for analysis
- Don't use v2 scores yet

**Phase 2: Opt-in for power users**
- Add flag: `USE_MULTI_PROFILE_SCORING=true`
- Power users can enable v2 scoring
- Collect feedback

**Phase 3: Default to v2**
- Switch default to v2 evaluator
- Keep v1 as fallback option
- Monitor tier distributions

**Phase 4: Deprecate v1**
- Remove v1 evaluator after 6 months
- All claims use multi-profile scoring

---

## Cost Analysis

### LLM Cost Comparison

**Current System (v1)**:
- 1 LLM call per claim
- Returns: `{importance: 8, novelty: 7, confidence: 9}`
- Tokens: ~200 input + ~100 output = 300 tokens
- Cost: ~$0.01 per claim (Claude Sonnet 3.5)

**New System (v2)**:
- 1 LLM call per claim (SAME)
- Returns: `{dimensions: {epistemic_value: 9, actionability: 6, novelty: 8, verifiability: 8, understandability: 7}}`
- Tokens: ~300 input + ~150 output = 450 tokens (50% more)
- Cost: ~$0.015 per claim (50% increase)

**Profile Scoring**:
- 12 profiles × 5 dimensions = 60 multiplications per claim
- Time: <1ms per claim
- Cost: $0 (pure arithmetic)

**Total Cost**:
- v1: $0.01 per claim
- v2: $0.015 per claim (50% increase)
- Cost for 10,000 claims: $150 (vs $100)

**Benefit/Cost Ratio**:
- 50% cost increase
- Unlimited profiles at no marginal cost
- Better tier accuracy (fewer false negatives)
- Queryable dimensions for analytics
- Recalculable scores without re-running LLM

**Verdict**: Worth the 50% cost increase for the flexibility and accuracy gains.

### Computational Cost

**v1 System**:
- LLM call: 500ms-2s
- Tier assignment: <1ms
- Total: ~1s per claim

**v2 System**:
- LLM call: 500ms-2s (same)
- Profile scoring: <1ms (12 profiles)
- Tier assignment: <1ms
- Total: ~1s per claim (no change)

**Scaling**:
- Adding 100 profiles: +10ms per claim
- Adding 1000 profiles: +100ms per claim
- Still negligible compared to LLM latency

---

## Success Metrics

### Quantitative

1. **Tier Distribution**:
   - A-tier: 10-20% of claims (vs current ~15%)
   - B-tier: 20-30% of claims
   - C-tier: 30-40% of claims
   - Rejected: 30-40% of claims

2. **Dimension Coverage**:
   - All claims have complete dimension scores
   - No dimension consistently = 5 (would indicate LLM defaulting)

3. **Profile Distribution**:
   - No single profile dominates (>40% of claims)
   - All profiles represented in top claims

4. **Cost**:
   - LLM cost increase ≤ 60%
   - Processing time increase ≤ 10%

### Qualitative

1. **Niche Insights Rescued**:
   - Technical claims (high epistemic_value, low actionability) promoted to A-tier
   - Validated by domain experts

2. **Trivial Claims Still Rejected**:
   - Obvious facts (e.g., "Jerome Powell is Fed Chairman") score <5 on all dimensions
   - No false positives in A-tier

3. **Dimension Independence**:
   - Claims can be high on one dimension, low on another
   - No spurious correlations between dimensions

4. **User Satisfaction**:
   - Power users prefer multi-profile scoring
   - Tier assignments feel more accurate

---

## Open Questions

### 1. How to handle user-specific profiles?

**Options**:
a) **Predefined profiles only** (MVP)
   - 12 standard profiles
   - User picks closest match
   - Simple, no storage needed

b) **Custom profile builder** (v2)
   - User adjusts dimension weights
   - Store in user preferences table
   - Calculate on-demand

c) **Learned profiles** (v3)
   - Track user feedback (upvote/downvote)
   - Learn weights via collaborative filtering
   - Personalized importance scores

**Recommendation**: Start with (a), add (b) in 3 months, (c) in 6 months.

### 2. Should we expose dimension scores in UI?

**Pros**:
- Transparency: Users see why claim is A-tier
- Filtering: Users can find high-actionability claims
- Analytics: Track dimension trends over time

**Cons**:
- Complexity: 5 numbers instead of 1
- UI clutter: More data to display
- User confusion: What's the difference between epistemic_value and verifiability?

**Recommendation**: Expose in "Advanced" view, hide by default.

### 3. Should we allow per-episode profile selection?

Example: "I'm processing a finance podcast, use 'investor' profile"

**Pros**:
- Better tier accuracy for domain-specific content
- User control over scoring

**Cons**:
- Adds complexity to UI
- May miss cross-domain insights
- Profile selection is another decision point

**Recommendation**: Not in MVP. Evaluate after 3 months of usage data.

### 4. Should we re-score all existing claims?

**Pros**:
- Uniform scoring across all claims
- Better search and filtering
- Analytics on full dataset

**Cons**:
- Cost: ~$100-200 for 10,000 claims
- Time: ~3 hours of processing
- May change existing tier distributions

**Recommendation**:
- Option 1: Lazy migration (only score new claims with v2)
- Option 2: Approximate backfill (map old importance → estimated dimensions, free)
- Option 3: Bulk re-scoring (re-run evaluator on all claims, $100-200)

Suggest: Start with Option 1, do Option 2 for analytics, consider Option 3 if budget allows.

---

## Appendix A: Profile Definitions

### Standard Profiles (12)

```python
STANDARD_PROFILES = {
    "scientist": UserProfile(
        name="Scientist/Researcher",
        description="Values deep understanding, theoretical insights, and well-supported claims",
        weights={
            "epistemic_value": 0.50,
            "verifiability": 0.30,
            "novelty": 0.15,
            "actionability": 0.05,
        }
    ),

    "philosopher": UserProfile(
        name="Philosopher/Critical Thinker",
        description="Values conceptual clarity, novel perspectives, and logical coherence",
        weights={
            "epistemic_value": 0.40,
            "novelty": 0.30,
            "verifiability": 0.20,
            "actionability": 0.10,
        }
    ),

    "educator": UserProfile(
        name="Educator/Teacher",
        description="Values clear explanations, foundational knowledge, and broad applicability",
        weights={
            "understandability": 0.40,
            "epistemic_value": 0.30,
            "actionability": 0.20,
            "novelty": 0.10,
        }
    ),

    "student": UserProfile(
        name="Student/Learner",
        description="Values accessible insights, surprising facts, and learning-oriented content",
        weights={
            "understandability": 0.35,
            "novelty": 0.30,
            "epistemic_value": 0.25,
            "actionability": 0.10,
        }
    ),

    "skeptic": UserProfile(
        name="Skeptic/Fact-Checker",
        description="Values evidence quality, source reliability, and falsifiability",
        weights={
            "verifiability": 0.60,
            "epistemic_value": 0.25,
            "novelty": 0.10,
            "actionability": 0.05,
        }
    ),

    "investor": UserProfile(
        name="Investor/Financial Professional",
        description="Values practical utility, market insights, and actionable intelligence",
        weights={
            "actionability": 0.50,
            "verifiability": 0.25,
            "epistemic_value": 0.15,
            "novelty": 0.10,
        }
    ),

    "policy_maker": UserProfile(
        name="Policy Maker/Governance",
        description="Values broad impact, evidence-based policy, and systemic thinking",
        weights={
            "actionability": 0.35,
            "epistemic_value": 0.30,
            "verifiability": 0.20,
            "understandability": 0.15,
        }
    ),

    "tech_professional": UserProfile(
        name="Tech Professional/Engineer",
        description="Values practical implementation, technical depth, and reproducibility",
        weights={
            "actionability": 0.45,
            "epistemic_value": 0.25,
            "verifiability": 0.20,
            "novelty": 0.10,
        }
    ),

    "health_professional": UserProfile(
        name="Health/Medical Professional",
        description="Values clinical evidence, patient safety, and therapeutic utility",
        weights={
            "verifiability": 0.45,
            "actionability": 0.30,
            "epistemic_value": 0.20,
            "novelty": 0.05,
        }
    ),

    "journalist": UserProfile(
        name="Journalist/Communicator",
        description="Values newsworthy insights, clear communication, and source credibility",
        weights={
            "novelty": 0.35,
            "understandability": 0.30,
            "verifiability": 0.20,
            "epistemic_value": 0.15,
        }
    ),

    "generalist": UserProfile(
        name="Curious Generalist",
        description="Values interesting facts, accessible knowledge, and broad learning",
        weights={
            "novelty": 0.40,
            "understandability": 0.25,
            "epistemic_value": 0.20,
            "actionability": 0.15,
        }
    ),

    "pragmatist": UserProfile(
        name="Pragmatist/Decision-Maker",
        description="Values immediate utility, practical application, and reliable information",
        weights={
            "actionability": 0.50,
            "verifiability": 0.25,
            "understandability": 0.15,
            "epistemic_value": 0.10,
        }
    ),
}
```

Note: All weights sum to 1.0. Understandability is omitted from profiles that don't weight it (equivalent to 0.0 weight).

---

## Appendix B: Example Dimension Scoring

### Example 1: Neuroscience Insight

**Claim**: "Dopamine regulates motivation, not pleasure"

**Dimensions** (LLM evaluation):
```json
{
  "epistemic_value": 9,     // Fundamental insight about brain function
  "actionability": 6,        // Some practical implications for behavior
  "novelty": 8,              // Challenges popular misconception
  "verifiability": 8,        // Well-supported by neuroscience research
  "understandability": 7     // Clear claim, some jargon
}
```

**Profile Scores** (arithmetic):
```json
{
  "scientist": 8.4,          // High epistemic_value (50%) + verifiability (30%)
  "investor": 7.1,           // Moderate actionability (50%), low practical use
  "philosopher": 8.2,        // High epistemic_value (40%) + novelty (30%)
  "educator": 7.8,           // Good understandability (40%) + epistemic_value (30%)
  "student": 7.6,            // Good novelty (30%) + understandability (35%)
  "skeptic": 8.3,            // High verifiability (60%) + epistemic_value (25%)
  "generalist": 7.8,         // High novelty (40%) + understandability (25%)
  "health_professional": 8.0 // High verifiability (45%) + actionability (30%)
}
```

**Final Score**:
- Importance: **8.4** (max across profiles)
- Best Profile: **scientist**
- Tier: **A** (≥ 8.0)

**Analysis**: Niche neuroscience insight rescued by max-scoring. Would score ~7.5 with single profile approach (borderline B/A). With multi-profile, clearly A-tier because it's extremely valuable to scientists and skeptics.

### Example 2: Practical Finance Tip

**Claim**: "The Fed's QE program creates asset inflation, not CPI inflation"

**Dimensions**:
```json
{
  "epistemic_value": 8,      // Explains mechanism of monetary policy
  "actionability": 9,         // Actionable for investment decisions
  "novelty": 7,               // Somewhat known but not obvious
  "verifiability": 7,         // Supported by economic data, some debate
  "understandability": 6      // Requires some econ knowledge
}
```

**Profile Scores**:
```json
{
  "scientist": 7.7,          // Good epistemic_value, not core research
  "investor": 8.6,           // High actionability (50%) + verifiability (25%)
  "philosopher": 7.7,        // Good epistemic_value + novelty
  "policy_maker": 8.4,       // High actionability (35%) + epistemic_value (30%)
  "tech_professional": 8.2,  // High actionability (45%) + epistemic_value (25%)
  "pragmatist": 8.1          // High actionability (50%) + verifiability (25%)
}
```

**Final Score**:
- Importance: **8.6** (max across profiles)
- Best Profile: **investor**
- Tier: **A** (≥ 8.0)

**Analysis**: Actionable financial insight scores highest for investors and policy makers. Even though epistemic_value is not maximal, high actionability makes it A-tier.

### Example 3: Trivial Fact

**Claim**: "Jerome Powell is the current Fed Chairman"

**Dimensions**:
```json
{
  "epistemic_value": 1,      // No insight, just a fact
  "actionability": 2,         // Minimal practical use
  "novelty": 1,               // Widely known
  "verifiability": 10,        // Easily verified, completely accurate
  "understandability": 10     // Crystal clear
}
```

**Profile Scores**:
```json
{
  "scientist": 2.8,          // Low on all dimensions except verifiability
  "investor": 2.8,           // Low actionability
  "philosopher": 2.5,        // No epistemic value or novelty
  "skeptic": 6.3,            // High verifiability, but low on other dimensions
  "journalist": 3.9,         // Low novelty (everyone knows this)
  "generalist": 3.9          // Low novelty
}
```

**Final Score**:
- Importance: **6.3** (max across profiles, from skeptic)
- Best Profile: **skeptic**
- Tier: **C** (< 6.5)

**Analysis**: Even with max-scoring, trivial claim scores low (<6.5) because it's low on ALL meaningful dimensions. High verifiability (10) isn't enough to make it valuable. Would be rejected or C-tier.

---

## Appendix C: Implementation Checklist

### Schema Changes
- [ ] Create `flagship_output.v2.json` schema
- [ ] Add `dimensions`, `profile_scores`, `best_profile` fields
- [ ] Update schema validator with v2 repair logic
- [ ] Add backward compatibility for v1 schema

### Prompt Changes
- [ ] Create `flagship_evaluator_v2.txt` prompt
- [ ] Add 5-dimension scoring section with clear definitions
- [ ] Add examples for each dimension (1, 5, 10 scores)
- [ ] Test prompt with sample claims

### Code Changes
- [ ] Create `src/knowledge_system/scoring/profiles.py`
- [ ] Define 12 standard `UserProfile` objects
- [ ] Create `src/knowledge_system/scoring/multi_profile_scorer.py`
- [ ] Implement `score_for_profile()`, `score_all_profiles()`, `get_importance_max()`
- [ ] Update `flagship_evaluator.py` to call multi-profile scorer
- [ ] Update `EvaluatedClaim` class with new properties
- [ ] Add unit tests for profile scoring
- [ ] Add integration tests for v2 evaluator

### Database Changes
- [ ] Add `dimensions JSON` column to claims table
- [ ] Add `profile_scores JSON` column to claims table
- [ ] Add `best_profile TEXT` column to claims table
- [ ] Create index on `best_profile`
- [ ] Write migration script for existing claims (optional)

### Testing
- [ ] Unit tests: Profile weight validation
- [ ] Unit tests: Profile scoring arithmetic
- [ ] Unit tests: Max-scoring vs top-k vs percentile
- [ ] Integration tests: v2 evaluator output schema
- [ ] Integration tests: Tier distribution comparison
- [ ] Cost validation: LLM calls constant across profiles
- [ ] Smoke test: Process 100 real episodes

### Deployment
- [ ] Deploy to staging environment
- [ ] Run parallel v1/v2 evaluation on 100 episodes
- [ ] Compare tier distributions
- [ ] Validate costs (should be +50%)
- [ ] Deploy to production
- [ ] Monitor LLM API costs
- [ ] Create analytics queries for dimension distributions

### Documentation
- [ ] Document profile definitions
- [ ] Document dimension scoring criteria
- [ ] Add migration guide for v1→v2
- [ ] Add API documentation for multi-profile scoring
- [ ] Create user guide with examples

---

## Conclusion

The multi-profile scoring system provides a robust, scalable, and cost-effective way to evaluate claim importance across diverse user needs. By separating semantic evaluation (LLM) from profile scoring (arithmetic), we achieve:

1. **Zero marginal cost for additional profiles**
2. **Better tier accuracy** (rescues niche-but-valuable insights)
3. **Queryable dimensions** (enables analytics and filtering)
4. **Recalculable scores** (change weights without re-running LLM)
5. **Transparent scoring** (users understand why claims are A-tier)

The system is designed for **backward compatibility**, **gradual rollout**, and **minimal cost increase** (~50% LLM cost, same computational cost).

**Recommended Timeline**:
- Week 1: Prototype testing and validation
- Week 2: Schema and prompt updates
- Week 3: Profile scoring module implementation
- Week 4: Database migration and integration testing
- Week 5: Deployment and monitoring

**Estimated Total Effort**: 3-4 weeks for 1 developer

**Estimated Cost Increase**: +50% LLM costs (~$0.015 vs $0.01 per claim)

**Expected Benefits**:
- Better tier accuracy (+10-20% A-tier claims, all justified)
- Queryable dimensions for advanced filtering
- Extensible to unlimited profiles at no cost
- Foundation for personalized importance scoring

---

**Next Steps**:
1. Review and approve this plan
2. Run prototype on 100 existing claims
3. Validate tier distributions make sense
4. Proceed with Phase 1 implementation
