"""
Header-to-YAML conversion utilities for document summaries.

This module provides functionality to parse summary content and extract
bullet points under specific headers, converting them to YAML fields.
"""

import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from ..logger import get_logger

logger = get_logger(__name__)


def load_yaml_headers() -> list[str]:
    """
    Load header phrases from the Headers_to_YAML.txt config file.

    Returns:
        List of header phrases to look for in summary content
    """
    config_file = Path("config/Headers_to_YAML.txt")
    try:
        if config_file.exists():
            with open(config_file, encoding="utf-8") as f:
                content = f.read().strip()
                if content:
                    # Split by semicolon and clean up whitespace
                    headers = [
                        header.strip()
                        for header in content.split(";")
                        if header.strip()
                    ]
                    logger.debug(f"Loaded {len(headers)} header phrases: {headers}")
                    return headers
        else:
            logger.warning(f"Headers_to_YAML.txt not found at {config_file}")
    except Exception as e:
        logger.error(f"Failed to load header phrases from {config_file}: {e}")

    # Return default headers if file doesn't exist or fails to load
    return ["Mental Models", "Jargon", "People"]


def extract_bullet_points_under_header(content: str, header: str) -> list[str]:
    """
    Extract bullet points that appear under a specific header in the content.

    For Mental Models and Jargon headers, extracts only the clean term/concept name
    for YAML fields, while keeping the full definition in the document body.

    Args:
        content: The summary content to parse
        header: The header to look for (case-insensitive)

    Returns:
        List of clean terms/names extracted from bullet points
    """
    bullet_points = []

    try:
        # Create case-insensitive pattern to find the header
        # Look for headers that might be in markdown format (# Header) or just plain text
        header_patterns = [
            rf"^#+\s*{re.escape(header)}\s*$",  # Markdown header (exact match)
            rf"^#+\s*.*{re.escape(header)}.*$",  # Markdown header containing the phrase
            rf"^\s*{re.escape(header)}\s*:?\s*$",  # Plain header with optional colon
            rf"^\s*\*\*{re.escape(header)}\*\*\s*:?\s*$",  # Bold header
        ]

        for pattern in header_patterns:
            matches = list(re.finditer(pattern, content, re.IGNORECASE | re.MULTILINE))

            for match in matches:
                # Find the start position after the header line
                start_pos = match.end()

                # Find the end position (next header or end of content)
                remaining_content = content[start_pos:]

                # Look for the next header to determine where this section ends
                next_header_patterns = [
                    r"\n#+\s+[^\n]+",  # Next markdown header
                    r"\n\*\*[^*\n]+\*\*\s*:?\s*\n",  # Next bold header
                    r"\n\n[A-Z][^.\n]*:?\s*\n",  # Next plain header
                ]

                end_pos = None
                for next_pattern in next_header_patterns:
                    next_match = re.search(next_pattern, remaining_content)
                    if next_match:
                        if end_pos is None or next_match.start() < end_pos:
                            end_pos = next_match.start()

                if end_pos is not None:
                    section_content = remaining_content[:end_pos]
                else:
                    section_content = remaining_content

                logger.debug(
                    f"Section content for '{header}': {repr(section_content[:200])}..."
                )

                # Extract bullet points from this section
                bullet_patterns = [
                    r"^\s*[-*•]\s+(.+)$",  # Standard bullet points
                    r"^\s*\d+\.\s+(.+)$",  # Numbered lists
                    r"^\s*[a-zA-Z]\.\s+(.+)$",  # Lettered lists
                ]

                for bullet_pattern in bullet_patterns:
                    bullet_matches = re.findall(
                        bullet_pattern, section_content, re.MULTILINE
                    )
                    for bullet_text in bullet_matches:
                        # Clean up the bullet text
                        cleaned_text = bullet_text.strip()
                        if cleaned_text and cleaned_text not in bullet_points:
                            # For Mental Models and Jargon, extract only the clean term/concept name
                            # to ensure consistency across thousands of notes
                            if header.lower() in ["mental models", "jargon"]:
                                # Extract the term before any dash, colon, or hyphen separator
                                # Examples: "The Lindy Effect - definition" -> "The Lindy Effect"
                                #          "Enshittification - definition" -> "Enshittification"
                                clean_term = re.split(r"\s*[-–—:]\s*", cleaned_text)[
                                    0
                                ].strip()
                                if clean_term:
                                    bullet_points.append(clean_term)
                                    logger.debug(
                                        f"Extracted clean term for {header}: '{clean_term}' from '{cleaned_text}'"
                                    )
                            else:
                                # For other headers like People, use the full text
                                bullet_points.append(cleaned_text)
                                logger.debug(f"Found bullet point: {cleaned_text}")

                # If we found bullet points under this header, we're done
                if bullet_points:
                    break

            # If we found bullet points with this pattern, stop trying other patterns
            if bullet_points:
                break

        logger.debug(
            f"Found {len(bullet_points)} bullet points under header '{header}'"
        )

    except Exception as e:
        logger.error(f"Error extracting bullet points for header '{header}': {e}")

    return bullet_points


