"""Musixmatch LRC provider"""

import logging
from typing import Optional, List
from rapidfuzz.fuzz import token_sort_ratio
from .base import LRCProvider

logger = logging.getLogger(__name__)

# Minimum similarity score for fuzzy matching (0-100)
MIN_SIMILARITY_SCORE = 65


class Musixmatch(LRCProvider):
    """Musixmatch provider class"""

    USER_TOKEN = "190523f77464fba06fa5f82a9bfab0aa9dc201244ecf5124a06d95"
    SEARCH_ENDPOINT = "https://apic-desktop.musixmatch.com/ws/1.1/track.search?format=json&q={q}&page_size=10&page=1&s_track_rating=desc&quorum_factor=1.0&app_id=web-desktop-app-v1.0&usertoken={token}"
    LRC_ENDPOINT = "https://apic-desktop.musixmatch.com/ws/1.1/track.subtitle.get?format=json&track_id={track_id}&subtitle_format=lrc&app_id=web-desktop-app-v1.0&usertoken={token}"

    def _get_track_name(self, track: dict) -> str:
        """Construct a comparable track name from track metadata."""
        track_name = track.get("track_name", "")
        artist_name = track.get("artist_name", "")
        return f"{track_name} {artist_name}".strip().lower()

    def _find_best_match(self, search_term: str, tracks: List[dict]) -> Optional[dict]:
        """Find the best matching track using fuzzy matching."""
        search_lower = search_term.lower()
        best_match = None
        best_score = 0

        for track_info in tracks:
            track = track_info.get("track", {})
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
        url = self.LRC_ENDPOINT.format(track_id=track_id, token=self.USER_TOKEN)
        data = self._get_json(url)
        if not data:
            return None

        try:
            body = data["message"]["body"]
            if not body:
                return None
            return body["subtitle"]["subtitle_body"]
        except (KeyError, TypeError) as e:
            logger.debug(f"{self.provider_name}: Failed to extract LRC: {e}")
            return None

    def get_lrc(self, search_term: str) -> Optional[str]:
        url = self.SEARCH_ENDPOINT.format(q=search_term, token=self.USER_TOKEN)
        data = self._get_json(url)
        if not data:
            return None

        try:
            body = data["message"]["body"]
            if not body:
                return None
            tracks = body.get("track_list", [])
            if not tracks:
                return None
        except (KeyError, TypeError) as e:
            logger.debug(f"{self.provider_name}: Failed to parse search results: {e}")
            return None

        # Find best matching track using fuzzy matching
        best_track = self._find_best_match(search_term, tracks)
        if not best_track:
            return None

        return self.get_lrc_by_id(best_track["track_id"])
