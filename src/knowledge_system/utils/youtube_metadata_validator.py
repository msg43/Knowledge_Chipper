"""
YouTube Metadata Validator

Validates and cleans metadata from multiple sources (YouTube Data API, yt-dlp)
to ensure consistent database storage format.
"""

import re
from datetime import datetime
from typing import Any

from ..logger import get_logger

logger = get_logger(__name__)


class MetadataValidationError(Exception):
    """Metadata validation error."""
    pass


def validate_and_clean_metadata(
    metadata: dict[str, Any],
    source: str = "ytdlp"
) -> dict[str, Any]:
    """
    Validate and clean metadata from any source.
    
    Args:
        metadata: Raw metadata dict
        source: Source of metadata ("youtube_api" or "ytdlp")
    
    Returns:
        Clean dict matching MediaSource schema exactly
    
    Raises:
        MetadataValidationError: If critical fields are missing
    """
    if source == "youtube_api":
        return _validate_api_metadata(metadata)
    elif source == "ytdlp":
        return _validate_ytdlp_metadata(metadata)
    else:
        raise ValueError(f"Unknown metadata source: {source}")


def _validate_api_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    """
    Validate metadata from YouTube Data API v3.
    
    API metadata is already clean, just need to ensure required fields.
    """
    cleaned = {}
    
    # Required fields
    cleaned["source_id"] = metadata.get("source_id", "")
    if not cleaned["source_id"]:
        raise MetadataValidationError("Missing source_id")
    
    cleaned["title"] = _sanitize_string(
        metadata.get("title", "Unknown Title"),
        max_length=500
    )
    
    # Optional fields with defaults
    cleaned["description"] = _sanitize_string(
        metadata.get("description", ""),
        max_length=5000
    )
    cleaned["uploader"] = _sanitize_string(
        metadata.get("uploader", ""),
        max_length=200
    )
    cleaned["uploader_id"] = metadata.get("uploader_id", "")
    cleaned["upload_date"] = metadata.get("upload_date", "")
    
    # Numeric fields
    cleaned["duration_seconds"] = _safe_int(metadata.get("duration_seconds"))
    cleaned["view_count"] = _safe_int(metadata.get("view_count"))
    cleaned["like_count"] = _safe_int(metadata.get("like_count"))
    cleaned["comment_count"] = _safe_int(metadata.get("comment_count"))
    
    # List fields
    cleaned["tags_json"] = _ensure_list(metadata.get("tags_json", []))
    cleaned["categories_json"] = _ensure_list(metadata.get("categories_json", []))
    
    # Other fields
    cleaned["thumbnail_url"] = metadata.get("thumbnail_url", "")
    cleaned["language"] = metadata.get("language", "en")
    cleaned["caption_availability"] = bool(metadata.get("caption_availability", False))
    cleaned["privacy_status"] = metadata.get("privacy_status", "public")
    
    return cleaned


