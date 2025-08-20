import re
from datetime import datetime


def normalize_relative_date(rel: str, recording_date: datetime) -> str:
    """Normalize relative date expressions to absolute dates.

    Args:
        rel: Relative date expression (e.g., "last week", "yesterday")
        recording_date: The date when the content was recorded

    Returns:
        Normalized date string
    """
    try:
        # Handle common relative date patterns
        rel_lower = rel.lower().strip()

        # Simple pattern matching for common expressions
        if "today" in rel_lower:
            return recording_date.strftime("%Y-%m-%d")
        elif "yesterday" in rel_lower:
            from datetime import timedelta

            yesterday = recording_date - timedelta(days=1)
            return yesterday.strftime("%Y-%m-%d")
        elif "last week" in rel_lower:
            from datetime import timedelta

            last_week = recording_date - timedelta(weeks=1)
            return last_week.strftime("%Y-%m-%d")
        elif "last month" in rel_lower:
            from datetime import timedelta

            last_month = recording_date - timedelta(days=30)
            return last_month.strftime("%Y-%m-%d")
        elif "last year" in rel_lower:
            from datetime import timedelta

            last_year = recording_date - timedelta(days=365)
            return last_year.strftime("%Y-%m-%d")

        # Try to extract year patterns
        year_match = re.search(r"\b(19|20)\d{2}\b", rel)
        if year_match is not None:
            return f"{year_match.group(0)}-01-01"  # Default to January 1st

        # Try to extract month/day patterns if no year found
        date_match = re.search(r"\b(\d{1,2})/(\d{1,2})\b", rel)
        if date_match is not None:
            month, day = date_match.groups()
            return f"{recording_date.year}-{month.zfill(2)}-{day.zfill(2)}"

    except Exception as e:
        import logging

        logger = logging.getLogger(__name__)
        logger.warning(f"Failed to normalize date '{rel}': {e}")

    # Fallback: return original
    return rel


def numeric_sanity(
    value: float, low: float | None = None, high: float | None = None
) -> bool:
    if low is not None and value < low:
        return False
    if high is not None and value > high:
        return False
    return True
