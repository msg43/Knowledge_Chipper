"""
Claim Code Generation for Device Claiming

Generates short, human-readable codes from device IDs for easy device claiming.
Users can enter this code on the web to link their devices to their account.

Inspired by Happy's device claiming flow.
"""

import hashlib
import base64


def generate_claim_code(device_id: str) -> str:
    """
    Generate a short 6-character claim code from device_id.

    Uses base32 encoding for human-readable codes (no confusing characters).
    Same device_id always produces the same code (deterministic).

    Args:
        device_id: UUID string of the device

    Returns:
        6-character uppercase claim code (e.g., "A3B7C2")

    Examples:
        >>> generate_claim_code("be114cb7-ed43-44b4-8c64-e66b14ea7576")
        'VE2WKY'
        >>> generate_claim_code("12345678-1234-1234-1234-123456789012")
        'GE3TQM'
    """
    # Hash the device_id for consistent short code
    hash_bytes = hashlib.sha256(device_id.encode()).digest()

    # Take first 4 bytes (enough for ~4 billion unique codes)
    short_hash = hash_bytes[:4]

    # Encode to base32 (human-readable, uppercase, no ambiguous chars)
    # base32 uses: A-Z and 2-7 (no 0/O, 1/I/L confusion)
    encoded = base64.b32encode(short_hash).decode('ascii')

    # Take first 6 characters (enough for millions of unique codes)
    claim_code = encoded[:6]

    return claim_code


def verify_claim_code(device_id: str, claim_code: str) -> bool:
    """
    Verify that a claim code matches a device_id.

    Args:
        device_id: UUID string of the device
        claim_code: 6-character claim code to verify

    Returns:
        True if claim code is valid for this device_id

    Examples:
        >>> verify_claim_code("be114cb7-ed43-44b4-8c64-e66b14ea7576", "VE2WKY")
        True
        >>> verify_claim_code("be114cb7-ed43-44b4-8c64-e66b14ea7576", "WRONG1")
        False
    """
    expected_code = generate_claim_code(device_id)
    return claim_code.upper() == expected_code


def format_claim_code(claim_code: str) -> str:
    """
    Format claim code for display with spacing.

    Args:
        claim_code: 6-character claim code

    Returns:
        Formatted code with spacing (e.g., "VE2 WKY")

    Examples:
        >>> format_claim_code("VE2WKY")
        'VE2 WKY'
    """
    claim_code = claim_code.upper()
    if len(claim_code) == 6:
        return f"{claim_code[:3]} {claim_code[3:]}"
    return claim_code
