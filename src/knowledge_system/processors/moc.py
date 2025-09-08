"""
HCE-based Maps of Content (MOC) Processor

Drop-in replacement for legacy MOCProcessor using the Hybrid Claim Extractor (HCE).
Generates structured Maps of Content from markdown files using HCE entity extraction.
"""

import re
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

from ..database import DatabaseService
from ..logger import get_logger
from .base import BaseProcessor, ProcessorResult
from .hce.config_flex import PipelineConfigFlex, StageModelConfig
from .hce.types import EpisodeBundle, PipelineOutputs, Segment

logger = get_logger(__name__)


class SpeakerAppearance(BaseModel):
    """Represents a speaker appearance in a recording."""

    recording_file: str = Field(..., description="Recording file path")
    speaker_id: str = Field(..., description="Original speaker ID (e.g., SPEAKER_00)")
    total_duration: float = Field(
        default=0.0, description="Total speaking time in seconds"
    )
    segment_count: int = Field(default=0, description="Number of speaking segments")
    confidence: float = Field(
        default=1.0, description="Confidence in speaker identification"
    )
    assigned_date: datetime = Field(
        default_factory=datetime.now, description="When assignment was made"
    )


class Person(BaseModel):
    """Represents a person mentioned in documents."""

    name: str = Field(..., description="Person's name")
    mentions: list[str] = Field(
        default_factory=list, description="Files where person is mentioned"
    )
    first_mention: str | None = Field(
        default=None, description="First file where person appears"
    )
    mention_count: int = Field(default=0, description="Total number of mentions")

    # Speaker-related fields
    speaker_appearances: list[SpeakerAppearance] = Field(
        default_factory=list,
        description="Appearances as identified speaker in recordings",
    )
    voice_learned: bool = Field(
        default=False, description="Whether voice characteristics have been learned"
    )
    speaker_confidence: float = Field(
        default=0.0, description="Overall confidence in speaker identification"
    )
    total_speaking_time: float = Field(
        default=0.0, description="Total speaking time across all recordings (seconds)"
    )

    def add_speaker_appearance(self, appearance: SpeakerAppearance) -> None:
        """Add a new speaker appearance."""
        self.speaker_appearances.append(appearance)
        self.total_speaking_time += appearance.total_duration

        # Update overall confidence (weighted average)
        if self.speaker_appearances:
            total_confidence = sum(app.confidence for app in self.speaker_appearances)
            self.speaker_confidence = total_confidence / len(self.speaker_appearances)

    def get_recording_count(self) -> int:
        """Get the number of recordings this person appears in as a speaker."""
        return len(self.speaker_appearances)

    def get_average_speaking_time(self) -> float:
        """Get average speaking time per recording."""
        if not self.speaker_appearances:
            return 0.0
        return self.total_speaking_time / len(self.speaker_appearances)


class Tag(BaseModel):
    """Represents a tag/concept found in documents."""

    name: str = Field(..., description="Tag name")
    category: str = Field(default="general", description="Tag category")
    files: list[str] = Field(
        default_factory=list, description="Files containing this tag"
    )
    count: int = Field(default=0, description="Number of occurrences")


class MentalModel(BaseModel):
    """Represents a mental model or framework."""

    name: str = Field(..., description="Model name")
    description: str = Field(..., description="Model description")
    source_files: list[str] = Field(
        default_factory=list, description="Files referencing this model"
    )
    related_concepts: list[str] = Field(
        default_factory=list, description="Related concepts"
    )


class JargonEntry(BaseModel):
    """Represents a jargon term or technical term."""

    term: str = Field(..., description="The jargon term")
    definition: str = Field(default="", description="Definition or explanation")
    context: str = Field(default="", description="Context where term appears")
    files: list[str] = Field(
        default_factory=list, description="Files containing this term"
    )


class Claim(BaseModel):
    """Represents a claim extracted from content."""

    statement: str = Field(..., description="The claim statement")
    sources: list[str] = Field(default_factory=list, description="Source files")
    epistemic_weight: float = Field(
        default=0.5, ge=0.0, le=1.0, description="Confidence in claim"
    )
    contradictions: list[str] = Field(
        default_factory=list, description="Contradicting statements"
    )
    supporting_evidence: list[str] = Field(
        default_factory=list, description="Supporting evidence"
    )


