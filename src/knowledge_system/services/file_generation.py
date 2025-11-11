"""
File generation service for Knowledge System.

Regenerates markdown transcripts, MOC files, summaries, and export files from SQLite
database data. Supports multiple output formats and maintains compatibility with
existing file structures.
"""

import json
from datetime import datetime
from pathlib import Path

import yaml

from ..database import DatabaseService
from ..logger import get_logger

logger = get_logger(__name__)


def _format_segments_to_markdown_transcript(
    segments: list[dict],
    include_speakers: bool = True,
    include_timestamps: bool = True,
    diarization_enabled: bool = False,
    source_id: str | None = None,
) -> str:
    """
    Format transcript segments into properly formatted markdown with speaker separation.

    Groups segments into logical paragraphs based on:
    - Speaker changes (always starts new paragraph)
    - Long pauses (7+ seconds)
    - Sentence boundaries (for natural reading flow)
    - Maximum paragraph length (900 chars, with sentence boundary preference)

    Args:
        segments: List of transcript segments with start, text, and optionally speaker
        include_speakers: Whether to include speaker information
        include_timestamps: Whether to include timestamps
        diarization_enabled: Whether diarization was performed
        source_id: YouTube video ID for creating hyperlinked timestamps

    Returns:
        Formatted markdown transcript content with logical paragraph breaks
    """
    if not segments:
        return ""

    def ends_with_sentence_boundary(text: str) -> bool:
        """Check if text ends with a sentence boundary."""
        text = text.rstrip()
        return text.endswith((".", "!", "?", '."', '!"', '?"', '.")', '!")', '?")'))

    def format_timestamp(start_time: float) -> str:
        """Format timestamp with or without hyperlink."""
        if (
            include_timestamps
            and source_id is not None
            and isinstance(source_id, str)
            and source_id != "youtube_video"
            and source_id != ""
            and len(source_id) == 11
        ):
            # Create hyperlinked timestamp for YouTube videos
            timestamp_str = _format_timestamp_for_display(start_time)
            youtube_url = (
                f"https://www.youtube.com/watch?v={source_id}&t={int(start_time)}s"
            )
            return f"[{timestamp_str}]({youtube_url})"
        elif include_timestamps:
            # Plain timestamp
            return f"[{_format_timestamp_for_display(start_time)}]"
        return ""

    def format_speaker_display(speaker: str) -> str:
        """Convert speaker ID to human-readable format."""
        if speaker.startswith("SPEAKER_"):
            speaker_num = speaker.replace("SPEAKER_", "")
            try:
                speaker_number = int(speaker_num) + 1
                return f"Speaker {speaker_number}"
            except (ValueError, TypeError):
                return speaker
        return speaker

    # Configuration for paragraph grouping
    PAUSE_THRESHOLD_SECONDS = 7.0
    MAX_PARAGRAPH_CHARS = 900
    FORCE_BREAK_CHARS = 1200  # Force break even without sentence boundary

    content_parts = []
    current_paragraph = []
    current_speaker = None
    paragraph_start_time = None
    last_end_time = None
    last_flushed_speaker = None  # Track last speaker label written

    def flush_paragraph():
        """Write accumulated paragraph to content_parts."""
        nonlocal current_paragraph, paragraph_start_time, current_speaker, last_flushed_speaker

        if not current_paragraph:
            return

        paragraph_text = " ".join(current_paragraph).strip()
        if not paragraph_text:
            current_paragraph = []
            paragraph_start_time = None
            return

        # Build paragraph with speaker and timestamp
        paragraph_lines = []

        if include_speakers and current_speaker and diarization_enabled:
            speaker_display = format_speaker_display(current_speaker)
            timestamp = (
                format_timestamp(paragraph_start_time)
                if paragraph_start_time is not None
                else ""
            )

            # Only show speaker label if it changed from last paragraph (for readability in monologues)
            if current_speaker != last_flushed_speaker:
                if timestamp:
                    paragraph_lines.append(f"**{speaker_display}** {timestamp}\n")
                else:
                    paragraph_lines.append(f"**{speaker_display}**\n")
                last_flushed_speaker = current_speaker
            elif timestamp:
                # Same speaker, just show timestamp
                paragraph_lines.append(f"{timestamp}\n")
        elif include_timestamps and paragraph_start_time is not None:
            timestamp = format_timestamp(paragraph_start_time)
            paragraph_lines.append(f"{timestamp}\n")

        paragraph_lines.append(f"{paragraph_text}\n")

        content_parts.append("".join(paragraph_lines))
        current_paragraph = []
        paragraph_start_time = None

    # Process segments into paragraphs
    for segment in segments:
        text = segment.get("text", "").strip()
        if not text:
            continue

        speaker = segment.get("speaker", "")
        start_time = segment.get("start", 0)
        end_time = segment.get("end", start_time)

        # Calculate if there's a long pause
        long_pause = (
            last_end_time is not None
            and start_time is not None
            and (float(start_time) - float(last_end_time)) >= PAUSE_THRESHOLD_SECONDS
        )

        # Calculate potential paragraph length
        paragraph_candidate_length = len(" ".join(current_paragraph + [text]))

        # Determine if we need a new paragraph
        needs_new_paragraph = False
        if current_paragraph:
            # Always break on speaker change
            if speaker != current_speaker:
                needs_new_paragraph = True
            # Break on long pauses
            elif long_pause:
                needs_new_paragraph = True
            # For length-based breaks, prefer sentence boundaries
            elif paragraph_candidate_length >= MAX_PARAGRAPH_CHARS:
                if current_paragraph and ends_with_sentence_boundary(
                    current_paragraph[-1]
                ):
                    needs_new_paragraph = True
                # Force break if way over limit
                elif paragraph_candidate_length >= FORCE_BREAK_CHARS:
                    needs_new_paragraph = True

        if needs_new_paragraph:
            flush_paragraph()

        # Start new paragraph if needed
        if not current_paragraph:
            current_speaker = speaker
            paragraph_start_time = float(start_time) if start_time is not None else None

        current_paragraph.append(text)
        last_end_time = (
            float(end_time)
            if end_time is not None
            else float(start_time)
            if start_time is not None
            else None
        )

    # Flush any remaining paragraph
    flush_paragraph()

    # Join with blank lines between paragraphs for readability
    return "\n".join(content_parts)


