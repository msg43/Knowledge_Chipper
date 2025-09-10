"""
Obsidian Tag Conversion Utilities

Handles conversion between YAML frontmatter tags and Obsidian hashtag format.
"""

import re
from typing import List, Set


def sanitize_tag_for_obsidian(tag: str) -> str:
    """
    Sanitize a tag string to be compatible with Obsidian hashtag format.

    This function now preserves more characters to maintain readability
    while still ensuring Obsidian compatibility.

    Args:
        tag: Raw tag string

    Returns:
        Sanitized tag suitable for Obsidian hashtags
    """
    if not tag or not isinstance(tag, str):
        return ""

    # Remove leading/trailing whitespace
    tag = tag.strip()

    # If tag is empty after stripping, return empty
    if not tag:
        return ""

    # Only replace truly problematic characters for Obsidian
    # Keep alphanumeric, hyphens, underscores, forward slashes, periods, and apostrophes
    # Replace spaces with hyphens, but preserve other punctuation that's readable
    tag = re.sub(r"\s+", "-", tag)  # Replace spaces/whitespace with hyphens
    tag = re.sub(r"[^\w\-_/.'']", "-", tag)  # Only replace truly problematic chars

    # Replace multiple consecutive hyphens with single hyphen
    tag = re.sub(r"-{2,}", "-", tag)

    # Remove leading/trailing hyphens and periods
    tag = tag.strip("-.")

    # Don't force lowercase - preserve original casing for readability
    # tag = tag.lower()  # Commented out to preserve readability

    # Return empty if nothing valid remains
    return tag if tag else ""


def yaml_tags_to_obsidian_hashtags(yaml_tags: list[str]) -> set[str]:
    """
    Convert a list of YAML frontmatter tags to Obsidian hashtag format.

    Args:
        yaml_tags: List of tag strings from YAML frontmatter

    Returns:
        Set of properly formatted Obsidian hashtags (including #)
    """
    hashtags = set()

    for tag in yaml_tags:
        if not tag:
            continue

        sanitized = sanitize_tag_for_obsidian(tag)
        if sanitized:
            hashtags.add(f"#{sanitized}")

    return hashtags


def extract_yaml_tags_from_frontmatter(content: str) -> list[str]:
    """
    Extract tags from YAML frontmatter in markdown content.

    Args:
        content: Full markdown content with YAML frontmatter

    Returns:
        List of tag strings found in frontmatter
    """
    # Find YAML frontmatter
    lines = content.split("\n")
    if not lines or lines[0].strip() != "---":
        return []

    # Find end of frontmatter
    yaml_end = None
    for i, line in enumerate(lines[1:], 1):
        if line.strip() == "---":
            yaml_end = i
            break

    if yaml_end is None:
        return []

    # Extract tags from YAML section
    yaml_content = "\n".join(lines[1:yaml_end])

    # Look for tags field (handles both array and string formats)
    tags = []

    # Match tags: ["tag1", "tag2"] or tags: [tag1, tag2]
    array_match = re.search(r"tags:\s*\[(.*?)\]", yaml_content, re.DOTALL)
    if array_match:
        tag_content = array_match.group(1)
        # Extract individual tags (handle quoted and unquoted)
        tag_matches = re.findall(r'["\']([^"\']*)["\']|([^,\s]+)', tag_content)
        for match in tag_matches:
            tag = match[0] if match[0] else match[1]
            if tag.strip():
                tags.append(tag.strip())
    else:
        # Match tags: "tag1, tag2" or tags: tag1
        string_match = re.search(r'tags:\s*["\']([^"\']*)["\']', yaml_content)
        if string_match:
            tag_content = string_match.group(1)
            tags = [tag.strip() for tag in tag_content.split(",") if tag.strip()]
        else:
            # Match unquoted single tag
            single_match = re.search(r"tags:\s*([^\n\r]+)", yaml_content)
            if single_match:
                tag = single_match.group(1).strip()
                if tag and not tag.startswith("["):
                    tags = [tag]

    return tags


def add_obsidian_hashtags_to_content(content: str) -> str:
    """
    Add Obsidian hashtags to markdown content based on YAML frontmatter tags.

    Args:
        content: Full markdown content with YAML frontmatter

    Returns:
        Content with hashtags added after the frontmatter
    """
    # Extract tags from frontmatter
    yaml_tags = extract_yaml_tags_from_frontmatter(content)

    if not yaml_tags:
        return content

    # Convert to hashtags
    hashtags = yaml_tags_to_obsidian_hashtags(yaml_tags)

    if not hashtags:
        return content

    # Find where to insert hashtags (after frontmatter)
    lines = content.split("\n")
    if not lines or lines[0].strip() != "---":
        # No frontmatter, add at top
        hashtag_line = " ".join(sorted(hashtags))
        return f"{hashtag_line}\n\n{content}"

    # Find end of frontmatter
    yaml_end = None
    for i, line in enumerate(lines[1:], 1):
        if line.strip() == "---":
            yaml_end = i
            break

    if yaml_end is None:
        return content

    # Insert hashtags after frontmatter
    hashtag_line = " ".join(sorted(hashtags))

    # Insert with proper spacing
    before_frontmatter = lines[: yaml_end + 1]
    after_frontmatter = lines[yaml_end + 1 :]

    # Remove empty lines immediately after frontmatter to avoid too much spacing
    while after_frontmatter and not after_frontmatter[0].strip():
        after_frontmatter.pop(0)

    # Combine with hashtags
    result_lines = before_frontmatter + ["", hashtag_line, ""] + after_frontmatter

    return "\n".join(result_lines)


def format_obsidian_tags_section(hashtags: set[str]) -> str:
    """
    Format a set of hashtags into a clean tags section for Obsidian.

    Args:
        hashtags: Set of hashtag strings (including #)

    Returns:
        Formatted tags section
    """
    if not hashtags:
        return ""

    # Sort tags for consistency
    sorted_tags = sorted(hashtags)

    # Group tags by category if they use forward slash notation
    categorized = {}
    uncategorized = []

    for tag in sorted_tags:
        if "/" in tag:
            category = tag.split("/")[0]
            if category not in categorized:
                categorized[category] = []
            categorized[category].append(tag)
        else:
            uncategorized.append(tag)

    # Format output
    result_parts = []

    # Add uncategorized tags first
    if uncategorized:
        result_parts.append(" ".join(uncategorized))

    # Add categorized tags
    for category in sorted(categorized.keys()):
        result_parts.append(" ".join(categorized[category]))

    return " ".join(result_parts)
