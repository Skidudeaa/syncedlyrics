"""NetEase (music.163.com) china-based provider"""

import logging
from typing import Optional, List
from rapidfuzz.fuzz import partial_ratio, token_sort_ratio
from requests.exceptions import RequestException
from .base import LRCProvider, DEFAULT_TIMEOUT

logger = logging.getLogger(__name__)

# Minimum similarity score for fuzzy matching (0-100)
MIN_SIMILARITY_SCORE = 65

headers = {
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
    "accept-language": "en-US,en;q=0.9,fa;q=0.8",
    "cache-control": "max-age=0",
    "sec-ch-ua": '".Not/A)Brand";v="99", "Google Chrome";v="103", "Chromium";v="103"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest": "document",
    "sec-fetch-mode": "navigate",
    "sec-fetch-site": "none",
    "sec-fetch-user": "?1",
    "upgrade-insecure-requests": "1",
    "cookie": "NMTID=00OAVK3xqDG726ITU6jopU6jF2yMk0AAAGCO8l1BA; JSESSIONID-WYYY=8KQo11YK2GZP45RMlz8Kn80vHZ9%2FGvwzRKQXXy0iQoFKycWdBlQjbfT0MJrFa6hwRfmpfBYKeHliUPH287JC3hNW99WQjrh9b9RmKT%2Fg1Exc2VwHZcsqi7ITxQgfEiee50po28x5xTTZXKoP%2FRMctN2jpDeg57kdZrXz%2FD%2FWghb%5C4DuZ%3A1659124633932; _iuqxldmzr_=32; _ntes_nnid=0db6667097883aa9596ecfe7f188c3ec,1659122833973; _ntes_nuid=0db6667097883aa9596ecfe7f188c3ec; WNMCID=xygast.1659122837568.01.0; WEVNSM=1.0.0; WM_NI=CwbjWAFbcIzPX3dsLP%2F52VB%2Bxr572gmqAYwvN9KU5X5f1nRzBYl0SNf%2BV9FTmmYZy%2FoJLADaZS0Q8TrKfNSBNOt0HLB8rRJh9DsvMOT7%2BCGCQLbvlWAcJBJeXb1P8yZ3RHA%3D; WM_NIKE=9ca17ae2e6ffcda170e2e6ee90c65b85ae87b9aa5483ef8ab3d14a939e9a83c459959caeadce47e991fbaee82af0fea7c3b92a81a9ae8bd64b86beadaaf95c9cedac94cf5cedebfeb7c121bcaefbd8b16dafaf8fbaf67e8ee785b6b854f7baff8fd1728287a4d1d246a6f59adac560afb397bbfc25ad9684a2c76b9a8d00b2bb60b295aaafd24a8e91bcd1cb4882e8beb3c964fb9cbd97d04598e9e5a4c6499394ae97ef5d83bd86a3c96f9cbeffb1bb739aed9ea9c437e2a3; WM_TID=AAkRFnl03RdABEBEQFOBWHCPOeMra4IL; playerid=94262567",
}


class NetEase(LRCProvider):
    """NetEase provider class"""

    API_ENDPOINT_METADATA = "https://music.163.com/api/search/pc"
    API_ENDPOINT_LYRICS = "https://music.163.com/api/song/lyric"

    def __init__(self) -> None:
        super().__init__()
        self.session.headers.update(headers)

    def _get_track_name(self, track: dict) -> str:
        """Construct a comparable track name from track metadata."""
        name = track.get("name", "")
        artists = track.get("artists", [])
        artist_name = artists[0].get("name", "") if artists else ""
        return f"{name} {artist_name}".strip().lower()

    def _find_best_match(self, search_term: str, tracks: List[dict]) -> Optional[dict]:
        """Find the best matching track using fuzzy matching."""
        search_lower = search_term.lower()
        best_match = None
        best_score = 0

        for track in tracks:
            track_name = self._get_track_name(track)
            # Use both partial_ratio and token_sort_ratio for better matching
            score = max(
                partial_ratio(search_lower, track_name),
                token_sort_ratio(search_lower, track_name)
            )

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

    def search_track(self, search_term: str) -> Optional[dict]:
        """Returns a `dict` containing some metadata for the found track."""
        params = {"limit": 15, "type": 1, "offset": 0, "s": search_term}

        try:
            response = self.session.get(
                self.API_ENDPOINT_METADATA,
                params=params,
                timeout=DEFAULT_TIMEOUT
            )
            response.raise_for_status()
            data = response.json()
        except RequestException as e:
            logger.warning(f"{self.provider_name}: Request failed: {e}")
            return None
        except ValueError as e:
            logger.warning(f"{self.provider_name}: JSON parsing failed: {e}")
            return None

        try:
            results = data.get("result", {}).get("songs", [])
            if not results:
                return None
        except (AttributeError, TypeError) as e:
            logger.debug(f"{self.provider_name}: Failed to parse results: {e}")
            return None

        # Find best match using fuzzy matching
        track = self._find_best_match(search_term, results)
        if not track:
            return None

        # Update the session cookies from the new sent cookies for the next request.
        self.session.cookies.update(response.cookies)
        self.session.headers.update({"referer": response.url})
        return track

    def get_lrc_by_id(self, track_id: str) -> Optional[str]:
        params = {"id": track_id, "lv": 1}

        try:
            response = self.session.get(
                self.API_ENDPOINT_LYRICS,
                params=params,
                timeout=DEFAULT_TIMEOUT
            )
            response.raise_for_status()
            data = response.json()
        except RequestException as e:
            logger.warning(f"{self.provider_name}: Request failed: {e}")
            return None
        except ValueError as e:
            logger.warning(f"{self.provider_name}: JSON parsing failed: {e}")
            return None

        try:
            lrc = data.get("lrc", {}).get("lyric")
            if not lrc:
                return None
            return lrc
        except (AttributeError, TypeError) as e:
            logger.debug(f"{self.provider_name}: Failed to extract LRC: {e}")
            return None

    def get_lrc(self, search_term: str) -> Optional[str]:
        track = self.search_track(search_term)
        if not track:
            return None
        return self.get_lrc_by_id(track["id"])
