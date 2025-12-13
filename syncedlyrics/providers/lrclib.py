"""LRCLIB (lrclib.net) - Free crowdsourced lyrics API"""

import logging
from typing import Optional, List
from urllib.parse import quote
from rapidfuzz.fuzz import token_sort_ratio
from .base import LRCProvider, DEFAULT_TIMEOUT

logger = logging.getLogger(__name__)

# Minimum similarity score for fuzzy matching (0-100)
MIN_SIMILARITY_SCORE = 60


class Lrclib(LRCProvider):
    """
    LRCLIB provider class.

    LRCLIB is a free, open-source, crowdsourced lyrics database.
    No API key required. Supports both synced and plain lyrics.

    API Documentation: https://lrclib.net/docs
    """

    API_BASE = "https://lrclib.net/api"
    SEARCH_ENDPOINT = API_BASE + "/search"
    GET_ENDPOINT = API_BASE + "/get"

    def __init__(self) -> None:
        super().__init__()
        # LRCLIB recommends setting a descriptive User-Agent
        self.session.headers.update({
            "User-Agent": "syncedlyrics/1.0 (https://github.com/moehmeni/syncedlyrics)"
        })

    def _get_track_name(self, track: dict) -> str:
        """Construct a comparable track name from track metadata."""
        track_name = track.get("trackName", "")
        artist_name = track.get("artistName", "")
        return f"{track_name} {artist_name}".strip().lower()

    def _find_best_match(
        self,
        search_term: str,
        tracks: List[dict],
        prefer_synced: bool = True
    ) -> Optional[dict]:
        """
        Find the best matching track using fuzzy matching.

        Args:
            search_term: The search query
            tracks: List of track dictionaries from API
            prefer_synced: If True, prioritize tracks with synced lyrics
        """
        search_lower = search_term.lower()
        candidates = []

        for track in tracks:
            track_name = self._get_track_name(track)
            score = token_sort_ratio(search_lower, track_name)

            # Bonus for having synced lyrics
            has_synced = bool(track.get("syncedLyrics"))
            if prefer_synced and has_synced:
                score = min(score + 10, 100)

            if score >= MIN_SIMILARITY_SCORE:
                candidates.append((score, track, has_synced))

        if not candidates:
            logger.debug(
                f"{self.provider_name}: No match above {MIN_SIMILARITY_SCORE}% threshold"
            )
            return None

        # Sort by score (descending), then by has_synced (True first)
        candidates.sort(key=lambda x: (x[0], x[2]), reverse=True)
        best_score, best_track, has_synced = candidates[0]

        logger.debug(
            f"{self.provider_name}: Best match score {best_score:.1f}% "
            f"(synced: {has_synced}) for '{search_term}'"
        )
        return best_track

    def get_lrc_by_id(self, track_id: str) -> Optional[str]:
        """Get lyrics by LRCLIB track ID."""
        url = f"{self.API_BASE}/get/{track_id}"
        data = self._get_json(url)
        if not data:
            return None

        # Prefer synced lyrics, fall back to plain
        synced = data.get("syncedLyrics")
        if synced:
            return synced

        plain = data.get("plainLyrics")
        if plain:
            logger.debug(f"{self.provider_name}: Only plain lyrics available")
            return plain

        return None

    def get_lrc(self, search_term: str) -> Optional[str]:
        """
        Search for lyrics using a search term.

        Args:
            search_term: Track name and/or artist (e.g., "Shape of You Ed Sheeran")
        """
        # Use search endpoint
        url = f"{self.SEARCH_ENDPOINT}?q={quote(search_term)}"
        data = self._get_json(url)

        if not data or not isinstance(data, list) or len(data) == 0:
            logger.debug(f"{self.provider_name}: No search results for '{search_term}'")
            return None

        # Find best match with fuzzy matching
        best_track = self._find_best_match(search_term, data)
        if not best_track:
            return None

        # Return synced lyrics if available, otherwise plain
        synced = best_track.get("syncedLyrics")
        if synced:
            return synced

        plain = best_track.get("plainLyrics")
        if plain:
            logger.debug(f"{self.provider_name}: Only plain lyrics available")
            return plain

        return None

    def get_lrc_by_metadata(
        self,
        track_name: str,
        artist_name: str,
        album_name: str = None,
        duration: int = None
    ) -> Optional[str]:
        """
        Get lyrics using exact track metadata (more accurate than search).

        Args:
            track_name: The track/song name
            artist_name: The artist name
            album_name: Optional album name
            duration: Optional track duration in seconds

        Note: This endpoint requires all parameters to match exactly.
        """
        params = {
            "track_name": track_name,
            "artist_name": artist_name,
        }
        if album_name:
            params["album_name"] = album_name
        if duration:
            params["duration"] = str(duration)

        # Build URL with parameters
        param_str = "&".join(f"{k}={quote(str(v))}" for k, v in params.items())
        url = f"{self.GET_ENDPOINT}?{param_str}"

        data = self._get_json(url)
        if not data:
            return None

        synced = data.get("syncedLyrics")
        if synced:
            return synced

        plain = data.get("plainLyrics")
        if plain:
            logger.debug(f"{self.provider_name}: Only plain lyrics available")
            return plain

        return None