def _validate_ytdlp_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    """
    Validate and clean metadata from yt-dlp.
    
    yt-dlp metadata needs more validation and format conversion.
    """
    cleaned = {}
    
    # Title (try multiple fields)
    title = metadata.get("title") or metadata.get("fulltitle") or "Unknown Title"
    cleaned["title"] = _sanitize_string(title, max_length=500)
    
    # Description
    cleaned["description"] = _sanitize_string(
        metadata.get("description", ""),
        max_length=5000
    )
    
    # Uploader (try multiple fields)
    uploader = metadata.get("uploader") or metadata.get("channel") or ""
    cleaned["uploader"] = _sanitize_string(uploader, max_length=200)
    cleaned["uploader_id"] = metadata.get("uploader_id") or metadata.get("channel_id") or ""
    
    # Upload date (convert YYYYMMDD to YYYYMMDD if needed)
    upload_date = metadata.get("upload_date", "")
    if upload_date and len(upload_date) == 8 and upload_date.isdigit():
        cleaned["upload_date"] = upload_date  # Already in correct format
    elif upload_date:
        # Try to parse and convert
        cleaned["upload_date"] = _convert_date_to_yyyymmdd(upload_date)
    else:
        cleaned["upload_date"] = ""
    
    # Duration (ensure integer)
    duration = metadata.get("duration")
    cleaned["duration_seconds"] = _safe_int(duration)
    
    # Statistics (ensure integers or None)
    cleaned["view_count"] = _safe_int(metadata.get("view_count"))
    cleaned["like_count"] = _safe_int(metadata.get("like_count"))
    cleaned["comment_count"] = _safe_int(metadata.get("comment_count"))
    
    # Tags (ensure list)
    tags = metadata.get("tags")
    if isinstance(tags, list):
        cleaned["tags_json"] = [str(t) for t in tags if t]
    elif tags:
        cleaned["tags_json"] = [str(tags)]
    else:
        cleaned["tags_json"] = []
    
    # Categories (ensure list)
    categories = metadata.get("categories")
    if isinstance(categories, list):
        cleaned["categories_json"] = [str(c) for c in categories if c]
    elif categories:
        cleaned["categories_json"] = [str(categories)]
    else:
        cleaned["categories_json"] = []
    
    # Thumbnail
    cleaned["thumbnail_url"] = metadata.get("thumbnail", "")
    
    # Language
    cleaned["language"] = metadata.get("language") or "en"
    
    # Caption availability
    cleaned["caption_availability"] = bool(
        metadata.get("subtitles") or metadata.get("automatic_captions")
    )
    
    # Privacy status
    cleaned["privacy_status"] = metadata.get("availability") or "public"
    
    return cleaned


def _sanitize_string(value: str, max_length: int = None) -> str:
    """
    Sanitize string for database storage.
    
    - Removes control characters
    - Trims whitespace
    - Enforces max length
    """
    if not value:
        return ""
    
    # Convert to string if not already
    value = str(value)
    
    # Remove control characters (except newlines and tabs)
    value = re.sub(r'[\x00-\x08\x0B-\x0C\x0E-\x1F\x7F]', '', value)
    
    # Trim whitespace
    value = value.strip()
    
    # Enforce max length
    if max_length and len(value) > max_length:
        value = value[:max_length-3] + "..."
    
    return value


def _ensure_list(value: Any) -> list:
    """Ensure value is a list."""
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _safe_int(value: Any) -> int | None:
    """Safely convert value to integer."""
    if value is None:
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        logger.debug(f"Could not convert to int: {value}")
        return None


def _convert_date_to_yyyymmdd(date_str: str) -> str:
    """
    Convert various date formats to YYYYMMDD.
    
    Handles:
    - ISO 8601: 2024-01-15T10:30:00Z
    - YYYY-MM-DD: 2024-01-15
    - Unix timestamp: 1705276800
    """
    if not date_str:
        return ""
    
    try:
        # Try ISO 8601
        if 'T' in date_str or '-' in date_str:
            dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            return dt.strftime("%Y%m%d")
        
        # Try unix timestamp
        if date_str.isdigit():
            dt = datetime.fromtimestamp(int(date_str))
            return dt.strftime("%Y%m%d")
        
        # Already in YYYYMMDD format
        if len(date_str) == 8 and date_str.isdigit():
            return date_str
        
    except Exception as e:
        logger.warning(f"Failed to convert date '{date_str}': {e}")
    
    return ""


def validate_source_id(source_id: str) -> bool:
    """
    Validate YouTube video ID format.
    
    Args:
        source_id: Video ID to validate
    
    Returns:
        True if valid, False otherwise
    """
    if not source_id:
        return False
    
    # YouTube video IDs are exactly 11 characters: [a-zA-Z0-9_-]
    pattern = r'^[a-zA-Z0-9_-]{11}$'
    return bool(re.match(pattern, source_id))

