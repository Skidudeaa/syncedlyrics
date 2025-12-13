"""
Search for an LRC format (synchronized lyrics) of a music.

```py
import syncedlyrics
lrc_text = syncedlyrics.search("[TRACK_NAME] [ARTIST_NAME]")
```
"""

from typing import Optional, List
import logging
from .providers import NetEase, Lyricsify, Megalobiz, Musixmatch, Deezer
from .utils import is_lrc_valid, save_lrc_file

logger = logging.getLogger(__name__)

# Default provider order (prioritized by reliability)
DEFAULT_PROVIDERS = ["Musixmatch", "Lyricsify", "NetEase", "Megalobiz"]


def search(
    search_term: str,
    allow_plain_format: bool = False,
    save_path: str = None,
    providers: List[str] = None,
) -> Optional[str]:
    """
    Returns the synced lyrics of the song in [LRC](https://en.wikipedia.org/wiki/LRC_(file_format)) format if found.

    ### Arguments
    - `search_term`: The search term to find the track (e.g., "Song Name Artist Name")
    - `allow_plain_format`: Return plain text (not synced) lyrics if no LRC was found
    - `save_path`: Path to save `.lrc` lyrics. No saving if `None`. Supports `{search_term}` placeholder
    - `providers`: A list of provider names to include in searching; tries each provider until valid LRC is found

    ### Returns
    - LRC formatted string if found, None otherwise

    ### Available providers
    - Musixmatch: Uses Musixmatch API (reliable for popular tracks)
    - Lyricsify: Web scraping with fuzzy matching
    - NetEase: Chinese music service API
    - Megalobiz: Web scraping with fuzzy matching
    - Deezer: Uses Deezer API (may require valid session)
    """
    if not search_term or not search_term.strip():
        logger.warning("Empty search term provided")
        return None

    search_term = search_term.strip()

    # Initialize providers
    available_providers = {
        "Musixmatch": Musixmatch,
        "Lyricsify": Lyricsify,
        "NetEase": NetEase,
        "Megalobiz": Megalobiz,
        "Deezer": Deezer,
    }

    # Determine which providers to use
    provider_names = providers if providers else DEFAULT_PROVIDERS

    _providers = []
    for name in provider_names:
        if name in available_providers:
            try:
                _providers.append(available_providers[name]())
            except Exception as e:
                logger.warning(f"Failed to initialize provider {name}: {e}")

    if not _providers:
        logger.error("No valid providers available")
        return None

    lrc = None
    for provider in _providers:
        provider_name = provider.__class__.__name__
        logger.debug(f"Searching for LRC on {provider_name}")

        try:
            lrc = provider.get_lrc(search_term)
        except Exception as e:
            logger.warning(f"{provider_name}: Unexpected error: {e}")
            continue

        if is_lrc_valid(lrc, allow_plain_format):
            logger.info(
                f'Synced lyrics found for "{search_term}" on {provider_name}'
            )
            break
        else:
            if lrc:
                logger.debug(
                    f"{provider_name}: Found lyrics but validation failed"
                )
            lrc = None

    if not lrc:
        logger.info(f'No synced lyrics found for "{search_term}"')
        return None

    if save_path:
        try:
            save_path = save_path.format(search_term=search_term)
            save_lrc_file(save_path, lrc)
            logger.debug(f"Saved LRC to {save_path}")
        except (IOError, OSError) as e:
            logger.warning(f"Failed to save LRC file: {e}")

    return lrc
