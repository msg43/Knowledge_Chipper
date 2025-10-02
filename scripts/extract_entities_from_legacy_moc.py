#!/usr/bin/env python3
"""
Extract entities from legacy MOC data and populate HCE entity cache.

This script processes old MOC files to extract people and concepts,
then populates the HCE entity cache for improved future processing.
"""

import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Set

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from knowledge_system.database import DatabaseService
from knowledge_system.logger import get_logger
from knowledge_system.utils.entity_cache import get_entity_cache

logger = get_logger(__name__)


class LegacyMOCEntityExtractor:
    """Extract entities from legacy MOC data."""

    def __init__(self):
        """Initialize extractor."""
        self.db = DatabaseService()
        self.entity_cache = get_entity_cache()
        self.extracted_people = set()
        self.extracted_concepts = set()

    def extract_from_database(self) -> dict[str, int]:
        """Extract entities from legacy MOC data in database.

        Returns:
            Dictionary with extraction statistics
        """
        stats = {
            "moc_extractions_processed": 0,
            "people_extracted": 0,
            "concepts_extracted": 0,
            "entities_cached": 0,
        }

        try:
            with self.db.get_session() as session:
                from knowledge_system.database.models import MOCExtraction

                # Get all MOC extractions
                moc_extractions = session.query(MOCExtraction).all()
                stats["moc_extractions_processed"] = len(moc_extractions)

                logger.info(f"Processing {len(moc_extractions)} MOC extractions...")

                for moc in moc_extractions:
                    # Extract from people_json
                    if moc.people_json:
                        people_data = json.loads(moc.people_json)
                        people_count = self._extract_people_from_moc_data(people_data)
                        stats["people_extracted"] += people_count

                    # Extract from concepts_json
                    if moc.concepts_json:
                        concepts_data = json.loads(moc.concepts_json)
                        concepts_count = self._extract_concepts_from_moc_data(
                            concepts_data
                        )
                        stats["concepts_extracted"] += concepts_count

                    # Extract from jargon_json (treat as concepts)
                    if moc.jargon_json:
                        jargon_data = json.loads(moc.jargon_json)
                        jargon_count = self._extract_jargon_as_concepts(jargon_data)
                        stats["concepts_extracted"] += jargon_count

                # Save entity cache
                self.entity_cache.save()
                stats["entities_cached"] = len(self.extracted_people) + len(
                    self.extracted_concepts
                )

                logger.info(f"Extraction completed: {stats}")
                return stats

        except Exception as e:
            logger.error(f"Failed to extract entities from database: {e}")
            return stats

    def _extract_people_from_moc_data(self, people_data) -> int:
        """Extract people from MOC people data."""
        count = 0

        if isinstance(people_data, dict):
            # Handle different MOC formats
            for key, value in people_data.items():
                if isinstance(value, str) and value.strip():
                    name = key.strip()
                    description = value.strip()

                    if name and name not in self.extracted_people:
                        self.entity_cache.add_or_update_entity(
                            name=name,
                            description=description,
                            entity_type="person",
                            confidence=0.8,  # Medium confidence for legacy data
                        )
                        self.extracted_people.add(name)
                        count += 1

        elif isinstance(people_data, list):
            # Handle list format
            for item in people_data:
                if isinstance(item, dict):
                    name = item.get("name", "").strip()
                    description = item.get("description", "").strip()

                    if name and name not in self.extracted_people:
                        self.entity_cache.add_or_update_entity(
                            name=name,
                            description=description,
                            entity_type="person",
                            confidence=0.8,
                        )
                        self.extracted_people.add(name)
                        count += 1

        return count

    def _extract_concepts_from_moc_data(self, concepts_data) -> int:
        """Extract concepts from MOC concepts data."""
        count = 0

        if isinstance(concepts_data, dict):
            for key, value in concepts_data.items():
                if isinstance(value, str) and value.strip():
                    name = key.strip()
                    description = value.strip()

                    if name and name not in self.extracted_concepts:
                        self.entity_cache.add_or_update_entity(
                            name=name,
                            description=description,
                            entity_type="concept",
                            confidence=0.8,
                        )
                        self.extracted_concepts.add(name)
                        count += 1

        elif isinstance(concepts_data, list):
            for item in concepts_data:
                if isinstance(item, dict):
                    name = item.get("name", "").strip()
                    description = item.get("description", "").strip()

                    if name and name not in self.extracted_concepts:
                        self.entity_cache.add_or_update_entity(
                            name=name,
                            description=description,
                            entity_type="concept",
                            confidence=0.8,
                        )
                        self.extracted_concepts.add(name)
                        count += 1

        return count

    def _extract_jargon_as_concepts(self, jargon_data) -> int:
        """Extract jargon terms as concepts."""
        count = 0

        if isinstance(jargon_data, dict):
            for key, value in jargon_data.items():
                if isinstance(value, str) and value.strip():
                    name = key.strip()
                    description = f"Jargon term: {value.strip()}"

                    if name and name not in self.extracted_concepts:
                        self.entity_cache.add_or_update_entity(
                            name=name,
                            description=description,
                            entity_type="concept",
                            confidence=0.7,  # Slightly lower confidence for jargon
                        )
                        self.extracted_concepts.add(name)
                        count += 1

        return count

    def extract_from_files(self, moc_directory: Path) -> dict[str, int]:
        """Extract entities from MOC markdown files.

        Args:
            moc_directory: Directory containing MOC markdown files

        Returns:
            Dictionary with extraction statistics
        """
        stats = {"files_processed": 0, "people_extracted": 0, "concepts_extracted": 0}

        if not moc_directory.exists():
            logger.warning(f"MOC directory not found: {moc_directory}")
            return stats

        # Find MOC markdown files
        moc_files = list(moc_directory.glob("*.md"))
        logger.info(f"Found {len(moc_files)} MOC files to process")

        for moc_file in moc_files:
            try:
                content = moc_file.read_text(encoding="utf-8")
                file_stats = self._extract_from_markdown_content(content)

                stats["files_processed"] += 1
                stats["people_extracted"] += file_stats["people"]
                stats["concepts_extracted"] += file_stats["concepts"]

            except Exception as e:
                logger.error(f"Failed to process {moc_file}: {e}")

        # Save entity cache
        self.entity_cache.save()
        logger.info(f"File extraction completed: {stats}")
        return stats

    def _extract_from_markdown_content(self, content: str) -> dict[str, int]:
        """Extract entities from markdown content."""
        stats = {"people": 0, "concepts": 0}

        # Extract people from ## People section
        people_match = re.search(r"## People\s*\n(.*?)(?=\n##|\Z)", content, re.DOTALL)
        if people_match:
            people_section = people_match.group(1)
            people_count = self._extract_entities_from_section(people_section, "person")
            stats["people"] = people_count

        # Extract concepts from ## Concepts section
        concepts_match = re.search(
            r"## Concepts\s*\n(.*?)(?=\n##|\Z)", content, re.DOTALL
        )
        if concepts_match:
            concepts_section = concepts_match.group(1)
            concepts_count = self._extract_entities_from_section(
                concepts_section, "concept"
            )
            stats["concepts"] = concepts_count

        return stats

    def _extract_entities_from_section(
        self, section_text: str, entity_type: str
    ) -> int:
        """Extract entities from a markdown section."""
        count = 0

        # Look for bullet points or numbered lists
        lines = section_text.split("\n")

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Remove markdown formatting
            line = re.sub(r"^[-*+]\s*", "", line)  # Remove bullet points
            line = re.sub(r"^\d+\.\s*", "", line)  # Remove numbers
            line = re.sub(r"\*\*(.*?)\*\*", r"\1", line)  # Remove bold
            line = re.sub(r"\*(.*?)\*", r"\1", line)  # Remove italic

            # Split on colon or dash to separate name from description
            if ":" in line:
                name, description = line.split(":", 1)
                name = name.strip()
                description = description.strip()
            elif " - " in line:
                name, description = line.split(" - ", 1)
                name = name.strip()
                description = description.strip()
            else:
                name = line.strip()
                description = ""

            if name and len(name) > 1:  # Basic validation
                entity_set = (
                    self.extracted_people
                    if entity_type == "person"
                    else self.extracted_concepts
                )

                if name not in entity_set:
                    self.entity_cache.add_or_update_entity(
                        name=name,
                        description=description,
                        entity_type=entity_type,
                        confidence=0.7,  # Medium confidence for extracted data
                    )
                    entity_set.add(name)
                    count += 1

        return count

    def print_extraction_report(self, db_stats: dict, file_stats: dict = None):
        """Print entity extraction report."""
        print("\n" + "=" * 60)
        print("📊 LEGACY MOC ENTITY EXTRACTION REPORT")
        print("=" * 60)

        print(f"\n📁 Database Extraction:")
        print(
            f"   • MOC extractions processed: {db_stats['moc_extractions_processed']}"
        )
        print(f"   • People extracted: {db_stats['people_extracted']}")
        print(f"   • Concepts extracted: {db_stats['concepts_extracted']}")
        print(f"   • Total entities cached: {db_stats['entities_cached']}")

        if file_stats:
            print(f"\n📄 File Extraction:")
            print(f"   • MOC files processed: {file_stats['files_processed']}")
            print(f"   • People extracted: {file_stats['people_extracted']}")
            print(f"   • Concepts extracted: {file_stats['concepts_extracted']}")

        # Get cache statistics
        cache_stats = self.entity_cache.get_entity_stats()
        print(f"\n💾 Entity Cache Status:")
        print(f"   • Total entities: {cache_stats['total_entities']}")
        print(f"   • People: {cache_stats['people']}")
        print(f"   • Concepts: {cache_stats['concepts']}")
        print(f"   • Cache size: {cache_stats['cache_size_mb']:.2f} MB")

        print(f"\n✅ Entity extraction completed successfully!")
        print("=" * 60)


def main():
    """Run legacy MOC entity extraction."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Extract entities from legacy MOC data"
    )
    parser.add_argument("--moc-dir", help="Directory containing MOC markdown files")
    parser.add_argument(
        "--db-only", action="store_true", help="Only extract from database"
    )
    args = parser.parse_args()

    extractor = LegacyMOCEntityExtractor()

    # Extract from database
    db_stats = extractor.extract_from_database()

    # Extract from files if specified
    file_stats = None
    if not args.db_only and args.moc_dir:
        moc_dir = Path(args.moc_dir)
        file_stats = extractor.extract_from_files(moc_dir)

    # Print report
    extractor.print_extraction_report(db_stats, file_stats)


if __name__ == "__main__":
    main()
