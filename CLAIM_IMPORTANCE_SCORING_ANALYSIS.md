# Claim Importance Scoring: Analysis and Recommendations

**Date:** December 15, 2025
**Purpose:** Evaluate current claim scoring methodology and propose improvements based on academic research

---

## Table of Contents

1. [Current System Analysis](#1-current-system-analysis)
2. [Academic Research on Information Value](#2-academic-research-on-information-value)
3. [Problems with Current Approach](#3-problems-with-current-approach)
4. [Proposed Improvements](#4-proposed-improvements)
5. [Tier Classification System](#5-tier-classification-system)
6. [Implementation Recommendations](#6-implementation-recommendations)

---

## 1. Current System Analysis

### 1.1 Current Scoring Dimensions

Your flagship evaluator uses **three independent dimensions** (1-10 scale):

| Dimension | Current Definition | Weight in Practice |
|-----------|-------------------|-------------------|
| **Importance** | Intellectual significance, centrality to message | PRIMARY (used for tiering) |
| **Novelty** | Surprise value, challenges conventional wisdom | Secondary (tie-breaker) |
| **Confidence** | Evidence quality, logical coherence | Secondary (tie-breaker) |

### 1.2 Current Tier System

**Implicit tiers** based on importance score:

- **A-tier:** Importance 8-10 ("high-value claims")
- **B-tier:** Importance 6-7 ("moderate value")
- **C-tier:** Importance <6 ("low value")

**Usage in proposed claims-first architecture:**
- Lazy speaker attribution applies only to A/B-tier (importance ≥7)
- C-tier claims don't get speaker attribution (not worth the effort)

### 1.3 Current Importance Criteria

From `flagship_evaluator.txt`:

**9-10: Core insights**
> "Fundamentally shape understanding of the topic"

**7-8: Significant claims**
> "Add substantial intellectual value"

**5-6: Useful claims**
> "Provide moderate insight or context"

**3-4: Minor claims**
> "Limited value but some merit"

**1-2: Trivial claims**
> "Should likely be rejected"

### 1.4 Example Scoring

**Accepted (Importance 8):**
> "The Federal Reserve's quantitative easing program has fundamentally altered the relationship between monetary policy and asset prices"

**Rejected (Importance 1):**
> "Jerome Powell is the current Fed Chairman"

**Rejected (Importance 2):**
> "Asset prices respond to monetary policy changes"

---

## 2. Academic Research on Information Value

### 2.1 Value of Information (VOI) Theory

From healthcare decision science research (ISPOR, 2020):

**Core principle:** Information has value when it **reduces decision uncertainty**.

**Key VOI Metrics:**

1. **EVPI** (Expected Value of Perfect Information)
   - What's the value of resolving ALL uncertainty?
   - Maximum value this information could provide

2. **EVPPI** (Expected Value of Perfect Parameter Information)
   - What's the value of resolving uncertainty in SPECIFIC parameters?
   - More practical than EVPI

3. **EVSI** (Expected Value of Sample Information)
   - What's the value of collecting a SPECIFIC dataset?
   - Accounts for sample size limitations

**Application to claims:**

A claim's value = **How much does it reduce uncertainty for decision-makers?**

### 2.2 Epistemic Value Framework

From machine learning research (2025, WIREs):

**Two types of uncertainty:**

1. **Aleatoric uncertainty** (irreducible)
   - Inherent randomness in the world
   - Cannot be reduced with more information
   - Example: "Markets sometimes go up, sometimes down"

2. **Epistemic uncertainty** (reducible)
   - Uncertainty due to lack of knowledge
   - CAN be reduced with better information
   - Example: "The Fed's QE program caused asset inflation"

**High-value claims reduce epistemic uncertainty.**

### 2.3 Knowledge Graph Quality Assessment

From recent research (Nature, 2024):

**Dimensions of knowledge quality:**

1. **Accuracy** - Is the claim correct?
2. **Completeness** - Does it capture the full picture?
3. **Consistency** - Does it contradict other knowledge?
4. **Timeliness** - Is it still relevant/current?
5. **Relevance** - Does it matter for the use case?

**For knowledge extraction:**
- Accuracy → Your "confidence" score
- Completeness → Partially captured in "evidence quality"
- Consistency → NOT currently evaluated
- Timeliness → NOT currently evaluated
- Relevance → Your "importance" score

### 2.4 Critical Appraisal Skills Programme (CASP)

From systematic review methodology:

**Questions for evaluating research claims:**

1. **Validity:** Is the claim well-supported?
2. **Reliability:** Would different evaluators reach the same conclusion?
3. **Applicability:** Can this be applied to our context?
4. **Clinical/Practical significance:** Does it matter in practice?
5. **Statistical vs practical significance:** Big effect size?

**For knowledge extraction:**
- Validity → Your "confidence" score
- Reliability → NOT currently evaluated
- Applicability → Your "relevance/importance" score
- Practical significance → Partially in "importance"
- Effect size → NOT currently evaluated

---

## 3. Problems with Current Approach

### 3.1 Oversimplified Importance Definition

**Problem:** "Intellectual significance" is too vague and subjective.

Different evaluators might score the same claim very differently based on:
- Their background knowledge
- What they find personally interesting
- Their interpretation of "fundamentally shape understanding"

**Example ambiguity:**

Claim: "The Fed's QE program creates asset inflation, not consumer inflation"

- Economist: Importance 9 (fundamental insight into monetary transmission)
- General audience: Importance 5 (interesting but doesn't change their life)
- Investor: Importance 10 (directly actionable for portfolio decisions)

**Who's right?** All of them—importance is context-dependent.

### 3.2 No User Context Consideration

**Problem:** Importance is scored without knowing WHO the user is or WHY they care.

A claim about "neurotransmitter receptor binding" might be:
- Importance 9 for a neuroscientist
- Importance 3 for a casual podcast listener
- Importance 7 for a medical student

**Your system assumes a single, universal importance score.**

### 3.3 Independence Assumption Questionable

**Problem:** You treat importance, novelty, and confidence as independent dimensions.

**Reality:** They're correlated:

- **High novelty often means lower confidence**
  - Novel claims lack established evidence
  - "The Fed's secret gold manipulation" (novel=10, confidence=2)

- **High confidence often means lower novelty**
  - Well-established claims are not surprising
  - "Supply and demand determine prices" (confidence=10, novelty=1)

**Sweet spot:** Medium-high novelty + medium-high confidence
- Novel enough to be interesting
- Supported enough to be credible

### 3.4 No Temporal Dimension

**Problem:** Claims don't decay in value over time in your system.

**Reality:**

- **Timeless claims** retain value indefinitely
  - "Gravity follows an inverse square law"
  - Mathematical proofs, fundamental principles

- **Time-sensitive claims** decay rapidly
  - "Jerome Powell is the current Fed Chairman" (true in 2025, false in 2030)
  - "AI cannot reason abstractly" (maybe true in 2020, false in 2025)

**Your system doesn't distinguish these.**

### 3.5 No Actionability Metric

**Problem:** You don't score "can I DO anything with this claim?"

**Value hierarchy:**

1. **Actionable claims** (highest value)
   - "Diversifying across asset classes reduces portfolio volatility"
   - User can immediately apply this

2. **Analytical claims** (medium value)
   - "QE creates asset inflation"
   - User understands the world better but unclear what to do

3. **Descriptive claims** (lower value)
   - "The Fed meets 8 times per year"
   - Informative but not transformative

**Your importance score conflates these.**

### 3.6 Binary Tier Cutoffs Are Arbitrary

**Problem:** Why is importance 7 the cutoff for speaker attribution?

- Importance 6.9 → No speaker attribution (C-tier)
- Importance 7.0 → Gets speaker attribution (B-tier)

**This assumes:**
- The importance scale is linear and continuous
- The jump from 6→7 is meaningful
- LLMs can score with this precision (they can't)

**Reality:** LLMs struggle to differentiate fine gradations. Their scores cluster around 5, 7, 9.

---

## 4. Proposed Improvements

### 4.1 Multi-Dimensional Value Framework

Instead of a single "importance" score, use **multiple value dimensions** relevant to different use cases:

#### Dimension 1: Epistemic Value (Reduces Uncertainty)

**Question:** "Does this claim meaningfully reduce my uncertainty about how the world works?"

**Scale:**
- **10:** Resolves a major open question or misconception
- **8:** Clarifies a previously confusing topic
- **6:** Adds useful context or detail
- **4:** Somewhat informative but doesn't change understanding much
- **2:** Redundant with common knowledge

**Example:**
- "QE creates asset inflation, not CPI inflation" → Epistemic value 9
  - Resolves confusion about why inflation metrics diverged from asset prices

#### Dimension 2: Actionability (Enables Decisions)

**Question:** "Can I DO something different based on this claim?"

**Scale:**
- **10:** Directly actionable, clear implications for behavior
- **8:** Suggests concrete actions, though context-dependent
- **6:** Informative for decisions but not directly prescriptive
- **4:** Background knowledge that might influence thinking
- **2:** Interesting but not practically useful

**Example:**
- "Diversification reduces portfolio risk" → Actionability 9
  - Clear investment strategy implication

#### Dimension 3: Novelty (Surprisingness)

**Keep this dimension, but refine definition:**

**Question:** "How surprising is this claim relative to common knowledge?"

**Scale:**
- **10:** Completely counterintuitive, challenges deeply held beliefs
- **8:** Unexpected connection or insight
- **6:** Somewhat surprising, fresh perspective
- **4:** Slightly novel angle on familiar topic
- **2:** Obvious or widely known

**Example:**
- "Dopamine regulates motivation, not pleasure" → Novelty 8
  - Challenges common misunderstanding of dopamine

#### Dimension 4: Verifiability (Evidence Strength)

**Rename "confidence" to "verifiability" for clarity:**

**Question:** "How strong is the evidence supporting this claim?"

**Scale:**
- **10:** Extensively researched, strong empirical support
- **8:** Well-supported by multiple credible sources
- **6:** Plausible with some supporting evidence
- **4:** Speculative but reasonable
- **2:** Unsupported assertion or opinion

#### Dimension 5: Scope (Generalizability)

**New dimension:**

**Question:** "How broadly applicable is this claim?"

**Scale:**
- **10:** Universal principle, applies across all contexts
- **8:** Broad applicability with few exceptions
- **6:** Applies to a specific domain or field
- **4:** Narrow applicability, limited contexts
- **2:** Highly specific edge case

**Example:**
- "Compound interest grows exponentially" → Scope 10
  - Universal mathematical principle
- "The Fed's repo operations affect overnight rates" → Scope 4
  - Specific to US monetary policy mechanics

#### Dimension 6: Temporal Stability

**New dimension:**

**Question:** "How long will this claim remain true/relevant?"

**Scale:**
- **10:** Timeless (mathematical proofs, physical laws)
- **8:** Long-lasting (decades+)
- **6:** Medium-term (years)
- **4:** Short-term (months)
- **2:** Ephemeral (days/weeks)

**Example:**
- "Jerome Powell is Fed Chairman" → Temporal stability 4
  - True for a few years, then outdated
- "Central banks use interest rates to manage inflation" → Temporal stability 9
  - Fundamental principle unlikely to change

### 4.2 Composite Importance Score

**Instead of asking LLM for "importance", derive it from dimensions:**

```
Composite Importance = Weighted Average of Dimensions

Default weights:
- Epistemic Value: 35%
- Actionability: 25%
- Novelty: 20%
- Verifiability: 10%
- Scope: 5%
- Temporal Stability: 5%

User-customizable weights based on use case
```

**Example calculation:**

Claim: "QE creates asset inflation, not CPI inflation"

- Epistemic Value: 9
- Actionability: 7 (informs investment decisions)
- Novelty: 8 (challenges common assumption)
- Verifiability: 7 (empirically supported but debated)
- Scope: 6 (specific to monetary policy)
- Temporal Stability: 8 (likely remains true for years)

```
Composite = (9×0.35) + (7×0.25) + (8×0.20) + (7×0.10) + (6×0.05) + (8×0.05)
          = 3.15 + 1.75 + 1.60 + 0.70 + 0.30 + 0.40
          = 7.9 → rounds to 8 (A-tier)
```

### 4.3 Context-Aware Tiering

**Problem:** Different users care about different things.

**Solution:** Allow users to customize weights:

**Academic Researcher Profile:**
- Epistemic Value: 50% (want to understand deeply)
- Novelty: 30% (want new insights)
- Verifiability: 15% (must be well-supported)
- Actionability: 5% (less concerned with practical use)

**Investor Profile:**
- Actionability: 50% (want to make money)
- Verifiability: 25% (need reliable info)
- Epistemic Value: 15% (understanding helps decisions)
- Novelty: 10% (edge if others don't know)

**Casual Learner Profile:**
- Novelty: 40% (want to be surprised)
- Epistemic Value: 30% (want to learn)
- Actionability: 20% (want to apply knowledge)
- Verifiability: 10% (trust but verify)

**Result:** Same claim scores differently for different users.

### 4.4 Probabilistic Tiers Instead of Hard Cutoffs

**Problem:** Binary cutoffs create artificial boundaries.

**Solution:** Use **fuzzy membership** in tiers:

```
Instead of:
- Importance 6.9 = C-tier (0% chance of A-tier)
- Importance 7.0 = B-tier (0% chance of C-tier)

Use:
- Importance 7.0 = 60% B-tier, 30% A-tier, 10% C-tier
- Importance 8.5 = 90% A-tier, 10% B-tier, 0% C-tier
```

**For speaker attribution:**

```
Attribution probability = f(importance_score)

- Importance 9-10: 100% get speaker attribution
- Importance 7-8: 75% get speaker attribution (randomly sample)
- Importance 5-6: 25% get speaker attribution (randomly sample)
- Importance <5: 0% get speaker attribution
```

**Benefit:** Softens boundaries, accounts for scoring uncertainty.

### 4.5 Claim Clustering and Redundancy Detection

**Problem:** Multiple similar claims each scored independently.

**Solution:** Detect clusters and score them collectively:

**Example cluster:**

1. "QE creates asset inflation" (importance 8)
2. "QE inflates equity prices" (importance 7)
3. "QE benefits asset holders disproportionately" (importance 9)

**These are related!** They should be:
- Merged into a single canonical claim
- Or scored as a **claim family** with representative claim

**Approach:**

1. **Semantic similarity:** Cluster claims with >0.8 cosine similarity
2. **Representative selection:** Pick highest-importance claim as representative
3. **Family scoring:** Boost representative claim's importance by 0.5-1.0 points
   - Having 3 variations suggests this is a key theme

### 4.6 Meta-Scoring: Evaluator Confidence

**Problem:** LLM scoring is uncertain but presented as definitive.

**Solution:** Ask LLM to report **confidence in its own scoring**:

```json
{
  "claim": "QE creates asset inflation",
  "importance": 8,
  "importance_confidence": 0.85,  // NEW: How sure are you of this score?
  "scoring_rationale": "Strong evidence and clear significance, but some subjectivity in 'fundamental' vs 'significant'"
}
```

**Use for tiering:**

- Importance 7, confidence 0.95 → Definitely B-tier
- Importance 7, confidence 0.50 → Maybe B-tier, maybe C-tier (probabilistic)
- Importance 9, confidence 0.40 → Might be A-tier, but unreliable scoring

**Flag for review:** Claims with low scoring confidence need human verification.

---

## 5. Tier Classification System

### 5.1 Proposed Tier Definitions

#### A-Tier: "Must-Know" Claims

**Criteria (ALL must be true):**
- Composite importance ≥8.0
- Epistemic value ≥7 OR Actionability ≥8
- Verifiability ≥6 (must be reasonably well-supported)
- NOT redundant with other A-tier claims (>0.9 similarity)

**Characteristics:**
- Core insights that fundamentally shape understanding
- Directly actionable or resolve major uncertainties
- Well-supported by evidence
- Non-obvious and intellectually significant

**Examples:**
- "Dopamine regulates motivation, not pleasure" (neuroscience)
- "Compound interest is exponential, not linear" (finance)
- "Diversification reduces unsystematic risk" (investment)

**Treatment in claims-first architecture:**
- Always get speaker attribution (100%)
- Displayed prominently to users
- Indexed for semantic search
- Used in summaries and highlights

#### B-Tier: "Good-to-Know" Claims

**Criteria:**
- Composite importance 6.0-7.9
- OR: High on one dimension (≥8) even if others are lower
  - Example: Novelty 9, Epistemic 5 → B-tier (interesting even if not deeply significant)

**Characteristics:**
- Useful insights that add meaningful context
- Moderately actionable or informative
- May be surprising or valuable in specific contexts
- Reasonably well-supported

**Examples:**
- "The Fed uses reverse repo operations to manage overnight rates" (technical but important)
- "Processed foods often contain hidden sugars" (actionable but not groundbreaking)
- "Meditation can reduce amygdala activation" (interesting neuroscience)

**Treatment:**
- 75% get speaker attribution (probabilistic sampling)
- Shown to users but not in headlines
- Included in comprehensive summaries
- Indexed for search

#### C-Tier: "Nice-to-Know" Claims

**Criteria:**
- Composite importance 4.0-5.9
- OR: Failing verifiability (≤4) even if otherwise interesting
- OR: Very narrow scope (≤3) with limited applicability

**Characteristics:**
- Minor insights or background information
- Limited practical value
- May be interesting to specialists only
- Possibly speculative or weakly supported

**Examples:**
- "Andrew Huberman hosts a podcast" (true but trivial)
- "Some people prefer decaf coffee" (obvious)
- "The Fed might change policy next year" (speculative)

**Treatment:**
- 0% get speaker attribution (not worth the effort)
- Not shown to general users
- Available in full exports for completeness
- Not indexed for search

#### D-Tier: "Reject" Claims

**Criteria (ANY triggers rejection):**
- Composite importance <4.0
- Verifiability ≤3 (unsupported speculation)
- Temporal stability ≤2 (will be outdated within weeks)
- Redundancy >0.95 with higher-tier claim
- Procedural/meta statements ("Let me explain...")

**Characteristics:**
- Trivial facts or obvious statements
- Unsupported speculation
- Redundant with better claims
- Not actually claims (just narration)

**Examples:**
- "Jerome Powell is Fed Chairman" (trivial fact)
- "Economics is complicated" (meaningless)
- "The speaker will discuss this later" (meta)

**Treatment:**
- Completely removed from database
- Not shown to users
- Not used in any outputs

### 5.2 Tier Distribution Targets

**Ideal distribution for a 1-hour podcast:**

| Tier | Target Count | Target % | Rationale |
|------|--------------|----------|-----------|
| A-tier | 5-15 | 10-30% | Core insights (too many = low standards) |
| B-tier | 15-25 | 30-50% | Supporting insights (bulk of value) |
| C-tier | 10-20 | 20-30% | Background details (completeness) |
| D-tier | 0-5 | 0-10% | Rejected (should be minimal) |

**Total claims:** 30-65 per hour of content

**Quality signal:**
- Too many A-tier (>40%) → Evaluator is too lenient
- Too few A-tier (<5%) → Evaluator is too strict or content is low-quality
- Too many D-tier (>15%) → Miner needs better prompts

### 5.3 Dynamic Tier Adjustment

**Problem:** Tier boundaries depend on content type.

**Solution:** Adjust thresholds based on content genre:

**Academic lecture:**
- A-tier threshold: 8.5 (expect deep insights)
- Focus: Epistemic value, Verifiability

**Investment podcast:**
- A-tier threshold: 7.5 (actionability matters more than depth)
- Focus: Actionability, Temporal stability

**Pop science podcast:**
- A-tier threshold: 8.0 (balance novelty and accessibility)
- Focus: Novelty, Scope

**How to implement:**

```python
def get_tier_thresholds(content_type: str) -> dict:
    """Get tier thresholds based on content type."""

    THRESHOLDS = {
        "academic": {"A": 8.5, "B": 7.0, "C": 5.0},
        "finance": {"A": 7.5, "B": 6.0, "C": 4.5},
        "pop_science": {"A": 8.0, "B": 6.5, "C": 5.0},
        "news": {"A": 7.0, "B": 5.5, "C": 4.0},  # Lower bar, higher volume
        "default": {"A": 8.0, "B": 6.5, "C": 5.0}
    }

    return THRESHOLDS.get(content_type, THRESHOLDS["default"])
```

---

## 6. Implementation Recommendations

### 6.1 Phased Rollout

#### Phase 1: Add New Dimensions (No Breaking Changes)

**Week 1-2:**

1. Update `flagship_evaluator.txt` prompt to ask for **6 dimensions**:
   - Epistemic Value (new)
   - Actionability (new)
   - Novelty (existing)
   - Verifiability (rename from confidence)
   - Scope (new)
   - Temporal Stability (new)

2. Keep existing "importance" field for backward compatibility

3. Compute composite importance from dimensions

4. Compare old importance vs new composite:
   - Log discrepancies >2 points
   - Analyze patterns

**Deliverable:** Data on whether new scoring improves tier classification

#### Phase 2: Implement Probabilistic Tiering

**Week 3-4:**

1. Replace hard cutoffs with probability distributions

2. Test on 100 podcasts:
   - Compare old binary tiers vs new probabilistic tiers
   - Measure: How many claims change tiers?
   - Evaluate: Do new tiers feel more accurate?

3. A/B test speaker attribution:
   - Group A: Old system (all importance ≥7)
   - Group B: New system (probabilistic, expect ~75% of importance 7-8)

**Deliverable:** Evidence that probabilistic tiering reduces boundary artifacts

#### Phase 3: Add Context Profiles

**Week 5-6:**

1. Create 3-5 user profiles with different dimension weights:
   - Academic
   - Investor
   - Casual learner
   - Domain expert
   - Skeptic (weight verifiability heavily)

2. Allow users to select profile or customize weights

3. Measure: Do users engage more with personalized tiers?

**Deliverable:** User-customizable importance scoring

#### Phase 4: Meta-Scoring and Quality Metrics

**Week 7-8:**

1. Add "scoring confidence" to LLM output

2. Flag claims with low scoring confidence for review

3. Implement claim clustering and redundancy detection

4. Track tier distribution and flag anomalies

**Deliverable:** Quality monitoring dashboard

### 6.2 Updated Prompt Example

**Excerpt from revised `flagship_evaluator.txt`:**

```
## EVALUATION DIMENSIONS (1-10 Scale)

For each accepted claim, score on these SIX dimensions:

### 1. Epistemic Value (Reduces Uncertainty)
How much does this claim reduce uncertainty about how the world works?
- 9-10: Resolves major open questions or misconceptions
- 7-8: Clarifies previously confusing topics
- 5-6: Adds useful context or detail
- 3-4: Somewhat informative but doesn't change understanding
- 1-2: Redundant with common knowledge

### 2. Actionability (Enables Decisions)
Can someone DO something different based on this claim?
- 9-10: Directly actionable, clear behavioral implications
- 7-8: Suggests concrete actions (context-dependent)
- 5-6: Informative for decisions but not prescriptive
- 3-4: Background knowledge that might influence thinking
- 1-2: Interesting but not practically useful

### 3. Novelty (Surprisingness)
How surprising is this relative to common knowledge?
- 9-10: Completely counterintuitive, challenges deep beliefs
- 7-8: Unexpected connection or insight
- 5-6: Somewhat surprising, fresh perspective
- 3-4: Slightly novel angle on familiar topic
- 1-2: Obvious or widely known

### 4. Verifiability (Evidence Strength)
How strong is the evidence supporting this claim?
- 9-10: Extensively researched, strong empirical support
- 7-8: Well-supported by multiple credible sources
- 5-6: Plausible with some supporting evidence
- 3-4: Speculative but reasonable
- 1-2: Unsupported assertion or opinion

### 5. Scope (Generalizability)
How broadly applicable is this claim?
- 9-10: Universal principle, applies across all contexts
- 7-8: Broad applicability with few exceptions
- 5-6: Applies to a specific domain or field
- 3-4: Narrow applicability, limited contexts
- 1-2: Highly specific edge case

### 6. Temporal Stability (Longevity)
How long will this claim remain true/relevant?
- 9-10: Timeless (mathematical, physical laws)
- 7-8: Long-lasting (decades+)
- 5-6: Medium-term (years)
- 3-4: Short-term (months)
- 1-2: Ephemeral (days/weeks)

### 7. Scoring Confidence (Meta-Score)
How confident are you in these dimension scores?
- 0.9-1.0: Very confident, clear criteria apply
- 0.7-0.8: Reasonably confident, some subjectivity
- 0.5-0.6: Uncertain, could score differently on re-evaluation
- 0.3-0.4: Low confidence, highly subjective
- 0.0-0.2: Guessing, insufficient information

## COMPOSITE IMPORTANCE
The system will automatically compute composite importance as:
importance = (epistemic_value × 0.35) + (actionability × 0.25) + (novelty × 0.20) +
             (verifiability × 0.10) + (scope × 0.05) + (temporal_stability × 0.05)

DO NOT manually compute this—just provide the 6 dimension scores.
```

### 6.3 Schema Updates

**Update JSON schema to include new fields:**

```json
{
  "evaluated_claims": [
    {
      "original_claim_text": "...",
      "decision": "accept",

      // OLD (keep for backward compatibility)
      "importance": 8,
      "novelty": 7,
      "confidence_final": 8,

      // NEW (detailed dimensions)
      "dimensions": {
        "epistemic_value": 9,
        "actionability": 7,
        "novelty": 8,
        "verifiability": 7,
        "scope": 6,
        "temporal_stability": 8
      },

      // NEW (meta-scoring)
      "scoring_confidence": 0.85,
      "composite_importance": 7.9,

      // NEW (tier info)
      "tier": "A",
      "tier_probability": {"A": 0.90, "B": 0.10, "C": 0.00},

      "reasoning": "...",
      "rank": 1
    }
  ]
}
```

### 6.4 Testing and Validation

**Validation checklist:**

1. **Inter-rater reliability**
   - Have 2-3 humans score 20 claims independently
   - Compare to LLM scores
   - Measure agreement (Cohen's kappa)
   - Target: κ > 0.60 (substantial agreement)

2. **Tier stability**
   - Re-score same claims with same LLM (temperature=0.1)
   - Measure: % claims that change tiers
   - Target: <10% tier changes

3. **Distribution sanity**
   - Check tier distributions across 100 podcasts
   - Flag outliers (>50% A-tier or <5% A-tier)
   - Ensure targets met: 10-30% A-tier, 30-50% B-tier

4. **User satisfaction**
   - Survey users: "Do A-tier claims feel more important than B-tier?"
   - Measure engagement: Do users click on A-tier claims more?
   - Target: 80%+ agreement that tiers are meaningful

### 6.5 Monitoring Dashboard

**Track these metrics in production:**

```
CLAIM SCORING HEALTH

Tier Distribution (Last 100 podcasts):
├─ A-tier: 18% (target: 10-30%) ✅
├─ B-tier: 42% (target: 30-50%) ✅
├─ C-tier: 28% (target: 20-30%) ✅
└─ D-tier: 12% (target: 0-10%) ⚠️ SLIGHTLY HIGH

Dimension Score Distributions:
├─ Epistemic Value: mean=6.2, std=2.1 ✅
├─ Actionability: mean=5.8, std=2.3 ✅
├─ Novelty: mean=6.5, std=1.9 ✅
├─ Verifiability: mean=6.8, std=1.7 ✅
├─ Scope: mean=5.2, std=2.4 ✅
└─ Temporal Stability: mean=7.1, std=2.0 ✅

Scoring Confidence:
├─ Mean: 0.78 ✅
├─ Low confidence claims (<0.5): 8% ✅
└─ Flagged for review: 12 claims

Redundancy Detection:
├─ Claim clusters found: 8
├─ Avg cluster size: 2.4
└─ Representatives selected: 8

Tier Boundary Cases (importance 6.5-7.5):
├─ Total claims in boundary: 45
├─ Tier A probability >0.5: 18 (40%)
└─ Flagged for human review: 5
```

---

## 7. Comparison: Current vs Proposed

| Aspect | Current System | Proposed System |
|--------|---------------|-----------------|
| **Dimensions** | 3 (importance, novelty, confidence) | 6 (epistemic, actionability, novelty, verifiability, scope, temporal) |
| **Importance score** | Single LLM-generated number | Composite weighted average |
| **Tier boundaries** | Hard cutoffs (7, 6) | Probabilistic membership |
| **User customization** | None | Customizable dimension weights |
| **Context awareness** | Universal scoring | Profile-based scoring |
| **Redundancy handling** | None | Clustering + representative selection |
| **Meta-scoring** | None | LLM reports confidence in scores |
| **Quality monitoring** | Manual review | Automated distribution checks |
| **Temporal awareness** | None | Temporal stability dimension |
| **Actionability** | Conflated with importance | Explicit dimension |

---

## 8. Expected Outcomes

### 8.1 Improved Tier Accuracy

**Current problem:** Borderline claims (importance 6-8) have inconsistent tiers

**Expected improvement:**
- Probabilistic tiering reduces "this should be A-tier but scored 7.9" complaints
- Composite scoring considers multiple facets of value
- Tier distributions match targets (10-30% A, 30-50% B)

**Metric:** User survey shows 85%+ agreement that tiers feel "right"

### 8.2 Better Speaker Attribution Resource Allocation

**Current problem:** Attribute speakers to all claims with importance ≥7

**Expected improvement:**
- Probabilistic attribution: ~75% of importance 7-8 claims get speakers
- Saves ~15-20% of attribution API calls
- Focuses effort on highest-value claims

**Metric:** Speaker attribution cost reduced by 15-25%

### 8.3 User Personalization

**Current problem:** One-size-fits-all importance

**Expected improvement:**
- Academic users see more A-tier claims with high epistemic value
- Investors see more A-tier claims with high actionability
- Casual learners see more A-tier claims with high novelty

**Metric:** User engagement increases 20-30% with personalized tiers

### 8.4 Quality Assurance

**Current problem:** No systematic monitoring of scoring quality

**Expected improvement:**
- Automated detection of anomalous tier distributions
- Flagging of low-confidence scores for review
- Clustering reduces redundancy

**Metric:** 90%+ of podcasts have tier distributions within targets

---

## 9. Open Questions

**Q1: Should we expose dimension scores to users?**

Options:
- A: Show all 6 dimensions (transparent but overwhelming)
- B: Show composite importance only (simpler but less informative)
- C: Show dimensions on hover/expand (balance)

**Recommendation:** Option C (show by default, expand for details)

**Q2: How to handle claim evolution over time?**

If temporal_stability=4 (months), should we:
- Auto-downgrade tier after N months?
- Flag for re-evaluation?
- Leave unchanged?

**Recommendation:** Flag for re-evaluation after 2×temporal_stability period

**Q3: Should users be able to override tier assignments?**

Options:
- A: No (trust the algorithm)
- B: Yes (but track overrides to improve scoring)
- C: Yes, with reasoning (improve future prompts)

**Recommendation:** Option C (learn from user corrections)

**Q4: How granular should dimension weights be?**

Options:
- A: Preset profiles only (simpler)
- B: Full custom weights (flexible but complex)
- C: Presets with minor adjustments (balance)

**Recommendation:** Start with Option A, add Option C in Phase 3

**Q5: Should we use dimension scores for search ranking?**

Currently search is keyword-based. Could rank results by:
- Composite importance
- Specific dimension (e.g., "most actionable claims about inflation")

**Recommendation:** Add dimension-filtered search in future release

---

## 10. Conclusion

The current single-dimension "importance" scoring is **oversimplified for a complex knowledge extraction system**.

**Key improvements:**

1. **Multi-dimensional value framework** captures different facets of claim value
2. **Probabilistic tiering** eliminates artificial boundary effects
3. **Composite importance** provides more robust scoring
4. **User customization** makes tiers context-aware
5. **Meta-scoring** flags uncertain evaluations
6. **Clustering** reduces redundancy

**Recommended action:**
- Implement Phase 1 (add dimensions) immediately
- Test on 100 podcasts before full rollout
- Monitor tier distributions and adjust thresholds
- Iterate based on user feedback

**Bottom line:** Moving from a single "importance" score to a rich multi-dimensional framework will make tier assignments more accurate, transparent, and useful.

---

*Document version: 1.0*
*Last updated: December 15, 2025*