def _format_timestamp_for_display(seconds: float) -> str:
    """Format seconds to MM:SS or HH:MM:SS for display."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)

    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    else:
        return f"{minutes:02d}:{secs:02d}"


class FileGenerationService:
    """
    Service for generating output files from SQLite database data.

    Generates markdown transcripts, MOC files, summaries, and various export formats
    from the comprehensive data stored in the SQLite database.
    """

    def __init__(
        self,
        database_service: DatabaseService | None = None,
        output_dir: Path | None = None,
    ):
        """Initialize file generation service."""
        import os

        # Standardize on db_service; keep self.db as a backward-compatible alias
        self.db_service = database_service or DatabaseService()
        self.db = self.db_service

        # Allow tests to override output directory via environment variable
        if output_dir is not None:
            base_output = Path(output_dir)
        else:
            test_output_env = os.environ.get("KNOWLEDGE_CHIPPER_TEST_OUTPUT_DIR")
            base_output = Path(test_output_env) if test_output_env else Path("output")

        self.output_dir = base_output
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Create standard subdirectories
        self.transcripts_dir = self.output_dir / "transcripts"
        self.summaries_dir = self.output_dir / "summaries"
        self.moc_dir = self.output_dir / "moc"
        self.exports_dir = self.output_dir / "exports"
        self.thumbnails_dir = self.output_dir / "Thumbnails"

        for dir_path in [
            self.transcripts_dir,
            self.summaries_dir,
            self.moc_dir,
            self.exports_dir,
            self.thumbnails_dir,
        ]:
            dir_path.mkdir(parents=True, exist_ok=True)

    def generate_transcript_markdown(
        self,
        source_id: str,
        transcript_id: str | None = None,
        include_timestamps: bool = True,
        include_speakers: bool = True,
    ) -> Path | None:
        """
        Generate markdown transcript file from database data.

        Args:
            source_id: YouTube video ID
            transcript_id: Specific transcript ID (uses latest if None)
            include_timestamps: Include timestamp markers
            include_speakers: Include speaker labels if available

        Returns:
            Path to generated markdown file, or None if failed
        """
        try:
            # Get video and transcript data
            video = self.db.get_source(source_id)
            if not video:
                logger.error(f"Video {source_id} not found in database")
                return None

            transcripts = self.db.get_transcripts_for_video(source_id)
            if not transcripts:
                logger.error(f"No transcripts found for video {source_id}")
                return None

            # Use specific transcript or latest
            transcript = None
            if transcript_id:
                transcript = next(
                    (t for t in transcripts if t.transcript_id == transcript_id), None
                )
            else:
                transcript = transcripts[0]  # Latest transcript

            if not transcript:
                logger.error(f"Transcript {transcript_id} not found")
                return None

            # Generate YAML frontmatter
            frontmatter = {
                "title": f"Transcript of {video.title}",
                "source_id": video.source_id,
                "url": video.url,
                "uploader": video.uploader,
                "upload_date": video.upload_date,
                "duration": video.duration_seconds,
                "language": transcript.language,
                "transcript_type": transcript.transcript_type,
                "is_manual": transcript.is_manual,
                "diarization_enabled": transcript.diarization_enabled,
                "processed_at": (
                    transcript.created_at.isoformat() if transcript.created_at else None
                ),
                # Claim-centric schema doesn't have tags_json or categories_json
                "tags": [],
                "categories": [],
            }

            # Build transcript content
            transcript_content = ""

            # Prefer building from segments for proper formatting
            if transcript.transcript_segments_json:
                # Check if segments actually have speaker data
                has_speaker_data = any(
                    segment.get("speaker")
                    for segment in transcript.transcript_segments_json
                )

                transcript_content = _format_segments_to_markdown_transcript(
                    segments=transcript.transcript_segments_json,
                    include_speakers=include_speakers,
                    include_timestamps=include_timestamps,
                    diarization_enabled=has_speaker_data,  # Use actual speaker data presence
                    source_id=video.source_id,  # Pass source_id for YouTube timestamp hyperlinks
                )

            # Fallback to stored speaker text if segments not available
            elif include_speakers and transcript.transcript_text_with_speakers:
                transcript_content = transcript.transcript_text_with_speakers
            else:
                # Use plain transcript text as final fallback
                transcript_content = transcript.transcript_text

            # Generate markdown content
            yaml_frontmatter = yaml.dump(frontmatter, default_flow_style=False)

            # Claim-centric schema doesn't have tags_json, so no hashtags from database
            hashtags_section = ""

            markdown_content = f"""---
{yaml_frontmatter}---
{hashtags_section}
**Video URL:** [{video.url}]({video.url})
**Uploader:** {video.uploader or 'Unknown'}
**Duration:** {self._format_duration(video.duration_seconds)}
**Language:** {transcript.language}

## Transcript

{transcript_content}

