"""
Maps of Content (MOC) Processor

Generates structured Maps of Content from markdown files, including:
- People pages with links to mentions
- Tags pages with categorization
- Mental Models pages with definitions
- Jargon pages with explanations
- Belief YAMLs with sources and epistemic weight
"""

import re
import yaml
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field

from ..errors import MOCGenerationError
from ..logger import get_logger
from .base import BaseProcessor, ProcessorResult

logger = get_logger(__name__)


class Person(BaseModel):
    """Represents a person mentioned in documents."""

    name: str = Field(..., description="Person's name")
    mentions: List[str] = Field(
        default_factory=list, description="Files where person is mentioned"
    )
    first_mention: Optional[str] = Field(
        default=None, description="First file where person appears"
    )
    mention_count: int = Field(
    default=0, description="Total number of mentions")


class Tag(BaseModel):
    """Represents a tag used in documents."""

    name: str = Field(..., description="Tag name")
    files: List[str] = Field(
    default_factory=list,
     description="Files using this tag")
    usage_count: int = Field(default=0, description="Total usage count")


class MentalModel(BaseModel):
    """Represents a mental model mentioned in documents."""

    name: str = Field(..., description="Mental model name")
    definition: Optional[str] = Field(
        default=None, description="Definition or explanation"
    )
    files: List[str] = Field(
        default_factory=list, description="Files mentioning this model"
    )
    sources: List[str] = Field(
        default_factory=list, description="Sources for this model"
    )


class JargonTerm(BaseModel):
    """Represents a jargon term found in documents."""

    term: str = Field(..., description="Jargon term")
    definition: Optional[str] = Field(
        default=None, description="Definition or explanation"
    )
    files: List[str] = Field(
        default_factory=list, description="Files containing this term"
    )
    context: List[str] = Field(
    default_factory=list,
     description="Context sentences")


class Belief(BaseModel):
    """Represents a belief with epistemic weight and sources."""

    claim: str = Field(..., description="The belief or claim")
    sources: List[str] = Field(
        default_factory=list, description="Sources supporting this claim"
    )
    counterclaims: List[str] = Field(
        default_factory=list, description="Counterclaims or opposing views"
    )
    epistemic_weight: float = Field(
        default=0.5, ge=0.0, le=1.0, description="Confidence level (0-1)"
    )
    evidence_quality: str = Field(
    default="medium",
     description="Quality of evidence")
    last_updated: datetime = Field(
        default_factory=datetime.now, description="When belief was last updated"
    )


class MOCData(BaseModel):
    """Complete MOC data structure."""

    people: List[Person] = Field(default_factory=list)
    tags: List[Tag] = Field(default_factory=list)
    mental_models: List[MentalModel] = Field(default_factory=list)
    jargon: List[JargonTerm] = Field(default_factory=list)
    beliefs: List[Belief] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=datetime.now)
    source_files: List[str] = Field(default_factory=list)


