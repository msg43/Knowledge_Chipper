# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [3.5.3] - 2025-11-11

### Fixed
- **Summarize Tab Database Row Selection UX**: Fixed unintuitive checkbox selection behavior in the Summarize tab's database browser. Previously, users had to click directly on the tiny checkbox widget to select a transcript for summarization. Now clicking anywhere on a row (title, duration, etc.) toggles the checkbox, making selection much more intuitive. Added debug logging to track checkbox state changes and source selection for easier troubleshooting.

### Enhanced
- **Seamless Transcription-to-Summarization Workflow**: When clicking "Summarize Transcript" after transcription, the Summarization tab now automatically: (1) switches to Database mode (not Files), (2) refreshes and checks the boxes for all transcribed sources, and (3) immediately starts summarization without further user input. This provides a streamlined workflow consistent with the database-first architecture, where the rich database segments (with timestamps, speakers, metadata) are used as input instead of parsing markdown files. The system extracts `source_id` from transcription metadata and uses it to locate and select the corresponding database records.
- **Cookie File Persistence Diagnostics**: Added comprehensive logging throughout the cookie file loading and saving pipeline to diagnose persistence issues. System now logs: (1) full paths of cookie files being loaded from session, (2) verification that cookie_manager widget is initialized before loading, (3) signal disconnect/reconnect operations, (4) verification that files were actually set in the UI after loading, (5) detection of mismatches between expected and loaded file counts. Also logs all save operations with confirmation of successful writes to session. This enables rapid diagnosis of any cookie persistence failures by showing exactly where in the chain the issue occurs. See `COOKIE_PERSISTENCE_DIAGNOSIS_2025_11_10.md` for complete diagnostic guide.

### Changed
- **Summary Data Now Appended to Transcript Files**: Major architectural change - summary data (claims, people, concepts) is now appended to the existing transcript markdown file instead of creating a separate summary file. After summarization completes, the system finds the transcript file and appends: (1) Summary section with generated summary text, (2) Claims section organized by tier (A/B/C) with importance scores, (3) People section with descriptions, (4) Concepts section with definitions. This creates a single comprehensive markdown file per video with transcript + analysis, eliminating confusion about where files are located. The transcript file already contains thumbnail, YouTube description, and full transcript, making it the complete reference document.

### Fixed
- **Summary Markdown Template Bug**: Fixed critical bug in `FileGenerationService.generate_summary_markdown()` where non-HCE summaries were generated with literal template code instead of actual values. The template string was missing the `f` prefix, causing output like `{video.title}` instead of the actual video title. This affected legacy (non-HCE) summaries that fall back to the simple format when `hce_data_json` is not available. Now properly formats all summary markdown files with actual video metadata, model information, and summary text.
- **Claims Not Appearing in Summary Files**: Fixed issue where claims were stored in the database but not appearing in generated summary files. Root cause: The summary record's `hce_data_json` field was None, causing the file generator to fall back to legacy format. New `append_summary_to_transcript()` method reads claims directly from the database tables (claims, people, concepts) via proper joins, ensuring all extracted data appears in the output regardless of how it was stored.
- **CRITICAL: Transcribed YouTube Videos Not Appearing in Summarize Tab**: Fixed critical bug where transcribed YouTube videos didn't appear in the Summarize tab's database browser. Root cause: AudioProcessor was generating a NEW source_id (e.g., `audio_filename_hash123`) for every transcription instead of using the existing source_id from the YouTube download. This created orphaned Transcript records that weren't linked to any MediaSource record. The Summarize tab's query requires BOTH a MediaSource AND a Transcript with matching source_ids. Solution: AudioProcessor now checks for `source_metadata` in kwargs and uses the existing `source_id` before generating a new one. This ensures YouTube transcripts are properly linked to their MediaSource records and appear in the Summarize tab.
- **Transcription Format Parameter Not Respected**: Fixed critical bug where the audio processor ignored the `format` parameter from the GUI, causing markdown files to not be created even when format was set to "md". The code was checking `if output_dir:` but not checking `if output_dir and format != "none":` as documented in `FORMAT_NONE_OPTION.md`. Added proper format parameter extraction and conditional file writing logic. When format is "none", the system now logs "Output format set to 'none' - skipping file creation, will save to database only" and correctly skips file creation while still saving to the database.
- **Voice Fingerprinting Not Merging Single-Speaker Monologues**: Fixed critical bug where voice fingerprinting received the wrong audio file path (original input file instead of converted 16kHz mono WAV), preventing proper speaker merging. The system was passing `path` (original MP4/M4A) instead of `output_path` (converted WAV used for diarization) to `prepare_speaker_data()`. This caused voice fingerprinting to fail audio segment extraction, resulting in single-speaker content being incorrectly split into 2+ speakers. Now correctly passes the converted WAV file path, enabling proper voice similarity analysis and speaker merging.