---
*Generated from Knowledge System database on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*
"""

            # Save to file
            filename = self._sanitize_filename(f"{video.title}_{video.source_id}.md")
            file_path = self.transcripts_dir / filename

            with open(file_path, "w", encoding="utf-8") as f:
                f.write(markdown_content)

            # Track generated file in database
            self.db.track_generated_file(
                source_id=source_id,
                file_path=str(file_path),
                file_type="transcript_md",
                file_format="md",
                transcript_id=transcript.transcript_id,
                include_timestamps=include_timestamps,
                include_analysis=include_speakers,
            )

            logger.info(f"Generated transcript markdown: {file_path}")
            return file_path

        except Exception as e:
            logger.error(f"Failed to generate transcript markdown for {source_id}: {e}")
            return None

    def append_summary_to_transcript(
        self, source_id: str, summary_id: str | None = None
    ) -> Path | None:
        """
        Append summary data (claims, people, concepts) to existing transcript markdown file.

        This reads claims directly from the database and appends them to the transcript file
        instead of creating a separate summary file.

        Args:
            source_id: YouTube video ID
            summary_id: Specific summary ID (uses latest if None)

        Returns:
            Path to updated transcript file, or None if failed
        """
        try:
            from sqlalchemy.orm import Session

            from ..database.models import (
                Claim,
                ClaimConcept,
                ClaimPerson,
                Concept,
                Person,
            )

            # Get source data
            video = self.db.get_source(source_id)
            if not video:
                logger.error(f"Source {source_id} not found in database")
                return None

            # Get summary data
            summaries = self.db.get_summaries_for_video(source_id)
            if not summaries:
                logger.error(f"No summaries found for video {source_id}")
                return None

            summary = (
                summaries[0]
                if not summary_id
                else next((s for s in summaries if s.summary_id == summary_id), None)
            )
            if not summary:
                logger.error(f"Summary {summary_id} not found")
                return None

            # Find existing transcript markdown file
            # Strategy 1: Check GeneratedFile table
            from ..database.models import GeneratedFile

            transcript_path = None

            with self.db.Session() as session:
                generated_file = (
                    session.query(GeneratedFile)
                    .filter_by(source_id=source_id, file_type="transcript_md")
                    .order_by(GeneratedFile.created_at.desc())
                    .first()
                )

                if generated_file:
                    transcript_path = Path(generated_file.file_path)
                    if not transcript_path.exists():
                        logger.warning(
                            f"Tracked transcript file not found: {transcript_path}"
                        )
                        transcript_path = None

            # Strategy 2: Search output directory for transcript file
            if not transcript_path:
                logger.info(f"Searching output directory for transcript file...")
                # Sanitize title for filename matching
                safe_title = "".join(
                    c for c in video.title if c.isalnum() or c in (" ", "-", "_")
                ).rstrip()

                # Look for files - try multiple patterns
                search_patterns = [
                    f"*{source_id}*.md",  # Has source_id in name
                    f"{safe_title}.md",  # Exact title match
                    f"*{safe_title[:40]}*.md",  # Partial title match
                ]

                for pattern in search_patterns:
                    matches = list(self.output_dir.glob(pattern))
                    # Filter out summary files and special files
                    matches = [
                        m
                        for m in matches
                        if not m.name.startswith("Summary_")
                        and not m.name.endswith("_enhanced.md")
                        and not m.name.endswith("_color_coded.html")
                    ]
                    if matches:
                        # Use the most recently modified file
                        transcript_path = max(matches, key=lambda p: p.stat().st_mtime)
                        logger.info(f"Found transcript file: {transcript_path}")
                        break

                if not transcript_path:
                    logger.error(
                        f"No transcript markdown file found for {source_id} in {self.output_dir}"
                    )
                    logger.error(f"Tried patterns: {search_patterns}")
                    return None

            # Read existing transcript content
            with open(transcript_path, encoding="utf-8") as f:
                existing_content = f.read()

            # Check if summary section already exists
            if "## Summary" in existing_content and "## Claims" in existing_content:
                logger.info(
                    f"Summary already appended to {transcript_path}, updating..."
                )
                # Remove existing summary sections
                parts = existing_content.split("## Summary")
                existing_content = parts[0].rstrip()

            # Get claims from database
            with self.db.Session() as session:
                claims = (
                    session.query(Claim)
                    .filter(Claim.source_id == source_id)
                    .order_by(Claim.tier, Claim.importance_score.desc())
                    .all()
                )

                # Get people mentioned in claims
                people = (
                    session.query(Person)
                    .join(ClaimPerson)
                    .join(Claim)
                    .filter(Claim.source_id == source_id)
                    .distinct()
                    .all()
                )

                # Get concepts mentioned in claims
                concepts = (
                    session.query(Concept)
                    .join(ClaimConcept)
                    .join(Claim)
                    .filter(Claim.source_id == source_id)
                    .distinct()
                    .all()
                )

            # Build summary section
            summary_section = f"\n\n## Summary\n\n"

            # Add summary text if available
            if summary.summary_text:
                # Clean up dictionary formatting if present
                summary_text = summary.summary_text
                if summary_text.startswith("{") and "paragraphs" in summary_text:
                    # This is a dict string, try to extract meaningful text
                    import ast

                    try:
                        summary_dict = ast.literal_eval(summary_text)
                        if (
                            isinstance(summary_dict, dict)
                            and "paragraphs" in summary_dict
                        ):
                            paragraphs = summary_dict["paragraphs"]
                            summary_text = "\n\n".join(
                                p.get("text", "")
                                for p in paragraphs
                                if isinstance(p, dict)
                            )
                    except:
                        pass  # Use as-is if parsing fails

                summary_section += f"{summary_text}\n\n"

            summary_section += (
                f"**Analyzed by:** {summary.llm_model} ({summary.llm_provider})\n"
            )
            summary_section += f"**Processing Cost:** ${summary.processing_cost:.4f}\n"

            # Add Claims section
            if claims:
                summary_section += f"\n## Claims ({len(claims)} extracted)\n\n"

                # Group by tier
                tier_a = [c for c in claims if c.tier == "A"]
                tier_b = [c for c in claims if c.tier == "B"]
                tier_c = [c for c in claims if c.tier == "C"]

                if tier_a:
                    summary_section += "### 🥇 Tier A Claims (High Confidence)\n\n"
                    for i, claim in enumerate(tier_a, 1):
                        summary_section += f"{i}. **{claim.canonical}**\n"
                        if claim.claim_type:
                            summary_section += f"   - *Type:* {claim.claim_type}\n"
                        if claim.importance_score:
                            summary_section += (
                                f"   - *Importance:* {claim.importance_score:.1f}/10\n"
                            )
                        summary_section += "\n"

                if tier_b:
                    summary_section += "### 🥈 Tier B Claims (Medium Confidence)\n\n"
                    for i, claim in enumerate(tier_b, 1):
                        summary_section += f"{i}. {claim.canonical}\n"
                    summary_section += "\n"

                if tier_c:
                    summary_section += f"### 🥉 Tier C Claims (Lower Confidence)\n\n"
                    summary_section += f"*{len(tier_c)} additional claims with lower confidence scores*\n\n"

            # Add People section
            if people:
                summary_section += f"## People ({len(people)} mentioned)\n\n"
                for person in people:
                    summary_section += f"- **{person.name}**"
                    if person.description:
                        summary_section += f": {person.description}"
                    summary_section += "\n"
                summary_section += "\n"

            # Add Concepts section
            if concepts:
                summary_section += f"## Concepts ({len(concepts)} identified)\n\n"
                for concept in concepts:
                    summary_section += f"- **{concept.name}**"
                    if concept.description:
                        summary_section += f": {concept.description}"
                    summary_section += "\n"
                summary_section += "\n"

            # Add metadata footer
            summary_section += f"---\n*Summary generated from Knowledge System database on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n"

            # Write updated content
            updated_content = existing_content + summary_section
            with open(transcript_path, "w", encoding="utf-8") as f:
                f.write(updated_content)

            logger.info(f"✅ Appended summary data to transcript: {transcript_path}")
            logger.info(
                f"   Added {len(claims)} claims, {len(people)} people, {len(concepts)} concepts"
            )

            return transcript_path

        except Exception as e:
            logger.error(f"Failed to append summary to transcript for {source_id}: {e}")
            import traceback

            logger.debug(traceback.format_exc())
            return None

    def generate_summary_markdown(
        self, source_id: str, summary_id: str | None = None
    ) -> Path | None:
        """
        Generate markdown summary file from database data.

        DEPRECATED: Use append_summary_to_transcript() instead to append
        summary data to the existing transcript file.

        Args:
            source_id: YouTube video ID
            summary_id: Specific summary ID (uses latest if None)

        Returns:
            Path to generated markdown file, or None if failed
        """
        try:
            # Get source and summary data
            video = self.db.get_source(source_id)
            if not video:
                logger.error(f"Source {source_id} not found in database")
                return None

            summaries = self.db.get_summaries_for_video(source_id)
            if not summaries:
                logger.error(f"No summaries found for video {source_id}")
                return None

            # Use specific summary or latest
            summary = None
            if summary_id:
                summary = next(
                    (s for s in summaries if s.summary_id == summary_id), None
                )
            else:
                summary = summaries[0]  # Latest summary

            if not summary:
                logger.error(f"Summary {summary_id} not found")
                return None

            # Check if this is HCE-processed summary
            is_hce = summary.processing_type == "hce"
            # Note: hce_data_json is a JSONEncodedType field, already deserialized to dict
            hce_data = summary.hce_data_json if summary.hce_data_json else None

            # Generate YAML frontmatter
            frontmatter = {
                "title": f"Summary of {video.title}",
                "source_id": video.source_id,
                "url": video.url,
                "summary_id": summary.summary_id,
                "processing_type": summary.processing_type,
                "llm_provider": summary.llm_provider,
                "llm_model": summary.llm_model,
                "processing_cost": summary.processing_cost,
                "total_tokens": summary.total_tokens,
                "compression_ratio": summary.compression_ratio,
                "created_at": (
                    summary.created_at.isoformat() if summary.created_at else None
                ),
                "template_used": summary.template_used,
            }

            # Add HCE-specific metadata
            if is_hce and hce_data:
                frontmatter["claims_extracted"] = len(hce_data.get("claims", []))
                frontmatter["people_found"] = len(hce_data.get("people", []))
                frontmatter["concepts_found"] = len(hce_data.get("concepts", []))
                frontmatter["relations_found"] = len(hce_data.get("relations", []))

            # Add summary metadata if available
            if summary.summary_metadata_json:
                frontmatter.update(summary.summary_metadata_json)

            # Generate markdown content
            if is_hce and hce_data:
                # Enhanced HCE-specific markdown format
                markdown_content = self._generate_hce_markdown(
                    video, summary, hce_data, frontmatter
                )
            else:
                # Legacy format for non-HCE summaries
                yaml_frontmatter = yaml.dump(frontmatter, default_flow_style=False)
                markdown_content = f"""---
{yaml_frontmatter}---

