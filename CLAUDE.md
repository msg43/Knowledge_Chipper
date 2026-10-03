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
