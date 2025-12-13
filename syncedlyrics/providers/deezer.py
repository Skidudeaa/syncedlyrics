"""Deezer LRC provider (API powered by LyricFind)"""

import logging
from typing import Optional, List
from rapidfuzz.fuzz import token_sort_ratio
from requests.exceptions import RequestException
from .base import LRCProvider, DEFAULT_TIMEOUT

logger = logging.getLogger(__name__)

# Minimum similarity score for fuzzy matching (0-100)
MIN_SIMILARITY_SCORE = 65

# Mostly based on https://gist.github.com/akashrchandran/95915c2081815397c454bd8aa4a118b5


class Deezer(LRCProvider):
    """Deezer provider class"""

    SEARCH_ENDPOINT = "https://api.deezer.com/search?q="
    API_ENDPOINT = "http://www.deezer.com/ajax/gw-light.php"

    def __init__(self) -> None:
        super().__init__()
        self.token = "null"
        self._initialized = False

    def _initialize_token(self) -> bool:
        """Lazily initialize the CSRF token. Returns True if successful."""
        if self._initialized:
            return self.token != "null"

        self._initialized = True
        try:
            result = self._api_call("deezer.getUserData")
            if result and "results" in result:
                self.token = result["results"].get("checkForm", "null")
                if self.token != "null":
                    logger.debug(f"{self.provider_name}: Token initialized successfully")
                    return True
            logger.warning(f"{self.provider_name}: Failed to get valid CSRF token")
            return False
        except Exception as e:
            logger.warning(f"{self.provider_name}: Failed to initialize token: {e}")
            return False

    def _api_call(self, method: str, json=None) -> Optional[dict]:
        params = {
            "api_version": "1.0",
            "api_token": self.token,
            "input": "3",
            "method": method,
        }
        try:
            response = self.session.post(
                self.API_ENDPOINT,
                params=params,
                json=json,
                timeout=DEFAULT_TIMEOUT
            )
            response.raise_for_status()
            return response.json()
        except RequestException as e:
            logger.warning(f"{self.provider_name}: API request failed: {e}")
            return None
        except ValueError as e:
            logger.warning(f"{self.provider_name}: JSON parsing failed: {e}")
            return None

    def _get_track_name(self, track: dict) -> str:
        """Construct a comparable track name from track metadata."""
        title = track.get("title", "")
        artist = track.get("artist", {})
        artist_name = artist.get("name", "") if isinstance(artist, dict) else ""
        return f"{title} {artist_name}".strip().lower()

    def _find_best_match(self, search_term: str, tracks: List[dict]) -> Optional[dict]:
        """Find the best matching track using fuzzy matching."""
        search_lower = search_term.lower()
        best_match = None
        best_score = 0

        for track in tracks:
            track_name = self._get_track_name(track)
            score = token_sort_ratio(search_lower, track_name)

            if score > best_score:
                best_score = score
                best_match = track

        if best_score >= MIN_SIMILARITY_SCORE:
            logger.debug(
                f"{self.provider_name}: Best match score {best_score:.1f}% for '{search_term}'"
            )
            return best_match

        logger.debug(
            f"{self.provider_name}: No match above {MIN_SIMILARITY_SCORE}% threshold "
            f"(best was {best_score:.1f}%)"
        )
        return None

    def get_lrc_by_id(self, track_id: str) -> Optional[str]:
        if not self._initialize_token():
            return None

        lrc_response = self._api_call("song.getLyrics", json={"sng_id": track_id})
        if not lrc_response:
            return None

        try:
            results = lrc_response.get("results", {})
            lrc_json_objs = results.get("LYRICS_SYNC_JSON")

            if not lrc_json_objs:
                # Return plain text lyrics as fallback
                return results.get("LYRICS_TEXT")

            lrc = ""
            for chunk in lrc_json_objs:
                if chunk.get("lrc_timestamp") and chunk.get("line"):
                    lrc += f"{chunk['lrc_timestamp']} {chunk['line']}\n"
            return lrc.strip() if lrc else None

        except (KeyError, TypeError, AttributeError) as e:
            logger.debug(f"{self.provider_name}: Failed to extract LRC: {e}")
            return None

    def get_lrc(self, search_term: str) -> Optional[str]:
        try:
            response = self.session.get(
                self.SEARCH_ENDPOINT + search_term,
                timeout=DEFAULT_TIMEOUT
            )
            response.raise_for_status()
            search_results = response.json()
        except RequestException as e:
            logger.warning(f"{self.provider_name}: Search request failed: {e}")
            return None
        except ValueError as e:
            logger.warning(f"{self.provider_name}: JSON parsing failed: {e}")
            return None

        data = search_results.get("data", [])
        if not data:
            return None

        # Find best match using fuzzy matching
        song = self._find_best_match(search_term, data)
        if not song:
            return None

        return self.get_lrc_by_id(song["id"])