# Summary: {video.title}

**Original Video:** [{video.url}]({video.url})
**Summarized by:** {summary.llm_model} ({summary.llm_provider})
**Processing Cost:** ${summary.processing_cost:.4f} ({summary.total_tokens:,} tokens)

## Summary

{summary.summary_text}

---
*Generated from Knowledge System database on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*
"""

            # Save to file
            filename = self._sanitize_filename(
                f"Summary_{video.title}_{video.source_id}.md"
            )
            file_path = self.summaries_dir / filename

            with open(file_path, "w", encoding="utf-8") as f:
                f.write(markdown_content)

            # Track generated file in database
            self.db.track_generated_file(
                source_id=source_id,
                file_path=str(file_path),
                file_type="summary_md",
                file_format="md",
                summary_id=summary.summary_id,
            )

            logger.info(f"Generated summary markdown: {file_path}")
            return file_path

        except Exception as e:
            logger.error(f"Failed to generate summary markdown for {source_id}: {e}")
            return None

    def generate_moc_files(
        self, source_id: str | None = None, moc_id: str | None = None
    ) -> dict[str, Path]:
        """
        Generate MOC (Maps of Content) files from database data.

        Args:
            source_id: Specific video ID (generates for all videos if None)
            moc_id: Specific MOC extraction ID

        Returns:
            Dictionary mapping MOC type to generated file path
        """
        generated_files = {}

        try:
            # Get MOC extractions
            if source_id and moc_id:
                # Get specific MOC extraction
                moc_extractions = []  # Would need a get_moc_extraction method
            elif source_id:
                # Get all MOC extractions for video
                moc_extractions = (
                    []
                )  # Would need a get_moc_extractions_for_video method
            else:
                # Get all MOC extractions
                moc_extractions = []  # Would need a get_all_moc_extractions method

            if not moc_extractions:
                logger.warning("No MOC extractions found")
                return generated_files

            # Aggregate MOC data
            all_people = []
            all_tags = []
            all_mental_models = []
            all_jargon = []
            all_beliefs = []

            for moc in moc_extractions:
                if moc.people_json:
                    all_people.extend(moc.people_json)
                if moc.tags_json:
                    all_tags.extend(moc.tags_json)
                if moc.mental_models_json:
                    all_mental_models.extend(moc.mental_models_json)
                if moc.jargon_json:
                    all_jargon.extend(moc.jargon_json)
                if moc.beliefs_json:
                    all_beliefs.extend(moc.beliefs_json)

            # Generate People.md
            if all_people:
                people_path = self._generate_people_file(all_people)
                if people_path:
                    generated_files["people"] = people_path

            # Generate Tags.md
            if all_tags:
                tags_path = self._generate_tags_file(all_tags)
                if tags_path:
                    generated_files["tags"] = tags_path

            # Generate Mental_Models.md
            if all_mental_models:
                models_path = self._generate_mental_models_file(all_mental_models)
                if models_path:
                    generated_files["mental_models"] = models_path

            # Generate Jargon.md
            if all_jargon:
                jargon_path = self._generate_jargon_file(all_jargon)
                if jargon_path:
                    generated_files["jargon"] = jargon_path

            # Generate claims.yaml
            if all_beliefs:
                beliefs_path = self._generate_beliefs_file(all_beliefs)
                if beliefs_path:
                    generated_files["beliefs"] = beliefs_path

            logger.info(f"Generated {len(generated_files)} MOC files")
            return generated_files

        except Exception as e:
            logger.error(f"Failed to generate MOC files: {e}")
            return {}

    def generate_export_files(
        self, source_id: str, formats: list[str] = ["srt", "vtt", "txt"]
    ) -> dict[str, Path]:
        """
        Generate export files in various formats.

        Args:
            source_id: YouTube video ID
            formats: List of formats to generate ('srt', 'vtt', 'txt', 'json')

        Returns:
            Dictionary mapping format to generated file path
        """
        generated_files = {}

        try:
            # Get video and transcript data
            video = self.db.get_source(source_id)
            transcripts = self.db.get_transcripts_for_video(source_id)

            if not video or not transcripts:
                logger.error(f"Video or transcripts not found for {source_id}")
                return generated_files

            transcript = transcripts[0]  # Use latest transcript

            # Generate each requested format
            for format_type in formats:
                file_path = None

                if format_type == "srt":
                    file_path = self._generate_srt_file(video, transcript)
                elif format_type == "vtt":
                    file_path = self._generate_vtt_file(video, transcript)
                elif format_type == "txt":
                    file_path = self._generate_txt_file(video, transcript)
                elif format_type == "json":
                    file_path = self._generate_json_file(video, transcript)

                if file_path:
                    generated_files[format_type] = file_path

                    # Track generated file in database
                    self.db.track_generated_file(
                        source_id=source_id,
                        file_path=str(file_path),
                        file_type=f"transcript_{format_type}",
                        file_format=format_type,
                        transcript_id=transcript.transcript_id,
                    )

            logger.info(
                f"Generated {len(generated_files)} export files for {source_id}"
            )
            return generated_files

        except Exception as e:
            logger.error(f"Failed to generate export files for {source_id}: {e}")
            return {}

    def regenerate_all_files(self, source_id: str) -> dict[str, any]:
        """
        Regenerate all files for a specific video.

        Args:
            source_id: YouTube video ID

        Returns:
            Dictionary with paths to all generated files
        """
        results = {
            "source_id": source_id,
            "transcript_markdown": None,
            "summary_markdown": None,
            "export_files": {},
            "errors": [],
        }

        try:
            # Generate transcript markdown
            transcript_path = self.generate_transcript_markdown(source_id)
            if transcript_path:
                results["transcript_markdown"] = str(transcript_path)
            else:
                results["errors"].append("Failed to generate transcript markdown")

            # Generate summary markdown
            summary_path = self.generate_summary_markdown(source_id)
            if summary_path:
                results["summary_markdown"] = str(summary_path)
            else:
                results["errors"].append("Failed to generate summary markdown")

            # Generate export files
            export_files = self.generate_export_files(source_id)
            results["export_files"] = {
                fmt: str(path) for fmt, path in export_files.items()
            }

            if not export_files:
                results["errors"].append("Failed to generate export files")

            logger.info(f"Regenerated all files for video {source_id}")
            return results

        except Exception as e:
            logger.error(f"Failed to regenerate files for {source_id}: {e}")
            results["errors"].append(str(e))
            return results

    # Helper methods
    def _generate_hce_markdown(self, video, summary, hce_data, frontmatter) -> str:
        """Generate enhanced HCE-specific markdown content."""

        # Extract claim data
        claims = hce_data.get("claims", [])
        people = hce_data.get("people", [])
        concepts = hce_data.get("concepts", [])
        relations = hce_data.get("relations", [])
        contradictions = hce_data.get("contradictions", [])

        # Categorize claims by tier
        tier_a_claims = [c for c in claims if c.get("tier") == "A"]
        tier_b_claims = [c for c in claims if c.get("tier") == "B"]
        _tier_c_claims = [c for c in claims if c.get("tier") == "C"]

        # Generate markdown content with proper YAML frontmatter
        yaml_frontmatter = yaml.dump(frontmatter, default_flow_style=False)

        markdown_content = f"""---
{yaml_frontmatter}---

