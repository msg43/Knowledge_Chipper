# GAMEPLAN

The only status document for this repo. Edit in place. Cold start: this file, then CLAUDE.md, then the top ~100 lines of CHANGELOG.md.

## Current status (23 Nov 2026)

Knowledge_Chipper (Skipthepodcast.com) is a macOS background daemon (`daemon/`) that turns videos, audio and documents into claims uploaded to GetReceipts.org (MANIFEST.md:13). The PyQt6 desktop app is deprecated; the daemon is the only product (DESKTOP_APP_DEPRECATION.md, 2026-01-11).

State: parked [inferred, owner to confirm]. The last commit that touched `src`, `daemon`, `scripts` or `pyproject.toml` is 0bb3de8 (2026-01-18); every later commit is docs or checklist cards. No daemon LaunchAgent is loaded (checked 2026-11-23 with `launchctl list`).

Version 4.1.0 (pyproject.toml:7). yt-dlp is pinned at 2025.11.12 and needs the Deno runtime (pyproject.toml:52).

## Strategy and constraints

- Claims are the primary record; the database is the source of truth and files are regenerated from it (CLAUDE.md).
- No graceful fallbacks without asking the owner (CLAUDE.md).
- The version lives only in `pyproject.toml` (CLAUDE.md).
- Proxy providers: the config no longer loads WebShare settings; the default preferred provider is PacketStream and Bright Data is also supported (`src/knowledge_system/config.py:1312`, `:1475`).
- Pitfall: run `gitleaks git` before any push; never commit a settings file.

## Owner to-dos

- Confirm that this project is parked.
- Other owner items are tracked in the owner's private checklist.

## Decisions taken

- 2026-01-11 Desktop GUI deprecated, daemon only (DESKTOP_APP_DEPRECATION.md).
- 2026-01-11 Legacy HCE (Hybrid Claim Extraction), diarization and model bundling removed from the build (CHANGELOG.md, entry "Removed Legacy HCE, Diarization, and Model Bundling (January 11, 2026)", line 562 on 2026-11-23).
- 2026-10-26 Duplicate local branch `cursor/summarize-large-documents-beyond-context-window-fabe` deleted after a verified bundle backup; the GitHub copy was left (`docs/human-cards/KC-delete-duplicate-cursor-summarize-branch.md`).

## Where to look

Code map: MANIFEST.md. History: CHANGELOG.md. Checklist cards for this repo: `docs/human-cards/`. Root files named `*_COMPLETE.md`, `*_STATUS.md`, `*_FIX*.md` and `ACTIVE_TODOS.md` are history, not status.
