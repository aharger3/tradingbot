"""L2: a 401 from /sessions must fall through to the OAuth refresh_token grant
instead of raising straight away. Mocked — no network, no real creds."""

import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from tastytrade_feed import TastytradeFeed  # noqa: E402


class _Resp:
    def __init__(self, status_code, json_data=None, text=""):
        self.status_code = status_code
        self._json = json_data or {}
        self.text = text

    def json(self):
        return self._json


def test_401_falls_through_to_oauth():
    feed = TastytradeFeed(
        username="user",
        password="pass",
        client_id="cid",
        client_secret="csec",
        refresh_token="rtok",
    )

    calls = []

    def fake_post(url, **kwargs):
        calls.append(url)
        if url.endswith("/sessions"):
            return _Resp(401, text="invalid credentials")
        if url.endswith("/oauth/token"):
            return _Resp(200, {"access_token": "at123", "expires_in": 900})
        raise AssertionError(f"unexpected POST {url}")

    with patch("tastytrade_feed.requests.post", side_effect=fake_post):
        token = feed._get_access_token()

    assert token == "at123", f"expected oauth token, got {token!r}"
    assert any(u.endswith("/sessions") for u in calls), "must try /sessions first"
    assert any(u.endswith("/oauth/token") for u in calls), "must fall through to oauth on 401"


def test_non_401_does_not_fall_through():
    feed = TastytradeFeed(
        username="user",
        password="pass",
        client_id="cid",
        client_secret="csec",
        refresh_token="rtok",
    )

    def fake_post(url, **kwargs):
        if url.endswith("/sessions"):
            return _Resp(500, text="server error")
        raise AssertionError(f"unexpected POST {url}")

    with patch("tastytrade_feed.requests.post", side_effect=fake_post):
        try:
            feed._get_access_token()
            raised = False
        except RuntimeError:
            raised = True

    assert raised, "a non-401 /sessions failure must raise, not fall through to oauth"


def test_successful_session_auth_does_not_call_oauth():
    feed = TastytradeFeed(
        username="user",
        password="pass",
        client_id="cid",
        client_secret="csec",
        refresh_token="rtok",
    )

    calls = []

    def fake_post(url, **kwargs):
        calls.append(url)
        if url.endswith("/sessions"):
            return _Resp(201, {"data": {"session-token": "sess123"}})
        raise AssertionError(f"unexpected POST {url}")

    with patch("tastytrade_feed.requests.post", side_effect=fake_post), \
         patch.object(TastytradeFeed, "get_accounts", return_value=[]):
        token = feed._get_access_token()

    assert token == "sess123"
    assert not any(u.endswith("/oauth/token") for u in calls)


if __name__ == "__main__":
    test_401_falls_through_to_oauth()
    test_non_401_does_not_fall_through()
    test_successful_session_auth_does_not_call_oauth()
    print("OK")
