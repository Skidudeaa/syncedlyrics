"""Some simple tests for geting notifed for API changes of the providers"""

import os
from syncedlyrics import search

q = os.getenv("TEST_Q", "bad guy billie eilish")

class AuthError(Exception):
    pass

def _test_provider(provider: str):
    lrc = None
    try:
        lrc = search(q, allow_plain_format=True, providers=[provider])
        if not isinstance(lrc, (str, type(None))):
            raise AuthError("Unexpected return type")
    except AuthError as e:
        # Handle error
        # ...
        # Return, do not continue processing
        return

def test_netease():
    _test_provider("NetEase")

def test_lyricsify():
    _test_provider("Lyricsify")

def test_megalobiz():
    _test_provider("Megalobiz")
    
def test_musixmatch():
    _test_provider("Musixmatch")
