"""Lyricsify (lyricsify.com) LRC provider"""

import logging
from typing import Optional
from bs4 import SoupStrainer
import rapidfuzz
from requests.exceptions import RequestException
from .base import LRCProvider
from ..utils import generate_bs4_soup

logger = logging.getLogger(__name__)

# Minimum similarity score for fuzzy matching (0-100)
MIN_SIMILARITY_SCORE = 75


class Lyricsify(LRCProvider):
    """Lyricsify LRC provider class"""

    ROOT_URL = "https://www.lyricsify.com"
    SEARCH_ENDPOINT = ROOT_URL + "/search?q="

    def __init__(self) -> None:
        super().__init__()
        self.parser = "html.parser"

    def _normalize_text(self, text: str) -> str:
        """Normalize text for comparison."""
        if not text:
            return ""
        return text.lower().replace("-", "").strip()

    def get_lrc(self, search_term: str) -> Optional[str]:
        url = self.SEARCH_ENDPOINT + search_term.replace(" ", "+")

        try:
            # Normalize function for comparison
            text_match = lambda t: rapidfuzz.fuzz.token_sort_ratio(
                self._normalize_text(search_term),
                self._normalize_text(t)
            )
            href_match = lambda h: h.startswith("/lyric/") if h else False
            a_tags_bound = SoupStrainer("a", href=href_match)
            soup = generate_bs4_soup(self.session, url, parse_only=a_tags_bound)

            # Find all links with sufficient similarity
            a_tags = soup.find_all(
                "a",
                string=lambda t: text_match(t) > MIN_SIMILARITY_SCORE,
                limit=10
            )
            if not a_tags:
                logger.debug(
                    f"{self.provider_name}: No matches above {MIN_SIMILARITY_SCORE}% threshold"
                )
                return None

            # Select the one with the highest similarity score
            a_tag = max(a_tags, key=lambda tag: text_match(tag.string) if tag.string else 0)

            best_score = text_match(a_tag.string) if a_tag.string else 0
            logger.debug(
                f"{self.provider_name}: Best match score {best_score:.1f}% for '{search_term}'"
            )

            # Scraping from the LRC page
            lrc_id = a_tag["href"].split(".")[-1]
            soup = generate_bs4_soup(self.session, self.ROOT_URL + a_tag["href"])

            lrc_div = soup.find("div", {"id": f"lyrics_{lrc_id}_details"})
            if not lrc_div:
                logger.debug(f"{self.provider_name}: LRC div not found for id {lrc_id}")
                return None

            return lrc_div.get_text()

        except RequestException as e:
            logger.warning(f"{self.provider_name}: Request failed: {e}")
            return None
        except (AttributeError, KeyError, TypeError) as e:
            logger.debug(f"{self.provider_name}: Failed to parse page: {e}")
            return None
