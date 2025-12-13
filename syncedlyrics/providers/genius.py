"""Genius (genius.com) - Plain text lyrics provider"""

import logging
import re
from typing import Optional, List
from bs4 import BeautifulSoup, SoupStrainer
from rapidfuzz.fuzz import token_sort_ratio
from requests.exceptions import RequestException
from .base import LRCProvider, DEFAULT_TIMEOUT

logger = logging.getLogger(__name__)

# Minimum similarity score for fuzzy matching (0-100)
MIN_SIMILARITY_SCORE = 70


class Genius(LRCProvider):
    """
    Genius provider class.

    Genius provides plain text lyrics (not synced).
    This provider is useful as a fallback when synced lyrics aren't available.

    Note: This uses web scraping as Genius API requires authentication.
    """

    SEARCH_URL = "https://genius.com/api/search/song"
    ROOT_URL = "https://genius.com"

    def __init__(self) -> None:
        super().__init__()
        self.session.headers.update({
            "Accept": "application/json",
        })

    def _get_track_name(self, hit: dict) -> str:
        """Construct a comparable track name from search result."""
        result = hit.get("result", {})
        title = result.get("title", "")
        artist = result.get("primary_artist", {}).get("name", "")
        return f"{title} {artist}".strip().lower()

    def _find_best_match(self, search_term: str, hits: List[dict]) -> Optional[dict]:
        """Find the best matching track using fuzzy matching."""
        search_lower = search_term.lower()
        best_match = None
        best_score = 0

        for hit in hits:
            track_name = self._get_track_name(hit)
            score = token_sort_ratio(search_lower, track_name)

            if score > best_score:
                best_score = score
                best_match = hit

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

    def _scrape_lyrics(self, url: str) -> Optional[str]:
        """Scrape lyrics from a Genius song page."""
        try:
            response = self.session.get(url, timeout=DEFAULT_TIMEOUT)
            response.raise_for_status()
        except RequestException as e:
            logger.warning(f"{self.provider_name}: Failed to fetch lyrics page: {e}")
            return None

        try:
            soup = BeautifulSoup(response.text, "html.parser")

            # Genius lyrics are in div elements with data-lyrics-container="true"
            lyrics_containers = soup.find_all(
                "div",
                attrs={"data-lyrics-container": "true"}
            )

            if not lyrics_containers:
                # Fallback: try older structure
                lyrics_div = soup.find("div", class_=re.compile(r"Lyrics__Container"))
                if lyrics_div:
                    lyrics_containers = [lyrics_div]

            if not lyrics_containers:
                logger.debug(f"{self.provider_name}: No lyrics container found")
                return None

            # Extract text from all containers
            lyrics_parts = []
            for container in lyrics_containers:
                # Replace <br> tags with newlines
                for br in container.find_all("br"):
                    br.replace_with("\n")

                # Get text and clean it up
                text = container.get_text(separator="\n")
                lyrics_parts.append(text)

            lyrics = "\n".join(lyrics_parts)

            # Clean up the lyrics
            lyrics = re.sub(r'\n{3,}', '\n\n', lyrics)  # Max 2 consecutive newlines
            lyrics = lyrics.strip()

            if not lyrics:
                return None

            return lyrics

        except Exception as e:
            logger.debug(f"{self.provider_name}: Failed to parse lyrics: {e}")
            return None

    def get_lrc(self, search_term: str) -> Optional[str]:
        """
        Search for plain text lyrics.

        Note: Genius only provides plain text lyrics, not synced LRC format.
        """
        # Search for the song
        params = {"q": search_term}
        try:
            response = self.session.get(
                self.SEARCH_URL,
                params=params,
                timeout=DEFAULT_TIMEOUT
            )
            response.raise_for_status()
            data = response.json()
        except RequestException as e:
            logger.warning(f"{self.provider_name}: Search request failed: {e}")
            return None
        except ValueError as e:
            logger.warning(f"{self.provider_name}: JSON parsing failed: {e}")
            return None

        # Extract hits from response
        try:
            hits = data.get("response", {}).get("sections", [{}])[0].get("hits", [])
            if not hits:
                logger.debug(f"{self.provider_name}: No search results")
                return None
        except (KeyError, IndexError, TypeError) as e:
            logger.debug(f"{self.provider_name}: Failed to parse search results: {e}")
            return None

        # Find best match
        best_hit = self._find_best_match(search_term, hits)
        if not best_hit:
            return None

        # Get the URL and scrape lyrics
        try:
            url = best_hit.get("result", {}).get("url")
            if not url:
                return None
        except (KeyError, TypeError):
            return None

        return self._scrape_lyrics(url)
