# Decisions

Every decision that shapes this project, newest first. Each entry is
written in the same change the decision is made, and its full text lives
only here. `GAMEPLAN.md` keeps a one-line pointer to an entry while the
decision still shapes current work.

This file is never trimmed. A reversed decision keeps its entry and gains
a line naming the later one ("Reversed YYYY-MM-DD: see the <title> entry").
Read the top and grep the rest; search here before reopening a settled
question.

Entry format:

```
## YYYY-MM-DD: <the decision, stated as a fact>

- **Decided by:** <person>
- **Why:** <the reason, in a sentence or two>
- **What was built:** <commit, file or "not built yet">
```

## 2026-11-26: decisions are recorded in this file

- **Decided by:** Matthew Greer
- **Why:** a restarted session reads the decision and its reason here
  instead of re-arguing it; keeping decisions inside `GAMEPLAN.md` made
  that file too long to read first.
- **What was built:** this file, from `~/.claude/templates/repo-protocol/`.
