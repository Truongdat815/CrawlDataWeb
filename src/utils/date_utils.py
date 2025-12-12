"""Date/time helpers for consistent DB formatting.

Exports:
- format_for_db(value) -> str | None: convert various inputs (ISO string, epoch seconds/ms, datetime)
  into format: DD/MM/YYYY, H:MM AM/PM (example: '28/10/2018, 1:22 PM').
"""
from __future__ import annotations

from datetime import datetime
import time
from typing import Optional, Any


def _to_datetime(value: Any) -> Optional[datetime]:
    if value is None:
        return None

    if isinstance(value, datetime):
        return value

    # numeric timestamp (seconds or milliseconds)
    if isinstance(value, (int, float)):
        # Determine if milliseconds
        if value > 1e12:
            # milliseconds
            return datetime.fromtimestamp(value / 1000.0)
        elif value > 1e9:
            # seconds
            return datetime.fromtimestamp(value)
        else:
            return datetime.fromtimestamp(value)

    if isinstance(value, str):
        s = value.strip()
        if not s:
            return None

        # Try common ISO formats
        try:
            # Allow trailing Z
            if s.endswith('Z'):
                s2 = s[:-1]
                # If fractional seconds
                try:
                    return datetime.fromisoformat(s2)
                except Exception:
                    # try with timezone naive parse
                    pass
            return datetime.fromisoformat(s)
        except Exception:
            pass

        # Fallback formats
        fmts = [
            "%Y-%m-%dT%H:%M:%S.%f",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d %H:%M:%S",
            "%d/%m/%Y, %I:%M %p",
            "%d/%m/%Y %H:%M",
        ]
        for fmt in fmts:
            try:
                return datetime.strptime(s, fmt)
            except Exception:
                continue

    return None


def format_for_db(value: Any) -> Optional[str]:
    """Format value into 'DD/MM/YYYY, H:MM AM/PM'.

    Returns None if value is falsy/unknown.
    """
    dt = _to_datetime(value)
    if not dt:
        return None

    day = dt.day
    month = dt.month
    year = dt.year
    hour = dt.hour
    minute = dt.minute

    ampm = 'AM' if hour < 12 else 'PM'
    hour12 = hour % 12
    if hour12 == 0:
        hour12 = 12

    return f"{day:02d}/{month:02d}/{year}, {hour12}:{minute:02d} {ampm}"
