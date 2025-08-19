"""
File generation service for Knowledge System.

Regenerates markdown transcripts, MOC files, summaries, and export files from SQLite
database data. Supports multiple output formats and maintains compatibility with
existing file structures.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Union

import yaml

from ..database import DatabaseService
from ..logger import get_logger

logger = get_logger(__name__)


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
        self.db = database_service or DatabaseService()
        self.output_dir = Path(output_dir) if output_dir else Path("output")
        self.output_dir.mkdir(exist_ok=True)

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
            dir_path.mkdir(exist_ok=True)

    def generate_transcript_markdown(
        self,
        video_id: str,
        transcript_id: str | None = None,
        include_timestamps: bool = True,
        include_speakers: bool = True,
    ) -> Path | None:
        """
        Generate markdown transcript file from database data.

        Args:
            video_id: YouTube video ID
            transcript_id: Specific transcript ID (uses latest if None)
            include_timestamps: Include timestamp markers
            include_speakers: Include speaker labels if available

        Returns:
            Path to generated markdown file, or None if failed
        """
        try:
            # Get video and transcript data
            video = self.db.get_video(video_id)
            if not video:
                logger.error(f"Video {video_id} not found in database")
                return None

            transcripts = self.db.get_transcripts_for_video(video_id)
            if not transcripts:
                logger.error(f"No transcripts found for video {video_id}")
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
                "video_id": video.video_id,
                "url": video.url,
                "uploader": video.uploader,
                "upload_date": video.upload_date,
                "duration": video.duration_seconds,
                "language": transcript.language,
                "transcript_type": transcript.transcript_type,
                "is_manual": transcript.is_manual,
                "diarization_enabled": transcript.diarization_enabled,
                "processed_at": transcript.created_at.isoformat()
                if transcript.created_at
                else None,
                "tags": video.tags_json if video.tags_json else [],
                "categories": video.categories_json if video.categories_json else [],
            }

            # Build transcript content
            transcript_content = ""

            # Use speaker-labeled text if available and requested
            if include_speakers and transcript.transcript_text_with_speakers:
                transcript_content = transcript.transcript_text_with_speakers
            elif include_timestamps and transcript.transcript_segments_json:
                # Build timestamped transcript from segments
                segments = transcript.transcript_segments_json
                for segment in segments:
                    start_time = self._format_timestamp(segment.get("start", 0))
                    text = segment.get("text", "").strip()
                    if text:
                        transcript_content += f"[{start_time}] {text}\n\n"
            else:
                # Use plain transcript text
                transcript_content = transcript.transcript_text

            # Generate markdown content
            markdown_content = f"""---
{yaml.dump(frontmatter, default_flow_style=False)}---

