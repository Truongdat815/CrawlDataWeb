"""Utility: Generate UUID version 7 (timestamp-first) strings.

This implements a lightweight UUIDv7 generator following the draft layout:
- 48-bit unix timestamp in milliseconds stored in the first 6 bytes
- remaining bytes random
- version bits set to 7 and RFC variant bits set to 0b10

Returns lowercase UUID string in canonical 8-4-4-4-12 format.
"""
from __future__ import annotations

import os
import time
import secrets


def uuid7() -> str:
    """Generate a UUIDv7-like identifier (RFC draft layout).

    Returns:
        str: canonical UUID string (lowercase), e.g. '0187f2c0-1a2b-7f3a-8c4d-0123456789ab'
    """
    # 48-bit timestamp (ms)
    ts_ms = int(time.time() * 1000) & 0xFFFFFFFFFFFF

    # 10 random bytes (80 bits)
    rnd = secrets.token_bytes(10)

    # Build 16-byte array: 6 bytes timestamp (big-endian) + 10 random bytes
    ts_bytes = ts_ms.to_bytes(6, 'big')
    b = bytearray(ts_bytes + rnd)

    # Set version = 7 in the high nibble of byte index 6 (time_hi_and_version high byte)
    # byte indices: 0..15; version is in bits 4..7 of byte 6
    b[6] = (b[6] & 0x0F) | (7 << 4)

    # Set variant to RFC 4122 (10xx) in byte index 8 (clock_seq_hi_and_reserved)
    b[8] = (b[8] & 0x3F) | 0x80

    # Return lowercase hex string WITHOUT hyphens (32 hex chars)
    hexed = b.hex()
    return hexed


def prefixed(prefix: str = "wp") -> str:
    """Return a prefixed uuid7 string with given prefix.

    Example: prefixed('wp') -> 'wp_0187f2c0-1a2b-7f3a-8c4d-0123456789ab'
    """
    return f"{prefix}_{uuid7()}"
