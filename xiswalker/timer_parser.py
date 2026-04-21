"""Pure functions for parsing timer text found via OCR.

This module has no OS or UI dependencies and is fully unit-testable.

Supported timer formats
-----------------------
Textual (case-insensitive):
    "1h. 21min."         →  4920 s
    "1h 21min 30s"       →  4950 s
    "1h 21min 30sec"     →  4950 s
    "45min"              →  2700 s
    "45 minutes"         →  2700 s
    "2h"                 →  7200 s
    "2 hours"            →  7200 s
    "30s"                →    30 s
    "30 seconds"         →    30 s

Clock (H:MM:SS or MM:SS):
    "01:21:30"           →  4890 s
    "21:30"              →  1290 s
"""

import re
from typing import Optional

# ---------------------------------------------------------------------------
# Component patterns – intentionally simple and readable
# ---------------------------------------------------------------------------

_H_PATTERN = re.compile(
    r'(\d+)\s*h(?:ours?|rs?)?\s*\.?', re.IGNORECASE
)
_M_PATTERN = re.compile(
    r'(\d+)\s*min(?:utes?)?\s*\.?', re.IGNORECASE
)
_S_PATTERN = re.compile(
    r'(\d+)\s*(?:seconds?|secs?|s)\.?(?=\s|$|[,;.])',
    re.IGNORECASE,
)
_CLOCK_PATTERN = re.compile(
    r'^(?:(\d+):)?(\d{1,2}):(\d{2})$'
)

# Pattern used to locate a timer *inside a larger text blob*.
# Each alternative is tried left-to-right; more specific ones come first.
_BLOB_TIMER_PATTERN = re.compile(
    r'\b(?:'
    # hours (+ optional minutes + optional seconds)
    r'\d+\s*h(?:ours?|rs?)?\s*\.?\s*'
    r'(?:\d+\s*min(?:utes?)?\s*\.?\s*)?'
    r'(?:\d+\s*(?:seconds?|secs?|s)\.?\s*)?'
    r'|'
    # minutes (+ optional seconds)
    r'\d+\s*min(?:utes?)?\s*\.?\s*'
    r'(?:\d+\s*(?:seconds?|secs?|s)\.?\s*)?'
    r'|'
    # bare seconds  ("30s", "30 sec", "30 seconds")
    r'\d+\s*(?:seconds?|secs?|s)\.?\s*'
    r'|'
    # clock format
    r'\d+:\d{2}(?::\d{2})?'
    r')',
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Public pure functions
# ---------------------------------------------------------------------------

def parse_timer_seconds(text: str) -> Optional[int]:
    """Parse a timer string and return total seconds.

    Accepts textual ("1h. 21min.") and clock ("01:21:30") formats.
    Returns None when no recognisable pattern is found.
    Returns 0 when a valid timer whose value is zero is found.
    """
    text = text.strip()

    # ---- Clock format -------------------------------------------------------
    clock = _CLOCK_PATTERN.match(text)
    if clock:
        h_part, m_part, s_part = clock.group(1), clock.group(2), clock.group(3)
        h = int(h_part) if h_part is not None else 0
        m = int(m_part)
        s = int(s_part)
        return h * 3600 + m * 60 + s

    # ---- Textual components -------------------------------------------------
    total = 0
    found_any = False

    h = _H_PATTERN.search(text)
    if h:
        total += int(h.group(1)) * 3600
        found_any = True

    m = _M_PATTERN.search(text)
    if m:
        total += int(m.group(1)) * 60
        found_any = True

    s = _S_PATTERN.search(text)
    if s:
        total += int(s.group(1))
        found_any = True

    return total if found_any else None


def find_timer_in_text(blob: str) -> Optional[str]:
    """Return the first timer-like substring found in *blob*, or None.

    The returned snippet can be passed to ``parse_timer_seconds``.
    """
    m = _BLOB_TIMER_PATTERN.search(blob)
    return m.group(0).strip() if m else None


def extract_timer_seconds(blob: str) -> Optional[int]:
    """Convenience: find a timer in *blob* and return its value in seconds.

    Returns None when no timer pattern is found.
    """
    snippet = find_timer_in_text(blob)
    return parse_timer_seconds(snippet) if snippet is not None else None


def format_seconds(seconds: int) -> str:
    """Format a duration in seconds as a human-readable string.

    Examples:
        4920  →  "1h 22m 0s"
        2700  →  "45m 0s"
          30  →  "30s"
    """
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    if h:
        return f"{h}h {m}m {s}s"
    if m:
        return f"{m}m {s}s"
    return f"{s}s"
