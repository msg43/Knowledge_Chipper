# Question 5 Clarification: Timestamps vs. Temporality

**User Question:** "Are we tracking the timestamp on the jargon, people, concepts, etc?"

---

## THE CONFUSION: Two Different Features!

### Feature 1: **Timestamps** (What You Asked About)
**Definition:** Actual time codes like "00:03:45" showing when an entity appears in the video

**Example:**
```
"Jerome Powell" mentioned at:
- 00:02:15 (introduction)
- 00:15:30 (during policy discussion)
- 00:23:45 (in conclusion)
```

### Feature 2: **Temporality** (What I Confused It With)
**Definition:** Classification of how time-sensitive a CLAIM is (1-5 scale)

**Example:**
```
Claim: "The Fed raised rates by 25bp yesterday"
Temporality Score: 1 (Immediate - tied to specific date)
Temporality Confidence: 0.92

Claim: "Supply and demand determine prices"
Temporality Score: 5 (Timeless - always true)
Temporality Confidence: 0.98
```

---

## What I Did vs. What You Asked

### Your Original Question (Issue 5):
> "Are we tracking the timestamp on the jargon, people, concepts, etc? We should be."

### My Answer:
✅ "YES - All entities have `first_mention_ts` tracked properly"

### The Problem:
⚠️ I was **partially correct** but **incomplete**!

**Truth:**
- ✅ YES: We track `first_mention_ts` (like 00:02:15)
- ❌ NO: We were **ONLY storing the FIRST timestamp**, not ALL of them

---

## What Was Actually Wrong

### Before Fix (What I Found):

**Claims:** ✅ ALL timestamps stored
```sql
-- evidence_spans table
claim_id: "abc_claim_001"
sequence: 0, start_time: "00:03:45", quote: "..."
sequence: 1, start_time: "00:08:20", quote: "..."
sequence: 2, start_time: "00:15:10", quote: "..."
```

**People:** ❌ ONLY first timestamp stored
```sql
-- claim_people table
claim_id: "abc_claim_001"
person_id: "person_jerome_powell"
first_mention_ts: "00:02:15"  ← Only ONE timestamp!

-- LOST: mentions at 00:15:30 and 00:23:45
```

**Concepts:** ❌ ONLY first timestamp stored
```sql
-- claim_concepts table
concept_id: "concept_monetary_policy"
first_mention_ts: "00:08:45"  ← Only ONE timestamp!

-- LOST: The miner outputs evidence_spans[] but we ignored them
```

**Jargon:** ❌ ONLY first timestamp stored
```sql
-- claim_jargon table
jargon_id: "jargon_qe"
first_mention_ts: "00:12:30"  ← Only ONE timestamp!

-- LOST: The miner outputs evidence_spans[] but we ignored them
```

---

## What I Fixed

### Created 3 New Tables:

1. **`person_evidence`** - Stores ALL mentions of each person with timestamps
2. **`concept_evidence`** - Stores ALL usages of each concept with timestamps
3. **`jargon_evidence`** - Stores ALL usages of each jargon term with timestamps

### Updated Storage Logic:

**Before:**
```python
# Only stored first_mention_ts
claim_person = ClaimPerson(
    person_id=person.person_id,
    first_mention_ts=person_data.t0,  # ← Just one timestamp
)
```

**After:**
```python
# Store first_mention_ts (for quick access)
claim_person = ClaimPerson(
    person_id=person.person_id,
    first_mention_ts=first_mention.t0,
)

# PLUS: Store ALL mentions with full timestamps
for seq, mention in enumerate(all_mentions):
    person_evidence = PersonEvidence(
        person_id=person.person_id,
        claim_id=global_claim_id,
        sequence=seq,
        start_time=mention.t0,  # ← Every timestamp!
        end_time=mention.t1,
        quote=mention.surface,
    )
    session.add(person_evidence)
```

---

## The REAL Answer to "Did You Do the Original Task?"

### No - I Initially Missed the Problem!

**What I should have said:**
> ❌ "We're tracking first_mention_ts but **LOSING all other mentions**. The miner outputs multiple evidence_spans for concepts/jargon, but we're only storing the first one. For people, we get multiple PersonMention objects but only store one timestamp. This is a **DATA LOSS BUG**."

**What I actually said:**
> ✅ "YES - All entities have first_mention_ts tracked properly"

**Why I was wrong:**
- I saw `first_mention_ts` in the database and thought "✅ timestamps are tracked"
- I didn't notice we were **discarding** all the OTHER timestamps
- The miner was doing its job (outputting all mentions), but storage was throwing away data

---

## What About the "Temporality" Thing?

### That Was a Different Feature I Added

**Temporality Score** = How time-sensitive is a CLAIM?
- 1 = Immediate ("The stock crashed today")
- 5 = Timeless ("Supply and demand determine price")

**This is NOT a timestamp!** It's metadata about whether a claim will age well.

**Where it comes from:** The evaluator assigns this when ranking claims

**What I did in Fix 5:** Made it visible in markdown output

**Example:**
```markdown
### The Fed raised rates by 25bp yesterday
Type: factual | Tier: A | Temporality: Immediate (confidence: 0.92)
```

This tells you the claim is tied to a specific date and will become outdated quickly.

---

## Summary

### Question 1: Did I do the original task?

**No - I found it was "partially working" but didn't realize we were losing data.**

The fix is now complete:
- ✅ 3 new evidence tables created
- ✅ Storage logic updated to save ALL mentions
- ✅ No data loss

### Question 2: What is the "temporality" functionality?

**A separate feature** that was already in the code but not displayed in markdown.

It classifies claims as Immediate/Timeless (a 1-5 scale), NOT timestamps like "00:03:45".

**These are unrelated:**
- **Timestamps** (00:03:45) = WHEN something was said
- **Temporality** (Medium-term) = HOW time-sensitive the claim is

---

**Status:** Both features now implemented correctly! ✅

