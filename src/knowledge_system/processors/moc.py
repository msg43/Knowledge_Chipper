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
from ..errors import MOCGenerationError
from ..logger import get_logger
from .base import BaseProcessor, ProcessorResult
from .hce.config_flex import PipelineConfigFlex, StageModelConfig
from .hce.types import EpisodeBundle, PipelineOutputs, Segment

logger = get_logger(__name__)


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


class Belief(BaseModel):
    """Represents a belief or claim extracted from content."""

    statement: str = Field(..., description="The belief statement")
    sources: list[str] = Field(default_factory=list, description="Source files")
    epistemic_weight: float = Field(
        default=0.5, ge=0.0, le=1.0, description="Confidence in belief"
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
    beliefs: list[Belief] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=datetime.now)
    source_files: list[str] = Field(default_factory=list)


class MOCProcessor(BaseProcessor):
    """HCE-based processor for generating Maps of Content from markdown files."""

    @property
    def supported_formats(self) -> list[str]:
        return [".md", ".txt"]

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
        **kwargs: Any,
    ) -> ProcessorResult:
        """Process input files to generate Maps of Content using HCE."""
        theme = kwargs.get("theme", "topical")
        depth = kwargs.get("depth", 3)
        include_beliefs = kwargs.get("include_beliefs", True)

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
                    data=f"[DRY RUN] Would generate MOC from {len(input_files)} files with theme '{theme}', depth {depth}, beliefs {include_beliefs}{template_info}.",
                    metadata={
                        "files_count": len(input_files),
                        "theme": theme,
                        "depth": depth,
                        "include_beliefs": include_beliefs,
                        "template": str(template) if template else None,
                        "dry_run": True,
                    },
                    dry_run=True,
                )

            # Process all files
            moc_data = MOCData(source_files=[str(f) for f in input_files])

            # Check if files have HCE data in database
            has_hce_data = False
            if self.db_service:
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

                            # Extract beliefs from claims
                            if include_beliefs:
                                for claim in hce_data.get("claims", []):
                                    if claim.get("tier") in ["A", "B"]:
                                        belief = Belief(
                                            statement=claim.get("canonical"),
                                            sources=[str(file_path.name)],
                                            epistemic_weight=claim.get(
                                                "scores", {}
                                            ).get("confidence", 0.5),
                                        )
                                        moc_data.beliefs.append(belief)

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

                        # Extract beliefs from claims
                        if include_beliefs:
                            for claim in outputs.claims:
                                if claim.tier in ["A", "B"]:
                                    belief = Belief(
                                        statement=claim.canonical,
                                        sources=[str(file_path.name)],
                                        epistemic_weight=claim.scores.get(
                                            "confidence", 0.5
                                        ),
                                    )
                                    moc_data.beliefs.append(belief)

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

            return ProcessorResult(
                success=True,
                data=output_files,
                metadata={
                    "people_found": len(moc_data.people),
                    "tags_found": len(moc_data.tags),
                    "mental_models_found": len(moc_data.mental_models),
                    "jargon_found": len(moc_data.jargon),
                    "beliefs_found": len(moc_data.beliefs),
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

        # beliefs.yaml
        if moc_data.beliefs:
            beliefs_data = {
                "beliefs": [
                    {
                        "statement": belief.statement,
                        "sources": belief.sources,
                        "epistemic_weight": belief.epistemic_weight,
                        "supporting_evidence": belief.supporting_evidence,
                        "contradictions": belief.contradictions,
                    }
                    for belief in moc_data.beliefs
                ],
                "metadata": {
                    "generated_at": moc_data.generated_at.isoformat(),
                    "source_files": moc_data.source_files,
                    "total_beliefs": len(moc_data.beliefs),
                },
            }
            files["beliefs.yaml"] = yaml.dump(beliefs_data, default_flow_style=False)

        return files