# Claim Analysis: {video.title}

**Original Video:** [{video.url}]({video.url})
**Analyzed by:** {summary.llm_model} ({summary.llm_provider})
**Processing Cost:** ${summary.processing_cost:.4f} ({summary.total_tokens:,} tokens)
**Claims Extracted:** {len(claims)} | **Relations Mapped:** {len(relations)} | **Contradictions:** {len(contradictions)}

## Executive Summary

"""

        # Generate executive summary from A-tier claims
        if tier_a_claims:
            markdown_content += "**Key High-Confidence Claims:**\n\n"
            for i, claim in enumerate(tier_a_claims[:5], 1):  # Top 5 A-tier claims
                canonical = claim.get("canonical", "")
                markdown_content += f"{i}. {canonical}\n"

            markdown_content += "\n"
        else:
            markdown_content += (
                "*No high-confidence (Tier A) claims were identified.*\n\n"
            )

        # Add traditional summary if available
        if summary.summary_text:
            markdown_content += f"**Generated Summary:** {summary.summary_text}\n\n"

        markdown_content += "## Key Claims by Category\n\n"

        # Tier A Claims
        if tier_a_claims:
            markdown_content += "### 🥇 Tier A Claims (High Confidence)\n\n"
            for claim in tier_a_claims:
                canonical = claim.get("canonical", "")
                claim_type = claim.get("claim_type", "General")
                evidence = claim.get("evidence", [])

                markdown_content += f"**{canonical}**\n"
                markdown_content += f"- *Type:* {claim_type}\n"
                if evidence:
                    markdown_content += (
                        f"- *Evidence:* {len(evidence)} supporting points\n"
                    )
                markdown_content += "\n"

        # Tier B Claims
        if tier_b_claims:
            markdown_content += "### 🥈 Tier B Claims (Medium Confidence)\n\n"
            for claim in tier_b_claims[:10]:  # Limit to 10 for readability
                canonical = claim.get("canonical", "")
                claim_type = claim.get("claim_type", "General")
                markdown_content += f"- **{canonical}** *(Type: {claim_type})*\n"

            if len(tier_b_claims) > 10:
                markdown_content += (
                    f"\n*...and {len(tier_b_claims) - 10} more Tier B claims*\n"
                )
            markdown_content += "\n"

        # People, Concepts, and Jargon sections
        if people:
            markdown_content += "## People\n\n"
            for person in people[:20]:  # Limit for readability
                name = person.get("name", "")
                description = person.get("description", "")
                markdown_content += f"- **{name}**"
                if description:
                    markdown_content += f": {description}"
                markdown_content += "\n"
            markdown_content += "\n"

        if concepts:
            markdown_content += "## Concepts\n\n"
            for concept in concepts[:20]:
                name = concept.get("name", "")
                description = concept.get("description", "")
                markdown_content += f"- **{name}**"
                if description:
                    markdown_content += f": {description}"
                markdown_content += "\n"
            markdown_content += "\n"

        # Evidence Citations
        if any(claim.get("evidence") for claim in claims):
            markdown_content += "## Evidence Citations\n\n"
            claims_with_evidence = [
                c for c in tier_a_claims + tier_b_claims if c.get("evidence")
            ]

            for claim in claims_with_evidence[:10]:  # Top 10 claims with evidence
                canonical = claim.get("canonical", "")
                evidence = claim.get("evidence", [])

                markdown_content += f"**{canonical}**\n"
                for i, ev in enumerate(evidence[:3], 1):  # Top 3 evidence points
                    markdown_content += f"{i}. {ev}\n"
                markdown_content += "\n"

        # Relations and Contradictions
        if contradictions:
            markdown_content += "## Contradictions Detected\n\n"
            for i, contradiction in enumerate(contradictions[:5], 1):
                claim1 = contradiction.get("claim1", {}).get("canonical", "")
                claim2 = contradiction.get("claim2", {}).get("canonical", "")
                markdown_content += f"{i}. **Claim:** {claim1}\n"
                markdown_content += f"   **Contradicts:** {claim2}\n\n"

        # Add Obsidian-compatible tags and links
        markdown_content += "## Tags\n\n"

        # Generate Obsidian tags from concepts and claim types
        obsidian_tags = set()

        # Claim-centric schema doesn't have tags_json, so no hashtags from database

        # Add video-related tags
        obsidian_tags.add(f"#video/{video.source_id}")
        obsidian_tags.add("#claim-analysis")
        obsidian_tags.add("#hce-processed")

        # Add concept tags
        for concept in concepts[:15]:  # Limit to prevent tag overload
            name = concept.get("name", "").strip()
            if name:
                # Clean tag name for Obsidian compatibility
                tag_name = name.replace(" ", "-").replace("/", "-").lower()
                tag_name = "".join(c for c in tag_name if c.isalnum() or c in "-_")
                if tag_name:
                    obsidian_tags.add(f"#concept/{tag_name}")

        # Add tier tags based on what was found
        if tier_a_claims:
            obsidian_tags.add("#high-confidence")
        if tier_b_claims:
            obsidian_tags.add("#medium-confidence")
        if contradictions:
            obsidian_tags.add("#contradictions")
        if relations:
            obsidian_tags.add("#relations")

        # Output tags
        if obsidian_tags:
            # Format tags in a clean line
            markdown_content += " ".join(sorted(obsidian_tags))
            markdown_content += "\n\n"

        # Add Obsidian-style wikilinks for people
        if people:
            markdown_content += "## Related People\n\n"
            for person in people[:10]:
                name = person.get("name", "").strip()
                if name:
                    # Create Obsidian wikilink
                    markdown_content += f"- [[{name}]]\n"
            markdown_content += "\n"

        markdown_content += f"""---