# {video.title}

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
            filename = self._sanitize_filename(f"{video.title}_{video.video_id}.md")
            file_path = self.transcripts_dir / filename

            with open(file_path, "w", encoding="utf-8") as f:
                f.write(markdown_content)

            # Track generated file in database
            self.db.track_generated_file(
                video_id=video_id,
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
            logger.error(f"Failed to generate transcript markdown for {video_id}: {e}")
            return None

    def generate_summary_markdown(
        self, video_id: str, summary_id: str | None = None
    ) -> Path | None:
        """
        Generate markdown summary file from database data.

        Args:
            video_id: YouTube video ID
            summary_id: Specific summary ID (uses latest if None)

        Returns:
            Path to generated markdown file, or None if failed
        """
        try:
            # Get video and summary data
            video = self.db.get_video(video_id)
            if not video:
                logger.error(f"Video {video_id} not found in database")
                return None

            summaries = self.db.get_summaries_for_video(video_id)
            if not summaries:
                logger.error(f"No summaries found for video {video_id}")
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

            # Generate YAML frontmatter
            frontmatter = {
                "title": f"Summary of {video.title}",
                "video_id": video.video_id,
                "url": video.url,
                "summary_id": summary.summary_id,
                "llm_provider": summary.llm_provider,
                "llm_model": summary.llm_model,
                "processing_cost": summary.processing_cost,
                "total_tokens": summary.total_tokens,
                "compression_ratio": summary.compression_ratio,
                "created_at": summary.created_at.isoformat()
                if summary.created_at
                else None,
                "template_used": summary.template_used,
            }

            # Add summary metadata if available
            if summary.summary_metadata_json:
                frontmatter.update(summary.summary_metadata_json)

            # Generate markdown content
            markdown_content = f"""---
{yaml.dump(frontmatter, default_flow_style=False)}---

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
                f"Summary_{video.title}_{video.video_id}.md"
            )
            file_path = self.summaries_dir / filename

            with open(file_path, "w", encoding="utf-8") as f:
                f.write(markdown_content)

            # Track generated file in database
            self.db.track_generated_file(
                video_id=video_id,
                file_path=str(file_path),
                file_type="summary_md",
                file_format="md",
                summary_id=summary.summary_id,
            )

            logger.info(f"Generated summary markdown: {file_path}")
            return file_path

        except Exception as e:
            logger.error(f"Failed to generate summary markdown for {video_id}: {e}")
            return None

    def generate_moc_files(
        self, video_id: str | None = None, moc_id: str | None = None
    ) -> dict[str, Path]:
        """
        Generate MOC (Maps of Content) files from database data.

        Args:
            video_id: Specific video ID (generates for all videos if None)
            moc_id: Specific MOC extraction ID

        Returns:
            Dictionary mapping MOC type to generated file path
        """
        generated_files = {}

        try:
            # Get MOC extractions
            if video_id and moc_id:
                # Get specific MOC extraction
                moc_extractions = []  # Would need a get_moc_extraction method
            elif video_id:
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

            # Generate beliefs.yaml
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
        self, video_id: str, formats: list[str] = ["srt", "vtt", "txt"]
    ) -> dict[str, Path]:
        """
        Generate export files in various formats.

        Args:
            video_id: YouTube video ID
            formats: List of formats to generate ('srt', 'vtt', 'txt', 'json')

        Returns:
            Dictionary mapping format to generated file path
        """
        generated_files = {}

        try:
            # Get video and transcript data
            video = self.db.get_video(video_id)
            transcripts = self.db.get_transcripts_for_video(video_id)

            if not video or not transcripts:
                logger.error(f"Video or transcripts not found for {video_id}")
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
                        video_id=video_id,
                        file_path=str(file_path),
                        file_type=f"transcript_{format_type}",
                        file_format=format_type,
                        transcript_id=transcript.transcript_id,
                    )

            logger.info(f"Generated {len(generated_files)} export files for {video_id}")
            return generated_files

        except Exception as e:
            logger.error(f"Failed to generate export files for {video_id}: {e}")
            return {}

    def regenerate_all_files(self, video_id: str) -> dict[str, any]:
        """
        Regenerate all files for a specific video.

        Args:
            video_id: YouTube video ID

        Returns:
            Dictionary with paths to all generated files
        """
        results = {
            "video_id": video_id,
            "transcript_markdown": None,
            "summary_markdown": None,
            "export_files": {},
            "errors": [],
        }

        try:
            # Generate transcript markdown
            transcript_path = self.generate_transcript_markdown(video_id)
            if transcript_path:
                results["transcript_markdown"] = str(transcript_path)
            else:
                results["errors"].append("Failed to generate transcript markdown")

            # Generate summary markdown
            summary_path = self.generate_summary_markdown(video_id)
            if summary_path:
                results["summary_markdown"] = str(summary_path)
            else:
                results["errors"].append("Failed to generate summary markdown")

            # Generate export files
            export_files = self.generate_export_files(video_id)
            results["export_files"] = {
                fmt: str(path) for fmt, path in export_files.items()
            }

            if not export_files:
                results["errors"].append("Failed to generate export files")

            logger.info(f"Regenerated all files for video {video_id}")
            return results

        except Exception as e:
            logger.error(f"Failed to regenerate files for {video_id}: {e}")
            results["errors"].append(str(e))
            return results

    # Helper methods
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
        """Generate beliefs.yaml file."""
        try:
            # Convert to YAML format
            beliefs_yaml = {"beliefs": beliefs_data}

            file_path = self.moc_dir / "beliefs.yaml"
            with open(file_path, "w", encoding="utf-8") as f:
                yaml.dump(beliefs_yaml, f, default_flow_style=False, allow_unicode=True)

            return file_path

        except Exception as e:
            logger.error(f"Failed to generate beliefs.yaml: {e}")
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

            filename = self._sanitize_filename(f"{video.title}_{video.video_id}.srt")
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

            filename = self._sanitize_filename(f"{video.title}_{video.video_id}.vtt")
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
            filename = self._sanitize_filename(f"{video.title}_{video.video_id}.txt")
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
                    "video_id": video.video_id,
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
                    "diarization_segments": transcript.diarization_segments_json
                    if transcript.diarization_enabled
                    else None,
                },
                "metadata": {
                    "generated_at": datetime.now().isoformat(),
                    "source": "Knowledge System Database",
                },
            }

            filename = self._sanitize_filename(f"{video.title}_{video.video_id}.json")
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


# Convenience functions
def regenerate_video_files(
    video_id: str, output_dir: Path | None = None
) -> dict[str, any]:
    """Convenience function to regenerate all files for a video."""
    service = FileGenerationService(output_dir=output_dir)
    return service.regenerate_all_files(video_id)


def generate_transcript_from_db(
    video_id: str, output_dir: Path | None = None
) -> Path | None:
    """Convenience function to generate transcript markdown from database."""
    service = FileGenerationService(output_dir=output_dir)
    return service.generate_transcript_markdown(video_id)