### Enhanced
- **Voice Fingerprinting Diagnostic Logging**: Added comprehensive diagnostic logging to identify why voice fingerprinting fails to merge speakers. System now logs: (1) which features were successfully extracted vs. empty (mfcc, spectral, prosodic, wav2vec2, ecapa), (2) per-feature similarity scores and which features are available/missing during comparison, (3) total weight used in similarity calculation (should be 1.0 if all features available), (4) actual similarity scores between all speaker pairs with merge decision reasoning, (5) audio file format verification (confirms 16kHz mono WAV is being used, not original MP4/M4A), (6) CSV database loading and lookup (confirms channel_hosts.csv is found, loaded with ~524 entries, and host names are successfully matched). This enables rapid diagnosis of issues like missing deep learning models (wav2vec2/ecapa not loading), audio extraction failures, wrong audio format being passed, CSV not being invoked, or threshold problems. See `VOICE_FINGERPRINTING_DIAGNOSIS_NOV_2025.md` for complete diagnostic guide.
- **Summarize Tab Database List Not Refreshing**: Fixed issue where newly transcribed YouTube URLs didn't appear in the Summarize tab's database browser. Added automatic refresh when the Summarize tab becomes visible and the database view is active. Also added diagnostic logging to detect transcripts without corresponding MediaSource records (orphaned transcripts).
- **Missing Summary Markdown Files & Schema Migration Completion**: Fixed critical issue where summarization reported success but no `.md` file was generated. Root cause: The unified pipeline was storing data to the `episodes` table but never creating the required `Summary` record in the `summaries` table. Added call to `_create_summary_from_pipeline_outputs()` to create the Summary record before attempting markdown generation. Also completed the incomplete migration to claim-centric schema by fixing all remaining references to old schema: (1) Changed `video_id` to `source_id` in 3 Summary instantiations in `system2_orchestrator.py`, (2) Changed `get_video()` to `get_source()` in 6 locations across `file_generation.py` and `speaker_processor.py`. This completes the architectural migration from episode-centric to claim-centric schema and ensures `generate_summary_markdown()` can find the data it needs to create properly formatted summary files.

### Removed
- **Duplicate Summary Generation Code Path**: Removed `generate_summary_markdown_from_pipeline()` method which was creating inconsistent markdown formats. The unified pipeline now uses the standard `generate_summary_markdown()` method that reads from database and uses `_generate_hce_markdown()` for consistent formatting. This eliminates code duplication and ensures ONE format for all HCE summaries, following the painstakingly laid out format specifications.

### Changed
- **Robust LLM Fallback System**: Enhanced MVP LLM detection to use ANY available Ollama model if preferred models aren't found. Priority order: (1) Preferred models (qwen2.5:7b, etc.), (2) Any Qwen model, (3) Any Llama model, (4) Any instruct model, (5) Any available model. This ensures speaker attribution never fails when Ollama has models installed, even if they're not the bundled defaults. System logs which fallback tier is used and warns if quality may be reduced.
- **Transcript Markdown Formatting Optimization**: Improved paragraph breaking for better readability. Reduced max paragraph length from 900 to 500 characters and pause threshold from 7s to 3s for more natural breaks. Paragraphs now break more aggressively on sentence boundaries and pauses, making transcripts easier to scan and read. Force break threshold reduced from 1200 to 700 characters.
- **YouTube Description Header**: Changed "Description" header to "YouTube Description" specifically for YouTube videos, making the source of the description clearer in markdown files.
- **Transcript Markdown Filename**: Removed "_transcript" suffix from markdown filenames for cleaner file naming (e.g., "Trump exploits antisemitism.md" instead of "Trump exploits antisemitism_transcript.md").
- **Transcript Markdown Formatting**: Completely redesigned human-readable transcript formatting with intelligent paragraph grouping. Segments are now grouped into logical paragraphs based on speaker changes, long pauses, sentence boundaries, and character limits. Speaker names and timestamps appear on a header line (`**Speaker** [00:00]`) followed by paragraph text, with blank lines between paragraphs for improved readability. The system automatically adapts to monologues (showing speaker label once at start, then only timestamps) vs dialogues (showing speaker label on every speaker change), eliminating redundant labels while maintaining clarity. This applies to both database-generated markdown files and direct transcription output.
- **Summarization Debugging Enhancements**: Added comprehensive diagnostic logging throughout the unified mining pipeline to track progress and identify hangs. Mining phase now reports progress at INFO level when 3% change OR 10 seconds elapsed (whichever comes first), with all segments logged at DEBUG level. Parallel processor logs initial batch submission, task completions, and active task counts. All errors now include full tracebacks at debug level. This addresses cases where summarization hung at 35% without clear error reporting.

