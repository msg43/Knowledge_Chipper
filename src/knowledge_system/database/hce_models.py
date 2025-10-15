"""
HCE models - Re-exports from unified models.py for backward compatibility.

This module maintains the old import paths while using the unified Base.
All HCE models now live in models.py to ensure proper foreign key resolution.
"""

from .models import Base, Claim, Concept, Episode, Jargon, Person

__all__ = [
    "Base",
    "Episode",
    "Claim",
    "Person",
    "Concept",
    "Jargon",
]