def sanitize_yaml_field_name(header: str) -> str:
    """
    Sanitize header name for use as YAML field name in Obsidian.

    Preserves the exact header name from the prompt template, only converting
    spaces to underscores for valid YAML syntax. This ensures consistency
    between the H3 headers in the prompt and the resulting YAML field names.

    Args:
        header: The original header name (e.g., "Mental Models", "People", "Jargon")

    Returns:
        YAML field name that exactly matches the header pattern
    """
    import re

    # First normalize multiple spaces to single spaces, then replace with underscores
    # This maintains consistency with H3 headers: "Mental Models" -> "Mental_Models"
    clean_header = re.sub(r"\s+", " ", header.strip())  # Normalize whitespace

    # Remove any characters that could cause YAML parsing issues before replacing spaces
    # This prevents creating multiple underscores from adjacent special chars and spaces
    clean_header = re.sub(
        r"[^a-zA-Z0-9\s-]", " ", clean_header
    )  # Replace special chars with spaces
    clean_header = re.sub(r"\s+", " ", clean_header)  # Normalize whitespace again
    clean_header = clean_header.replace(" ", "_")  # Replace spaces with underscores

    # Remove any leading/trailing underscores that might have been created
    clean_header = clean_header.strip("_")

    # Ensure it doesn't start with a number (YAML field names should start with letter or underscore)
    if clean_header and clean_header[0].isdigit():
        clean_header = f"field_{clean_header}"

    # Fallback if somehow the field name becomes empty
    if not clean_header:
        clean_header = "field"

    return clean_header


def generate_yaml_fields(header: str, bullet_points: list[str]) -> dict[str, str]:
    """
    Generate YAML fields from bullet points with numbered suffixes.

    Args:
        header: The header name (will be used as field prefix)
        bullet_points: List of bullet point texts

    Returns:
        Dictionary of YAML field names to values
    """
    yaml_fields = {}

    try:
        # Properly sanitize header name for YAML field compatibility
        clean_header = sanitize_yaml_field_name(header)

        for i, bullet_point in enumerate(bullet_points, 1):
            # Format the field name with zero-padded number
            field_name = f"{clean_header}_{i:02d}"
            yaml_fields[field_name] = bullet_point

        logger.debug(
            f"Generated {len(yaml_fields)} YAML fields for header '{header}' -> '{clean_header}'"
        )

    except Exception as e:
        logger.error(f"Error generating YAML fields for header '{header}': {e}")

    return yaml_fields


def process_summary_for_yaml_headers(
    content: str, analysis_type: str
) -> dict[str, str]:
    """
    Process summary content to extract header-based YAML fields and add Is_MOC field.

    Args:
        content: The summary content to process
        analysis_type: The analysis type

    Returns:
        Dictionary of additional YAML fields to include in metadata
    """
    additional_yaml_fields = {}

    # Add Is_MOC field based on analysis type
    if analysis_type.lower() == "document summary":
        additional_yaml_fields["Is_MOC"] = "false"
    elif analysis_type.lower() in ["create moc", "create moc of mocs"]:
        additional_yaml_fields["Is_MOC"] = "true"
    else:
        # For other analysis types, default to false
        additional_yaml_fields["Is_MOC"] = "false"

    # Only process header extraction for "Document Summary" analysis type
    if analysis_type.lower() != "document summary":
        logger.debug(
            f"Skipping header-to-YAML processing for analysis type: {analysis_type}"
        )
        return additional_yaml_fields

    try:
        # Load header phrases from config
        header_phrases = load_yaml_headers()

        if not header_phrases:
            logger.warning(
                "No header phrases loaded, skipping header-to-YAML processing"
            )
            return additional_yaml_fields

        logger.info(f"Processing summary content for headers: {header_phrases}")

        # Process each header phrase and add to existing fields (preserving Is_MOC)
        for header in header_phrases:
            bullet_points = extract_bullet_points_under_header(content, header)

            if bullet_points:
                yaml_fields = generate_yaml_fields(header, bullet_points)
                additional_yaml_fields.update(yaml_fields)
                logger.info(
                    f"Added {len(yaml_fields)} YAML fields for header '{header}'"
                )
            else:
                logger.debug(f"No bullet points found for header '{header}'")

        logger.info(
            f"Generated {len(additional_yaml_fields)} additional YAML fields from headers"
        )

    except Exception as e:
        logger.error(f"Error processing summary for YAML headers: {e}")

    return additional_yaml_fields