### Removed
- **Deprecated Old HCE Extractors**: Moved pre-unified-pipeline extraction modules to `_deprecated/hce_old_extractors/`: `people.py`, `glossary.py`, `concepts.py`, `skim.py`. These standalone extractors were replaced by the unified pipeline in October 2025, which extracts all entity types in a single pass (70% fewer LLM calls, 3-8x faster). Also moved 12 unused prompt files from the old two-tier evaluation system and standalone detection architecture. See `VESTIGIAL_CODE_ANALYSIS.md` for full details.

### Fixed
- **Flagship Evaluator Model Dropdown Empty on Launch**: Fixed critical bug where the "Flagship Evaluator Model" dropdown appeared empty on first launch despite default models being configured. Root cause: When no provider was saved in session state (e.g., first launch), `_load_settings()` would get an empty string from `get_combo_selection()`, fail the `if saved_provider:` check, and never call `_update_advanced_model_combo()` to populate models. Solution: Default to "local" provider when no provider is saved, ensuring model combo is always populated. This fix applies to all advanced model dropdowns (Unified Miner Model, Flagship Evaluator Model) in the Summarization tab. See `FLAGSHIP_EVALUATOR_MODEL_DEFAULT_FIX.md` for complete analysis of the two-bug compound issue (empty provider handling + model name suffix mismatch).
- **Speaker Attribution Model Name Mismatch**: Fixed critical issue where speaker attribution failed even when Qwen model was bundled and installed. Root cause: installation scripts pulled `"qwen2.5:7b"` but code expected `"qwen2.5:7b-instruct"` (Ollama strips the `-instruct` suffix when storing models). Updated MVP_MODEL_ALTERNATIVES to match actual Ollama model names: `["qwen2.5:7b", "qwen2.5:14b", "qwen2.5:3b", ...]`. This ensures the bundled LLM is properly detected and used for speaker attribution with the 262-podcast CSV mapping database, providing real speaker names instead of generic SPEAKER_01 labels.
- **CRITICAL: Flagship Evaluator Scoring Scale Inconsistency**: Fixed a critical bug in the flagship evaluator prompt that caused all claims to be scored as low-quality (tier C). The prompt had conflicting instructions: sections 25-47 instructed scoring on a 0.0-1.0 scale, while sections 66-88 specified a 1-10 scale. This caused the LLM to return scores like 0.8 (meaning 80% on a 0-1 scale) which were interpreted as 0.8/10 (8% on a 1-10 scale), resulting in importance scores below 5 and tier C assignment. All three scoring dimensions (importance, novelty, confidence) now consistently use the 1-10 scale throughout the prompt. This fix restores proper claim quality assessment where high-quality claims (importance >= 8) are correctly identified as tier A.
- **Vestigial Relations and Contradictions Statistics**: Removed misleading "Relations mapped" and "Contradictions detected" statistics from the summarization output. These features were never implemented in the unified pipeline (which explicitly returns empty arrays for relations and contradictions), but the GUI was still displaying them as if they were functional. This created confusion when they suddenly appeared showing "0" values. The RelationMiner class exists but is disabled, and the unified pipeline comments indicate "Relations not implemented in unified pipeline yet". Cleaned up all UI code that referenced these unimplemented features to avoid false expectations.
- **Logger Variable Shadowing in Unified Miner**: Fixed `cannot access local variable 'logger'` error caused by redundant logger re-assignments within exception handlers that shadowed the module-level logger. Removed all `import logging; logger = logging.getLogger(__name__)` statements within functions and consistently use the module-level logger throughout.
- **QueueTab AttributeError**: Fixed `AttributeError: 'QueueTab' object has no attribute 'log_error'` by replacing all `self.log_error()` calls with the correct `self.append_log()` method from BaseTab. Added error emoji (❌) prefix to error messages for consistency with other tabs.
- **Summarization Progress Reporting Frequency**: Fixed progress reporting throttling to match specification of every 5% or 10 seconds (whichever comes first). Previously was reporting every 10% or 30 seconds, resulting in less frequent status updates during long summarization operations. Now provides more responsive feedback in both the console log and chunk processing displays.
- **Transcript Markdown Display**: Removed redundant H1 heading from transcript markdown files since Obsidian and similar markdown viewers automatically display the YAML frontmatter `title` field as the document heading. This eliminates duplicate titles in the UI.
- **Transcript Markdown Filename Spaces**: Changed transcript filenames to preserve spaces instead of converting to underscores (e.g., `Will Japan and South Korea Gang Up on China Peter Zeihan_transcript.md` instead of `Will_Japan_and_South_Korea_Gang_Up_on_China_Peter_Zeihan_transcript.md`). This provides more natural display in file browsers and Obsidian's file tree.
- **Transcript Markdown Filename Generation**: Fixed transcript filenames to use clean video titles instead of including video IDs. Filenames are now human-readable (e.g., `Why_Im_Bullish_on_Southeast_Asia_Peter_Zeihan_transcript.md` instead of `Why_Im_Bullish_on_Southeast_Asia__Peter_Zeihan_gYnAgWRcZPM_transcript.md`).
- **Description Preview Truncation**: Fixed a bug where the first character of video descriptions was being removed in the YAML frontmatter `description_preview` field. The `.rstrip()` operation after slicing was incorrectly stripping leading characters.
- **Mining Fallback Warning Context**: Improved logging to distinguish between DB-centric processing (where missing segments is unexpected) and file-centric processing (where parsing markdown is expected). The warning "⚠️ No DB segments found" now only appears when processing from database, not when explicitly processing standalone markdown files.
- **Speaker Attribution Incomplete Assignment**: Enhanced error logging in LLM speaker suggester to diagnose cases where diarization detects multiple speakers but LLM only provides names for some. Added critical error messages showing which speakers were missed and emergency fallback names. This addresses cases where transcripts showed "SPEAKER_01" instead of real names despite the multi-layered speaker attribution system.
- **Thumbnail Absolute Paths**: Changed thumbnail image references in markdown transcripts from absolute paths to relative paths (e.g., `downloads/youtube/Thumbnails/filename.jpg`). This ensures thumbnails display correctly when files are moved, shared, or viewed in different markdown editors like Obsidian.
- **Single-Speaker Over-Segmentation Diagnostics**: Added comprehensive logging to track speaker merging through all three defensive layers (voice fingerprinting, heuristic detection, LLM analysis). System now logs when diarization over-segments single-speaker content (monologues, solo podcasts) and whether each layer successfully merges or correctly assigns the same name to all speaker IDs. Makes it immediately obvious which layer is failing when single-speaker videos incorrectly show multiple speaker labels.
- **Speaker Assignment System Not Invoked**: Added critical diagnostic logging to detect when the entire speaker attribution system is bypassed. Logs now show whether the speaker assignment block is reached, and if not, displays the exact condition flags (`diarization_successful`, `diarization_segments`) that prevented it from running. This diagnoses cases where speaker attribution fails not because of a bug in the system, but because the system never runs at all.
- **Markdown Transcript Segment Parsing**: Fixed `_parse_transcript_to_segments()` to correctly parse speaker-attributed markdown transcripts with `[MM:SS] (Speaker Name): text` format. The system now preserves all speaker segments instead of re-chunking by tokens, fixing the issue where 6 speaker segments were incorrectly reported as 3 segments.
- **Short Summary Generation Type Error**: Fixed `'dict' object has no attribute 'strip'` error in `_generate_short_summary()` by adding robust type checking for nested dictionary responses from LLM. The code now handles cases where `response.get("summary")` returns another dict instead of a string.
- **Archive Skip Logging Clarity**: Improved logging when yt-dlp skips videos already in the download archive. Changed misleading WARNING message to DEBUG level and clarified that returning None is expected behavior when videos are already downloaded. The system now clearly indicates when it's reusing existing files from the archive vs encountering actual download errors.

