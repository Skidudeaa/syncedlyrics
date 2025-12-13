"""Utility functions for `syncedlyrics` package"""

import re
import logging
from bs4 import BeautifulSoup, FeatureNotFound

logger = logging.getLogger(__name__)

# LRC timestamp pattern: [mm:ss.xx] or [mm:ss:xx] or [mm:ss]
LRC_TIMESTAMP_PATTERN = re.compile(r"\[(\d{1,2}):(\d{2})([.:]\d{1,3})?\]")

# Minimum number of timestamped lines to consider valid synced lyrics
MIN_TIMESTAMPED_LINES = 3


def is_lrc_valid(lrc: str, allow_plain_format: bool = False) -> bool:
    """
    Checks whether a given LRC string is valid or not.

    For synced lyrics (allow_plain_format=False):
    - Must contain at least MIN_TIMESTAMPED_LINES valid LRC timestamps
    - Timestamps must be in format [mm:ss.xx] or [mm:ss]

    For plain lyrics (allow_plain_format=True):
    - Must have non-empty content with multiple lines
    """
    if not lrc or not lrc.strip():
        return False

    if not allow_plain_format:
        # Count valid LRC timestamps
        timestamps = LRC_TIMESTAMP_PATTERN.findall(lrc)
        if len(timestamps) < MIN_TIMESTAMPED_LINES:
            logger.debug(
                f"LRC validation failed: found {len(timestamps)} timestamps, "
                f"need at least {MIN_TIMESTAMPED_LINES}"
            )
            return False
    else:
        # For plain format, just check we have some content with multiple lines
        lines = [line.strip() for line in lrc.split("\n") if line.strip()]
        if len(lines) < 2:
            return False

    return True


def has_valid_timestamps(lrc: str) -> bool:
    """
    Check if LRC has properly ordered timestamps.
    Returns True if timestamps are in ascending order.
    """
    if not lrc:
        return False

    timestamps = []
    for match in LRC_TIMESTAMP_PATTERN.finditer(lrc):
        minutes = int(match.group(1))
        seconds = int(match.group(2))
        # Handle optional centiseconds
        cs_str = match.group(3)
        centiseconds = 0
        if cs_str:
            cs_str = cs_str[1:]  # Remove leading . or :
            centiseconds = int(cs_str.ljust(2, "0")[:2])  # Normalize to 2 digits
        total_cs = minutes * 6000 + seconds * 100 + centiseconds
        timestamps.append(total_cs)

    if len(timestamps) < MIN_TIMESTAMPED_LINES:
        return False

    # Check if timestamps are generally ascending (allow some tolerance)
    ascending_count = sum(1 for i in range(1, len(timestamps)) if timestamps[i] >= timestamps[i-1])
    return ascending_count >= len(timestamps) * 0.8  # 80% should be ascending


def save_lrc_file(path: str, lrc_text: str):
    """Saves the `.lrc` file"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(lrc_text)


# Default timeout for HTTP requests (connect timeout, read timeout)
DEFAULT_TIMEOUT = (10, 30)


def generate_bs4_soup(session, url: str, timeout=DEFAULT_TIMEOUT, **kwargs):
    """Returns a `BeautifulSoup` from the given `url`.
    Tries to use `lxml` as the parser if available, otherwise `html.parser`

    Args:
        session: requests.Session object
        url: URL to fetch
        timeout: Request timeout (connect, read) in seconds
        **kwargs: Additional arguments passed to BeautifulSoup
    """
    r = session.get(url, timeout=timeout)
    r.raise_for_status()  # Raise exception for bad status codes
    try:
        soup = BeautifulSoup(r.text, features="lxml", **kwargs)
    except FeatureNotFound:
        soup = BeautifulSoup(r.text, features="html.parser", **kwargs)
    return soup
