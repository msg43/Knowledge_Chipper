# Lessons — the full stories behind CLAUDE.md's rules

**Class: Living** (operational guide). Edited in place; appended to when a new incident
yields a durable rule.

## What this file is for

[`CLAUDE.md`](../CLAUDE.md) is loaded into **every agent request**, so it holds the *rule* —
one to three lines, stated as an instruction. This file holds the *evidence*: the measured
numbers, the commit hashes, the detection tells, and the reasoning that made each rule worth
writing.

**Read a section here when you are about to touch the thing it describes**, when a rule in
CLAUDE.md seems wrong or inconvenient and you want to know what it cost to learn, or when you
are debugging something in the same family. Do not read it end-to-end on cold start — that is
what CLAUDE.md is for.

**When you add a rule to CLAUDE.md, add its story here in the same commit.** The rule without
the evidence gets argued away by the next session; the evidence without the rule never gets
read. A pre-commit check warns when CLAUDE.md grows without this file being staged alongside.

## Why the split exists

CLAUDE.md is a per-turn tax on every session, and incident write-ups are what make it grow.
Two repos here have run this experiment: both split their rulebook from its evidence, and both
watched the rulebook grow straight back — one went 87,097 → 44,672 bytes and was at 67,953
sixteen days later, because every new gotcha was appended to the rules instead of here.
Nothing measured it, so nothing objected. That is why the split ships with a size ratchet
rather than as a one-time cleanup.

## Conventions

- One `##` section per incident, with an explicit anchor: `## Title {#short-anchor}`.
  CLAUDE.md links to it as `→ [postmortem](docs/LESSONS.md#short-anchor)`. A pre-commit check
  warns when a link here resolves to nothing — a dead anchor strands the evidence and leaves a
  rule whose justification is unreachable.
- Open each section with **Rule in CLAUDE.md:** and a one-line restatement, so the section
  stands alone.
- Keep the numbers. The measured value, the date, the commit hash and the detection tell are
  the whole point — they are what makes the rule arguable-with rather than folklore.
- End with a **detection tell** where one exists: the cheapest signal that this class of
  problem is happening again.

---

## Contents

<!-- Add a line per section as you write them; group under headers once there are enough. -->

---

<!--
Template for a new entry:

## Short title naming the mechanism {#anchor-name}

**Rule in CLAUDE.md:** one line.

**YYYY-MM-DD.** What happened, with the measured numbers. What it looked like from the
outside, and why the obvious reading was wrong.

**Transferable rules:**

- The generalisable lesson, stated so it applies beyond this incident.

Detection tell: the cheapest signal that this is happening again.
-->
