# Session memory — an INBOX, not a second rulebook

This directory is Claude Code's per-project memory. It is a **symlink target**:
`~/.claude/projects/-Users-matthewgreer-Projects-Knowledge-Chipper/memory` points here, so anything a session writes to
memory lands **inside this repo** and travels with it.

## Why it is in the repo

Memory used to live only under `~/.claude/`, which is synced by nothing. A lesson learned on
one machine was invisible on another, so the same mistake could be repeated after simply
switching machines. Committing the inbox fixes that — but it introduces the risk that doc
discipline exists to prevent, so the contract below is not optional.

## The contract

**This directory is an inbox. It is not a source of truth, and nothing here is authoritative.**

- **The repo's own docs win, always.** `CLAUDE.md`, the project's lessons/postmortems file,
  and `GAMEPLAN.md` outrank anything here. If a note contradicts them, the doc is correct and
  the note is stale. Never resolve a conflict in memory's favour, and never cite a memory file
  as justification for a change.
- **Entries are promoted, then deleted.** A durable, repo-relevant fact belongs in the repo
  proper: rules and concepts to `CLAUDE.md`, incident narratives to the lessons file, roadmap
  and status to `GAMEPLAN.md`. Once promoted, **delete the memory file** — a promoted entry
  left here becomes a second copy that drifts.
- **`/wrap-up` owns the promotion pass.** Draining this directory is part of closing out a
  session, not a someday task.
- **Cross-project preferences do not belong here.** Anything about how to work in general
  (response length, tone, verification habits) goes in the **global** repo
  (`msg43/claude-config` → `~/.claude/CLAUDE.md`), which reaches every machine *and* every
  project. A preference filed here reaches exactly one repo, which is the wrong scope. If you
  find one here, promote it up and delete it.

## Before you commit anything in here

These files are written by an agent mid-session and are **not reviewed**. Read what you are
committing. Nothing that would not survive being public belongs in a tracked file: no
credentials, tokens, customer data, or personal detail about anyone — and that holds even in a
private repo, because repos change visibility and get cloned. If a note needs such context to
make sense, promote the general lesson and drop the specifics.

## Setting up the symlink on another machine

The memory path is keyed off the project's absolute path, so it is per-machine:

```bash
rm -rf ~/.claude/projects/-Users-matthewgreer-Projects-Knowledge-Chipper/memory && ln -s /Users/matthewgreer/Projects/Knowledge_Chipper/.claude/memory ~/.claude/projects/-Users-matthewgreer-Projects-Knowledge-Chipper/memory
```

If the project lives at a different path on that machine, the `-Users-matthewgreer-Projects-Knowledge-Chipper` portion changes
to match — check `ls ~/.claude/projects/` for the right directory name, and create it if the
project has not been opened there yet.
