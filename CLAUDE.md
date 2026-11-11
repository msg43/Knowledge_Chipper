# Knowledge_Chipper

Skipthepodcast.com (formerly Knowledge_Chipper) is a macOS PyQt6 desktop app that turns videos, audio and documents into a searchable database of claims. The CLI was removed; the GUI is the only interface. Commands are in the Makefile (`make help`).

## Constraints

- **Claims are the primary record.** Write "claims attributed to a source", never "a source contains claims". Queries start from `claims` and JOIN `media_sources` for context. Details: `.cursor/rules/claim-centric-architecture.mdc`.
- **The database is the source of truth, not files.** Output files are regenerated from it. Look up metadata in the database, never by parsing filenames.
- **No graceful fallbacks.** Before adding a fallback or suppressing a warning, ask the owner. Fix the root cause instead of masking it. (`.cursor/rules/no-graceful-fallback.mdc` has no body, so this line is the only copy of the rule.)
- **The version lives only in `pyproject.toml`.** Bump it before significant changes with `python3 scripts/bump_version.py --part patch|minor|major`, then run `bash scripts/update_build_date.sh` to sync README.md.
- **yt-dlp is pinned in `pyproject.toml`**, and the pinned version needs the Deno runtime (bundled into the DMG by `scripts/silent_deno_installer.py`). Change the pin only by following `docs/YT_DLP_UPGRADE_PROCEDURE.md`.
- The other Cursor rules in `.cursor/rules/` are not loaded automatically. Read the relevant one before touching that area, for example `hce-workflow.mdc` for the legacy-to-HCE (Hybrid Claim Extraction) cut-over.

## Gotchas

- Claim extraction uses JSON mode rather than grammar-enforced output, chosen for speed. A post-validation step repairs common omissions such as the `domain` field.
- The code uses two data directories. The main database lives in `~/Library/Application Support/Knowledge Chipper/` (`database/service.py` resolves it through `utils/macos_paths.py`). `~/Library/Application Support/SkipThePodcast/` is a second directory: `entity_sync.py` and `feedback_processor.py` default to a `knowledge_system.db` there, and `device_auth.py` keeps its config there. Check which one a code path uses before assuming they are the same database.
- Tests may fail when optional dependencies are missing: `pyannote.audio`, `soundfile`, and a local Ollama for the integration tests. `pytest -m "not integration"` skips the Ollama ones.

# GAMEPLAN.md is the cold-start file

A new session should get the project's direction from `GAMEPLAN.md` for a few thousand tokens, instead of carrying the history in a long conversation. That only works if the file is short, keeps everything that still shapes future work, and is updated on a schedule.

**What goes in it** (about 200 lines in all, roughly 6K tokens)
- The goal, and the current state in a few lines.
- **Strategy and constraints:** the approach and why it was chosen, the rules that must not be broken, and the known pitfalls. This section is required.
- What is in progress, the next three steps, and decisions still open (each with its owner).
- Decisions taken, each with its reason and date, so a restarted session does not re-argue them.
- Where to look for detail (code map, changelog, archive sections by heading and line).

**Keep or archive test:** if something still shapes future work (a strategy, a constraint, a decision's reason, an unresolved item, a pitfall that could recur), it stays in `GAMEPLAN.md`. Only finished work, evidence and superseded material move to `CHANGELOG.md` or `docs/archive/`, and the opening section links to it. When in doubt, keep the one-line version and link the detail.

**When to update it**
- When a task finishes, a decision is made, or a blocker appears, in the same change.
- Before a session ends, and before a restart or compaction. Write the handoff first: what is done, what is not, and what waits on Matthew.
- When the context advisory fires (400K tokens), as a checkpoint.
- Resolved items leave in the same update, so the file does not grow.

**Size check:** if the file is past about 200 lines or 30K tokens, archive per the test above before doing anything else. Each time you archive, read what you removed once and confirm nothing that still shapes future work went with it.

# Keep sessions cheap to start and to run

Every turn re-reads the whole conversation, so a session that starts small and stays small costs far less.

- **Start from `GAMEPLAN.md`.** Read it first; its opening section is written to be enough to begin work. Read only the top of `CHANGELOG.md` (newest entries come first, so about the first 100 lines). Use grep to find older entries. Never read a whole changelog or an archive file; read the line range you need.
- **Changelog entries are short.** About five lines each: what changed, why, and where to look. Detail belongs in the commit message or the pull request. The changelog is append-only history and is never trimmed or archived: its size costs nothing as long as sessions read only the top and grep for the rest. Use `grep -m` or a few lines of context so a search returns a short result.
- **Grep before reading.** Search for the name, then read only the lines around it. Send a large file, log or batch of sessions to a small helper agent that returns a short answer, as the helper-agent rule describes.
- **Restart before the context gets heavy.** At about 400K tokens, update `GAMEPLAN.md` with the handoff (done, not done, waiting on Matthew) and continue in a fresh session, as your global instructions describe.

# Recovering something deleted from GAMEPLAN.md

Git keeps every version of `GAMEPLAN.md`, so do not save dated copies. To find a strategy, constraint, decision or to-do that went missing:

- Find when a phrase left the file: `git log -S"some phrase" --oneline -- GAMEPLAN.md`. The newest commit listed is usually the one that removed it.
- Read the file as it was then: `git show <commit>:GAMEPLAN.md`, or see exactly what a commit removed: `git show <commit> -- GAMEPLAN.md`.
- Sweep for anything lost: list the lines each commit removed with `git log -p --format="== %h %ad %s" --date=short -- GAMEPLAN.md`, then check each removed line against the keep-or-archive test in this file and restore what is still live. Sweep by time window (for example one month per helper agent) and write findings to a file, as the helper-agent rule describes.