## [3.5.2] - 2025-11-08

### Added
- **Claim Domain Classification**: Added `domain` field to claims table and schema for broad field classification (e.g., "physics", "economics", "politics"). Claims can now be filtered and searched by domain alongside jargon terms.
- **Domain Column Migration Script**: Created `scripts/add_domain_column_to_claims.py` to add the missing `domain` column to existing databases.

### Changed
- **Domain Guidance in Miner Prompts**: Updated all 7 miner prompts to guide LLMs toward broad, searchable domain categories. Prompts now explicitly instruct to use general fields like "physics" not "quantum mechanics", "economics" not "monetary policy", ensuring consistent categorization for filtering.
- **Open-Ended Domain Classification**: Both claims and jargon use free-form domain strings (no enum restrictions), allowing natural categorization while prompt guidance ensures broad, searchable categories.
- **Transcription Progress Reporting Frequency**: Reduced the progress update threshold from 5% to 2% increments in whisper_cpp_transcribe.py, providing more frequent visual feedback during long transcription operations.

### Fixed
- **Queue Tab Initialization Error**: Fixed `AttributeError` where `_last_refresh_interval` was accessed before initialization, causing crashes when filters changed during startup.
- **Review Tab Database Error**: Fixed `OperationalError` caused by missing `domain` column in claims table. Added migration to system2_migration.py and standalone migration script for existing databases.
- **Summarization Tab Model Selection**: Improved model combo default selection logic to automatically select the first available model when no previous selection exists, and made warning messages more informative to distinguish between "no models available" vs "models available but none selected".
- **Schema Validation for Missing Claim Domains**: Added repair logic to automatically set `domain = "general"` for claims when LLMs fail to include the required domain field, preventing validation failures and fallback to non-structured JSON generation.
- **Stage Status Race Condition**: Fixed `IntegrityError` in `upsert_stage_status()` caused by concurrent transactions attempting to insert the same stage status record. The method now catches the integrity error and retries with an update operation, properly handling the race condition.

