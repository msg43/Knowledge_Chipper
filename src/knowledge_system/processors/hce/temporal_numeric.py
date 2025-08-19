import re
from datetime import datetime


def normalize_relative_date(rel: str, recording_date: datetime) -> str:
    # TODO: implement with dateparser; simple passthrough for scaffold
    return rel


def numeric_sanity(
    value: float, low: float | None = None, high: float | None = None
) -> bool:
    if low is not None and value < low:
        return False
    if high is not None and value > high:
        return False
    return True
