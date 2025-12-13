"""Megalobiz (megalobiz.com) LRC provider"""

import logging
from typing import Optional, List
from bs4 import SoupStrainer, Tag
from rapidfuzz.fuzz import token_sort_ratio
from requests.exceptions import RequestException
from .base import LRCProvider
from ..utils import generate_bs4_soup

logger = logging.getLogger(__name__)

# Minimum similarity score for fuzzy matching (0-100)
MIN_SIMILARITY_SCORE = 70


class Megalobiz(LRCProvider):
    """Megalobiz provider class"""

    ROOT_URL = "https://www.megalobiz.com"
    SEARCH_ENDPOINT = ROOT_URL + "/search/all?qry={q}&searchButton.x=0&searchButton.y=0"

    def _normalize_text(self, text: str) -> str:
        """Normalize text for comparison."""
        if not text:
            return ""
        return text.lower().replace("-", " ").strip()

    def _find_best_match(self, search_term: str, a_tags: List[Tag]) -> Optional[Tag]:
        """Find the best matching link using fuzzy matching."""
        search_normalized = self._normalize_text(search_term)
        best_match = None
        best_score = 0

        for tag in a_tags:
            tag_text = tag.get_text() if tag else ""
            tag_normalized = self._normalize_text(tag_text)
            score = token_sort_ratio(search_normalized, tag_normalized)

            if score > best_score:
                best_score = score
                best_match = tag

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

    def get_lrc(self, search_term: str) -> Optional[str]:
        url = self.SEARCH_ENDPOINT.format(q=search_term)

        def href_match(h: Optional[str]):
            if h and h.startswith("/lrc/maker/"):
                return True
            return False

        try:
            a_tags_bound = SoupStrainer("a", href=href_match)
            soup = generate_bs4_soup(self.session, url, parse_only=a_tags_bound)

            # Get all matching links for fuzzy comparison
            a_tags = soup.find_all("a", limit=20)
            if not a_tags:
                return None

            # Find best matching link using fuzzy matching
            a_tag = self._find_best_match(search_term, a_tags)
            if not a_tag:
                return None

            # Scraping from the LRC page
            lrc_id = a_tag["href"].split(".")[-1]
            soup = generate_bs4_soup(self.session, self.ROOT_URL + a_tag["href"])

            lrc_div = soup.find("div", {"id": f"lrc_{lrc_id}_details"})
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