## [3.5.1] - 2025-11-05

### Added
- **Queue Tab**: New tab to visualize real-time pipeline status for all processing stages (download, transcription, summarization). Users can monitor progress, filter by stage/status, and view throughput metrics.
- **Advanced GUI Testing Suite**: Comprehensive GUI testing with pytest-qt and pytest-timeout to simulate real user interactions, test async operations, and debug UI failures interactively.

### Changed
- **Schema Consolidation**: Deleted `miner_output.v2.json` as it was redundant. The v1 file now contains the v2 structure (nested `evidence_spans`, `definition` field) and is what the validator actually uses. This eliminates confusion between file naming and content structure.
- **Queue Tab Default Filter**: The Queue tab now defaults to "Active Only" filter, automatically hiding completed and failed items for a cleaner view.
- **Removed Jargon Domain Enum Constraint**: Changed jargon `domain` field from restricted enum to free-form string, allowing LLM to naturally describe specialized fields (e.g., "quantum mechanics", "constitutional law") rather than forcing into predefined categories.

### Fixed
- **Schema Validation Errors**: Fixed `context_type` enum mismatch in `miner_output.v1.json` (was `["exact", "sentence", "paragraph"]`, now correctly `["exact", "extended", "segment"]` to match database schema). Removed restrictive `domain` enum constraint to allow LLM to freely describe jargon domains without artificial categorization limits.
- **Queue Tab View Details Dialog**: Fixed JSON parsing error that caused empty popup when viewing queue item details. The `metadata_json` field is now correctly handled as a pre-deserialized dictionary.
- **Queue Tab File Links**: Added clickable hyperlinks to completed markdown files in the Actions column. Double-clicking a completed item now opens the summary file directly in the default markdown editor.
- **Queue Tab Failed Items**: Added "Active Only" filter option to automatically hide completed and failed items, keeping the queue view focused on in-progress work.
- **Queue Tab Failure Tracking**: Fixed summarization failures not updating queue status in real-time. The queue now immediately reflects failed status when summarization encounters errors, preventing items from appearing stuck "in progress".
- **YouTube Archive Reuse**: Retranscription runs can now reuse previously downloaded audio when yt-dlp skips via its archive, preventing overwrite workflow failures. A user confirmation dialog has been added.
- **Thumbnail Embedding**: Thumbnails are now correctly embedded in markdown files by ensuring the database is updated *after* the thumbnail is downloaded.
- **Transcription Model Default**: The transcription model now correctly defaults to "medium" instead of "tiny", ensuring better quality out-of-the-box.
- **Vestigial UI Elements**: Removed a non-functional "Prompt File" picker from the Summarization tab to reduce user confusion.
- **UI Layout**: Improved the layout of the Transcription tab by repositioning the Proxy selector for a better visual flow.
- **Startup Validation Noise**: Reduced false-positive warnings during startup validation by intelligently filtering out test files and old entries.
- **YAML Corruption with Color-Coded Transcripts**: Disabled the color-coded transcript feature that was breaking YAML frontmatter parsing. Speaker assignments now work correctly without this feature.
- **Archive Validation Edge Case**: Added validation to remove invalid yt-dlp archive entries (e.g., from failed downloads) to prevent videos from being permanently skipped.
- **Transcription Pipeline Errors**: Fixed a blocking `NameError` on `Segment` import and 10 other issues related to database operations, error handling, and performance in the transcription pipeline.
- **Speaker Diarization Accuracy**: Improved speaker attribution by modifying the LLM prompt to skeptically evaluate diarization splits, allowing it to correctly merge speakers that were incorrectly split.
- **Transcript Formatting**: Fixed a parameter name mismatch to ensure YouTube metadata is correctly included in transcripts. Also improved readability by grouping consecutive segments by the same speaker into paragraphs.
- **Database Parameter Names**: Corrected database parameter names (e.g., `video_id` to `source_id`) in the audio processor to ensure transcripts are saved correctly. Improved logging to reflect the claim-centric architecture.