class MOCProcessor(BaseProcessor):
    """Processor for generating Maps of Content from markdown files."""

    def __init__(self, name: Optional[str] = None):
        """Initialize the MOC processor."""
        super().__init__(name or "moc")

        # Patterns for extracting different types of content
        self.person_patterns = [
            r"\b[A-Z][a-z]+ [A-Z][a-z]+\b",  # First Last
            r"\b[A-Z][a-z]+ [A-Z]\. [A-Z][a-z]+\b",  # First M. Last
            r"\b[A-Z][a-z]+ [A-Z][a-z]+ [A-Z][a-z]+\b",  # First Middle Last
        ]

        # Common false positives to exclude
        self.person_false_positives = {
            "key points",
            "mental models",
            "systems thinking",
            "first principles",
            "people mentioned",
            "full transcript",
            "sample knowledge",
            "test author",
            "knowledge system",
            "sample knowledge article",
            "john doe",
            "jane smith",
        }

        self.tag_patterns = [
            r"#(\w+)",  # #tag
            r"\[\[(\w+)\]\]",  # [[tag]]
            r"\*\*(\w+)\*\*",  # **tag**
        ]

        self.mental_model_patterns = [
            r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+(?:model|framework|theory|principle)\b",
            r"\*\*([^*]+)\*\*\s*[-:]\s*(?:mental model|framework|theory)",
        ]

        self.jargon_patterns = [
            r"\b([A-Z][A-Z]+)\b",  # ACRONYMS
            r"\*\*([^*]+)\*\*\s*[-:]\s*([^.\n]+)",  # **term** - definition
            r"`([^`]+)`\s*[-:]\s*([^.\n]+)",  # `term` - definition
        ]

    @property
    def supported_formats(self) -> List[str]:
        """Return list of supported input formats."""
        return [".md", ".txt"]

    def validate_input(self, input_data: Any) -> bool:
        """Validate that the input data is suitable for processing."""
        if isinstance(input_data, (str, Path)):
            path = Path(input_data)
            return (
                path.exists()
                and path.is_file()
                and path.suffix.lower() in self.supported_formats
            )
        elif isinstance(input_data, list):
            return all(self.validate_input(item) for item in input_data)
        return False

    def can_process(self, input_path: Union[str, Path]) -> bool:
        """Check if this processor can handle the given input."""
        path = Path(input_path)
        return path.suffix.lower() in self.supported_formats

    def process(
        self,
        input_data: Any,
        dry_run: bool = False,
        template: Optional[Union[str, Path]] = None,
        **kwargs: Any,
    ) -> ProcessorResult:
        """Process input and generate MOC."""
        # Extract additional parameters from kwargs
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

            for file_path in input_files:
                if not file_path.exists():
                    logger.warning(f"File not found: {file_path}")
                    continue

                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()

                    # Extract different types of content
                    self._extract_people(content, str(file_path), moc_data)
                    self._extract_tags(content, str(file_path), moc_data)
                    self._extract_mental_models(
                        content, str(file_path), moc_data)
                    self._extract_jargon(content, str(file_path), moc_data)

                    if include_beliefs:
                        self._extract_beliefs(
    content, str(file_path), moc_data)

                except Exception as e:
                    logger.error(f"Error processing file {file_path}: {e}")
                    continue

            # Generate MOC files
            moc_files = self._generate_moc_files(
                moc_data, theme, depth, template)

            return ProcessorResult(
                success=True,
                data=moc_files,
                metadata={
                    "files_processed": len(input_files),
                    "people_found": len(moc_data.people),
                    "tags_found": len(moc_data.tags),
                    "mental_models_found": len(moc_data.mental_models),
                    "jargon_terms_found": len(moc_data.jargon),
                    "beliefs_found": len(moc_data.beliefs),
                    "theme": theme,
                    "depth": depth,
                    "include_beliefs": include_beliefs,
                    "template": str(template) if template else None,
                },
                dry_run=dry_run,
            )

        except Exception as e:
            logger.error(f"Error in MOC processing: {e}")
            return ProcessorResult(
                success=False, errors=[f"MOC generation failed: {e}"], dry_run=dry_run
            )

    def _extract_people(self, content: str, filename: str,
                        moc_data: MOCData) -> None:
        """Extract people mentioned in content."""
        for pattern in self.person_patterns:
            matches = re.finditer(pattern, content)
            for match in matches:
                name = match.group()
                # Skip common false positives
                if name.lower() in self.person_false_positives:
                    continue

                # Find or create person
                person = next(
    (p for p in moc_data.people if p.name == name), None)
                if not person:
                    person = Person(name=name)
                    moc_data.people.append(person)

                # Always increment mention count for each match
                person.mention_count += 1

                # Only add filename once to mentions list
                if filename not in person.mentions:
                    person.mentions.append(filename)
                    if not person.first_mention:
                        person.first_mention = filename

    def _extract_tags(self, content: str, filename: str,
                      moc_data: MOCData) -> None:
        """Extract tags from content."""
        for pattern in self.tag_patterns:
            matches = re.finditer(pattern, content)
            for match in matches:
                tag_name = match.group(1)

                # Find or create tag
                tag = next(
    (t for t in moc_data.tags if t.name == tag_name), None)
                if not tag:
                    tag = Tag(name=tag_name)
                    moc_data.tags.append(tag)

                if filename not in tag.files:
                    tag.files.append(filename)
                    tag.usage_count += 1

    def _extract_mental_models(
        self, content: str, filename: str, moc_data: MOCData
    ) -> None:
        """Extract mental models from content."""
        for pattern in self.mental_model_patterns:
            matches = re.finditer(pattern, content, re.IGNORECASE)
            for match in matches:
                model_name = match.group(1)

                # Find or create mental model
                model = next(
                    (
                        m
                        for m in moc_data.mental_models
                        if m.name.lower() == model_name.lower()
                    ),
                    None,
                )
                if not model:
                    model = MentalModel(name=model_name)
                    moc_data.mental_models.append(model)

                if filename not in model.files:
                    model.files.append(filename)
                    model.sources.append(filename)

    def _extract_jargon(self, content: str, filename: str,
                        moc_data: MOCData) -> None:
        """Extract jargon terms from content."""
        for pattern in self.jargon_patterns:
            matches = re.finditer(pattern, content)
            for match in matches:
                term = match.group(1)
                definition = match.group(2) if len(
                    match.groups()) > 1 else None

                # Find or create jargon term
                jargon = next(
                    (j for j in moc_data.jargon if j.term.lower() == term.lower()), None
                )
                if not jargon:
                    jargon = JargonTerm(term=term)
                    moc_data.jargon.append(jargon)

                if filename not in jargon.files:
                    jargon.files.append(filename)
                    if definition and definition not in jargon.context:
                        jargon.context.append(definition)
                        jargon.definition = definition

    def _extract_beliefs(self, content: str, filename: str,
                         moc_data: MOCData) -> None:
        """Extract beliefs and claims from content."""
        # Look for belief-like statements
        belief_patterns = [
            r"(?:I believe|I think|It is|This is|We know|Research shows|Studies indicate)\s+([^.\n]+)",
            r"\*\*([^*]+)\*\*\s*[-:]\s*([^.\n]+)",  # **claim** - evidence
        ]

        for pattern in belief_patterns:
            matches = re.finditer(pattern, content, re.IGNORECASE)
            for match in matches:
                claim = match.group(1).strip()
                evidence = match.group(2) if len(match.groups()) > 1 else None

                # Create belief
                belief = Belief(
                    claim=claim,
                    sources=[filename],
                    epistemic_weight=0.6,  # Default medium confidence
                    evidence_quality="medium",
                )

                if evidence:
                    belief.sources.append(evidence)

                moc_data.beliefs.append(belief)

    def _generate_moc_files(
        self,
        moc_data: MOCData,
        theme: str,
        depth: int,
        template: Optional[Union[str, Path]] = None,
    ) -> Dict[str, Any]:
        """Generate MOC files from extracted data."""
        files = {}

        # Generate People.md
        if moc_data.people:
            people_content = self._generate_people_page(moc_data.people)
            files["People.md"] = people_content

        # Generate Tags.md
        if moc_data.tags:
            tags_content = self._generate_tags_page(moc_data.tags)
            files["Tags.md"] = tags_content

        # Generate Mental Models.md
        if moc_data.mental_models:
            models_content = self._generate_mental_models_page(
                moc_data.mental_models)
            files["Mental Models.md"] = models_content

        # Generate Jargon.md
        if moc_data.jargon:
            jargon_content = self._generate_jargon_page(moc_data.jargon)
            files["Jargon.md"] = jargon_content

        # Generate Beliefs YAML
        if moc_data.beliefs:
            beliefs_yaml = self._generate_beliefs_yaml(moc_data.beliefs)
            files["beliefs.yaml"] = beliefs_yaml

        # Generate main MOC
        main_moc = self._generate_main_moc(moc_data, theme, depth, template)
        files["MOC.md"] = main_moc

        return files

    def _generate_people_page(self, people: List[Person]) -> str:
        """Generate People.md content."""
        lines = ["# People", ""]

        # Sort by mention count
        sorted_people = sorted(
    people,
    key=lambda p: p.mention_count,
     reverse=True)

        for person in sorted_people:
            lines.append(f"## {person.name}")
            lines.append(f"Mentioned in {person.mention_count} files:")
            for mention in person.mentions:
                lines.append(f"- [[{Path(mention).stem}]]")
            lines.append("")

        return "\n".join(lines)

    def _generate_tags_page(self, tags: List[Tag]) -> str:
        """Generate Tags.md content."""
        lines = ["# Tags", ""]

        # Sort by usage count
        sorted_tags = sorted(tags, key=lambda t: t.usage_count, reverse=True)

        for tag in sorted_tags:
            lines.append(f"## #{tag.name}")
            lines.append(f"Used in {tag.usage_count} files:")
            for file in tag.files:
                lines.append(f"- [[{Path(file).stem}]]")
            lines.append("")

        return "\n".join(lines)

    def _generate_mental_models_page(self, models: List[MentalModel]) -> str:
        """Generate Mental Models.md content."""
        lines = ["# Mental Models", ""]

        for model in models:
            lines.append(f"## {model.name}")
            if model.definition:
                lines.append(f"**Definition:** {model.definition}")
            lines.append(f"Mentioned in {len(model.files)} files:")
            for file in model.files:
                lines.append(f"- [[{Path(file).stem}]]")
            lines.append("")

        return "\n".join(lines)

    def _generate_jargon_page(self, jargon_terms: List[JargonTerm]) -> str:
        """Generate Jargon.md content."""
        lines = ["# Jargon", ""]

        for term in jargon_terms:
            lines.append(f"## {term.term}")
            if term.definition:
                lines.append(f"**Definition:** {term.definition}")
            lines.append(f"Found in {len(term.files)} files:")
            for file in term.files:
                lines.append(f"- [[{Path(file).stem}]]")
            lines.append("")

        return "\n".join(lines)

    def _generate_beliefs_yaml(self, beliefs: List[Belief]) -> str:
        """Generate beliefs.yaml content."""
        beliefs_data = []
        for belief in beliefs:
            belief_dict = belief.model_dump()
            belief_dict["last_updated"] = belief_dict["last_updated"].isoformat()
            beliefs_data.append(belief_dict)

        return yaml.dump(
            beliefs_data, default_flow_style=False, sort_keys=False)

    def _load_template(
        self, template_path: Optional[Union[str, Path]]
    ) -> Optional[str]:
        """Load and process MOC template with placeholder replacement."""
        if not template_path:
            return None

        try:
            template_file = Path(template_path)
            if not template_file.exists():
                logger.warning(f"Template file not found: {template_path}")
                return None

            with open(template_file, "r", encoding="utf-8") as f:
                template = f.read().strip()

            return template

        except Exception as e:
            logger.error(f"Error loading template {template_path}: {e}")
            return None

    def _replace_template_placeholders(
        self, template: str, moc_data: MOCData, theme: str, depth: int
    ) -> str:
        """Replace placeholders in MOC template."""
        # Available placeholders:
        # {generated_at} - Generation timestamp
        # {theme} - MOC theme
        # {depth} - MOC depth
        # {source_files_count} - Number of source files
        # {people_count} - Number of people found
        # {tags_count} - Number of tags found
        # {mental_models_count} - Number of mental models found
        # {jargon_count} - Number of jargon terms found
        # {beliefs_count} - Number of beliefs found
        # {people_list} - Formatted list of people
        # {tags_list} - Formatted list of tags
        # {mental_models_list} - Formatted list of mental models
        # {jargon_list} - Formatted list of jargon terms
        # {beliefs_list} - Formatted list of beliefs
        # {source_files_list} - Formatted list of source files

        replacements = {
            "{generated_at}": moc_data.generated_at.strftime("%Y-%m-%d %H:%M:%S"),
            "{theme}": theme,
            "{depth}": str(depth),
            "{source_files_count}": str(len(moc_data.source_files)),
            "{people_count}": str(len(moc_data.people)),
            "{tags_count}": str(len(moc_data.tags)),
            "{mental_models_count}": str(len(moc_data.mental_models)),
            "{jargon_count}": str(len(moc_data.jargon)),
            "{beliefs_count}": str(len(moc_data.beliefs)),
            "{people_list}": self._format_people_list(moc_data.people),
            "{tags_list}": self._format_tags_list(moc_data.tags),
            "{mental_models_list}": self._format_mental_models_list(
                moc_data.mental_models
            ),
            "{jargon_list}": self._format_jargon_list(moc_data.jargon),
            "{beliefs_list}": self._format_beliefs_list(moc_data.beliefs),
            "{source_files_list}": self._format_source_files_list(
                moc_data.source_files
            ),
        }

        result = template
        for placeholder, replacement in replacements.items():
            result = result.replace(placeholder, replacement)

        return result

    def _format_people_list(self, people: List[Person]) -> str:
        """Format people list for template."""
        if not people:
            return "None found"

        lines = []
        for person in sorted(
            people, key=lambda p: p.mention_count, reverse=True):
            lines.append(
                f"- {person.name} (mentioned in {person.mention_count} files)")

        return "\n".join(lines)

    def _format_tags_list(self, tags: List[Tag]) -> str:
        """Format tags list for template."""
        if not tags:
            return "None found"

        lines = []
        for tag in sorted(tags, key=lambda t: t.usage_count, reverse=True):
            lines.append(f"- #{tag.name} (used in {tag.usage_count} files)")

        return "\n".join(lines)

    def _format_mental_models_list(self, models: List[MentalModel]) -> str:
        """Format mental models list for template."""
        if not models:
            return "None found"

        lines = []
        for model in models:
            lines.append(
                f"- {model.name} (mentioned in {len(model.files)} files)")

        return "\n".join(lines)

    def _format_jargon_list(self, jargon_terms: List[JargonTerm]) -> str:
        """Format jargon list for template."""
        if not jargon_terms:
            return "None found"

        lines = []
        for term in jargon_terms:
            lines.append(f"- {term.term} (found in {len(term.files)} files)")

        return "\n".join(lines)

    def _format_beliefs_list(self, beliefs: List[Belief]) -> str:
        """Format beliefs list for template."""
        if not beliefs:
            return "None found"

        lines = []
        for belief in beliefs:
            lines.append(
                f"- {belief.claim[:100]}{'...' if len(belief.claim) > 100 else ''}"
            )

        return "\n".join(lines)

    def _format_source_files_list(self, source_files: List[str]) -> str:
        """Format source files list for template."""
        if not source_files:
            return "None"

        lines = []
        for file_path in source_files:
            lines.append(f"- {Path(file_path).name}")

        return "\n".join(lines)

    def _generate_main_moc(
        self,
        moc_data: MOCData,
        theme: str,
        depth: int,
        template: Optional[Union[str, Path]] = None,
    ) -> str:
        """Generate main MOC.md content."""
        # Try to load and use custom template
        if template:
            template_content = self._load_template(template)
            if template_content:
                return self._replace_template_placeholders(
                    template_content, moc_data, theme, depth
                )
            else:
                logger.warning(
                    f"Failed to load template {template}, falling back to default MOC generation"
                )

        # Default MOC generation (existing logic)
        lines = ["# Maps of Content", ""]
        lines.append(
            f"Generated on: {moc_data.generated_at.strftime('%Y-%m-%d %H:%M:%S')}"
        )
        lines.append(f"Theme: {theme}")
        lines.append(f"Depth: {depth}")
        lines.append("")

        lines.append("## Overview")
        lines.append(f"- **Source Files:** {len(moc_data.source_files)}")
        lines.append(f"- **People Mentioned:** {len(moc_data.people)}")
        lines.append(f"- **Tags Used:** {len(moc_data.tags)}")
        lines.append(f"- **Mental Models:** {len(moc_data.mental_models)}")
        lines.append(f"- **Jargon Terms:** {len(moc_data.jargon)}")
        lines.append(f"- **Beliefs/Claims:** {len(moc_data.beliefs)}")
        lines.append("")

        # Add links to generated pages
        if moc_data.people:
            lines.append("## People")
            lines.append("See [[People]] for detailed list.")
            lines.append("")

        if moc_data.tags:
            lines.append("## Tags")
            lines.append("See [[Tags]] for detailed list.")
            lines.append("")

        if moc_data.mental_models:
            lines.append("## Mental Models")
            lines.append("See [[Mental Models]] for detailed list.")
            lines.append("")

        if moc_data.jargon:
            lines.append("## Jargon")
            lines.append("See [[Jargon]] for detailed list.")
            lines.append("")

        if moc_data.beliefs:
            lines.append("## Beliefs")
            lines.append(
                "See `beliefs.yaml` for detailed beliefs with epistemic weight."
            )
            lines.append("")

        return "\n".join(lines)


def generate_moc(
    input_files: List[Union[str, Path]],
    theme: str = "topical",
    depth: int = 3,
    include_beliefs: bool = True,
    template: Optional[Union[str, Path]] = None,
) -> Dict[str, Any]:
    """Convenience function to generate MOC from files."""
    processor = MOCProcessor()
    result = processor.process(
        input_files,
        theme=theme,
        depth=depth,
        include_beliefs=include_beliefs,
        template=template,
    )

    if not result.success:
        raise MOCGenerationError(f"Failed to generate MOC: {result.errors}")

    # Ensure we return a Dict[str, Any] as specified in the type annotation
    if isinstance(result.data, dict):
        return result.data
    else:
        # If data is not a dict, wrap it in a dict
        return {"moc_data": result.data}