class MOCData(BaseModel):
    """Container for all MOC data."""

    people: dict[str, Person] = Field(default_factory=dict)
    tags: dict[str, Tag] = Field(default_factory=dict)
    mental_models: dict[str, MentalModel] = Field(default_factory=dict)
    jargon: dict[str, JargonEntry] = Field(default_factory=dict)
    claims: list[Claim] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=datetime.now)
    source_files: list[str] = Field(default_factory=list)


class MOCProcessor(BaseProcessor):
    """HCE-based processor for generating Maps of Content from markdown files."""

    @property
    def supported_formats(self) -> list[str]:
        return [".md", ".txt"]

    def validate_input(self, input_data: Any) -> bool:
        """
        Validate that the input data is suitable for MOC processing.

        Args:
            input_data: The data to validate (file path, directory, or list)

        Returns:
            True if input is valid, False otherwise
        """
        from ..utils.validation import validate_file_input

        return validate_file_input(
            input_data, self.supported_formats, allow_directories=True
        )

    def __init__(self) -> None:
        super().__init__()
        # Configure HCE pipeline for entity extraction
        self.hce_config = PipelineConfigFlex(
            models=StageModelConfig(
                miner="ollama://qwen2.5:14b-instruct",
                judge="openai://gpt-4o-mini-2024-07-18",
                embedder="local://bge-small-en-v1.5",
                reranker="local://bge-reranker-base",
            )
        )
        self.db_service = None
        try:
            self.db_service = DatabaseService()
        except Exception as e:
            logger.warning(f"Database service not available: {e}")

    def _process_file_with_hce(self, file_path: Path) -> PipelineOutputs:
        """Process a single file through HCE pipeline."""
        from .summarizer import HCEPipeline

        # Read file content
        content = file_path.read_text(encoding="utf-8")

        # Convert to EpisodeBundle
        episode_id = f"moc_{file_path.stem}"
        paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]

        segments = []
        for i, para in enumerate(paragraphs):
            segments.append(
                Segment(
                    episode_id=episode_id,
                    segment_id=f"seg_{i:04d}",
                    speaker="narrator",
                    t0=f"{i*10:06d}",
                    t1=f"{(i+1)*10:06d}",
                    text=para,
                )
            )

        episode = EpisodeBundle(episode_id=episode_id, segments=segments)

        # Run HCE pipeline
        pipeline = HCEPipeline(self.hce_config)
        return pipeline.process(episode)

    def _extract_legacy_patterns(
        self, content: str, file_name: str, moc_data: MOCData
    ) -> None:
        """Extract patterns using legacy regex for backward compatibility."""
        # Extract people (legacy pattern)
        people_pattern = r"(?:^|\s)([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)"
        for match in re.finditer(people_pattern, content):
            name = match.group(1).strip()
            if len(name) > 2 and " " in name:  # Basic validation
                if name not in moc_data.people:
                    moc_data.people[name] = Person(name=name, first_mention=file_name)
                moc_data.people[name].mentions.append(file_name)
                moc_data.people[name].mention_count += 1

        # Extract tags (legacy pattern)
        tag_pattern = r"#(\w+)"
        for match in re.finditer(tag_pattern, content):
            tag = match.group(1)
            if tag not in moc_data.tags:
                moc_data.tags[tag] = Tag(name=tag)
            moc_data.tags[tag].files.append(file_name)
            moc_data.tags[tag].count += 1

        # Extract mental models (legacy pattern)
        model_indicators = ["framework", "model", "principle", "theory", "approach"]
        sentences = content.split(".")
        for sentence in sentences:
            sentence_lower = sentence.lower()
            for indicator in model_indicators:
                if indicator in sentence_lower:
                    # Simple extraction of model name
                    words = sentence.strip().split()
                    for i, word in enumerate(words):
                        if word.lower() == indicator and i > 0:
                            model_name = " ".join(words[max(0, i - 2) : i + 1])
                            if len(model_name) > 5:
                                if model_name not in moc_data.mental_models:
                                    moc_data.mental_models[model_name] = MentalModel(
                                        name=model_name,
                                        description=sentence.strip(),
                                    )
                                moc_data.mental_models[model_name].source_files.append(
                                    file_name
                                )
                            break

    def process(
        self,
        input_data: Any,
        dry_run: bool = False,
        template: str | Path | None = None,
        write_obsidian_pages: bool = False,
        **kwargs: Any,
    ) -> ProcessorResult:
        """Process input files to generate Maps of Content using HCE."""
        theme = kwargs.get("theme", "topical")
        depth = kwargs.get("depth", 3)
        include_claims = kwargs.get("include_claims", True)
        use_database_entities = kwargs.get("use_database_entities", True)

        try:
            # Convert single input to list
            if isinstance(input_data, (str, Path)):
                input_files = [Path(input_data)]
            else:
                input_files = [Path(f) for f in input_data]

            if not input_files:
                return ProcessorResult(
                    success=False, errors=["No input files provided"], dry_run=dry_run
                )

            if dry_run:
                template_info = f" with template '{template}'" if template else ""
                return ProcessorResult(
                    success=True,
                    data=f"[DRY RUN] Would generate MOC from {len(input_files)} files with theme '{theme}', depth {depth}, claims {include_claims}{template_info}.",
                    metadata={
                        "files_count": len(input_files),
                        "theme": theme,
                        "depth": depth,
                        "include_claims": include_claims,
                        "template": str(template) if template else None,
                        "dry_run": True,
                    },
                    dry_run=True,
                )

            # Process all files
            moc_data = MOCData(source_files=[str(f) for f in input_files])

            # Check if files have HCE data in database
            has_hce_data = False
            if use_database_entities and self.db_service:
                try:
                    # Try to load HCE data from database
                    for file_path in input_files:
                        video_id = f"file_{file_path.stem}"
                        summary = self.db_service.get_latest_summary(video_id)
                        if (
                            summary
                            and summary.metadata
                            and "hce_data" in summary.metadata
                        ):
                            has_hce_data = True
                            hce_data = summary.metadata["hce_data"]

                            # Extract people
                            for person in hce_data.get("people", []):
                                name = person.get("normalized") or person.get("surface")
                                if name and name not in moc_data.people:
                                    moc_data.people[name] = Person(
                                        name=name, first_mention=str(file_path.name)
                                    )
                                moc_data.people[name].mentions.append(
                                    str(file_path.name)
                                )
                                moc_data.people[name].mention_count += 1

                            # Extract concepts as tags
                            for concept in hce_data.get("concepts", []):
                                tag_name = concept.get("name")
                                if tag_name and tag_name not in moc_data.tags:
                                    moc_data.tags[tag_name] = Tag(
                                        name=tag_name, category="concept"
                                    )
                                moc_data.tags[tag_name].files.append(
                                    str(file_path.name)
                                )
                                moc_data.tags[tag_name].count += 1

                                # Also add as mental model
                                if tag_name not in moc_data.mental_models:
                                    moc_data.mental_models[tag_name] = MentalModel(
                                        name=tag_name,
                                        description=concept.get("definition", ""),
                                    )
                                moc_data.mental_models[tag_name].source_files.append(
                                    str(file_path.name)
                                )

                            # Extract jargon
                            for term in hce_data.get("jargon", []):
                                term_name = term.get("term")
                                if term_name and term_name not in moc_data.jargon:
                                    moc_data.jargon[term_name] = JargonEntry(
                                        term=term_name,
                                        definition=term.get("definition", ""),
                                    )
                                moc_data.jargon[term_name].files.append(
                                    str(file_path.name)
                                )

                            # Extract claims from HCE data
                            if include_claims:
                                for claim in hce_data.get("claims", []):
                                    if claim.get("tier") in ["A", "B"]:
                                        claim_obj = Claim(
                                            statement=claim.get("canonical"),
                                            sources=[str(file_path.name)],
                                            epistemic_weight=claim.get(
                                                "scores", {}
                                            ).get("confidence", 0.5),
                                        )
                                        moc_data.claims.append(claim_obj)

                except Exception as e:
                    logger.warning(f"Could not load HCE data from database: {e}")

            # If no HCE data, process files directly or use legacy patterns
            if not has_hce_data:
                for file_path in input_files:
                    if not file_path.exists():
                        logger.warning(f"File not found: {file_path}")
                        continue

                    try:
                        # Try HCE processing first
                        outputs = self._process_file_with_hce(file_path)

                        # Extract entities from HCE output
                        for person in outputs.people:
                            name = person.normalized or person.surface
                            if name not in moc_data.people:
                                moc_data.people[name] = Person(
                                    name=name, first_mention=str(file_path.name)
                                )
                            moc_data.people[name].mentions.append(str(file_path.name))
                            moc_data.people[name].mention_count += 1

                        for concept in outputs.concepts:
                            if concept.name not in moc_data.tags:
                                moc_data.tags[concept.name] = Tag(
                                    name=concept.name, category="concept"
                                )
                            moc_data.tags[concept.name].files.append(
                                str(file_path.name)
                            )
                            moc_data.tags[concept.name].count += 1

                            if concept.name not in moc_data.mental_models:
                                moc_data.mental_models[concept.name] = MentalModel(
                                    name=concept.name,
                                    description=concept.definition or "",
                                )
                            moc_data.mental_models[concept.name].source_files.append(
                                str(file_path.name)
                            )

                        for jargon in outputs.jargon:
                            if jargon.term not in moc_data.jargon:
                                moc_data.jargon[jargon.term] = JargonEntry(
                                    term=jargon.term, definition=jargon.definition or ""
                                )
                            moc_data.jargon[jargon.term].files.append(
                                str(file_path.name)
                            )

                        # Extract claims from outputs
                        if include_claims:
                            for claim in outputs.claims:
                                if claim.tier in ["A", "B"]:
                                    claim_obj = Claim(
                                        statement=claim.canonical,
                                        sources=[str(file_path.name)],
                                        epistemic_weight=claim.scores.get(
                                            "confidence", 0.5
                                        ),
                                    )
                                    moc_data.claims.append(claim_obj)

                    except Exception as e:
                        logger.warning(
                            f"HCE processing failed for {file_path}, using legacy patterns: {e}"
                        )
                        # Fall back to legacy pattern extraction
                        content = file_path.read_text(encoding="utf-8")
                        self._extract_legacy_patterns(
                            content, str(file_path.name), moc_data
                        )

            # Generate MOC files
            output_files = self._generate_moc_files(moc_data, template)

            # Optionally generate Obsidian dataview pages
            if write_obsidian_pages:
                obsidian_files = self._generate_obsidian_pages()
                output_files.update(obsidian_files)

            return ProcessorResult(
                success=True,
                data=output_files,
                metadata={
                    "people_found": len(moc_data.people),
                    "tags_found": len(moc_data.tags),
                    "mental_models_found": len(moc_data.mental_models),
                    "jargon_found": len(moc_data.jargon),
                    "claims_found": len(moc_data.claims),
                    "files_processed": len(input_files),
                },
                dry_run=False,
            )

        except Exception as e:
            logger.error(f"MOC generation failed: {e}")
            return ProcessorResult(
                success=False,
                errors=[str(e)],
                dry_run=dry_run,
            )

    def _generate_moc_files(
        self, moc_data: MOCData, template: Path | None = None
    ) -> dict[str, str]:
        """Generate the actual MOC files."""
        files = {}

        # People.md
        people_content = ["# People\n\n"]
        people_content.append(
            f"*Generated from {len(moc_data.source_files)} source files on {moc_data.generated_at.strftime('%Y-%m-%d')}*\n\n"
        )

        for name, person in sorted(moc_data.people.items()):
            people_content.append(f"## {name}\n")
            people_content.append(f"- First mentioned in: {person.first_mention}\n")
            people_content.append(f"- Total mentions: {person.mention_count}\n")
            people_content.append("- Appears in:\n")
            for file in person.mentions:
                people_content.append(f"  - [[{Path(file).stem}]]\n")
            people_content.append("\n")

        files["People.md"] = "".join(people_content)

        # Tags.md
        tags_content = ["# Tags\n\n"]
        tags_content.append(
            f"*Generated from {len(moc_data.source_files)} source files on {moc_data.generated_at.strftime('%Y-%m-%d')}*\n\n"
        )

        # Group by category
        categories: dict[str, list[Tag]] = {}
        for tag in moc_data.tags.values():
            if tag.category not in categories:
                categories[tag.category] = []
            categories[tag.category].append(tag)

        for category, tags in sorted(categories.items()):
            tags_content.append(f"## {category.title()}\n\n")
            for tag in sorted(tags, key=lambda t: t.name):
                tags_content.append(f"### #{tag.name}\n")
                tags_content.append(f"- Occurrences: {tag.count}\n")
                tags_content.append("- Found in:\n")
                for file in tag.files[:5]:  # Limit to 5 files
                    tags_content.append(f"  - [[{Path(file).stem}]]\n")
                if len(tag.files) > 5:
                    tags_content.append(f"  - ...and {len(tag.files) - 5} more\n")
                tags_content.append("\n")

        files["Tags.md"] = "".join(tags_content)

        # Mental_Models.md
        models_content = ["# Mental Models\n\n"]
        models_content.append(
            f"*Generated from {len(moc_data.source_files)} source files on {moc_data.generated_at.strftime('%Y-%m-%d')}*\n\n"
        )

        for name, model in sorted(moc_data.mental_models.items()):
            models_content.append(f"## {name}\n\n")
            if model.description:
                models_content.append(f"{model.description}\n\n")
            models_content.append("### Sources:\n")
            for file in model.source_files:
                models_content.append(f"- [[{Path(file).stem}]]\n")
            if model.related_concepts:
                models_content.append("\n### Related Concepts:\n")
                for concept in model.related_concepts:
                    models_content.append(f"- {concept}\n")
            models_content.append("\n")

        files["Mental_Models.md"] = "".join(models_content)

        # Jargon.md
        jargon_content = ["# Jargon & Technical Terms\n\n"]
        jargon_content.append(
            f"*Generated from {len(moc_data.source_files)} source files on {moc_data.generated_at.strftime('%Y-%m-%d')}*\n\n"
        )

        for term, entry in sorted(moc_data.jargon.items()):
            jargon_content.append(f"## {term}\n\n")
            if entry.definition:
                jargon_content.append(f"**Definition:** {entry.definition}\n\n")
            if entry.context:
                jargon_content.append(f"**Context:** {entry.context}\n\n")
            jargon_content.append("**Found in:**\n")
            for file in entry.files:
                jargon_content.append(f"- [[{Path(file).stem}]]\n")
            jargon_content.append("\n")

        files["Jargon.md"] = "".join(jargon_content)

        # claims.yaml
        if moc_data.claims:
            claims_data = {
                "claims": [
                    {
                        "statement": belief.statement,
                        "sources": belief.sources,
                        "epistemic_weight": belief.epistemic_weight,
                        "supporting_evidence": belief.supporting_evidence,
                        "contradictions": belief.contradictions,
                    }
                    for belief in moc_data.claims
                ],
                "metadata": {
                    "generated_at": moc_data.generated_at.isoformat(),
                    "source_files": moc_data.source_files,
                    "total_claims": len(moc_data.claims),
                },
            }
            files["claims.yaml"] = yaml.dump(claims_data, default_flow_style=False)

        return files

    def add_speakers_to_people_database(
        self,
        speaker_assignments: dict[str, str],
        source_file: str,
        speaker_data_list: list = None,
    ) -> None:
        """
        Add identified speakers to People database.

        Args:
            speaker_assignments: Dictionary mapping speaker IDs to names
            source_file: Source recording file path
            speaker_data_list: Optional list of SpeakerData objects with timing info
        """
        try:
            pass

            # Load existing MOC data or create new
            moc_data = MOCData()

            # Add each speaker to the people database
            for speaker_id, assigned_name in speaker_assignments.items():
                # Find speaker data if available
                speaker_data = None
                if speaker_data_list:
                    speaker_data = next(
                        (s for s in speaker_data_list if s.speaker_id == speaker_id),
                        None,
                    )

                # Create or update person entry
                if assigned_name not in moc_data.people:
                    moc_data.people[assigned_name] = Person(
                        name=assigned_name, first_mention=Path(source_file).name
                    )

                person = moc_data.people[assigned_name]

                # Add speaker appearance
                appearance = SpeakerAppearance(
                    recording_file=source_file,
                    speaker_id=speaker_id,
                    total_duration=speaker_data.total_duration if speaker_data else 0.0,
                    segment_count=speaker_data.segment_count if speaker_data else 0,
                    confidence=speaker_data.confidence_score if speaker_data else 1.0,
                )

                person.add_speaker_appearance(appearance)

                # Mark voice as learned if confidence is high
                if appearance.confidence > 0.8:
                    person.voice_learned = True

                # Add to mentions if not already there
                if source_file not in person.mentions:
                    person.mentions.append(source_file)
                    person.mention_count += 1

            logger.info(f"Added {len(speaker_assignments)} speakers to People database")

        except Exception as e:
            logger.error(f"Error adding speakers to People database: {e}")

    def update_people_yaml_with_speakers(
        self, people_data: dict, speaker_assignments: dict[str, str], source_file: str
    ) -> dict:
        """
        Update People.md and YAML with speaker information.

        Args:
            people_data: Existing people data dictionary
            speaker_assignments: Dictionary mapping speaker IDs to names
            source_file: Source recording file path

        Returns:
            Updated people data dictionary
        """
        try:
            updated_people = people_data.copy()

            for speaker_id, assigned_name in speaker_assignments.items():
                # Create or update person entry
                if assigned_name not in updated_people:
                    updated_people[assigned_name] = {
                        "name": assigned_name,
                        "mentions": [],
                        "first_mention": Path(source_file).name,
                        "mention_count": 0,
                        "speaker_appearances": [],
                        "voice_learned": False,
                        "speaker_confidence": 0.0,
                        "total_speaking_time": 0.0,
                    }

                person = updated_people[assigned_name]

                # Add recording to mentions if not already there
                if source_file not in person["mentions"]:
                    person["mentions"].append(source_file)
                    person["mention_count"] += 1

                # Add speaker appearance
                appearance = {
                    "recording_file": source_file,
                    "speaker_id": speaker_id,
                    "assigned_date": datetime.now().isoformat(),
                }

                if "speaker_appearances" not in person:
                    person["speaker_appearances"] = []

                person["speaker_appearances"].append(appearance)

                logger.debug(
                    f"Updated person '{assigned_name}' with speaker appearance"
                )

            return updated_people

        except Exception as e:
            logger.error(f"Error updating people YAML with speakers: {e}")
            return people_data

    def generate_speaker_enhanced_people_md(self, moc_data: MOCData) -> str:
        """
        Generate enhanced People.md with speaker information.

        Args:
            moc_data: MOC data containing people with speaker info

        Returns:
            Enhanced People.md content as string
        """
        try:
            content = ["# People\n\n"]
            content.append(
                f"*Generated from {len(moc_data.source_files)} source files on {moc_data.generated_at.strftime('%Y-%m-%d')}*\n\n"
            )

            # Sort people by total speaking time (most active speakers first)
            sorted_people = sorted(
                moc_data.people.items(),
                key=lambda x: x[1].total_speaking_time,
                reverse=True,
            )

            for name, person in sorted_people:
                content.append(f"## {name}\n\n")

                # Basic information
                content.append(f"- **First mentioned in:** {person.first_mention}\n")
                content.append(f"- **Total mentions:** {person.mention_count}\n")

                # Speaker information
                if person.speaker_appearances:
                    content.append(
                        f"- **Recordings as speaker:** {person.get_recording_count()}\n"
                    )

                    # Format total speaking time
                    total_minutes = int(person.total_speaking_time // 60)
                    total_seconds = int(person.total_speaking_time % 60)
                    content.append(
                        f"- **Total speaking time:** {total_minutes}:{total_seconds:02d}\n"
                    )

                    if person.get_recording_count() > 1:
                        avg_time = person.get_average_speaking_time()
                        avg_minutes = int(avg_time // 60)
                        avg_seconds = int(avg_time % 60)
                        content.append(
                            f"- **Average speaking time:** {avg_minutes}:{avg_seconds:02d} per recording\n"
                        )

                    content.append(
                        f"- **Speaker confidence:** {person.speaker_confidence:.1%}\n"
                    )

                    if person.voice_learned:
                        content.append("- **Voice learned:** ✅ Yes\n")
                    else:
                        content.append("- **Voice learned:** ❌ No\n")

                # File appearances
                content.append("\n### Appears in:\n")
                for file in person.mentions:
                    content.append(f"- [[{Path(file).stem}]]\n")

                # Speaker appearances details
                if person.speaker_appearances:
                    content.append("\n### Speaker Appearances:\n")
                    for appearance in person.speaker_appearances:
                        recording_name = Path(appearance.recording_file).stem
                        duration_min = int(appearance.total_duration // 60)
                        duration_sec = int(appearance.total_duration % 60)

                        content.append(
                            f"- **[[{recording_name}]]**: {duration_min}:{duration_sec:02d} "
                            f"({appearance.segment_count} segments, {appearance.confidence:.1%} confidence)\n"
                        )

                content.append("\n")

            return "".join(content)

        except Exception as e:
            logger.error(f"Error generating speaker-enhanced People.md: {e}")
            return "# People\n\nError generating content."

    def _generate_obsidian_pages(self) -> dict[str, str]:
        """Generate Obsidian MOC pages with dataview queries."""
        from ..utils.obsidian_moc_generator import generate_all_obsidian_pages

        obsidian_files = generate_all_obsidian_pages()

        logger.info(
            f"Generated {len(obsidian_files)} Obsidian MOC pages with dataview queries"
        )
        return obsidian_files