## [3.5.0] - 2025-10-17

### Breaking Changes
- Removed CLI interface - application is now GUI-only. All functionality is available through the enhanced GUI with the System2 architecture.

### Added
- Comprehensive System2Orchestrator tests for asynchronous job processing.
- LLM adapter async behavior tests, including event loop cleanup validation.
- GUI integration tests using automated workflows.
- Direct logic tests for complete code coverage.
- An automated test suite with zero human intervention required.

### Changed
- The Monitor tab now uses System2Orchestrator, consistent with the Summarization tab.
- Unified code path: all operations now use the System2Orchestrator architecture, eliminating divergence between CLI and GUI implementations.

### Removed
- All CLI commands (`transcribe`, `summarize`, `moc`, `process`, `database`, `upload`, `voice_test`).
- CLI-specific processors and legacy summarizer modules.
- The `commands/` directory and `cli.py` entry point.

### Fixed
- Transcript files now load correctly in the summarization tab after transcription.
- Event loop closure errors during async HTTP client cleanup have been resolved.
- The Monitor tab now uses the same tested code path as the rest of the GUI.

---

## [3.2.22] - 2025-09-17

### Added
- **System 2 HCE Migration**: All HCE processors now use a centralized LLM adapter with System 2 architecture for improved tracking, rate limiting, and cost management.
- **Complete Bundle Approach**: The application is now distributed as a ~600MB DMG with all models and dependencies included, enabling full offline functionality from the first launch.
- **Advanced Voice Fingerprinting**: A new system with 97% accuracy using ECAPA-TDNN and Wav2Vec2 models, bundled for immediate offline use. It automatically merges speakers incorrectly split by diarization.
- **Smart Podcast-Focused Speaker Detection**: A purely LLM-based approach for speaker suggestions that analyzes clean, deduplicated segments and full metadata for higher accuracy.
- **Diarization Excellence & Over-Segmentation Solution**: A conservative diarization strategy combined with voice fingerprinting and text overlap detection to ensure high-quality speaker segmentation.
- **Accuracy Achievement Pipeline**: A multi-step process (Conservative Diarization → Voice Fingerprinting → LLM Validation → Contextual Analysis → User Review) that achieves 99% final accuracy.

### Changed
- **Major Architecture Refactor**: The application has been refactored to support multiple formats (PDFs, Word docs), cloud sync with Supabase, and a unified processing pipeline that reduces API calls by 70%.

---

## Older Releases

Details for older releases can be found in the git history.
