---
id: "KC-delete-duplicate-cursor-summarize-branch"
display_number: "6.6"
legacy_page_id: "6.6"
project: "hygiene"
kind: "quick"
status: "closed"
time: "2 min"
due: null
urgent: false
due_note: null
order: 64
flag: null
added: null          # not recorded (the page has no added date)
updated: "2026-11-23"
verified_on: "2026-11-23"
verified_by: "agent:checklist-sync-2026-11-23"
verified_result: "current"
verified_against: {"KC": {"local": "8623ca78", "remote": "8623ca78"}}
owner_repo: "KC"
home_repo: "KC"
cross_repo: []
sensitive: false
depends_on: []
see_also: []
split_from: null
steps_from: "steps"
closed_note: "Done 26 Oct"
closed_evidence:
  - "Checked 2026-11-23: git branch --list 'cursor/*' prints nothing, so no local copy of the duplicate branch remains."
  - "Backup bundle in the owner's 2026-10-26 backup folder, re-verified 2026-11-23 with git bundle verify: 'The bundle records a complete history' (kept outside this repo)."
  - "GitHub copy left in place: refs/heads/cursor/summarize-large-documents-beyond-context-window-fabe at e60b5b6e, 21 commits not in main (git rev-list --count origin/main..origin/<branch>), as the closing reply says."
  - ".gitattributes (9 lines) is on main at 8623ca78."
closed_by: "migration"
---

# Duplicate Knowledge_Chipper branch deleted, with a backup

> Closed card. The Why and What-you-do text below is the wording from before it closed and may no longer be true; the outcome is in the Closure section.

## Why

Local and remote `cursor/summarize-large-documents-…` differ only by a rewritten root commit and an 8-line `.gitattributes` that the remote lacks.

## What you do

1. Approve keeping the remote and re-adding `.gitattributes`. Nothing else is lost.

## Source

gttp/docs/Human-Master-Checklist.md, item 6.6

## Closure

Done 26 Oct

Claude's closing reply (round 1, 2026-10-27):

Already done on Oct 26. The duplicate local branch held nothing main lacked, so it was deleted after a checked backup copy was made. The GitHub copy was left alone. Nothing left for you.

Evidence re-read on 2026-11-23 (agent:checklist-sync-2026-11-23, against KC 8623ca78):

- No local `cursor/*` branch exists.
- The backup bundle in the 2026-10-26 backup folder verifies as a complete history.
- The GitHub copy still exists, 21 commits ahead of main.
- `.gitattributes` (9 lines) is on main.
