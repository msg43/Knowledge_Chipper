"""
ID generation utilities for System 2.
"""

import hashlib
import json
from typing import Any


def create_deterministic_id(seed: str) -> str:
    """
    Create a deterministic ID from a seed string.

    Args:
        seed: The seed string to generate ID from

    Returns:
        A deterministic ID string
    """
    # Create a hash of the seed
    hash_obj = hashlib.sha256(seed.encode("utf-8"))
    # Take first 16 characters of hex digest
    return hash_obj.hexdigest()[:16]


def create_job_id(job_type: str, input_id: str, config: dict[str, Any]) -> str:
    """
    Create a deterministic job ID from job parameters.

    Args:
        job_type: Type of job
        input_id: Input identifier
        config: Job configuration

    Returns:
        A deterministic job ID
    """
    # Create seed from parameters
    seed = f"{job_type}_{input_id}_{json.dumps(config, sort_keys=True)}"
    return create_deterministic_id(seed)