*Generated from Knowledge System database on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*
*Processed using HCE (Hybrid Claim Extractor) v2.0*
"""

        return markdown_content

    def _sanitize_filename(self, filename: str) -> str:
        """Sanitize filename for filesystem compatibility."""
        import re

        # Replace invalid characters
        filename = re.sub(r'[<>:"/\\|?*]', "_", filename)
        # Limit length
        if len(filename) > 200:
            name, ext = filename.rsplit(".", 1) if "." in filename else (filename, "")
            filename = name[: 200 - len(ext) - 1] + "." + ext if ext else name[:200]
        return filename

    def _format_timestamp(self, seconds: float) -> str:
        """Format seconds to MM:SS or HH:MM:SS."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)

        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        else:
            return f"{minutes:02d}:{secs:02d}"

    def _format_duration(self, seconds: int | None) -> str:
        """Format duration in seconds to human readable format."""
        if not seconds:
            return "Unknown"
        return self._format_timestamp(seconds)

    def _generate_people_file(self, people_data: list[dict]) -> Path | None:
        """Generate People.md file from aggregated people data."""
        try:
            content = "# People\n\n"
            content += "People mentioned across processed videos:\n\n"

            # Sort by mention count (descending)
            sorted_people = sorted(
                people_data, key=lambda x: x.get("mentions", 0), reverse=True
            )

            for person in sorted_people:
                name = person.get("name", "Unknown")
                mentions = person.get("mentions", 0)
                description = person.get("description", "No description available")

                content += f"## {name}\n\n"
                content += f"**Mentions:** {mentions}\n\n"
                content += f"{description}\n\n"
                content += "---\n\n"

            file_path = self.moc_dir / "People.md"
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)

            return file_path

        except Exception as e:
            logger.error(f"Failed to generate People.md: {e}")
            return None

    def _generate_tags_file(self, tags_data: list[dict]) -> Path | None:
        """Generate Tags.md file from aggregated tags data."""
        try:
            content = "# Tags\n\n"
            content += "Tags extracted across processed videos:\n\n"

            # Sort by count (descending)
            sorted_tags = sorted(
                tags_data, key=lambda x: x.get("count", 0), reverse=True
            )

            for tag in sorted_tags:
                tag_name = tag.get("tag", "Unknown")
                count = tag.get("count", 0)
                contexts = tag.get("contexts", [])

                content += f"## {tag_name}\n\n"
                content += f"**Count:** {count}\n\n"

                if contexts:
                    content += "**Contexts:**\n"
                    for context in contexts[:5]:  # Show first 5 contexts
                        content += f"- {context}\n"
                    if len(contexts) > 5:
                        content += f"- ... and {len(contexts) - 5} more\n"

                content += "\n---\n\n"

            file_path = self.moc_dir / "Tags.md"
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)

            return file_path

        except Exception as e:
            logger.error(f"Failed to generate Tags.md: {e}")
            return None

    def _generate_mental_models_file(self, models_data: list[dict]) -> Path | None:
        """Generate Mental_Models.md file."""
        try:
            content = "# Mental Models\n\n"
            content += "Mental models identified across processed videos:\n\n"

            for model in models_data:
                name = model.get("name", "Unknown Model")
                description = model.get("description", "No description available")

                content += f"## {name}\n\n"
                content += f"{description}\n\n"
                content += "---\n\n"

            file_path = self.moc_dir / "Mental_Models.md"
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)

            return file_path

        except Exception as e:
            logger.error(f"Failed to generate Mental_Models.md: {e}")
            return None

    def _generate_jargon_file(self, jargon_data: list[dict]) -> Path | None:
        """Generate Jargon.md file."""
        try:
            content = "# Jargon\n\n"
            content += "Technical terms and jargon from processed videos:\n\n"

            # Sort alphabetically
            sorted_jargon = sorted(jargon_data, key=lambda x: x.get("term", "").lower())

            for item in sorted_jargon:
                term = item.get("term", "Unknown Term")
                definition = item.get("definition", "No definition available")

                content += f"## {term}\n\n"
                content += f"{definition}\n\n"
                content += "---\n\n"

            file_path = self.moc_dir / "Jargon.md"
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)

            return file_path

        except Exception as e:
            logger.error(f"Failed to generate Jargon.md: {e}")
            return None

    def _generate_beliefs_file(self, beliefs_data: list[dict]) -> Path | None:
        """Generate claims.yaml file."""
        try:
            # Convert to YAML format
            beliefs_yaml = {"beliefs": beliefs_data}

            file_path = self.moc_dir / "claims.yaml"
            with open(file_path, "w", encoding="utf-8") as f:
                yaml.dump(beliefs_yaml, f, default_flow_style=False, allow_unicode=True)

            return file_path

        except Exception as e:
            logger.error(f"Failed to generate claims.yaml: {e}")
            return None

    def _generate_srt_file(self, video, transcript) -> Path | None:
        """Generate SRT subtitle file."""
        try:
            if not transcript.transcript_segments_json:
                logger.warning("No segments available for SRT generation")
                return None

            content = ""
            segments = transcript.transcript_segments_json

            for i, segment in enumerate(segments, 1):
                start_time = self._seconds_to_srt_time(segment.get("start", 0))
                end_time = self._seconds_to_srt_time(
                    segment.get("end", segment.get("start", 0) + 5)
                )
                text = segment.get("text", "").strip()

                if text:
                    content += f"{i}\n"
                    content += f"{start_time} --> {end_time}\n"
                    content += f"{text}\n\n"

            filename = self._sanitize_filename(f"{video.title}_{video.source_id}.srt")
            file_path = self.exports_dir / filename

            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)

            return file_path

        except Exception as e:
            logger.error(f"Failed to generate SRT file: {e}")
            return None

    def _generate_vtt_file(self, video, transcript) -> Path | None:
        """Generate VTT subtitle file."""
        try:
            if not transcript.transcript_segments_json:
                logger.warning("No segments available for VTT generation")
                return None

            content = "WEBVTT\n\n"
            segments = transcript.transcript_segments_json

            for segment in segments:
                start_time = self._seconds_to_vtt_time(segment.get("start", 0))
                end_time = self._seconds_to_vtt_time(
                    segment.get("end", segment.get("start", 0) + 5)
                )
                text = segment.get("text", "").strip()

                if text:
                    content += f"{start_time} --> {end_time}\n"
                    content += f"{text}\n\n"

            filename = self._sanitize_filename(f"{video.title}_{video.source_id}.vtt")
            file_path = self.exports_dir / filename

            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)

            return file_path

        except Exception as e:
            logger.error(f"Failed to generate VTT file: {e}")
            return None

    def _generate_txt_file(self, video, transcript) -> Path | None:
        """Generate plain text file."""
        try:
            filename = self._sanitize_filename(f"{video.title}_{video.source_id}.txt")
            file_path = self.exports_dir / filename

            with open(file_path, "w", encoding="utf-8") as f:
                f.write(f"Transcript: {video.title}\n")
                f.write(f"URL: {video.url}\n")
                f.write(f"Duration: {self._format_duration(video.duration_seconds)}\n")
                f.write("-" * 50 + "\n\n")
                f.write(transcript.transcript_text)

            return file_path

        except Exception as e:
            logger.error(f"Failed to generate TXT file: {e}")
            return None

    def _generate_json_file(self, video, transcript) -> Path | None:
        """Generate JSON export file."""
        try:
            data = {
                "video": {
                    "source_id": video.source_id,
                    "title": video.title,
                    "url": video.url,
                    "uploader": video.uploader,
                    "duration_seconds": video.duration_seconds,
                    "upload_date": video.upload_date,
                    "description": video.description,
                },
                "transcript": {
                    "transcript_id": transcript.transcript_id,
                    "language": transcript.language,
                    "is_manual": transcript.is_manual,
                    "transcript_type": transcript.transcript_type,
                    "text": transcript.transcript_text,
                    "segments": transcript.transcript_segments_json,
                    "diarization_segments": (
                        transcript.diarization_segments_json
                        if transcript.diarization_enabled
                        else None
                    ),
                },
                "metadata": {
                    "generated_at": datetime.now().isoformat(),
                    "source": "Knowledge System Database",
                },
            }

            filename = self._sanitize_filename(f"{video.title}_{video.source_id}.json")
            file_path = self.exports_dir / filename

            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            return file_path

        except Exception as e:
            logger.error(f"Failed to generate JSON file: {e}")
            return None

    def _seconds_to_srt_time(self, seconds: float) -> str:
        """Convert seconds to SRT time format (HH:MM:SS,mmm)."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        milliseconds = int((seconds % 1) * 1000)

        return f"{hours:02d}:{minutes:02d}:{secs:02d},{milliseconds:03d}"

    def _seconds_to_vtt_time(self, seconds: float) -> str:
        """Convert seconds to VTT time format (HH:MM:SS.mmm)."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        milliseconds = int((seconds % 1) * 1000)

        return f"{hours:02d}:{minutes:02d}:{secs:02d}.{milliseconds:03d}"

    def generate_claims_report(
        self, source_id: str, summary_id: str | None = None
    ) -> Path | None:
        """
        Generate claims report from HCE data.

        Args:
            source_id: YouTube video ID
            summary_id: Specific summary ID (uses latest HCE summary if None)

        Returns:
            Path to generated claims report, or None if failed
        """
        try:
            # Get video and HCE summary data
            video = self.db.get_source(source_id)
            if not video:
                logger.error(f"Video {source_id} not found in database")
                return None

            summaries = self.db.get_summaries_for_video(source_id)
            # Filter for HCE summaries
            hce_summaries = [s for s in summaries if s.processing_type == "hce"]

            if not hce_summaries:
                logger.error(f"No HCE summaries found for video {source_id}")
                return None

            # Use specific summary or latest HCE summary
            if summary_id:
                summary = next(
                    (s for s in hce_summaries if s.summary_id == summary_id), None
                )
            else:
                summary = hce_summaries[0]

            if not summary or not summary.hce_data_json:
                logger.error(f"HCE data not found for summary {summary_id}")
                return None

            # Note: hce_data_json is a JSONEncodedType field, already deserialized to dict
            hce_data = summary.hce_data_json
            claims = hce_data.get("claims", [])

            # Generate markdown content
            markdown_content = """# Claims Report: {video.title}

**Source:** [{video.url}]({video.url})
**Processing Type:** HCE Claim Extraction
**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**Total Claims:** {len(claims)}

## Claims by Tier

"""

            # Group claims by tier
            tier_groups = {"A": [], "B": [], "C": []}
            for claim in claims:
                tier = claim.get("tier", "C")
                tier_groups[tier].append(claim)

            # Add claims by tier
            for tier, tier_claims in tier_groups.items():
                if tier_claims:
                    markdown_content += (
                        f"### Tier {tier} Claims ({len(tier_claims)})\n\n"
                    )

                    for claim in tier_claims:
                        canonical = claim.get("canonical", "")
                        claim_type = claim.get("claim_type", "descriptive")
                        confidence = claim.get("confidence", 0)

                        markdown_content += (
                            f"- **[{claim_type.upper()}]** {canonical}\n"
                        )
                        markdown_content += f"  - Confidence: {confidence:.2f}\n"

                        # Add evidence if available
                        evidence = claim.get("evidence", [])
                        if evidence:
                            markdown_content += "  - Evidence:\n"
                            for ev in evidence[:2]:  # Show max 2 evidence items
                                markdown_content += "    - \"{ev.get('text', '')}\"\n"

                        markdown_content += "\n"

                    markdown_content += "\n"

            # Add statistics
            markdown_content += """## Statistics

- **Tier A (High Quality):** {len(tier_groups['A'])} claims
- **Tier B (Medium Quality):** {len(tier_groups['B'])} claims
- **Tier C (Low Quality):** {len(tier_groups['C'])} claims

### Claim Types
"""

            # Count claim types
            claim_types = {}
            for claim in claims:
                ct = claim.get("claim_type", "descriptive")
                claim_types[ct] = claim_types.get(ct, 0) + 1

            for ct, count in sorted(
                claim_types.items(), key=lambda x: x[1], reverse=True
            ):
                markdown_content += f"- **{ct.title()}:** {count} claims\n"

            markdown_content += "\n---\n*Generated from HCE analysis*"

            # Save to file
            filename = self._sanitize_filename(
                f"Claims_{video.title}_{video.source_id}.md"
            )
            file_path = self.exports_dir / filename

            with open(file_path, "w", encoding="utf-8") as f:
                f.write(markdown_content)

            # Track generated file in database
            self.db.track_generated_file(
                source_id=source_id,
                file_path=str(file_path),
                file_type="claims_report",
                file_format="md",
                summary_id=summary.summary_id,
            )

            logger.info(f"Generated claims report: {file_path}")
            return file_path

        except Exception as e:
            logger.error(f"Failed to generate claims report for {source_id}: {e}")
            return None

    def generate_contradiction_analysis(
        self, source_id: str, summary_id: str | None = None
    ) -> Path | None:
        """
        Generate contradiction analysis report from HCE data.

        Args:
            source_id: YouTube video ID
            summary_id: Specific summary ID (uses latest HCE summary if None)

        Returns:
            Path to generated contradiction report, or None if failed
        """
        try:
            # Get video and HCE summary data
            video = self.db.get_source(source_id)
            if not video:
                return None

            summaries = self.db.get_summaries_for_video(source_id)
            hce_summaries = [s for s in summaries if s.processing_type == "hce"]

            if not hce_summaries:
                return None

            summary = (
                hce_summaries[0]
                if not summary_id
                else next(
                    (s for s in hce_summaries if s.summary_id == summary_id), None
                )
            )

            if not summary or not summary.hce_data_json:
                return None

            # Note: hce_data_json is a JSONEncodedType field, already deserialized to dict
            hce_data = summary.hce_data_json
            claims = hce_data.get("claims", [])

            # Find contradictions
            contradictions = []
            for i, claim1 in enumerate(claims):
                for claim2 in claims[i + 1 :]:
                    # Check if claims contradict (would need NLI info)
                    if claim1.get("contradicts") == claim2.get("claim_id"):
                        contradictions.append((claim1, claim2))

            # Generate report
            markdown_content = """# Contradiction Analysis: {video.title}

**Source:** [{video.url}]({video.url})
**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**Total Claims Analyzed:** {len(claims)}
**Contradictions Found:** {len(contradictions)}

"""

            if contradictions:
                markdown_content += "## Contradictions\n\n"

                for i, (c1, c2) in enumerate(contradictions, 1):
                    markdown_content += f"### Contradiction {i}\n\n"
                    markdown_content += f"**Claim 1:** {c1.get('canonical', '')}\n"
                    markdown_content += f"- Type: {c1.get('claim_type', 'unknown')}\n"
                    markdown_content += f"- Tier: {c1.get('tier', 'unknown')}\n\n"

                    markdown_content += f"**Claim 2:** {c2.get('canonical', '')}\n"
                    markdown_content += f"- Type: {c2.get('claim_type', 'unknown')}\n"
                    markdown_content += f"- Tier: {c2.get('tier', 'unknown')}\n\n"

                    markdown_content += "---\n\n"
            else:
                markdown_content += "*No contradictions detected in the claims.*\n"

            # Save to file
            filename = self._sanitize_filename(
                f"Contradictions_{video.title}_{video.source_id}.md"
            )
            file_path = self.exports_dir / filename

            with open(file_path, "w", encoding="utf-8") as f:
                f.write(markdown_content)

            logger.info(f"Generated contradiction analysis: {file_path}")
            return file_path

        except Exception as e:
            logger.error(f"Failed to generate contradiction analysis: {e}")
            return None

    def generate_evidence_mapping(
        self, source_id: str, summary_id: str | None = None
    ) -> Path | None:
        """
        Generate evidence mapping file from HCE data.

        Args:
            source_id: YouTube video ID
            summary_id: Specific summary ID (uses latest HCE summary if None)

        Returns:
            Path to generated evidence mapping, or None if failed
        """
        try:
            # Get video and HCE summary data
            video = self.db.get_source(source_id)
            if not video:
                return None

            summaries = self.db.get_summaries_for_video(source_id)
            hce_summaries = [s for s in summaries if s.processing_type == "hce"]

            if not hce_summaries:
                return None

            summary = (
                hce_summaries[0]
                if not summary_id
                else next(
                    (s for s in hce_summaries if s.summary_id == summary_id), None
                )
            )

            if not summary or not summary.hce_data_json:
                return None

            # Note: hce_data_json is a JSONEncodedType field, already deserialized to dict
            hce_data = summary.hce_data_json
            claims = hce_data.get("claims", [])

            # Generate evidence mapping
            markdown_content = """# Evidence Mapping: {video.title}

**Source:** [{video.url}]({video.url})
**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Claims with Evidence

"""

            # Only include claims with evidence
            claims_with_evidence = [c for c in claims if c.get("evidence")]

            for claim in claims_with_evidence:
                canonical = claim.get("canonical", "")
                tier = claim.get("tier", "C")

                markdown_content += f"### Claim: {canonical}\n"
                markdown_content += f"**Tier:** {tier} | **Type:** {claim.get('claim_type', 'unknown')}\n\n"

                markdown_content += "**Supporting Evidence:**\n"
                for i, ev in enumerate(claim.get("evidence", []), 1):
                    text = ev.get("text", "")
                    segment_id = ev.get("segment_id", "unknown")
                    markdown_content += f'{i}. "{text}"\n'
                    markdown_content += f"   - Source: Segment {segment_id}\n"

                markdown_content += "\n---\n\n"

            # Save to file
            filename = self._sanitize_filename(
                f"Evidence_{video.title}_{video.source_id}.md"
            )
            file_path = self.exports_dir / filename

            with open(file_path, "w", encoding="utf-8") as f:
                f.write(markdown_content)

            logger.info(f"Generated evidence mapping: {file_path}")
            return file_path

        except Exception as e:
            logger.error(f"Failed to generate evidence mapping: {e}")
            return None

    # NOTE: generate_summary_markdown_from_pipeline() has been REMOVED
    # The unified pipeline now calls generate_summary_markdown() which reads from database
    # This ensures ONE consistent format using _generate_hce_markdown() for all summaries
    # See system2_orchestrator_mining.py line ~407 for the call site


# Convenience functions
def regenerate_video_files(
    source_id: str, output_dir: Path | None = None
) -> dict[str, any]:
    """Convenience function to regenerate all files for a video."""
    service = FileGenerationService(output_dir=output_dir)
    return service.regenerate_all_files(source_id)


def generate_transcript_from_db(
    source_id: str, output_dir: Path | None = None
) -> Path | None:
    """Convenience function to generate transcript markdown from database."""
    service = FileGenerationService(output_dir=output_dir)
    return service.generate_transcript_markdown(source_id)
