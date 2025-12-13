import requests
import logging
from typing import Optional
from requests.exceptions import RequestException, Timeout, HTTPError

logger = logging.getLogger(__name__)

# Default timeout for HTTP requests (connect timeout, read timeout)
DEFAULT_TIMEOUT = (10, 30)


class LRCProvider:
    """
    Base class for all of the synced (LRC format) lyrics providers.
    """

    session = requests.Session()

    def __init__(self) -> None:
        self.session.headers.update(
            {
                "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36"
            }
        )

    @property
    def provider_name(self) -> str:
        """Returns the provider class name for logging."""
        return self.__class__.__name__

    def _get(self, url: str, **kwargs) -> Optional[requests.Response]:
        """
        Wrapper around session.get with timeout and error handling.

        Returns None if the request fails.
        """
        if "timeout" not in kwargs:
            kwargs["timeout"] = DEFAULT_TIMEOUT
        try:
            response = self.session.get(url, **kwargs)
            response.raise_for_status()
            return response
        except Timeout:
            logger.warning(f"{self.provider_name}: Request timed out for {url}")
            return None
        except HTTPError as e:
            logger.warning(f"{self.provider_name}: HTTP error {e.response.status_code} for {url}")
            return None
        except RequestException as e:
            logger.warning(f"{self.provider_name}: Request failed: {e}")
            return None

    def _get_json(self, url: str, **kwargs) -> Optional[dict]:
        """
        Wrapper around _get that also parses JSON response.

        Returns None if the request fails or JSON parsing fails.
        """
        response = self._get(url, **kwargs)
        if response is None:
            return None
        try:
            return response.json()
        except ValueError as e:
            logger.warning(f"{self.provider_name}: JSON parsing failed: {e}")
            return None

    def get_lrc_by_id(self, track_id: str) -> Optional[str]:
        """
        Returns the synced lyrics of the song in [LRC](https://en.wikipedia.org/wiki/LRC_(file_format)) format if found.

        ### Arguments
        - track_id: The ID of the track defined in the provider database. e.g. Spotify/Deezer track ID
        """
        raise NotImplementedError

    def get_lrc(self, search_term: str) -> Optional[str]:
        """
        Returns the synced lyrics of the song in [LRC](https://en.wikipedia.org/wiki/LRC_(file_format)) format if found.
        """
        raise NotImplementedError
